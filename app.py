from flask import Flask, jsonify, request, render_template
from db_handler import TramDatabase
from db_operations import TramDatabaseOperations
from shortest_path_1 import TramNetwork
from flask_cors import CORS
import sqlite3
from optimizer_from_db_and_xml import parse_xml_schedule_for_line, get_traffic_data_from_db, allocate_trips
import pandas as pd
import io
from flask import send_file
import logging
from variantdf import get_variants_for_line

db = TramDatabase()
db_ops = TramDatabaseOperations()
network = TramNetwork()

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

def standard_response(success, data=None, message=None, status_code=200):
    return jsonify({
        "success": success,
        "data": data,
        "message": message
    }), status_code

@app.route('/')
def index():
    """Serve the main HTML file"""
    return render_template('main.html')

# Stop Endpoints
@app.route('/api/stops', methods=['GET'])
def get_all_stops():
    try:
        stops_data = db.get_stops_with_names_and_ids()
        return standard_response(True, [{"id": id, "name": name} for id, name in stops_data])
    except Exception as e:
        return standard_response(False, message=str(e))


@app.route('/api/stops/<stop_id>', methods=['GET'])
def get_stop_details(stop_id):
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # Get basic stop info
            cursor.execute('''
                SELECT stop_id, stop_name, latitude, longitude, active_status
                FROM stops WHERE stop_id = ?
            ''', (stop_id,))
            stop_info = cursor.fetchone()

            if not stop_info:
                return standard_response(False, message="Stop not found", status_code=404)

            # Get lines serving this stop
            cursor.execute('''
                SELECT line_number FROM stop_line_relations
                WHERE stop_id = ?
            ''', (stop_id,))
            lines = [row[0] for row in cursor.fetchall()]

            # Get traffic data
            cursor.execute('''
                SELECT day_of_week, hour, congestion_percent
                FROM traffic_patterns
                WHERE stop_id = ?
                ORDER BY day_of_week, hour
            ''', (stop_id,))
            traffic_data = cursor.fetchall()

            return standard_response(True, {
                "info": {
                    "stop_id": stop_info[0],
                    "stop_name": stop_info[1],
                    "latitude": stop_info[2],
                    "longitude": stop_info[3],
                    "active_status": stop_info[4]
                },
                "lines": lines,
                "traffic": traffic_data
            })
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


@app.route('/api/stops/status', methods=['GET'])
def get_stops_by_status():
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # Get all stops with their line information
            cursor.execute('''
                SELECT s.stop_id, s.stop_name, s.active_status, 
                       GROUP_CONCAT(DISTINCT slr.line_number) as lines
                FROM stops s
                LEFT JOIN stop_line_relations slr ON s.stop_id = slr.stop_id
                GROUP BY s.stop_id
                ORDER BY s.stop_name
            ''')

            stops = []
            for row in cursor.fetchall():
                stop_id, stop_name, active_status, lines = row
                stops.append({
                    'id': stop_id,
                    'name': stop_name,
                    'active_status': active_status,
                    'lines': lines.split(',') if lines else []
                })

            return standard_response(True, {
                'active': [s for s in stops if s['active_status'] == 'yes'],
                'inactive': [s for s in stops if s['active_status'] == 'no']
            })
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)



@app.route('/api/stops', methods=['POST'])
def add_stop():
    try:
        data = request.get_json()
        if not all(key in data for key in ['id', 'name', 'lat', 'lng']):
            return standard_response(False, message="Missing required fields", status_code=400)

        db_ops.add_stop(
            stop_id=data['id'],
            stop_name=data['name'],
            latitude=data['lat'],
            longitude=data['lng']
        )
        return standard_response(True, message="Stop added successfully")
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


@app.route('/api/stops/<stop_id>', methods=['DELETE'])
def delete_stop(stop_id):
    try:
        db_ops.delete_stop(stop_id)
        return standard_response(True, message="Stop deleted successfully")
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


@app.route('/api/stops/<stop_id>/status', methods=['PUT'])
def set_stop_status(stop_id):
    try:
        data = request.get_json()
        if 'active' not in data:
            return standard_response(False, message="Missing 'active' field", status_code=400)

        db_ops.set_stop_active_status(stop_id, data['active'])
        return standard_response(True, message="Stop status updated")
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


