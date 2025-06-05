import os
import glob
import xml.etree.ElementTree as ET
from collections import defaultdict
import pandas as pd
import logging
from db_handler import TramDatabase
import sqlite3

    
def parse_xml_schedule_for_line(xml_folder, line_no):
    """
    Robust XML parser for tram schedule, inspired by scheduledf.py.
    Returns a DataFrame with columns: Line no., Variant, Variant ID, Day, Hour, Minute, Stop ID, Stop Name, No. of courses (default 1 per row)
    """
    import xml.etree.ElementTree as ET
    import pandas as pd
    import os
    # Accept both zero-padded and non-padded line numbers
    line_no_str = str(line_no)
    line_no_padded = line_no_str.zfill(4)
    # Find the XML file for this line
    xml_path = os.path.join(xml_folder, line_no_padded, f"{line_no_padded}.xml")
    if not os.path.exists(xml_path):
        # Try non-padded
        xml_path = os.path.join(xml_folder, line_no_str, f"{line_no_str}.xml")
        if not os.path.exists(xml_path):
            return pd.DataFrame()  # No file found
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return pd.DataFrame()
    schedule_data = []
    for wariant in root.findall(".//wariant"):
        variant_id = wariant.attrib.get("id")
        variant_name = wariant.attrib.get("nazwa")
        for przystanek in wariant.findall("przystanek"):
            stop_id = przystanek.attrib.get("id")
            stop_name = przystanek.attrib.get("nazwa")
            for tabliczka in przystanek.findall("tabliczka"):
                timetable_id = tabliczka.attrib.get("id")
                for dzien in tabliczka.findall("dzien"):
                    day_type = dzien.attrib.get("nazwa")
                    for godz in dzien.findall("godz"):
                        hour = godz.attrib.get("h")
                        for min_el in godz.findall("min"):
                            minute = min_el.attrib.get("m")
                            ozn = min_el.attrib.get("ozn")
                            przyp = min_el.attrib.get("przyp")
                            schedule_data.append({
                                "Line no.": line_no_str,
                                "Variant": variant_name,
                                "Variant ID": variant_id,
                                "Day": day_type,
                                "Hour": str(hour).zfill(2),
                                "Minute": str(minute).zfill(2),
                                "Stop ID": stop_id,
                                "Stop Name": stop_name,
                                "No. of courses": 1,
                                "Notation": ozn,
                                "Description": przyp
                            })
    df = pd.DataFrame(schedule_data)
    return df


def get_traffic_data_from_db():
    """Improved traffic data fetcher with detailed logging"""
    db = TramDatabase()
    try:
        with db._get_connection() as conn:
            # Adjusted query to match the actual schema
            query = """
                SELECT 
                    stop_id as 'Stop ID',
                    day_of_week as 'Day',
                    hour as 'Hour',
                    congestion_percent as 'traffic_percent'
                FROM traffic_patterns
                ORDER BY stop_id, day_of_week, hour
            """
            df = pd.read_sql(query, conn)

            # Ensure proper data types
            if not df.empty:
                df['Line no.'] = df['Stop ID']  # Map Stop ID to Line no. for compatibility
                df['Hour'] = df['Hour'].astype(str).str.split(':').str[0]
                df['Hour'] = df['Hour'].apply(lambda x: f"{int(x):02d}")

            logging.info(f"Retrieved {len(df)} traffic records from DB")
            if df.empty:
                logging.warning("Traffic data is empty. Check if the traffic_patterns table is populated.")
            else:
                logging.debug(f"Traffic data sample:\n{df.head()}")
            return df

    except Exception as e:
        logging.error(f"Error fetching traffic data: {e}")
        return pd.DataFrame()
    

def normalize_traffic(df):
    """Normalize traffic percentages to 0-1 scale with smoothing"""
    # Add small constant to avoid division by zero
    epsilon = 0.001
    
    min_t = df['traffic_percent'].min()
    max_t = df['traffic_percent'].max()
    
    # Handle case where all values are the same
    if max_t - min_t < epsilon:
        df['normalized_traffic'] = 0.5  # Midpoint if all values are equal
    else:
        df['normalized_traffic'] = (df['traffic_percent'] - min_t) / (max_t - min_t + epsilon)
    
    # Apply smoothing
    df['normalized_traffic'] = df['normalized_traffic'].clip(0.1, 0.9)
    
    return df

