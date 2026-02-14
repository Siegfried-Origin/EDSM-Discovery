#!/usr/bin/env python3

import requests
import csv
import time
import json
import os
from datetime import datetime, timedelta, UTC
from tqdm import tqdm
from dotenv import load_dotenv
from pathlib import Path

# ==============================
# CONFIGURATION
# ==============================

ENV_FILE    = Path(".env")
LOGS_URL    = "https://www.edsm.net/api-logs-v1/get-logs"
TRAFFIC_URL = "https://www.edsm.net/api-system-v1/traffic"


def create_env_file():
    print("🔧 First execution detected.")
    print("Please enter your EDSM credentials.\n")
    print("Visit https://www.edsm.net/en/settings/api to get your credentials.\n")

    commander = input("Commander Name: ").strip()
    api_key = input("API Key: ").strip()

    if not commander or not api_key:
        raise ValueError("Commander and API key cannot be empty.")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"COMMANDER={commander}\n")
        f.write(f"API_KEY={api_key}\n")

    print("\n✅ .env file created successfully.\n")


def load_config():
    if not ENV_FILE.exists():
        create_env_file()

    load_dotenv()

    commander = os.getenv("COMMANDER")
    api_key = os.getenv("API_KEY")

    if not commander or not api_key:
        raise RuntimeError("Invalid .env configuration.")

    return commander, api_key


# ==============================
# INTERVAL GENERATION (STABLE)
# ==============================

def utc_now():
    return datetime.now(UTC)


