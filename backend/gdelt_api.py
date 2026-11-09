import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

#https://api.gdeltproject.org/api/v2/doc/doc?query=(iran%20OR%20hormuz)&mode=artlist&maxrecords=200&timespan=1h&sort=datedesc&format=json

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_QUERY = "(the OR and OR of OR to)" # more general default than "(iran OR hormuz)", for specific queries, user will specify

# GDELT rate-limits by IP and can return 429 for rapid/bursty requests.
# Its 429 body asks for at most one request every 5 seconds, so start the
# backoff there rather than at a full minute.
MAX_RETRIES = 5
BACKOFF_BASE = 5    # seconds; waits 5, 10, 20, 40 between attempts
BACKOFF_MAX = 60
BACKOFF_JITTER = 2  # random 0-2s extra so retries don't sync up

# GDELT's TLS handshake is often 10-15s from some networks, so allow a
# generous connect timeout while still failing instead of hanging forever.
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 60

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

HEADERS = {
    "User-Agent": "gray-project-news/1.0 (contact: your-email@example.com)",
    "Accept": "application/json",
}

# Collected JSON lives here, named by UTC date+time, e.g. 20261021_095500.json
DATA_DIR = Path(__file__).resolve().parent / "gdelt_data"
FILENAME_STAMP = "%Y%m%d_%H%M%S"


def _request_json(params: dict) -> dict:
    """GET BASE_URL with retry/backoff; return the parsed JSON body."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"Requesting GDELT (attempt {attempt}/{MAX_RETRIES})...",
                file=sys.stderr,
                flush=True,
            )
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )

            # Retry on rate limiting and transient server errors.
            if response.status_code in RETRYABLE_STATUS:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} from GDELT",
                    response=response,
                )

            # Other 4xx responses (bad query, etc.) won't succeed on retry.
            if 400 <= response.status_code < 500:
                raise RuntimeError(
                    f"GDELT rejected the request ({response.status_code}): "
                    f"{response.text[:200]!r}"
                )

            response.raise_for_status()

            # GDELT sometimes returns a 200 with an empty body or an HTML
            # error page when it's overloaded; treat those as transient.
            if not response.text.strip():
                raise ValueError("empty response body from GDELT")

            try:
                return response.json()
            except requests.exceptions.JSONDecodeError as exc:
                raise ValueError(
                    "non-JSON response from GDELT "
                    f"(status {response.status_code}): {response.text[:200]!r}"
                ) from exc

        except (requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                ValueError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break

            wait = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_MAX)
            response = getattr(exc, "response", None)
            retry_after = response.headers.get("Retry-After") if response is not None else None
            if retry_after:
                try:
                    wait = max(wait, int(float(retry_after)))
                except ValueError:
                    pass
            wait += random.uniform(0, BACKOFF_JITTER)

            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed ({exc}); "
                f"retrying in {wait:.1f}s...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(wait)

    raise RuntimeError(f"GDELT request failed after {MAX_RETRIES} attempts: {last_error}")


def get_gdelt_json(
    query: str = DEFAULT_QUERY,
    maxrecords: int | None = None,
    timespan: str | None = None,
    sort: str = "datedesc",
) -> dict:
    """Fetch an article list from the GDELT DOC API and save it as JSON.

    Arguments left at their defaults fall back to maxrecords=200 and
    timespan="1h" (GDELT rejects shorter windows like "15min" as too short).
    Values you pass explicitly are always used as-is.

    The response is saved to gdelt_data/<UTC YYYYMMDD_HHMMSS>.json with the
    query under the "query" key, and the parsed GDELT dict is returned.
    """
    now = datetime.now(timezone.utc)

    if maxrecords is None:
        maxrecords = 200
    if timespan is None:
        timespan = "1h"

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": maxrecords,
        "timespan": timespan,
        "sort": sort,
        "format": "json",
    }

    data = _request_json(params)

    # Record the query alongside the articles so each saved file is
    # self-describing (the filename only contains a timestamp).
    payload = {"query": query, **data}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{now:{FILENAME_STAMP}}.json"
    suffix = 1
    while out_path.exists():  # don't clobber an earlier call in the same second
        out_path = DATA_DIR / f"{now:{FILENAME_STAMP}}_{suffix}.json"
        suffix += 1

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        f"Saved {len(data.get('articles', []))} articles "
        f"(query={query!r}, maxrecords={maxrecords}, timespan={timespan!r}, "
        f"sort={sort!r}) to {out_path}"
    )
    return data


if __name__ == "__main__":
    # Same call as the reference URL:
    # .../doc?query=(iran OR hormuz)&mode=artlist&maxrecords=200&timespan=1h&sort=datedesc&format=json
    get_gdelt_json()
