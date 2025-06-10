import os
import xml.etree.ElementTree as ET
import pandas as pd
import sqlite3
import json


def get_variants_for_line(line_no, xml_folder='./xmls/'):
    """
    Returns a DataFrame with all variant information including:
    - line_number
    - variant_id, variant_name
    - start_stop, end_stop (names)
    - start_stop_id, end_stop_id
    - stop_list (names in order as JSON)
    - stop_id_list (IDs in order as JSON)
    """
    line_no_str = str(line_no).zfill(4)
    xml_path = os.path.join(xml_folder, line_no_str, f"{line_no_str}.xml")

    if not os.path.exists(xml_path):
        return pd.DataFrame()

    tree = ET.parse(xml_path)
    root = tree.getroot()
    variants = []

    for wariant in root.findall(".//wariant"):
        variant_id = wariant.attrib.get("id")
        variant_name = wariant.attrib.get("nazwa")

        first_przystanek = wariant.find("przystanek")
        if first_przystanek is None:
            continue

        czasy = first_przystanek.find("czasy")
        if czasy is None:
            continue

        przystanki = czasy.findall("przystanek")
        if not przystanki:
            continue

        # Extract stop information
        stop_names = [p.attrib.get("nazwa") for p in przystanki]
        stop_ids = [p.attrib.get("id") for p in przystanki]

        variants.append({
            "line_number": line_no,
            "variant_id": variant_id,
            "variant_name": variant_name,
            "start_stop": stop_names[0],
            "end_stop": stop_names[-1],
            "start_stop_id": stop_ids[0],
            "end_stop_id": stop_ids[-1],
            "stop_list_json": json.dumps(stop_names),
            "stop_id_list_json": json.dumps(stop_ids)
        })

    return pd.DataFrame(variants)


def update_database(df, db_name='tram_data2.db'):
    """
    Updates the existing database with new data, handling conflicts on the composite key.
    """
    if df.empty:
        print("No data to update")
        return

    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Drop existing table if it exists
        cursor.execute("DROP TABLE IF EXISTS tram_lines")

        # Create new table with composite primary key
        cursor.execute("""
                CREATE TABLE tram_lines (
                    line_number INTEGER NOT NULL,
                    variant_id TEXT NOT NULL,
                    variant_name TEXT,
                    start_stop TEXT,
                    end_stop TEXT,
                    start_stop_id TEXT,
                    end_stop_id TEXT,
                    stop_list_json TEXT,
                    stop_id_list_json TEXT,
                    PRIMARY KEY (line_number, variant_id)
                )
                """)

        # Prepare the upsert (update or insert) query
        upsert_query = """
        INSERT OR REPLACE INTO tram_lines (
            line_number, variant_id, variant_name, 
            start_stop, end_stop, start_stop_id, end_stop_id,
            stop_list_json, stop_id_list_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert DataFrame to list of tuples for executemany
        data = [(
            row['line_number'], row['variant_id'], row['variant_name'],
            row['start_stop'], row['end_stop'], row['start_stop_id'], row['end_stop_id'],
            row['stop_list_json'], row['stop_id_list_json']
        ) for _, row in df.iterrows()]

        # Execute the upsert
        cursor.executemany(upsert_query, data)
        conn.commit()

        print(f"Successfully updated {len(df)} records in the database")

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()


def process_all_lines(xml_folder='./xmls/'):
    """Processes all available lines"""
    all_lines = []

    # Find all line directories (assuming they're 4-digit numbers)
    for dirname in os.listdir(xml_folder):
        if dirname.isdigit() and len(dirname) == 4:
            try:
                line_no = int(dirname)
                all_lines.append(line_no)
            except ValueError:
                continue

    if not all_lines:
        print("No valid line directories found")
        return pd.DataFrame()

    # Process each line
    all_variants = []
    for line_no in sorted(all_lines):
        print(f"Processing line {line_no}...")
        variants_df = get_variants_for_line(line_no, xml_folder)
        if not variants_df.empty:
            all_variants.append(variants_df)

    if all_variants:
        return pd.concat(all_variants, ignore_index=True)
    return pd.DataFrame()


def get_variant_names_for_line(line_no, db_path='tram_data2.db'):
    """
    Fetch variant names for a given line number from the tram_lines table.
    Returns a list of dictionaries with variant_id, variant_name, start_stop, end_stop.
    """
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT variant_id, variant_name, start_stop, end_stop
            FROM tram_lines
            WHERE line_number = ?
            ORDER BY variant_id
        """
        df = pd.read_sql_query(query, conn, params=(line_no,))
        conn.close()

        if df.empty:
            return []

        return df.to_dict(orient='records')

    except Exception as e:
        print(f"Error fetching variants for line {line_no}: {e}")
        return []


def get_variant_ids_for_line(line_no, db_path='tram_data2.db'):
    """
    Fetch variant IDs for a given line number from the tram_lines table.
    Returns a list of variant IDs.
    """
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT variant_id
            FROM tram_lines
            WHERE line_number = ?
            ORDER BY variant_id
        """
        df = pd.read_sql_query(query, conn, params=(line_no,))
        conn.close()

        if df.empty:
            return []

        return df['variant_id'].tolist()

    except Exception as e:
        print(f"Error fetching variant IDs for line {line_no}: {e}")
        return []


# Make get_variant_names_for_line importable from this module
__all__ = [
    'get_variants_for_line',
    'update_database',
    'process_all_lines',
    'get_variant_names_for_line',
    'get_variant_ids_for_line'
]


if __name__ == "__main__":
    # Process all lines
    combined_df = process_all_lines()

    if not combined_df.empty:
        # Update the existing database
        update_database(combined_df)

        # Print summary
        print("\nSummary:")
        print(f"Total lines processed: {combined_df['line_number'].nunique()}")
        print(f"Total variants processed: {len(combined_df)}")

        # Verify the update
        conn = sqlite3.connect('tram_data2.db')
        print("\nDatabase stats:")
        stats = pd.read_sql("""
            SELECT 
                COUNT(*) as total_variants,
                COUNT(DISTINCT line_number) as distinct_lines
            FROM tram_lines
        """, conn)
        print(stats.to_markdown())

        print("\nSample of updated data:")
        sample = pd.read_sql("SELECT * FROM tram_lines ORDER BY RANDOM() LIMIT 3", conn)
        print(sample.to_markdown())
        conn.close()
    else:
        print("No variant data found for any line.")