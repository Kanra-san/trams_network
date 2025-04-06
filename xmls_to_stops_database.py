import xml.etree.ElementTree as ET
import os
import sqlite3

def initialize_database(db_file='tram_data.db'):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stops (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS connections (
        line_number TEXT NOT NULL,
        from_stop TEXT NOT NULL,
        to_stop TEXT NOT NULL,
        weight INTEGER NOT NULL,
        active_status TEXT NOT NULL DEFAULT 'yes',
        PRIMARY KEY (line_number, from_stop, to_stop),
        FOREIGN KEY (from_stop) REFERENCES stops(stop_id),
        FOREIGN KEY (to_stop) REFERENCES stops(stop_id)
    )
    ''')

    conn.commit()
    conn.close()

def parse_tram_xml(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        connections = set()
        stops_info = set()

        linia = root.find('.//linia')
        line_number = linia.get('nazwa', '0')  # default to '0' if not found

        for wariant in root.findall('.//wariant'):
            stops = wariant.findall('.//przystanek[@numer]')
            line_connections = set()

            for i in range(len(stops) - 1):
                from_id = stops[i].get('id')
                from_name = stops[i].get('nazwa', 'Unknown')
                to_id = stops[i + 1].get('id')
                to_name = stops[i + 1].get('nazwa', 'Unknown')

                connection_key = (line_number, from_id, to_id)
                if connection_key not in line_connections:
                    try:
                        weight = max(0, int(stops[i + 1].get('czas', '0')) - int(stops[i].get('czas', '0')))
                    except (ValueError, TypeError):
                        weight = 0

                    connections.add((line_number, from_id, to_id, weight, 'yes'))  # Added 'yes' for active_status
                    stops_info.add((from_id, from_name))
                    stops_info.add((to_id, to_name))
                    line_connections.add(connection_key)

        return connections, stops_info
    except ET.ParseError as e:
        print(f"Error parsing {xml_file}: {e}")
        return set(), set()

def process_tram_lines(root_folder, db_file='tram_data.db'):
    all_connections = set()
    all_stops = set()

    initialize_database(db_file)

    for line_folder in os.listdir(root_folder):
        line_path = os.path.join(root_folder, line_folder)
        if os.path.isdir(line_path):
            for filename in os.listdir(line_path):
                if filename.endswith('.xml'):
                    file_path = os.path.join(line_path, filename)
                    connections, stops_info = parse_tram_xml(file_path)
                    all_connections.update(connections)
                    all_stops.update(stops_info)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        cursor.executemany('''
        INSERT OR IGNORE INTO stops (stop_id, stop_name)
        VALUES (?, ?)
        ''', all_stops)

        cursor.executemany('''
        INSERT OR IGNORE INTO connections 
        (line_number, from_stop, to_stop, weight, active_status)
        VALUES (?, ?, ?, ?, ?)
        ''', all_connections)

        conn.commit()
        print(f"\nDatabase created with:")
        print(f"- {len(all_stops)} stops")
        print(f"- {len(all_connections)} unique line connections")

        cursor.execute("SELECT DISTINCT line_number FROM connections")
        lines = [row[0] for row in cursor.fetchall()]
        print(f"- Lines found: {', '.join(sorted(lines))}")

    finally:
        conn.close()

if __name__ == "__main__":
    input_folder = 'xmls'
    db_file = 'tram_data_simple.db'

    if not os.path.exists(input_folder):
        print(f"Error: Folder '{input_folder}' not found")
    else:
        process_tram_lines(input_folder, db_file)
        print(f"\nSimplified database saved to: {db_file}")