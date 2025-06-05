import os
import xml.etree.ElementTree as ET
import pandas as pd
import sqlite3
from datetime import datetime, timedelta


class TramScheduleOptimizer:
    def __init__(self, xml_folder='./xmls/', db_path='tram_data2.db'):
        self.xml_folder = xml_folder
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def __del__(self):
        self.conn.close()

    def get_variant_info(self, line_no):
        """Get all variants for a line (similar to variantdf.py)"""
        line_no_str = str(line_no).zfill(4)
        xml_path = os.path.join(self.xml_folder, line_no_str, f"{line_no_str}.xml")

        if not os.path.exists(xml_path):
            return []

        tree = ET.parse(xml_path)
        root = tree.getroot()
        variants = []

        for wariant in root.findall(".//wariant"):
            variant_id = wariant.attrib.get("id")
            variant_name = wariant.attrib.get("nazwa")
            variants.append({
                "variant_id": variant_id,
                "variant_name": variant_name
            })

        return variants

    def get_schedule_data(self, line_no, variant_id, day_type):
        """Get schedule data for specific variant and day type (similar to scheduledf.py)"""
        line_no_str = str(line_no).zfill(4)
        xml_path = os.path.join(self.xml_folder, line_no_str, f"{line_no_str}.xml")

        if not os.path.exists(xml_path):
            return pd.DataFrame()

        tree = ET.parse(xml_path)
        root = tree.getroot()
        schedule_data = []

        # Find the specific variant
        wariant = root.find(f".//wariant[@id='{variant_id}']")
        if wariant is None:
            return pd.DataFrame()

        # Get all stops for this variant
        for przystanek in wariant.findall("przystanek"):
            stop_id = przystanek.attrib.get("id")
            stop_name = przystanek.attrib.get("nazwa")

            # Get all schedule boards
            for tabliczka in przystanek.findall("tabliczka"):
                # Get schedules for the specified day type
                dzien = tabliczka.find(f"dzien[@nazwa='{day_type}']")
                if dzien is None:
                    continue

                # Process all hours
                for godz in dzien.findall("godz"):
                    hour = int(godz.attrib.get("h"))

                    # Process all minutes
                    for min_el in godz.findall("min"):
                        minute = int(min_el.attrib.get("m"))

                        schedule_data.append({
                            "variant_id": variant_id,
                            "stop_id": stop_id,
                            "stop_name": stop_name,
                            "hour": hour,
                            "minute": minute
                        })

        return pd.DataFrame(schedule_data)

    def get_traffic_for_stop(self, stop_name, day_type):
        """
        Get traffic data for a specific stop and day type from database
        Returns dictionary of {hour: congestion_percent}
        """
        # First find all possible stop_ids for this stop_name
        query = """
        SELECT stop_id FROM stops 
        WHERE UPPER(stop_name) = UPPER(?)
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (stop_name,))
        stop_ids = [row[0] for row in cursor.fetchall()]

        if not stop_ids:
            return {}

        # Now get traffic patterns for these stop_ids
        query = """
        SELECT hour, AVG(congestion_percent) 
        FROM traffic_patterns 
        WHERE stop_id IN ({}) AND day_of_week = ?
        GROUP BY hour
        """.format(','.join(['?'] * len(stop_ids)))

        cursor.execute(query, stop_ids + [day_type])
        return {hour: percent for hour, percent in cursor.fetchall()}

    def optimize_schedule(self, line_no, variant_id, day_type, max_adjustment_min=5):
        """
        Optimize schedule based on traffic congestion:
        1. Get current schedule from XML
        2. Analyze traffic patterns from database
        3. Adjust departure times to avoid peak congestion
        """
        # Get current schedule
        current_schedule = self.get_schedule_data(line_no, variant_id, day_type)
        if current_schedule.empty:
            return None, "No schedule found for this line, variant, and day type"

        # Create optimized schedule dataframe
        optimized = current_schedule.copy()
        optimized['original_time'] = optimized['hour'].astype(str) + ':' + optimized['minute'].astype(str).str.zfill(2)
        optimized['optimized_time'] = ''
        optimized['adjustment_min'] = 0
        optimized['congestion'] = None

        # Get unique stops to pre-load traffic data
        unique_stops = optimized['stop_name'].unique()
        stop_traffic = {stop: self.get_traffic_for_stop(stop, day_type) for stop in unique_stops}

        # Adjust each departure time
        for idx, row in current_schedule.iterrows():
            stop_name = row['stop_name']
            hour = row['hour']
            minute = row['minute']

            # Get congestion for this stop at this hour (default to 0 if no data)
            congestion = stop_traffic.get(stop_name, {}).get(hour, 0)
            optimized.at[idx, 'congestion'] = congestion

            # Calculate adjustment based on congestion (0-100%)
            adjustment = int((congestion / 100) * max_adjustment_min)

            # Alternate direction of adjustment to spread out departures
            if hour % 2 == 0:  # Even hours adjust forward
                new_minute = minute + adjustment
            else:  # Odd hours adjust backward
                new_minute = minute - adjustment

            # Handle minute overflow/underflow
            new_hour = hour
            if new_minute < 0:
                new_minute += 60
                new_hour -= 1
            elif new_minute >= 60:
                new_minute -= 60
                new_hour += 1

            # Update optimized schedule
            optimized.at[idx, 'hour'] = new_hour
            optimized.at[idx, 'minute'] = new_minute
            optimized.at[idx, 'optimized_time'] = f"{new_hour}:{str(new_minute).zfill(2)}"
            optimized.at[idx, 'adjustment_min'] = (new_hour * 60 + new_minute) - (hour * 60 + minute)

        # Sort by new times
        optimized = optimized.sort_values(['hour', 'minute'])

        return optimized, None


# Example usage
if __name__ == "__main__":
    # Initialize with paths
    optimizer = TramScheduleOptimizer(
        xml_folder='./xmls/',
        db_path='../../../tram_data2.db'
    )

    # Example parameters from your image
    line_no = 4
    day_type = "Workday"
    variant_name = "OPORÓW - BISKUPIN (OPORÓW → BISKUPIN)"

    # First get variant ID from name
    variants = optimizer.get_variant_info(line_no)
    variant_id = None
    for var in variants:
        if var['variant_name'] == variant_name:
            variant_id = var['variant_id']
            break

    if not variant_id:
        print("Error: Variant not found")
    else:
        # Optimize schedule
        optimized_schedule, error = optimizer.optimize_schedule(
            line_no=line_no,
            variant_id=variant_id,
            day_type=day_type,
            max_adjustment_min=5
        )

        if error:
            print(f"Error: {error}")
        else:
            print("Optimized Schedule:")
            print(optimized_schedule[['stop_name', 'original_time', 'optimized_time', 'adjustment_min', 'congestion']])

            # Calculate summary statistics
            total_adjustments = optimized_schedule['adjustment_min'].abs().sum()
            avg_adjustment = optimized_schedule['adjustment_min'].mean()
            max_adjustment = optimized_schedule['adjustment_min'].abs().max()

            print(f"\nOptimization Summary:")
            print(f"Total minutes adjusted: {total_adjustments}")
            print(f"Average adjustment: {avg_adjustment:.1f} minutes")
            print(f"Maximum single adjustment: {max_adjustment} minutes")
            print(f"Average congestion: {optimized_schedule['congestion'].mean():.1f}%")