# Connection Endpoints
@app.route('/api/connections', methods=['POST'])
def add_connection():
    try:
        data = request.get_json()
        if not all(key in data for key in ['from', 'to', 'weight']):
            return standard_response(False, message="Missing required fields", status_code=400)

        db_ops.add_connection(
            line_number=data.get('line', 'MANUAL'),
            from_stop=data['from'],
            to_stop=data['to'],
            weight=data['weight']
        )
        return standard_response(True, message="Connection added successfully")
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


@app.route('/api/connections', methods=['DELETE'])
def delete_connection():
    try:
        data = request.get_json()
        if not all(key in data for key in ['from', 'to']):
            return standard_response(False, message="Missing required fields", status_code=400)

        db_ops.delete_connection(data['from'], data['to'])
        return standard_response(True, message="Connection deleted successfully")
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)

@app.route('/api/connections', methods=['GET'])
def get_all_connections():
    try:
        connections = []
        for from_stop, to_stop, weight in db.get_all_edges():
            connections.append({
                "from": from_stop,
                "to": to_stop,
                "weight": weight,
                "active": db_ops.is_stop_active(from_stop) and db_ops.is_stop_active(to_stop)
            })
        return standard_response(True, connections)
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)

# Route Endpoints
@app.route('/api/routes/shortest', methods=['POST'])
def find_shortest_path():
    try:
        data = request.get_json()
        if not all(key in data for key in ['start', 'end']):
            return standard_response(False, message="Missing start or end stop", status_code=400)

        path, duration = db_ops.find_shortest_path(data['start'], data['end'])
        if not path:
            return standard_response(False, data={"path": [], "duration": ""}, message="No path found", status_code=404)

        return standard_response(True, {
            "path": path,
            "duration": duration
        })
    except Exception as e:
        return standard_response(False, data={"path": [], "duration": ""}, message=str(e), status_code=500)


# Network Graph Endpoint
@app.route('/api/network/graph', methods=['GET'])
def get_network_graph():
    try:
        G = db.create_network_graph()

        nodes = []
        for node, data in G.nodes(data=True):
            pos = data.get('pos')
            nodes.append({
                "id": node,
                "label": data.get('name', node),
                "active": data.get('active', False),
                "x": pos[0] if pos else None,  # longitude
                "y": pos[1] if pos else None,  # latitude
                "physics": pos is None  # Only enable physics for nodes without coordinates
            })

        edges = []
        for u, v, data in G.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "weight": data.get('weight', 1),
                "label": str(data.get('weight', ''))
            })

        return standard_response(True, {
            "nodes": nodes,
            "edges": edges,
            "options": {
                "physics": {
                    "enabled": True,
                    "stabilization": {
                        "enabled": True,
                        "iterations": 1000
                    }
                },
                "nodes": {
                    "fixed": {
                        "x": True,
                        "y": True
                    }
                }
            }
        })
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


# Statistics Endpoint
@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # Total stops
            cursor.execute("SELECT COUNT(*) FROM stops")
            total_stops = cursor.fetchone()[0]

            # Active stops
            cursor.execute("SELECT COUNT(*) FROM stops WHERE active_status = 'yes'")
            active_stops = cursor.fetchone()[0]

            # Total routes (distinct line numbers)
            cursor.execute("SELECT COUNT(DISTINCT line_number) FROM connections")
            total_routes_result = cursor.fetchone()
            total_routes = total_routes_result[0] if total_routes_result else 0

            return standard_response(True, {
                'total_stops': total_stops,
                'active_stops': active_stops,
                'total_routes': total_routes,
                'recent_activity': []
            })
    except Exception as e:
        app.logger.error(f"Error in stats endpoint: {str(e)}")
        return standard_response(False, message=str(e), status_code=500)

