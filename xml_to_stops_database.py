import xml.etree.ElementTree as ET
import os
import sqlite3
from typing import Set, Tuple, List, Dict, Optional
import csv


def initialize_database(db_file: str = 'tram_data2.db') -> None:
    """Initialize database with complete schema including coordinates and traffic data"""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # drop existing tables if they exist (for fresh start)
    cursor.executescript('''
    DROP TABLE IF EXISTS traffic_patterns;
    DROP TABLE IF EXISTS stop_line_relations;
    DROP TABLE IF EXISTS connections;
    DROP TABLE IF EXISTS stops;
    DROP TABLE IF EXISTS tram_lines;
    ''')

    # create tables
    cursor.executescript('''
    CREATE TABLE stops (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        active_status TEXT NOT NULL DEFAULT 'yes' CHECK(active_status IN ('yes', 'no'))
    );

    CREATE TABLE tram_lines (
        line_number TEXT PRIMARY KEY,
        route_description TEXT
    );

    CREATE TABLE connections (
        connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        line_number TEXT NOT NULL,
        from_stop TEXT NOT NULL,
        to_stop TEXT NOT NULL,
        weight INTEGER NOT NULL,
        FOREIGN KEY (line_number) REFERENCES tram_lines(line_number),
        FOREIGN KEY (from_stop) REFERENCES stops(stop_id),
        FOREIGN KEY (to_stop) REFERENCES stops(stop_id),
        UNIQUE (line_number, from_stop, to_stop)
    );

    CREATE TABLE stop_line_relations (
        stop_id TEXT NOT NULL,
        line_number TEXT NOT NULL,
        PRIMARY KEY (stop_id, line_number),
        FOREIGN KEY (stop_id) REFERENCES stops(stop_id),
        FOREIGN KEY (line_number) REFERENCES tram_lines(line_number)
    );

    CREATE TABLE traffic_patterns (
        pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stop_id TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        hour TEXT NOT NULL,
        congestion_percent REAL NOT NULL,
        FOREIGN KEY (stop_id) REFERENCES stops(stop_id),
        UNIQUE (stop_id, day_of_week, hour)
    );
    ''')

    conn.commit()
    conn.close()


def get_ordered_stops_from_variant(variant: ET.Element) -> List[Tuple[str, str, int]]:
    """Extract stops with their times"""
    czasy = variant.find('.//czasy')
    stops = []
    if czasy is not None:
        for przystanek in czasy.findall('przystanek'):
            stop_id = przystanek.get('id')
            stop_name = przystanek.get('nazwa')
            czas = int(przystanek.get('czas', '0'))
            if stop_id and stop_name:
                stops.append((stop_id, stop_name, czas))
    return stops


def parse_tram_xml(xml_file: str) -> Tuple[Set[Tuple], Set[Tuple], Dict[str, List[Tuple[str, List[str]]]]]:
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        connections = set()
        stops_info = set()
        line_variants = {}

        linia = root.find('.//linia')
        line_number = linia.get('nazwa', '0')

        # Process each variant
        variants = root.findall('.//wariant')
        variant_data = []

        for variant in variants:
            variant_name = variant.get('nazwa', 'Variant')
            stops = get_ordered_stops_from_variant(variant)
            variant_data.append((variant_name, [stop[0] for stop in stops]))

            # Collect stops and connections
            for stop_id, stop_name, _ in stops:
                stops_info.add((stop_id, stop_name))

            # Create connections with proper weights based on time differences
            for i in range(len(stops) - 1):
                from_stop, _, from_time = stops[i]
                to_stop, _, to_time = stops[i + 1]
                weight = max(1, to_time - from_time)  # min weight = 1
                connections.add((line_number, from_stop, to_stop, weight))

        line_variants[line_number] = variant_data
        return connections, stops_info, line_variants
    except ET.ParseError as e:
        print(f"Error parsing {xml_file}: {e}")
        return set(), set(), {}


def load_coordinates_from_csv(csv_file: str) -> Dict[str, Tuple[float, float]]:
    """Load coordinates matching stop_code (col2) to stop_id (db)"""
    coordinates = {}
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 5:
                    stop_code = row[1].strip()  # Second column is stop_code
                    try:
                        lat = float(row[3])
                        lon = float(row[4])
                        coordinates[stop_code] = (lat, lon)
                    except (ValueError, IndexError):
                        continue
        print(f"Loaded coordinates for {len(coordinates)} stops")  # Debug
    except FileNotFoundError:
        print(f"Error: Coordinates file {csv_file} not found")
    return coordinates