def allocate_trips(traffic_df, schedule_df, max_trips_per_hour=7):
    """More robust trip allocation with better logging"""
    logging.info("Starting trip allocation")
    
    if traffic_df.empty:
        logging.warning("No traffic data available")
        return pd.DataFrame()
        
    if schedule_df.empty:
        logging.warning("No schedule data available")
        return pd.DataFrame()

    # Ensure consistent data types
    traffic_df = traffic_df.copy()
    schedule_df = schedule_df.copy()
    
    for col in ['Line no.', 'Day', 'Hour']:
        traffic_df[col] = traffic_df[col].astype(str)
        schedule_df[col] = schedule_df[col].astype(str)
    
    # Debug logging
    logging.debug(f"Traffic data sample:\n{traffic_df.head()}")
    logging.debug(f"Schedule data sample:\n{schedule_df.head()}")
    
    # Verify column values
    logging.debug(f"Unique Line no. in traffic data: {traffic_df['Line no.'].unique()}")
    logging.debug(f"Unique Line no. in schedule data: {schedule_df['Line no.'].unique()}")
    logging.debug(f"Unique Days in traffic data: {traffic_df['Day'].unique()}")
    logging.debug(f"Unique Days in schedule data: {schedule_df['Day'].unique()}")
    logging.debug(f"Unique Hours in traffic data: {traffic_df['Hour'].unique()}")
    logging.debug(f"Unique Hours in schedule data: {schedule_df['Hour'].unique()}")
    
    try:
        # Merge data
        merged = pd.merge(
            traffic_df,
            schedule_df,
            on=['Line no.', 'Day', 'Hour'],
            how='inner'
        )
        
        if merged.empty:
            logging.warning("No matching records between traffic and schedule data")
            return pd.DataFrame()
            
        # Normalize traffic and allocate trips
        merged['normalized_traffic'] = (merged['traffic_percent'] - merged['traffic_percent'].min()) / \
                                      (merged['traffic_percent'].max() - merged['traffic_percent'].min())
        merged['allocated_trips'] = (merged['normalized_traffic'] * max_trips_per_hour).round().astype(int)
        merged['allocated_trips'] = merged[['allocated_trips', 'No. of courses']].min(axis=1)
        
        logging.info(f"Successfully allocated trips for {len(merged)} time slots")
        return merged[['Line no.', 'Day', 'Hour', 'No. of courses', 'allocated_trips']]
        
    except Exception as e:
        logging.error(f"Error in allocation: {e}")
        return pd.DataFrame()
    

def allocate_trips_directly(schedule_df, traffic_df, max_trips_per_hour=7):
    """Adjust schedule directly based on traffic intensity"""
    logging.info("Starting direct trip allocation")

    if traffic_df.empty:
        logging.warning("No traffic data available")
        return schedule_df

    if schedule_df.empty:
        logging.warning("No schedule data available")
        return schedule_df

    # Normalize traffic intensity
    traffic_df['normalized_traffic'] = (traffic_df['traffic_percent'] - traffic_df['traffic_percent'].min()) / \
                                       (traffic_df['traffic_percent'].max() - traffic_df['traffic_percent'].min())
    traffic_df['normalized_traffic'] = traffic_df['normalized_traffic'].clip(0.1, 0.9)
    logging.debug(f"Normalized traffic data:\n{traffic_df.head()}")

    # Adjust schedule
    def adjust_row(row):
        relevant_traffic = traffic_df.loc[
            (traffic_df['Day'] == row['Day']) & (traffic_df['Hour'] == row['Hour']),
            'normalized_traffic'
        ]
        if relevant_traffic.empty:
            logging.debug(f"No traffic data for Day={row['Day']} Hour={row['Hour']}")
            return row['No. of courses']
        adjusted_trips = min(max_trips_per_hour * relevant_traffic.mean(), row['No. of courses'])
        logging.debug(f"Adjusted trips for Day={row['Day']} Hour={row['Hour']}: {adjusted_trips}")
        return adjusted_trips

    schedule_df['optimized_trips'] = schedule_df.apply(adjust_row, axis=1)

    logging.info(f"Successfully adjusted trips for {len(schedule_df)} schedule entries")
    return schedule_df

def debug_print_traffic_patterns_table(db_file='tram_data2.db'):
    print("\n--- DEBUG: First rows of traffic_patterns table ---")
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("SELECT * FROM traffic_patterns LIMIT 5;")
        rows = cur.fetchall()
        for row in rows:
            print(row)
        cur.execute("SELECT DISTINCT stop_id FROM traffic_patterns;")
        print("Unique stop_ids:", [r[0] for r in cur.fetchall()])
        cur.execute("SELECT DISTINCT day_of_week FROM traffic_patterns;")
        print("Unique day_of_week:", [r[0] for r in cur.fetchall()])
        cur.execute("SELECT DISTINCT hour FROM traffic_patterns;")
        print("Unique hour:", [r[0] for r in cur.fetchall()])
        conn.close()
    except Exception as e:
        print(f"Error reading traffic_patterns table: {e}")

