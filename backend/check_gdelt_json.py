"""Detect GDELT JSON files that lack a top-level ``query`` key."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_operations import DATA_DIR, find_invalid_json_files


def main() -> int:
    invalid = find_invalid_json_files(DATA_DIR)
    if invalid:
        print("GDELT JSON files missing a top-level 'query' key:")
        for path in invalid:
            print(f"  - {path}")
        return 1
    print("All GDELT JSON files have a top-level 'query' key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