@app.route('/api/optimize', methods=['POST'])
def optimize_schedule():
    try:
        data = request.get_json()
        lines = data.get('lines', '').strip()
        day_type = data.get('day_type', '').strip()
        variant = data.get('variant', '').strip()
        
        # Parse inputs
        line_numbers = [ln.strip() for ln in lines.split(',')] if lines else []
        
        # Get all lines if none specified
        if not line_numbers:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT line_number FROM connections")
                line_numbers = [str(row[0]) for row in cursor.fetchall()]
        
        results = []
        for line_no in line_numbers:
            try:
                logging.info(f"Processing line {line_no}")
                
                # Get schedule and traffic data
                schedule_df = parse_xml_schedule_for_line('./xmls/', line_no)
                if schedule_df.empty:
                    logging.warning(f"Schedule data is empty for line {line_no}")
                    continue
                logging.debug(f"Schedule data for line {line_no}:\n{schedule_df.head()}")
                
                traffic_df = get_traffic_data_from_db()
                if traffic_df.empty:
                    logging.warning("Traffic data is empty")
                    continue
                logging.debug(f"Traffic data:\n{traffic_df.head()}")
                
                # Filter traffic data
                traffic_df = traffic_df[traffic_df['Line no.'] == line_no]
                if traffic_df.empty:
                    logging.warning(f"Filtered traffic data is empty for line {line_no}")
                    continue
                logging.debug(f"Filtered traffic data for line {line_no}:\n{traffic_df.head()}")
                
                # Filter schedule by day_type and variant if provided
                if day_type:
                    schedule_df = schedule_df[schedule_df['Day'].str.lower() == day_type.lower()]
                if variant:
                    schedule_df = schedule_df[schedule_df['Variant'] == variant]
                
                # Allocate trips
                allocation = allocate_trips(traffic_df, schedule_df)
                if allocation.empty:
                    logging.warning(f"Allocation results are empty for line {line_no}")
                    continue
                logging.debug(f"Allocation results for line {line_no}:\n{allocation.head()}")
                
                # Format results
                for _, row in allocation.iterrows():
                    results.append({
                        'line': row['Line no.'],
                        'day': row.get('Day', ''),
                        'variant': row.get('Variant', ''),
                        'current_trips': int(row['No. of courses']),
                        'optimized_trips': int(row['allocated_trips'])
                    })
                    
            except Exception as e:
                logging.error(f"Error processing line {line_no}: {str(e)}")
                continue
                
        if not results:
            return standard_response(False, message="No optimization results found.", status_code=404)
            
        return standard_response(True, sorted(results, key=lambda x: (x['line'], x['day'], x['variant'])))
        
    except Exception as e:
        logging.error(f"Optimization error: {str(e)}")
        return standard_response(False, message=f"Optimization failed: {str(e)}", status_code=500)
    
    

@app.route('/api/optimize/download', methods=['POST'])
def download_optimized_schedule():
    try:
        data = request.get_json()
        lines = data.get('lines', '')
        day_type = data.get('day_type', '').strip()
        variant = data.get('variant', '').strip()
        if lines:
            line_numbers = [l.strip() for l in lines.split(',') if l.strip()]
        else:
            line_numbers = []
        from optimizer_from_db_and_xml import optimize_lines
        results = optimize_lines(None, line_numbers, day_type=day_type, variant=variant)
        if not results:
            return standard_response(False, message="No data to export", status_code=404)
        import pandas as pd
        df = pd.DataFrame(results)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        filename = f"optimized_schedule_{'_'.join(line_numbers) if line_numbers else 'all'}.csv"
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


@app.route('/api/variants/<line_no>', methods=['GET'])
def get_variants(line_no):
    try:
        clean_line_no = int(line_no)
        variants = get_variants_for_line(clean_line_no)

        essential_fields = ['variant_id', 'variant_name', 'start_stop', 'end_stop']
        cleaned_df = variants[essential_fields].dropna(subset=['variant_name'])

        cleaned = cleaned_df.to_dict(orient='records')
        return standard_response(True, cleaned)

    except Exception as e:
        app.logger.error(f"Variant fetch error for line {line_no}: {e}")
        return standard_response(False, message=str(e), status_code=500)

if __name__ == '__main__':
    app.run(debug=True)