def debug_print_xml_structure(xml_folder):
    print("\n--- DEBUG: XML Structure in folder ---")
    for root, dirs, files in os.walk(xml_folder):
        for file in files:
            if file.endswith('.xml'):
                path = os.path.join(root, file)
                try:
                    tree = ET.parse(path)
                    root_elem = tree.getroot()
                    print(f"\nFile: {path}")
                    print(f"Root tag: {root_elem.tag}")
                    print("First-level child tags:", [child.tag for child in root_elem])
                    for linia in root_elem.findall('.//linia'):
                        print(f"<linia> attributes: {linia.attrib}")
                except Exception as e:
                    print(f"Error parsing {path}: {e}")

def main():
    xml_folder = './xmls/'
    debug_print_xml_structure(xml_folder)
    # Example: optimize for line 4
    line_no = 4
    schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
    print(f'Schedule data from XML for line {line_no}:')
    print(schedule_df)

    #debug_print_traffic_patterns_table()  # <-- Add this debug print

    traffic_df = get_traffic_data_from_db()
    print('Traffic data from DB:')
    print(traffic_df)

    # Use direct allocation logic
    result = allocate_trips_directly(schedule_df, traffic_df)
    print('Optimized allocation:')
    print(result)
    result.to_csv(f'optimized_schedule_line_{line_no}.csv', index=False)
    

    traffic_df = get_traffic_data_from_db()
    # Filter traffic data for the selected line
    if not traffic_df.empty and 'Line no.' in traffic_df.columns:
        traffic_df = traffic_df[traffic_df['Line no.'] == str(line_no)]
        print('Traffic data from DB:')
        print(traffic_df.head())
        result = allocate_trips(traffic_df, schedule_df)
        print('Optimized allocation:')
        print(result.head())
        result.to_csv(f'optimized_schedule_line_{line_no}.csv', index=False)
    else:
        print('Traffic data from DB is empty or missing Line no. column.')
# For Flask import: expose a function for multi-line optimization

def optimize_lines(period, lines, hour=None, day_type=None, variant=None):
    """
    For each selected line and variant, extract only that variant's route from XML, get stop_ids, aggregate their traffic data, and propose a schedule.
    """
    xml_folder = './xmls/'
    results = []
    for line_no in lines:
        # Parse XML and extract only the selected variant's schedule
        schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
        if schedule_df.empty:
            continue
        if variant:
            schedule_df = schedule_df[schedule_df['Variant'] == variant]
        if day_type:
            schedule_df = schedule_df[schedule_df['Day'].str.lower() == day_type.lower()]
        if schedule_df.empty:
            continue
        # Get the route (ordered stop_ids) for this variant
        route_stop_ids = schedule_df['Stop ID'].unique().tolist()
        if not route_stop_ids:
            continue
        # Get traffic data for these stops
        traffic_df = get_traffic_data_from_db()
        relevant_traffic = traffic_df[traffic_df['Stop ID'].isin(route_stop_ids)]
        if relevant_traffic.empty:
            continue
        # Aggregate: average congestion per day/hour across all stops in the variant's route
        agg_traffic = (
            relevant_traffic.groupby(['Day', 'Hour'], as_index=False)
            .agg({'traffic_percent': 'mean'})
        )
        # Propose a schedule: for each hour, set number of trips proportional to congestion (e.g., 1-7 trips)
        min_t = agg_traffic['traffic_percent'].min()
        max_t = agg_traffic['traffic_percent'].max()
        if max_t - min_t < 0.001:
            agg_traffic['normalized_traffic'] = 0.5
        else:
            agg_traffic['normalized_traffic'] = (agg_traffic['traffic_percent'] - min_t) / (max_t - min_t + 0.001)
        agg_traffic['normalized_traffic'] = agg_traffic['normalized_traffic'].clip(0.1, 0.9)
        max_trips_per_hour = 7
        agg_traffic['proposed_trips'] = (agg_traffic['normalized_traffic'] * max_trips_per_hour).round().astype(int).clip(lower=1)
        # Build results for frontend: one entry per hour
        for _, row in agg_traffic.iterrows():
            results.append({
                'line': line_no,
                'variant': variant if variant else '',
                'day': row['Day'],
                'hour': row['Hour'],
                'proposed_trips': int(row['proposed_trips'])
            })
    return results

if __name__ == '__main__':
    main()
