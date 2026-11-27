# Spreadsheet vs. Pandas Comparison: Parsing Wikipedia Currency & Range Strings

## The Messy Real-World Problem
Wikipedia infobox `Budget` and `Box office` cells in our 12-film cohort arrive as heterogeneous strings mixing currency symbols, Indian/Western scale units, footnotes, and hyphenated ranges:
- `"₹1,813.39 crore"` (`F01 Dhurandhar: The Revenge`)
- `"₹90–130 crore[4]"` (en-dash `–` range requiring a midpoint)
- `"₹1.81 billion"` (needs `× 100` conversion to crore)
- `"N/A"` or missing infobox row (`F06 Saiyaara` had no parsable budget on Wikipedia)

---

## Side-by-Side Implementation

| Dimension | Excel / Google Sheets Approach | Python `pandas` (`src/common.py` -> `crore_from_text()`) |
| :--- | :--- | :--- |
| **Input Cell (`A2`)** | `"₹90–130 crore[4]"` | `"₹90–130 crore[4]"` |
| **Exact Logic / Formula** | Multi-step nested formula:<br>`=IFERROR(AVERAGE(VALUE(TRIM(LEFT(SUBSTITUTE(SUBSTITUTE(A2,"₹","")," crore",""), FIND("–",SUBSTITUTE(A2,"₹",""))-1))), VALUE(TRIM(MID(SUBSTITUTE(SUBSTITUTE(A2,"₹","")," crore",""), FIND("–",SUBSTITUTE(A2,"₹",""))+1, 10)))), IFERROR(VALUE(SUBSTITUTE(SUBSTITUTE(A2,"₹","")," crore","")), ""))` | Compiled regex + unit multiplier table:<br>`match = _AMOUNT_RE.search(str(text))`<br>`first = float(match.group(1).replace(",", ""))`<br>`second = float(match.group(2).replace(",", "")) if match.group(2) else first`<br>`round(((first + second) / 2) * _UNIT_FACTOR[unit], 2)` |
| **Unit Scaling (`billion`, `lakh`)** | Requires nested `IF(ISNUMBER(SEARCH("billion",A2)), ...*100, IF(ISNUMBER(SEARCH("lakh",A2)), .../100, ...))` | Single dictionary lookup (`_UNIT_FACTOR["billion"] = 100.0`, `_UNIT_FACTOR["lakh"] = 0.01`, `_UNIT_FACTOR["crore"] = 1.0`) |
| **Missing / `"N/A"` Handling** | `IFERROR(..., "")` silently turns both genuine missing values and unexpected formats (e.g., ASCII `-` vs en-dash `–`) into blank cells. | Returns explicit Python `None` (`NaN`), which `02_reconcile_wiki.py` flags and logs in `docs/cleaning_log.csv` (e.g., `F06 Saiyaara` missing budget). |

---

## Key Engineering Takeaways
1. **Reproducibility & Version Control:** In a spreadsheet, dragging a formula down 12 rows leaves no diffable history; in `pandas`, `crore_from_text()` is versioned in Git and applied identically every time the pipeline runs.
2. **En-dash vs. Hyphen Fragility:** Spreadsheet `FIND("–", ...)` breaks silently if one Wikipedia editor uses `-` instead of `–`. Regex `[–-]` handles both uniformly.
3. **Auditability:** Returning `None` rather than masking errors with `IFERROR` lets `02_reconcile_wiki.py` automatically log every missing or divergent cell into `docs/cleaning_log.csv`.
