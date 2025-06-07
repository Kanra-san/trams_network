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
    logging.info(f"Parsing XML file: {xml_path}")
    logging.info(f"Extracted schedule data sample: {schedule_data[:5]}")
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
    
    for col in ['Stop ID', 'Day', 'Hour']:
        traffic_df[col] = traffic_df[col].astype(str)
        schedule_df[col] = schedule_df[col].astype(str)
    
    # Debug logging
    logging.debug(f"Traffic data sample:\n{traffic_df.head()}")
    logging.debug(f"Schedule data sample:\n{schedule_df.head()}")
    
    # Add detailed logs to compare Stop ID, Day, and Hour values
    logging.debug(f"Traffic data Stop IDs: {traffic_df['Stop ID'].unique()}")
    logging.debug(f"Schedule data Stop IDs: {schedule_df['Stop ID'].unique()}")
    logging.debug(f"Traffic data Days: {traffic_df['Day'].unique()}")
    logging.debug(f"Schedule data Days: {schedule_df['Day'].unique()}")
    logging.debug(f"Traffic data Hours: {traffic_df['Hour'].unique()}")
    logging.debug(f"Schedule data Hours: {schedule_df['Hour'].unique()}")
    logging.debug(f"Unique Hours in Schedule Data: {schedule_df['Hour'].unique()}")
    logging.debug(f"Unique Hours in Traffic Data: {traffic_df['Hour'].unique()}")

    # Ensure Day values in traffic data are mapped correctly
    traffic_day_type_map = {
        'Monday': 'w dni robocze',
        'Tuesday': 'w dni robocze',
        'Wednesday': 'w dni robocze',
        'Thursday': 'w dni robocze',
        'Friday': 'w dni robocze',
        'Saturday': 'Sobota',
        'Sunday': 'Niedziela'
    }
    traffic_df['Day'] = traffic_df['Day'].map(traffic_day_type_map)
    logging.debug(f"Mapped traffic data Days to match schedule format:\n{traffic_df.head()}")

    # Ensure Hour values are consistent
    traffic_df['Hour'] = traffic_df['Hour'].astype(str).str.zfill(2)
    schedule_df['Hour'] = schedule_df['Hour'].astype(str).str.zfill(2)
    logging.debug(f"Normalized Hour values in traffic and schedule data")
    
    try:
        # Merge data on Stop ID, Day, Hour
        merged = pd.merge(
            traffic_df,
            schedule_df,
            on=['Stop ID', 'Day', 'Hour'],
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
        # Only include 'Line no.' if it exists in merged, otherwise drop it from result
        result_cols = [col for col in ['Line no.', 'Variant', 'Variant ID', 'Stop ID', 'Day', 'Hour', 'No. of courses', 'allocated_trips'] if col in merged.columns]
        return merged[result_cols]
        
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

def count_passes_per_hour(xml_folder, line_no, variant=None):
    """Count how many times during each hour the line with the selected variant passes."""
    schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
    if schedule_df.empty:
        logging.warning(f"No schedule data found for line {line_no}")
        return pd.DataFrame()

    if variant:
        schedule_df = schedule_df[schedule_df['Variant'] == variant]
        if schedule_df.empty:
            logging.warning(f"No schedule data found for line {line_no} with variant {variant}")
            return pd.DataFrame()

    # Count passes per hour
    passes_per_hour = (
        schedule_df.groupby(['Day', 'Hour'], as_index=False)
        .size()
        .rename(columns={'size': 'passes'})
    )

    logging.info(f"Counted passes per hour for line {line_no}, variant {variant}")
    return passes_per_hour

def optimize_schedule_based_on_passes(xml_folder, line_no, variant=None, max_trips_per_hour=7):
    """Optimize a new schedule based on passes through stops and traffic data."""
    # Count passes per hour
    passes_df = count_passes_per_hour(xml_folder, line_no, variant)
    if passes_df.empty:
        logging.warning(f"No passes data found for line {line_no}, variant {variant}")
        return pd.DataFrame()

    # Get traffic data
    traffic_df = get_traffic_data_from_db()
    if traffic_df.empty:
        logging.warning("No traffic data available")
        return pd.DataFrame()

    # Merge passes data with traffic data
    merged_df = pd.merge(
        passes_df,
        traffic_df,
        on=['Day', 'Hour'],
        how='inner'
    )

    if merged_df.empty:
        logging.warning("No matching records between passes and traffic data")
        return pd.DataFrame()

    # Normalize traffic and propose trips
    merged_df['normalized_traffic'] = (merged_df['traffic_percent'] - merged_df['traffic_percent'].min()) / \
                                      (merged_df['traffic_percent'].max() - merged_df['traffic_percent'].min())
    merged_df['proposed_trips'] = (merged_df['normalized_traffic'] * max_trips_per_hour).round().astype(int)
    merged_df['proposed_trips'] = merged_df[['proposed_trips', 'passes']].min(axis=1)

    logging.info(f"Optimized schedule for line {line_no}, variant {variant}")
    return merged_df[['Day', 'Hour', 'proposed_trips']]

def optimize_without_merging(xml_folder, line_no, day_type, variant=None, max_trips_per_hour=7):
    """Optimize tram schedule without merging traffic and schedule data."""
    # Parse schedule data for the chosen line
    schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
    if schedule_df.empty:
        logging.warning(f"No schedule data found for line {line_no}")
        return pd.DataFrame()

    # Filter by variant if provided
    if variant:
        schedule_df = schedule_df[schedule_df['Variant'] == variant]
        if schedule_df.empty:
            logging.warning(f"No schedule data found for line {line_no} with variant {variant}")
            return pd.DataFrame()

    # Filter by day type
    day_type_map = {
        'workday': 'w dni robocze',
        'saturday': 'Sobota',
        'sunday': 'Niedziela'
    }
    day_type_mapped = day_type_map.get(day_type.lower(), day_type)
    schedule_df = schedule_df[schedule_df['Day'] == day_type_mapped]
    if schedule_df.empty:
        logging.warning(f"No schedule data found for line {line_no} on {day_type}")
        return pd.DataFrame()

    # Count tram passes per stop per hour
    passes_per_hour = (
        schedule_df.groupby(['Stop ID', 'Hour'], as_index=False)
        .size()
        .rename(columns={'size': 'passes'})
    )

    # Get traffic data
    traffic_df = get_traffic_data_from_db()
    if traffic_df.empty:
        logging.warning("No traffic data available")
        return pd.DataFrame()

    # Normalize traffic data
    traffic_df['normalized_traffic'] = (
        (traffic_df['traffic_percent'] - traffic_df['traffic_percent'].min()) /
        (traffic_df['traffic_percent'].max() - traffic_df['traffic_percent'].min() + 0.001)
    ).clip(0.1, 0.9)

    logging.info(f"Schedule DataFrame: {schedule_df.head()}")
    logging.info(f"Traffic DataFrame: {traffic_df.head()}")
    logging.info(f"Day Type Mapped: {day_type_mapped}")
    logging.info(f"Passes Per Hour DataFrame: {passes_per_hour.head()}")

    # Calculate optimal tram passes per stop per hour
    optimal_passes = []
    for stop_id in passes_per_hour['Stop ID'].unique():
        logging.info(f"Processing Stop ID: {stop_id}")
        stop_data = passes_per_hour[passes_per_hour['Stop ID'] == stop_id]
        traffic_data = traffic_df[traffic_df['Stop ID'] == stop_id]
        logging.info(f"Stop Data: {stop_data}")
        logging.info(f"Traffic Data: {traffic_data}")

        stop_matrix = []
        for hour in stop_data['Hour'].unique():
            schedule_passes = stop_data[stop_data['Hour'] == hour]['passes'].sum()
            traffic_intensity = traffic_data[traffic_data['Hour'] == hour]['normalized_traffic'].mean()

            logging.info(f"Hour: {hour}, Scheduled Passes: {schedule_passes}, Traffic Intensity: {traffic_intensity}")

            if pd.isna(traffic_intensity):
                traffic_intensity = 0.5  # Default to midpoint if no traffic data

            optimal_trips = min(max_trips_per_hour * traffic_intensity, schedule_passes)
            stop_matrix.append({
                'Stop ID': stop_id,
                'Hour': hour,
                'Scheduled Passes': schedule_passes,
                'Optimal Passes': round(optimal_trips)
            })

        optimal_passes.extend(stop_matrix)

    logging.info(f"Final Optimal Passes DataFrame: {pd.DataFrame(optimal_passes).head()}")
    logging.info(f"Optimized schedule without merging for line {line_no}, variant {variant}, day type {day_type}")
    return pd.DataFrame(optimal_passes)

def main():
    xml_folder = './xmls/'
    line_no = 4
    schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
    print(f'Schedule data from XML for line {line_no}:')
    print(schedule_df)

    traffic_df = get_traffic_data_from_db()
    print('Traffic data from DB:')
    print(traffic_df)

    result = allocate_trips_directly(schedule_df, traffic_df)
    print('Optimized allocation:')
    print(result)
    result.to_csv(f'optimized_schedule_line_{line_no}.csv', index=False)

    if not traffic_df.empty and not schedule_df.empty:
        stop_ids = schedule_df['Stop ID'].unique().tolist()
        relevant_traffic = traffic_df[traffic_df['Stop ID'].isin(stop_ids)]
        print('Relevant traffic data for stops in this line/variant:')
        print(relevant_traffic.head())
        result = allocate_trips(relevant_traffic, schedule_df)
        print('Optimized allocation:')
        print(result.head())
        result.to_csv(f'optimized_schedule_line_{line_no}_merged.csv', index=False)
    else:
        print('Traffic data from DB or schedule data is empty.')

def optimize_lines(_, lines, day_type=None, variant=None):
    xml_folder = './xmls/'
    results = []
    traffic_df = get_traffic_data_from_db()

    day_type_map = {
        'workday': 'w dni robocze',
        'saturday': 'Sobota',
        'sunday': 'Niedziela'
    }
    day_type_mapped = day_type_map.get(day_type.lower(), day_type) if day_type else None

    for line_no in lines:
        schedule_df = parse_xml_schedule_for_line(xml_folder, line_no)
        if schedule_df.empty:
            continue
        if variant:
            schedule_df = schedule_df[schedule_df['Variant'].str.lower() == variant.lower()]
        if day_type_mapped:
            schedule_df = schedule_df[schedule_df['Day'].str.lower() == day_type_mapped.lower()]
        if schedule_df.empty:
            continue

        stop_ids = schedule_df['Stop ID'].unique().tolist()
        relevant_traffic = traffic_df[traffic_df['Stop ID'].isin(stop_ids)]
        if relevant_traffic.empty:
            continue

        agg_traffic = (
            relevant_traffic.groupby(['Day', 'Hour'], as_index=False)
            .agg({'traffic_percent': 'mean'})
        )

        min_t, max_t = agg_traffic['traffic_percent'].min(), agg_traffic['traffic_percent'].max()
        if max_t - min_t < 0.001:
            agg_traffic['normalized_traffic'] = 0.5
        else:
            agg_traffic['normalized_traffic'] = (
                (agg_traffic['traffic_percent'] - min_t) / (max_t - min_t + 0.001)
            )
        agg_traffic['normalized_traffic'] = agg_traffic['normalized_traffic'].clip(0.1, 0.9)

        max_trips = 7
        agg_traffic['proposed_trips'] = (
            agg_traffic['normalized_traffic'] * max_trips
        ).round().astype(int).clip(lower=1)

        for _, row in agg_traffic.iterrows():
            results.append({
                'line': line_no,
                'variant': variant or '',
                'day': row['Day'],
                'hour': row['Hour'],
                'proposed_trips': int(row['proposed_trips'])
            })

    return results

if __name__ == '__main__':
    main()
