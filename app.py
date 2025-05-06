from flask import Flask, jsonify, request, render_template
from db_handler import TramDatabase
from db_operations import TramDatabaseOperations
from shortest_path_1 import TramNetwork
from flask_cors import CORS
import sqlite3

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


app.route('/api/stops/<stop_id>', methods=['GET'])
def get_stop_details(stop_id):
    try:
        stop_info = db.get_stop_info(stop_id)
        if not stop_info:
            return standard_response(False, message="Stop not found", status_code=404)

        return standard_response(True, {
            "info": stop_info,
            "lines": db.get_lines_for_stop(stop_id),
            "connections": db.get_connections_for_stop(stop_id),
            "traffic": db.get_traffic_data_for_stop(stop_id)
        })
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)

@app.route('/api/stops/status', methods=['GET'])
def get_stops_by_status():
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # Active stops
            cursor.execute('''
                SELECT stop_id, stop_name 
                FROM stops 
                WHERE active_status = 'yes'
                ORDER BY stop_name
            ''')
            active_stops = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]

            # Inactive stops
            cursor.execute('''
                SELECT stop_id, stop_name 
                FROM stops 
                WHERE active_status = 'no'
                ORDER BY stop_name
            ''')
            inactive_stops = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]

            return standard_response(True, {
                'active': active_stops,
                'inactive': inactive_stops
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
            return standard_response(False, message="No path found", status_code=404)

        return standard_response(True, {
            "path": path,
            "duration": duration
        })
    except Exception as e:
        return standard_response(False, message=str(e), status_code=500)


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
                "x": pos[1] if pos else None,  # longitude
                "y": pos[0] if pos else None   # latitude
            })

        edges = []
        for u, v, data in G.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "weight": data.get('weight', 1),
                "label": str(data.get('weight', ''))
            })

        return standard_response(True, {"nodes": nodes, "edges": edges})
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
            total_routes = cursor.fetchone()[0] if cursor.fetchone() else 0

            # Recent activity - ensure this table exists or handle its absence
            recent_activity = []
            #try:
                #cursor.execute('''
                    #SELECT 'Stop Update' as type, stop_id, MAX(timestamp) as timestamp
                    #FROM stop_updates
                    #GROUP BY stop_id
                    #ORDER BY timestamp DESC
                    #LIMIT 5
                #''')
                #recent_activity = [dict(zip(['type', 'stop_id', 'timestamp'], row))
                                   #for row in cursor.fetchall()]
            #except sqlite3.OperationalError:
                # Table doesn't exist, use empty list
                #recent_activity = []

            return standard_response(True, {
                'total_stops': total_stops,
                'active_stops': active_stops,
                'total_routes': total_routes,
                #'recent_activity': recent_activity
            })
    except Exception as e:
        app.logger.error(f"Error in stats endpoint: {str(e)}")
        return standard_response(False, message=str(e), status_code=500)


if __name__ == '__main__':
    app.run(debug=True)