def populate_database(conn: sqlite3.Connection,
                      all_connections: Set[Tuple],
                      all_stops: Set[Tuple],
                      line_variants: Dict[str, List[Tuple[str, List[str]]]],
                      coordinates: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
    """Populate database with extracted data"""
    cursor = conn.cursor()

    # Insert stops with coordinates if available
    if coordinates:
        stops_with_coords = []
        for stop_id, stop_name in all_stops:
            lat, lon = coordinates.get(stop_id, (None, None))
            stops_with_coords.append((stop_id, stop_name, lat, lon))

        cursor.executemany('''
        INSERT OR IGNORE INTO stops (stop_id, stop_name, latitude, longitude, active_status)
        VALUES (?, ?, ?, ?, 'yes')
        ''', stops_with_coords)
    else:
        # Insert stops without coordinates
        cursor.executemany('''
        INSERT OR IGNORE INTO stops (stop_id, stop_name, active_status)
        VALUES (?, ?, 'yes')
        ''', all_stops)

    # Insert tram lines with variant information in route_description
    for line_number, variants in line_variants.items():
        # Format variants for display in route_description
        variant_descriptions = []
        for variant_name, stop_sequence in variants:
            variant_desc = f"{variant_name}: {' → '.join(stop_sequence)}"
            variant_descriptions.append(variant_desc)

        route_description = " | ".join(variant_descriptions)

        cursor.execute('''
        INSERT OR IGNORE INTO tram_lines (line_number, route_description)
        VALUES (?, ?)
        ''', (line_number, route_description))

    # Insert connections
    cursor.executemany('''
    INSERT OR IGNORE INTO connections 
    (line_number, from_stop, to_stop, weight)
    VALUES (?, ?, ?, ?)
    ''', all_connections)

    # Create stop-line relationships
    stop_line_relations = set()
    for line_number, variants in line_variants.items():
        for _, stop_sequence in variants:
            for stop_id in stop_sequence:
                stop_line_relations.add((stop_id, line_number))

    cursor.executemany('''
    INSERT OR IGNORE INTO stop_line_relations (stop_id, line_number)
    VALUES (?, ?)
    ''', stop_line_relations)

    # Commit changes
    conn.commit()


def process_tram_lines(root_folder: str, coordinates_file: str, db_file: str = 'tram_data2.db') -> None:
    """Process all XML files in directory and populate database"""
    all_connections = set()
    all_stops = set()
    all_line_variants = {}

    # Initialize fresh database
    initialize_database(db_file)
    conn = sqlite3.connect(db_file)

    # Load coordinates if file exists
    coordinates = load_coordinates_from_csv(coordinates_file) if coordinates_file else None

    try:
        # Process each line folder
        for line_folder in os.listdir(root_folder):
            line_path = os.path.join(root_folder, line_folder)
            if os.path.isdir(line_path):
                for filename in os.listdir(line_path):
                    if filename.endswith('.xml'):
                        file_path = os.path.join(line_path, filename)
                        connections, stops_info, line_variants = parse_tram_xml(file_path)
                        all_connections.update(connections)
                        all_stops.update(stops_info)

                        # Merge line variants
                        for line_num, variants in line_variants.items():
                            if line_num in all_line_variants:
                                all_line_variants[line_num].extend(variants)
                            else:
                                all_line_variants[line_num] = variants

        # Populate database
        populate_database(conn, all_connections, all_stops, all_line_variants, coordinates)

        # Print summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stops")
        print(f"\nDatabase created with {cursor.fetchone()[0]} stops")

        cursor.execute("SELECT COUNT(*) FROM stops WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        print(f"- {cursor.fetchone()[0]} stops with coordinates")

        cursor.execute("SELECT COUNT(*) FROM connections")
        print(f"- {cursor.fetchone()[0]} connections")

        cursor.execute("SELECT DISTINCT line_number FROM connections")
        lines = [row[0] for row in cursor.fetchall()]
        print(f"- Lines found: {', '.join(sorted(lines))}")

        # Print variant count per line
        cursor.execute("SELECT line_number, route_description FROM tram_lines")
        for line_number, route_description in cursor.fetchall():
            variant_count = route_description.count('|') + 1
            print(f"- Line {line_number} has {variant_count} variants")

    finally:
        conn.close()


if __name__ == "__main__":
    input_folder = 'xmls'
    coordinates_file = 'stops.txt'  # Coordinates file
    db_file = 'tram_data2.db'  # Database file

    if not os.path.exists(input_folder):
        print(f"Error: Folder '{input_folder}' not found")
    else:
        process_tram_lines(input_folder, coordinates_file, db_file)
        print(f"\nComplete tram network database saved to: {db_file}")