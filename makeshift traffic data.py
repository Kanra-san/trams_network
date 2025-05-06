import sqlite3
import json
import re

# Load traffic data from JSON file
with open("traffic_data.json", "r", encoding="utf-8") as f:
    traffic_entries = json.load(f)

# Connect to database
conn = sqlite3.connect("tram_data2.db")
cursor = conn.cursor()

cursor.execute("DELETE FROM traffic_patterns")

# Build mapping: uppercase(stop_name) → list of stop_ids
stop_name_to_ids = {}
cursor.execute("SELECT stop_id, stop_name FROM stops")
for stop_id, stop_name in cursor.fetchall():
    stop_name_to_ids.setdefault(stop_name.upper(), []).append(stop_id)

# Helper to extract hour and percent from "08:00: 12%."
def parse_hour_and_percent(entry_str):
    match = re.match(r"(\d{2}):\d{2}:\s*(\d+)%", entry_str)
    if match:
        hour = match.group(1)
        percent = float(match.group(2))
        return hour, percent
    return None, None

# Insert query
insert_query = '''
INSERT OR IGNORE INTO traffic_patterns (stop_id, day_of_week, hour, congestion_percent)
VALUES (?, ?, ?, ?)
'''

# Polish to English day mapping
day_translation = {
    "poniedziałek": "Monday",
    "wtorek": "Tuesday",
    "środa": "Wednesday",
    "czwartek": "Thursday",
    "piątek": "Friday",
    "sobota": "Saturday",
    "niedziela": "Sunday"
}

total_inserted = 0
missing_stops = set()

for entry in traffic_entries:
    stop_name_upper = entry["location"].upper()
    traffic_data = entry.get("traffic_data", [])
    stop_ids = stop_name_to_ids.get(stop_name_upper)

    if not stop_ids:
        missing_stops.add(entry["location"])
        continue

    for day_entry in traffic_data:
        day_polish, hourly_entries = day_entry
        day_english = day_translation.get(day_polish.lower())
        if not day_english:
            continue

        for line in hourly_entries:
            hour, percent = parse_hour_and_percent(line)
            if hour is None:
                continue
            for stop_id in stop_ids:
                cursor.execute(insert_query, (stop_id, day_english, hour, percent))
                total_inserted += 1

conn.commit()
conn.close()

print(f"Inserted {total_inserted} traffic pattern entries.")
if missing_stops:
    print("Missing stop names (not in DB):")
    for name in sorted(missing_stops):
        print(f" - {name}")