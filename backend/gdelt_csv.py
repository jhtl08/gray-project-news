# configure later as async api call to wait for immediate update on next timestamp per 15 minute

import os
import time
import zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

BASE_URL = "http://data.gdeltproject.org/gdeltv2/"
OUTPUT_DIR = "gdelt_data"
RETRY_WINDOW = timedelta(minutes=5)  # keep retrying the same slot for 5 min
RETRY_INTERVAL = 30  # seconds between retries


def latest_slot(now_utc: datetime) -> datetime:
    """Return the latest 15-minute slot, nudged forward when we are within
    5 minutes of the next multiple (e.g. 11:11 -> 11:15)."""
    minutes_since_midnight = now_utc.hour * 60 + now_utc.minute
    slot = (minutes_since_midnight // 15) * 15

    minutes_to_next = 15 - (minutes_since_midnight % 15)
    if minutes_to_next <= 5:
        slot += 15

    midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=slot)


def fetch_export(slot: datetime) -> requests.Response:
    """Download the export zip for `slot`.

    If it isn't available, alert and retry the SAME slot every
    RETRY_INTERVAL for up to RETRY_WINDOW -- never falls back to an
    earlier slot. Gives up (with an alert) once the window expires.
    """
    stamp = slot.strftime("%Y%m%d%H%M%S")  # seconds are always 00
    url = f"{BASE_URL}{stamp}.export.CSV.zip"
    deadline = datetime.now(timezone.utc) + RETRY_WINDOW
    attempt = 0

    while True:
        attempt += 1
        print(f"Fetching:   {url}  (attempt {attempt})")
        error = None
        try:
            response = requests.get(url, timeout=60)
        except requests.RequestException as exc:
            response = None
            error = exc

        if response is not None and response.status_code == 200:
            return response

        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            status = f"HTTP {response.status_code}" if response is not None else error
            window = (
                f"{RETRY_WINDOW.total_seconds() / 60:.0f} minutes"
                if RETRY_WINDOW >= timedelta(minutes=1)
                else f"{RETRY_WINDOW.total_seconds():.0f} seconds"
            )
            raise SystemExit(
                f"ALERT: Could not download {url} within {window} "
                f"(last result: {status}). Giving up -- try again later."
            )

        status = f"HTTP {response.status_code}" if response is not None else error
        wait = min(RETRY_INTERVAL, max(remaining, 1))
        left = f"{remaining / 60:.1f} min" if remaining >= 60 else f"{remaining:.0f}s"
        print(
            f"ALERT: Not available yet ({status}) for slot "
            f"{slot:%H:%M} UTC -- no fallback; retrying in {wait:.0f}s "
            f"({left} left in retry window)."
        )
        time.sleep(wait)


def main() -> None:
    # 1. Current time, converted from PHT to UTC
    now_pht = datetime.now(ZoneInfo("Asia/Manila"))
    now_utc = now_pht.astimezone(ZoneInfo("UTC"))
    print(f"Now (PHT): {now_pht:%Y-%m-%d %H:%M:%S %Z}")
    print(f"Now (UTC): {now_utc:%Y-%m-%d %H:%M:%S %Z}")

    # 2. Latest previous 15-minute multiple (with the <=5 minute nudge)
    slot = latest_slot(now_utc)
    print(f"Slot (UTC): {slot:%Y-%m-%d %H:%M}")

    # 3. Download the zip (alert + retry same slot for up to 5 minutes)
    response = fetch_export(slot)

    # 4. Extract it and keep only the CSV
    stamp = slot.strftime("%Y%m%d%H%M%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUTPUT_DIR, f"{stamp}.export.CSV.zip")
    with open(zip_path, "wb") as f:
        f.write(response.content)

    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            os.remove(zip_path)
            raise SystemExit("No CSV file found inside the archive.")
        csv_name = csv_names[0]
        csv_path = os.path.join(OUTPUT_DIR, os.path.basename(csv_name))
        with zf.open(csv_name) as src, open(csv_path, "wb") as dst:
            dst.write(src.read())

    # 5. Drop the zip so only the CSV remains
    os.remove(zip_path)
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