def make_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def utc_datetime(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def align_to_monday(dt):
    dt = make_utc(dt)
    return dt - timedelta(days=dt.weekday())


def generate_stable_week_intervals(start_date, end_date):
    start_date = make_utc(start_date)
    end_date = make_utc(end_date)

    current = align_to_monday(start_date)

    while current < end_date:
        week_end = current + timedelta(days=7)
        yield current, week_end
        current = week_end


def format_edsm_datetime(dt: datetime) -> str:
    dt = make_utc(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def interval_key(start):
    return start.strftime("%Y-%m-%d")


# ==============================
# CACHE HELPERS
# ==============================

def load_cache(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ==============================
# FIRST DISCOVERIES
# ==============================

def get_first_discoveries(commander, api_key, start, end):
    params = {
        "commanderName": commander,
        "apiKey": api_key,
        "startDateTime": format_edsm_datetime(start),
        "endDateTime": format_edsm_datetime(end),
        "showId": 1
    }

    try:
        r = requests.get(LOGS_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        if data.get("msgnum") != 100:
            print("⚠ API error:", data)
            return []

        return [
            (str(log["systemId"]), log["system"], log["date"])
            for log in data.get("logs", [])
            if log["firstDiscover"]
        ]

    except Exception as e:
        print("❌ Request failed:", e)
        return []


# ==============================
# SMART DISCOVERY CACHE SYSTEM
# ==============================

def update_discoveries_cache(commander, api_key, start_date, end_date, safety_weeks, cache_file):
    cache = load_cache(cache_file)

    if not cache:
        cache = {
            "meta": {"version": 1},
            "intervals": {},
            "systems": {}
        }

    # for safety, always refresh the last few weeks to catch any late updates
    safe_start = align_to_monday(end_date - timedelta(days=7*safety_weeks))
    for start, _ in generate_stable_week_intervals(safe_start, end_date):
        cache["intervals"].pop(interval_key(start), None)

    intervals_to_fetch = []

    for start, end in generate_stable_week_intervals(start_date, end_date):
        # ignore weeks completely outside the range
        if end <= start_date or start >= end_date:
            continue

        key = interval_key(start)

        if key not in cache["intervals"]:
            intervals_to_fetch.append((start, end, key))

    print(f"🔎 {len(intervals_to_fetch)} interval(s) to fetch...")

    # Avoid abuse of the API if we have a lot of intervals to fetch
    if len(intervals_to_fetch) > 360:
        print("⚠ Many intervals to fetch! Increasing delay to avoid rate limiting.")
        request_log_delay = 10.0
    else:
        request_log_delay = 0.4

    for start, end, key in tqdm(intervals_to_fetch):
        discoveries = get_first_discoveries(commander, api_key, start, end)

        for sys_id, name, date in discoveries:
            if sys_id in cache["systems"]:
                existing_date = cache["systems"][sys_id]["firstDiscoveryDate"]
                if date < existing_date:
                    cache["systems"][sys_id]["firstDiscoveryDate"] = date
            else:
                cache["systems"][sys_id] = {
                    "name": name,
                    "firstDiscoveryDate": date
                }

        cache["intervals"][key] = {
            "fetched_at": utc_now().isoformat()
        }

        save_cache(cache_file, cache)
        time.sleep(request_log_delay)

    print(f"\n✅ Total: systems first discovered : {len(cache['systems'])}")

    return cache["systems"]


# ==============================
# TRAFFIC ANALYSIS
# ==============================

def get_traffic(system_id):
    r = requests.get(TRAFFIC_URL, params={"systemId": system_id})
    data = r.json()
    return data


def main():
    COMMANDER, API_KEY = load_config()

    if not COMMANDER or not API_KEY:
        raise ValueError("COMMANDER or API_KEY missing in .env file")

    TRAFFIC_DELAY  = 0.4

    DISCOVERY_CACHE_FILE = "first_discoveries_cache.json"
    OUTPUT_FILE          = "edsm_first_discoveries_traffic.csv"

    SAFETY_WEEKS = 2  # Always refresh last two weeks

    START_DATE = utc_datetime(2026, 1, 1)
    END_DATE = utc_now()

    print("📡 Loading cache discoveries...")
    discoveries_cache = update_discoveries_cache(COMMANDER, API_KEY, START_DATE, END_DATE, SAFETY_WEEKS, DISCOVERY_CACHE_FILE)

    print(f"✅ Loaded {len(discoveries_cache)} system(s) first discovered.")

    traffic = {}

    print("🚦 Analysing trafic...")

    for sys_id in tqdm(discoveries_cache.keys()):
        try:
            data = get_traffic(sys_id)

            traffic[sys_id] = {
                "total": data.get("traffic", {}).get("total", 0),
                "week": data.get("traffic", {}).get("week", 0),
                "day": data.get("traffic", {}).get("day", 0),
                "breakdown": data.get("breakdown", {})
            }

            time.sleep(TRAFFIC_DELAY)

        except Exception as e:
            print("Error:", e)
            break

    print("✅ Analysing trafic completed.")

    # EXPORT CSV
    results = []

    for sys_id, info in discoveries_cache.items():
        traffic_info = traffic.get(sys_id, {})
        total = traffic_info.get("total", 0)

        results.append({
            "systemName": info["name"],
            "systemId": sys_id,
            "firstDiscoveryDate": info["firstDiscoveryDate"],
            "totalTraffic": total,
            "trafficWeek": traffic_info.get("week", 0),
            "trafficDay": traffic_info.get("day", 0),
            "visitedAfterDiscovery": total > 1
        })

    # Sort most visited first discoveries
    results_sorted = sorted(results, key=lambda x: x["totalTraffic"], reverse=True)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = results_sorted[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_sorted)

    print(f"\n💾 Export CSV done: {OUTPUT_FILE}")

    # STATS
    never = sum(1 for r in results if r["totalTraffic"] <= 1)

    print("\n📊 STATISTICS")
    print(f"Total systems         : {len(results)}")
    print(f"Never revisited       : {never}")
    print(f"Revisited             : {len(results) - never}")
    print(f"Intacts (%)           : {round((never/len(results))*100, 2)}%")

    print("\n🏆 TOP 10 most visited systems:")
    for r in results_sorted[:10]:
        print(f"{r['systemName']} → {r['totalTraffic']} visits")


if __name__ == '__main__':
    main()