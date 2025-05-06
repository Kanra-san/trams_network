import sqlite3
from typing import List, Tuple, Optional
import networkx as nx
from shortest_path_1 import TramNetwork
import datetime

class TramDatabaseOperations:
    def __init__(self, db_file='tram_data2.db'):
        self.db_file = db_file

    def _get_connection(self):
        return sqlite3.connect(self.db_file)

    # Stop Operations
    def add_stop(self, stop_id: str, stop_name: str, latitude: Optional[float] = None,
                 longitude: Optional[float] = None, active: bool = True):
        """Add a new stop to the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO stops (stop_id, stop_name, latitude, longitude, active_status)
                VALUES (?, ?, ?, ?, ?)
            ''', (stop_id, stop_name, latitude, longitude, 'yes' if active else 'no'))
            conn.commit()

    def delete_stop(self, stop_id: str):
        """Remove a stop from the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # First delete all connections involving this stop
            cursor.execute('DELETE FROM connections WHERE from_stop = ? OR to_stop = ?', (stop_id, stop_id))
            # Then delete the stop
            cursor.execute('DELETE FROM stops WHERE stop_id = ?', (stop_id,))
            conn.commit()

    # Connection Operations
    def add_connection(self, line_number: str, from_stop: str, to_stop: str, weight: int, active_status: str = 'yes'):
        """Add a new connection between stops"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO connections 
                (line_number, from_stop, to_stop, weight)
                VALUES (?, ?, ?, ?)
            ''', (line_number, from_stop, to_stop, weight))
            conn.commit()

    def delete_connection(self, from_stop: str, to_stop: str):
        """Remove a connection between stops"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM connections 
                WHERE (from_stop = ? AND to_stop = ?)
                OR (from_stop = ? AND to_stop = ?)
            ''', (from_stop, to_stop, to_stop, from_stop))
            conn.commit()

    def set_stop_active_status(self, stop_id: str, active: bool):
        """Activate or deactivate a stop"""
        status = 'yes' if active else 'no'
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Update the stop's active status
                cursor.execute('''
                    UPDATE stops 
                    SET active_status = ?
                    WHERE stop_id = ?
                ''', (status, stop_id))
                conn.commit()
                return True
            except sqlite3.Error as e:
                print(f"Database error when updating stop status: {e}")
                return False

    def find_shortest_path(self, start_stop: str, end_stop: str) -> Tuple[List[str], str]:
        """Find the shortest path between two active stops and return path with names"""
        with self._get_connection() as conn:
            # Create network instance
            network = TramNetwork(self.db_file)

            # Find path with names
            path, duration = network.find_shortest_path(start_stop, end_stop, return_names=True)
            return path, duration

    def is_stop_active(self, stop_id: str) -> bool:
        """Check if a stop is active"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT active_status FROM stops WHERE stop_id = ?", (stop_id,))
            result = cursor.fetchone()
            return result and result[0] == 'yes'

    def create_network_graph(self):
        cursor = self.conn.cursor()

        # Get all active stops with coordinates
        cursor.execute('''
            SELECT stop_id, latitude, longitude 
            FROM stops 
            WHERE active_status = 'yes'
        ''')
        coords = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        # Get all edges between active stops
        cursor.execute('''
            SELECT c.from_stop, c.to_stop, c.weight 
            FROM connections c
            JOIN stops s1 ON c.from_stop = s1.stop_id AND s1.active_status = 'yes'
            JOIN stops s2 ON c.to_stop = s2.stop_id AND s2.active_status = 'yes'
        ''')
        edges = cursor.fetchall()

        # Create and return graph
        G = nx.Graph()
        for stop, (lat, lon) in coords.items():
            G.add_node(stop, pos=(lat, lon))
        for from_stop, to_stop, weight in edges:
            G.add_edge(from_stop, to_stop, weight=weight)
        return G

