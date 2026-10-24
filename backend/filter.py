# Filter the latest GDELT export CSV, keeping only the location (city/region/
# country), date, url and headline columns, and only rows whose location is one
# of the countries below. Duplicate articles (same url) are removed, keeping the
# first location seen for each.
#
# GDELT 2.0 event files are tab-separated with 61 columns and no header.
# Relevant columns (0-indexed):
#   52  ActionGeo_FullName  -> event location as "city, region, country"
#   59  DATEADDED           -> date
#   60  SOURCEURL           -> url

import glob
import os
import re
from urllib.parse import unquote, urlparse

CSV_DIR = "gdelt_data/csv"
OUTPUT_DIR = "gdelt_data/filtered"

LOCATIONS = [
    "China",
    "United States",
    "Ukraine",
    "Russia",
    "Israel",
    "India",
    "Iran",
    "South Korea",
    "Venezuela",
    "Canada",
    "Romania",
    "Yemen",
    "Saudi Arabia",
    "United Kingdom",
    "France",
]

LOCATION_COL = 52
DATE_COL = 59
URL_COL = 60

# Whole-word, case-insensitive match so "India" doesn't match "Indiana".
LOCATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(loc) for loc in LOCATIONS) + r")\b",
    re.IGNORECASE,
)

# A real headline contains at least one plain alphabetic word; this rejects
# slug-shaped ids such as "article_369dea21-408f-5331-a932-8091afd71cbd".
TITLE_WORD_RE = re.compile(r"^[A-Za-z]{3,}$")

# File extensions to drop from a slug. Only known ones, so ids embedded with a
# dot (e.g. "26618677.county-durham-...") are kept intact.
EXTENSION_RE = re.compile(
    r"\.(?:html?|php\d?|aspx?|asp|jsp|shtml|cms|amp)$", re.IGNORECASE
)

# Numbers left over from the url: long digit ids (>=5 digits, standalone or
# glued to a word) and leading/trailing "YYYY MM DD" date stamps.
NOISE_NUMBER_RE = re.compile(r"\d{5,}")
LEADING_DATE_RE = re.compile(r"^\d{4}\s+\d{1,2}\s+\d{1,2}\s+")
TRAILING_DATE_RE = re.compile(r"\s+\d{4}\s+\d{1,2}\s+\d{1,2}$")


def latest_csv(directory: str) -> str:
    """Return the path to the newest .csv/.CSV in `directory` (by filename)."""
    files = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".csv")
    ]
    if not files:
        raise SystemExit(f"ALERT: No CSV files found in {directory!r}.")
    return max(files, key=os.path.basename)


def _strip_url_numbers(title: str) -> str:
    """Remove url-artifact numbers from a headline: long ids and date stamps."""
    words = []
    for word in title.split():
        if NOISE_NUMBER_RE.search(word):
            rest = NOISE_NUMBER_RE.sub("", word).strip("-_.")
            if len(rest) <= 1:  # nothing but a stray letter ("n2207871" -> "n")
                continue
            words.append(rest)
        else:
            words.append(word)

    text = " ".join(words).strip()
    text = LEADING_DATE_RE.sub("", text)
    text = TRAILING_DATE_RE.sub("", text)
    return text.strip()


def _slug_to_title(segment: str):
    """Turn one url path segment into a headline, or None if it isn't one."""
    stem = EXTENSION_RE.sub("", segment)
    if "-" not in stem:
        return None

    title = re.sub(r"\s+", " ", stem.replace("-", " ")).strip()
    title = _strip_url_numbers(title)
    if not any(TITLE_WORD_RE.match(word) for word in title.split()):
        return None
    return title


def extract_title(url: str):
    """Best-effort headline from the url path.

    News slugs separate words with "-" (e.g. ".../the-cost-of-drugs.html" ->
    "the cost of drugs"). Many sites put a numeric article id in the *last*
    segment, so segments are scanned right-to-left until one looks like a
    headline. Returns None when the url has no such slug.
    """
    path = unquote(urlparse(url).path)
    for segment in reversed([seg for seg in path.split("/") if seg]):
        title = _slug_to_title(segment)
        if title:
            return title
    return None


def main() -> None:
    src = latest_csv(CSV_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dest = os.path.join(OUTPUT_DIR, os.path.basename(src))

    # Dedupe on url, keeping the first location seen for each article.
    seen_urls = set()
    matched = 0
    kept = 0
    with open(src, encoding="utf-8-sig") as f_in, open(
        dest, "w", encoding="utf-8", newline=""
    ) as f_out:
        for line in f_in:
            row = line.rstrip("\n").split("\t")
            if len(row) <= URL_COL:
                continue

            location = row[LOCATION_COL].strip()
            if not location or not LOCATION_RE.search(location):
                continue
            matched += 1

            date = row[DATE_COL].strip()
            url = row[URL_COL].strip()
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = extract_title(url)

            f_out.write("\t".join([location, date, url, title or ""]) + "\n")
            kept += 1

    print(f"Latest CSV: {src}")
    print(f"Matched {matched} rows, removed {matched - kept} duplicates")
    print(f"Saved {kept} rows to: {dest}")


if __name__ == "__main__":
    main()
