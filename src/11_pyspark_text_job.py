"""Step 11 - PySpark big-data text processing job over 65,067+ YouTube comments.

Uses pyspark.sql.functions to:
  1. Clean comment_text (lowercase, strip URLs, strip non-alphanumeric noise,
     collapse whitespace).
  2. Measure char_length and word_count per comment.
  3. Tokenize and compute top frequent terms across the corpus and per film
     (excluding standard English + common Hinglish/film stopwords).
  4. Aggregate by film_id and export data/clean/pyspark_film_text_summary.csv
     and data/clean/pyspark_top_terms.csv.

Run:  python -X utf8 src/11_pyspark_text_job.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "is", "it", "this", "that", "was", "are", "be", "been", "with", "as", "by",
    "from", "not", "no", "so", "if", "you", "your", "i", "me", "my", "we", "our",
    "they", "them", "their", "he", "she", "his", "her", "its", "will", "just",
    "all", "one", "can", "like", "have", "has", "had", "do", "does", "did",
    "what", "when", "who", "how", "why", "which", "more", "very", "only", "out",
    "up", "get", "got", "see", "watch", "watching", "watched", "movie", "film",
    "trailer", "hai", "ka", "ki", "ke", "ko", "se", "me", "mein", "ho", "hi",
    "bhi", "toh", "nahi", "kya", "aur", "ye", "yeh", "wo", "woh", "ab", "kar",
    "bhai", "bro", "sir", "ji", "full", "video", "youtube", "com", "amp",
}


def main() -> int:
    c.ensure_dirs()
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("ReleaseDayRadar_PySparkTextJob")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        comments_path = str(c.CLEAN / "youtube_comments.csv")
        df = spark.read.option("header", "true").option("escape", '"').csv(comments_path)

        imdb_path = c.RAW / "external" / "IMDB Dataset.csv"
        if imdb_path.exists():
            imdb_df = spark.read.option("header", "true").option("escape", '"').csv(str(imdb_path))
            print(f"External IMDb corpus detected: {imdb_df.count():,} rows")
        else:
            print("External IMDb 50K corpus not present; running on 65K+ YouTube comments directly.")

        df = (
            df.withColumn("like_count_num", F.coalesce(F.col("like_count").cast("double"), F.lit(0.0)))
            .withColumn("in_7d_flag", F.when(F.lower(F.col("in_first_7d")) == "true", 1).otherwise(0))
            .withColumn("raw_text", F.coalesce(F.col("text_original"), F.lit("")))
            .withColumn("clean_text", F.lower(F.col("raw_text")))
            .withColumn("clean_text", F.regexp_replace("clean_text", r"https?://\S+|www\.\S+", " "))
            .withColumn("clean_text", F.regexp_replace("clean_text", r"[^a-z0-9\s]", " "))
            .withColumn("clean_text", F.trim(F.regexp_replace("clean_text", r"\s+", " ")))
            .withColumn("char_length", F.length("clean_text"))
            .withColumn(
                "word_count",
                F.when(F.col("clean_text") == "", 0).otherwise(F.size(F.split("clean_text", " "))),
            )
        )

        total_rows = df.count()
        print(f"PySpark loaded rows: {total_rows:,}")

        # 1. Per-film text summary
        film_summary = (
            df.groupBy("film_id")
            .agg(
                F.count("*").alias("total_comments"),
                F.sum("in_7d_flag").alias("trailer_week_comments"),
                F.round(F.avg("char_length"), 2).alias("avg_char_len"),
                F.round(F.avg("word_count"), 2).alias("avg_word_count"),
                F.round(F.avg("like_count_num"), 2).alias("avg_comment_likes"),
            )
            .orderBy("film_id")
        )
        film_pd = film_summary.toPandas()
        c.write_csv(film_pd, c.CLEAN / "pyspark_film_text_summary.csv")

        # 2. Tokenize and count top terms (corpus-wide and top-5 per film)
        tokens = (
            df.select("film_id", F.explode(F.split("clean_text", " ")).alias("term"))
            .filter((F.length("term") >= 3) & (~F.col("term").isin(list(STOPWORDS))))
            .filter(~F.col("term").rlike(r"^\d+$"))
        )

        corpus_top = (
            tokens.groupBy("term")
            .agg(F.count("*").alias("term_count"))
            .withColumn("scope", F.lit("ALL_FILMS"))
            .withColumn("film_id", F.lit("ALL"))
            .orderBy(F.desc("term_count"))
            .limit(30)
            .select("scope", "film_id", "term", "term_count")
        )

        w = Window.partitionBy("film_id").orderBy(F.desc("term_count"))
        per_film_top = (
            tokens.groupBy("film_id", "term")
            .agg(F.count("*").alias("term_count"))
            .withColumn("rn", F.row_number().over(w))
            .filter(F.col("rn") <= 5)
            .withColumn("scope", F.lit("PER_FILM"))
            .select("scope", "film_id", "term", "term_count")
            .orderBy("film_id", F.desc("term_count"))
        )

        terms_pd = corpus_top.unionByName(per_film_top).toPandas()
        c.write_csv(terms_pd, c.CLEAN / "pyspark_top_terms.csv")

        print(f"Wrote data/clean/pyspark_film_text_summary.csv ({len(film_pd)} rows)")
        print(f"Wrote data/clean/pyspark_top_terms.csv ({len(terms_pd)} rows)")
        print("\nTop 10 corpus terms:")
        print(terms_pd[terms_pd["scope"] == "ALL_FILMS"].head(10).to_string(index=False))
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
