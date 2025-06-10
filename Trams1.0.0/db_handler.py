import sqlite3
from typing import Dict, List, Tuple, Optional, Set
import networkx as nx


class TramDatabase:
    def __init__(self, db_file='tram_data2.db'):
        self.db_file = db_file

    def _get_connection(self):
        """Get a new thread-safe database connection"""
        return sqlite3.connect(self.db_file, check_same_thread=False)

    # Stop-related methods
    def get_stops_with_names_and_ids(self) -> List[Tuple[str, str]]:
        """Get list of all stops with (stop_id, stop_name)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stop_id, stop_name FROM stops ORDER BY stop_name')
            return cursor.fetchall()

    def get_stops_with_coordinates(self) -> List[Tuple[str, float, float]]:
        """Get list of stops with (stop_id, latitude, longitude)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stop_id, latitude, longitude FROM stops')
            return cursor.fetchall()

    def get_active_stops(self) -> List[str]:
        """Get list of active stop IDs"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stop_id FROM stops WHERE active_status = 'yes'")
            return [row[0] for row in cursor.fetchall()]

    def get_stop_info(self, stop_id: str) -> Optional[Dict]:
        """Get comprehensive information about a stop"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT stop_id, stop_name, latitude, longitude, active_status
                FROM stops WHERE stop_id = ?
            ''', (stop_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'id': row[0],
                'name': row[1],
                'lat': row[2],
                'lng': row[3],
                'active': row[4] == 'yes'
            }

    # Line-related methods
    def get_all_tram_routes(self) -> Dict[str, List[str]]:
        """Get all tram routes with their variants"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT line_number, route_description FROM tram_lines')
            return {row[0]: row[1].split(' | ') for row in cursor.fetchall()}

    def get_line_variants(self, line_number: str) -> List[List[str]]:
        """Get variants for a specific line"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT c.from_stop, c.to_stop, s1.stop_name, s2.stop_name
                FROM connections c
                JOIN stops s1 ON c.from_stop = s1.stop_id
                JOIN stops s2 ON c.to_stop = s2.stop_id
                WHERE c.line_number = ?
                ORDER BY c.connection_id
            ''', (line_number,))

            variants = []
            routes = cursor.fetchall()
            if routes:
                variant = [routes[0][2]]  # Start with first stop name
                for route in routes:
                    variant.append(route[3])  # Add the 'to' stop name
                variants.append(variant)
            return variants

    # Connection-related methods
    def get_all_edges(self) -> List[Tuple[str, str, int]]:
        """Get all connections (from_stop, to_stop, weight)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT from_stop, to_stop, weight FROM connections')
            return cursor.fetchall()

    def get_active_edges(self) -> List[Tuple[str, str, int]]:
        """Get connections between active stops only"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.from_stop, c.to_stop, c.weight 
                FROM connections c
                JOIN stops s1 ON c.from_stop = s1.stop_id AND s1.active_status = 'yes'
                JOIN stops s2 ON c.to_stop = s2.stop_id AND s2.active_status = 'yes'
            ''')
            return cursor.fetchall()

    def get_connections_for_stop(self, stop_id: str) -> List[Dict]:
        """Get all connections for a specific stop"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    c.from_stop, c.to_stop, c.weight, 
                    s1.stop_name as from_name, s2.stop_name as to_name
                FROM connections c
                JOIN stops s1 ON c.from_stop = s1.stop_id
                JOIN stops s2 ON c.to_stop = s2.stop_id
                WHERE c.from_stop = ? OR c.to_stop = ?
            ''', (stop_id, stop_id))

            return [{
                'from': row[0],
                'to': row[1],
                'weight': row[2],
                'from_name': row[3],
                'to_name': row[4]
            } for row in cursor.fetchall()]

    # Stop-Line relationship methods
    def get_stop_to_lines_mapping(self) -> Dict[str, List[str]]:
        """Get mapping of stop_id to list of line_numbers"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT stop_id, line_number FROM stop_line_relations')

            mapping = {}
            for stop_id, line_number in cursor.fetchall():
                if stop_id not in mapping:
                    mapping[stop_id] = []
                mapping[stop_id].append(line_number)
            return mapping

    def get_lines_for_stop(self, stop_id: str) -> List[str]:
        """Get all lines that serve a specific stop"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT line_number FROM stop_line_relations 
                WHERE stop_id = ?
            ''', (stop_id,))
            return [row[0] for row in cursor.fetchall()]

    # Traffic data methods
    def get_traffic_data_for_stop(self, stop_id: str) -> List[Tuple[str, str, float]]:
        """Get traffic patterns for a specific stop"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT day_of_week, hour, congestion_percent 
                FROM traffic_patterns 
                WHERE stop_id = ?
                ORDER BY day_of_week, hour
            ''', (stop_id,))
            return cursor.fetchall()

    # Network graph creation
    def create_network_graph(self) -> nx.Graph:
        """Create a NetworkX graph with proper coordinate handling"""
        G = nx.Graph()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Add nodes with all attributes including coordinates
            cursor.execute('''
                SELECT stop_id, stop_name, latitude, longitude, active_status 
                FROM stops
            ''')

            for stop_id, stop_name, lat, lon, active_status in cursor.fetchall():
                G.add_node(
                    stop_id,
                    name=stop_name,
                    active=active_status == 'yes',
                    pos=(float(lon), float(lat)) if lat and lon else None,  # Note: (lon, lat) for PyVis
                    color='#2ecc71' if active_status == 'yes' else '#e74c3c'
                )

            # Add edges between active stops
            cursor.execute('''
                SELECT c.from_stop, c.to_stop, c.weight 
                FROM connections c
                JOIN stops s1 ON c.from_stop = s1.stop_id AND s1.active_status = 'yes'
                JOIN stops s2 ON c.to_stop = s2.stop_id AND s2.active_status = 'yes'
            ''')

            for from_stop, to_stop, weight in cursor.fetchall():
                if from_stop in G and to_stop in G:
                    G.add_edge(
                        from_stop,
                        to_stop,
                        weight=weight,
                        active=True
                    )

        return G

    def close(self):
        """Close any persistent connections (not needed with context managers)"""
        pass