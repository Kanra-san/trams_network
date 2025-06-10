import os
import xml.etree.ElementTree as ET
import pandas as pd
import sqlite3
from collections import defaultdict
from math import ceil
from variantdf import get_variant_names_for_line

DB_PATH = 'tram_data2.db'
XML_FOLDER = './xmls/'
MAX_TRIPS_PER_HOUR = 7

def parse_xml_schedule_for_line(line, variant, day_type):
    """Parses schedule XML and returns tram pass counts per stop per hour."""
    line_str = str(line).zfill(4)
    path = os.path.join(XML_FOLDER, line_str, f"{line_str}.xml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"XML not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    result = defaultdict(lambda: defaultdict(int))  # stop_id -> hour -> count

    for wariant in root.findall(".//wariant"):
        if wariant.attrib.get("id") != variant:
            continue

        czasy_section = wariant.find("przystanek/czasy")
        if czasy_section is None:
            continue

        # Map stop_id -> offset time (in minutes)
        stop_offsets = []
        for p in czasy_section.findall("przystanek"):
            stop_offsets.append((p.attrib['id'], int(p.attrib['czas'])))

        # Find schedule tabliczka
        tabliczka = wariant.find("przystanek/tabliczka")
        if tabliczka is None:
            continue

        dzien_nodes = tabliczka.findall("dzien")
        target_dzien = None
        for dzien in dzien_nodes:
            if day_type.lower() in dzien.attrib.get("nazwa", "").lower():
                target_dzien = dzien
                break

        if not target_dzien:
            continue

        # Extract all departure hours
        for godz in target_dzien.findall("godz"):
            hour = int(godz.attrib["h"])
            for min_elem in godz.findall("min"):
                minute = int(min_elem.attrib["m"])
                departure_time = hour * 60 + minute  # in minutes

                # Propagate through stops
                for stop_id, offset in stop_offsets:
                    arrival_time = departure_time + offset
                    arrival_hour = arrival_time // 60
                    result[stop_id][arrival_hour] += 1

    return result

def get_variant_name(line, variant_id):
    variants = get_variant_names_for_line(line)
    for v in variants:
        if v["variant_id"] == str(variant_id):
            return v["variant_name"]
    return None

DAY_TYPE_MAP = {
    "workday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "w dni robocze": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "saturday": ["Saturday"],
    "sobota": ["Saturday"],
    "sunday": ["Sunday"],
    "niedziela": ["Sunday"]
}

def get_traffic_data_from_db(day_type):
    """Returns average congestion per stop/hour for matching day_type."""
    days = DAY_TYPE_MAP.get(day_type)
    if not days:
        raise ValueError(f"Unknown day_type: {day_type}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholder = ','.join('?' * len(days))

    cursor.execute(f"""
        SELECT stop_id, hour, AVG(congestion_percent)
        FROM traffic_patterns
        WHERE day_of_week IN ({placeholder})
        GROUP BY stop_id, hour
    """, days)

    rows = cursor.fetchall()
    conn.close()

    traffic = defaultdict(dict)
    for stop_id, hour, percent in rows:
        traffic[str(stop_id)][int(hour)] = round(percent, 1)
    return traffic


def allocate_trips(original_counts, traffic_data):
    """Returns a DataFrame with optimized suggestions."""
    result = []

    # print("\n[DEBUG] Sample traffic_data keys:", list(traffic_data.keys())[:5])
    # for k in list(traffic_data.keys())[:5]:
    #     print(f"[DEBUG] traffic_data[{k}] hours:", list(traffic_data[k].keys())[:5])

    for stop_id, hour_counts in original_counts.items():
        for hour, count in hour_counts.items():
            # print(f"[DEBUG] Processing stop_id={stop_id}, hour={hour}, count={count}")
            congestion = traffic_data.get(stop_id, {}).get(hour, 0)
            # print(f"[DEBUG] congestion for stop_id={stop_id}, hour={hour}: {congestion}")
            suggested = ceil(count * (1 + congestion / 100))
            suggested = min(suggested, MAX_TRIPS_PER_HOUR)

            result.append({
                "stop_id": stop_id,
                "hour": hour,
                "original_trams": count,
                "congestion_percent": congestion,
                "suggested_trams": suggested
            })

    return pd.DataFrame(result)


def optimize_without_merging(line, day_type, variant):
    print(f"[OPTIMIZER] Called with line={line}, day_type={day_type}, variant={variant}")
    counts = parse_xml_schedule_for_line(line, variant, day_type)
    print(f"[OPTIMIZER] Counts (first 3): {list(counts.items())[:3]}")
    traffic = get_traffic_data_from_db(day_type)
    print(f"[OPTIMIZER] Traffic data (first 3): {list(traffic.items())[:3]}")
    df = allocate_trips(counts, traffic)
    print(f"[OPTIMIZER] Resulting DataFrame shape: {df.shape}")
    print(f"[OPTIMIZER] Resulting DataFrame head:\n{df.head()}\n")
    return df

def run_quick_test():
    print("🔧 Running quick test for optimizer...")
    pd.set_option('display.max_rows', None)

    # Example known-good parameters
    test_line = "4"
    test_variant = "1"
    test_day_type = "w dni robocze"

    variant_name = get_variant_name(test_line, test_variant)
    print(f"🛤️ Line {test_line}, Variant {test_variant} — {variant_name}")
    print(f"📅 Day Type: {test_day_type}")

    try:
        df = optimize_without_merging(test_line, test_day_type, test_variant)
        if df.empty:
            print("⚠️  Optimization result is empty.")
        else:
            print("✅ Optimization returned data:")
            print(df.to_string(index=False))
            save_to_csv(df, test_line, variant_name, test_day_type)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

def save_to_csv(df,  line, variant, day_type, filename="optimizer_results"):
    # Rename columns for readability
    df = df.rename(columns={
        "stop_id": "Stop ID",
        "hour": "Hour",
        "original_trams": "Original Trams",
        "congestion_percent": "Congestion (%)",
        "suggested_trams": "Suggested Trams"
    })
    # Format hour as two-digit string
    df["Hour"] = df["Hour"].apply(lambda x: f"{int(x):02d}")
    # Sort by Stop ID and Hour
    df = df.sort_values(["Stop ID", "Hour"])
    filename = f"{filename}_{line}_{variant}_{day_type}.csv"
    df.to_csv(filename, index=False)
    print(f"✅ Data saved to {filename}")

if __name__ == "__main__":
    run_quick_test()