import requests
import sqlite3
from datetime import datetime
import time


class GooglePlacesTraffic:
    def __init__(self, api_key, db_file='tram_data.db'):
        self.api_key = api_key
        self.db_file = db_file
        self.base_url = "https://maps.googleapis.com/maps/api/place/details/json"

    def get_popular_times(self, place_id):
        params = {
            "place_id": place_id,
            "fields": "utc_offset,current_opening_hours,popular_times",
            "key": self.api_key
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()

            if data.get('status') == 'OK':
                return self._parse_response(data)
            else:
                print(f"API Error: {data.get('error_message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"Request failed: {str(e)}")
            return None

    def _parse_response(self, api_data):
        """Structure data to match your database schema"""
        popular_times = []
        days_map = ["Monday", "Tuesday", "Wednesday",
                    "Thursday", "Friday", "Saturday", "Sunday"]

        if 'popular_times' in api_data.get('result', {}):
            for day_idx, day_data in enumerate(api_data['result']['popular_times']):
                day_name = days_map[day_idx]
                hours = []

                for hour_idx, busy_percent in enumerate(day_data['data']):
                    hours.append({
                        "hour": f"{hour_idx:02d}:00",
                        "congestion_percent": busy_percent
                    })

                popular_times.append({
                    "day_of_week": day_name,
                    "hours": hours
                })

        return popular_times

    def save_to_database(self, place_id, stop_id, data):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM traffic_patterns WHERE stop_id = ?", (stop_id,))

            for day in data:
                for hour in day["hours"]:
                    cursor.execute('''
                        INSERT INTO traffic_patterns 
                        (stop_id, day_of_week, hour, congestion_percent)
                        VALUES (?, ?, ?, ?)
                    ''', (stop_id, day["day_of_week"], hour["hour"], hour["congestion_percent"]))

            conn.commit()
            print(f"Saved data for {place_id}")
        except Exception as e:
            print(f"Database error: {e}")
        finally:
            conn.close()

    def process_all_stops(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get stops with their Google Place IDs (you'll need to store these)
        cursor.execute('''
            SELECT stop_id, place_id FROM stops 
            WHERE place_id IS NOT NULL
        ''')

        for stop_id, place_id in cursor.fetchall():
            print(f"Processing {place_id}...")
            data = self.get_popular_times(place_id)
            if data:
                self.save_to_database(place_id, stop_id, data)
            time.sleep(0.5)  # Respect API rate limits


if __name__ == "__main__":
    API_KEY = "AIzaSyByExLQ6lmyx5ViVC-chYiv3IPalIWM3Ho"
    scraper = GooglePlacesTraffic(API_KEY)
    scraper.process_all_stops()