"""Step 15 - Package all 6 required final deliverables into TeamName_FinalSubmission.zip.

Includes:
  1. Project Report (docs/final_report.md + supporting docs)
  2. Presentation Slides (docs/Release_Day_Radar_Presentation.pptx + presentation_slides.md)
  3. Code Files (src/*.py, sql/*.sql, requirements.txt, .env.example)
  4. Data Files (data/clean/*.csv — excluding any file >50 MB)
  5. README.md
  6. Team Contribution Split (docs/team_contribution.md)

Never includes .env, .git/, __pycache__/, or files >50 MB.

Run:  python -X utf8 src/15_package_submission.py
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

MAX_FILE_BYTES = 50 * 1024 * 1024


def main() -> int:
    zip_path = c.REPO_ROOT / "TeamName_FinalSubmission.zip"
    candidates: list[Path] = [
        c.REPO_ROOT / "README.md",
        c.REPO_ROOT / "requirements.txt",
        c.REPO_ROOT / ".env.example",
    ]
    candidates.extend(sorted((c.REPO_ROOT / "src").glob("*.py")))
    candidates.extend(sorted((c.REPO_ROOT / "sql").glob("*.sql")))
    candidates.extend(sorted((c.REPO_ROOT / "docs").glob("*.md")))
    candidates.extend(sorted((c.REPO_ROOT / "docs").glob("*.csv")))
    candidates.extend(sorted((c.REPO_ROOT / "docs").glob("*.pptx")))
    candidates.extend(sorted((c.REPO_ROOT / "docs" / "charts").glob("*.png")))
    candidates.extend(sorted((c.REPO_ROOT / "data" / "clean").glob("*.csv")))

    included = 0
    skipped: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in candidates:
            if not path.exists() or path.name == ".env":
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped.append(f"{path.name} ({path.stat().st_size / (1024*1024):.1f} MB)")
                continue
            zf.write(path, arcname=str(path.relative_to(c.REPO_ROOT)))
            included += 1

    zip_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Created {zip_path.name}: {included} files, {zip_mb:.2f} MB")
    if skipped:
        print("Skipped (>50 MB):", ", ".join(skipped))
    if zip_mb >= 50.0:
        print("WARNING: Zip exceeds 50 MB!")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
