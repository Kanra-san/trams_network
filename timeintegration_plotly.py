from tram_stops_and_their_lines import get_lines
def generate_live():
    import json
    from datetime import datetime
    import plotly.graph_objects as go
    import plotly.express as px
    get_lines()
    def percentage_to_color(percentage):
        cmap = px.colors.sequential.Inferno[::-1]
        norm_percentage = int((percentage / 100) * (len(cmap) - 1))
        return cmap[norm_percentage]

    def get_traffic_intensity(day, time, location_data):
        for day_data in location_data['traffic_data']:
            if day_data[0].lower() == day.lower():
                for hour_data in day_data[1]:
                    if hour_data.startswith(time):
                        intensity = hour_data.split(": ")[1]
                        return int(intensity.strip('%.'))
        return 0

    def map_day_to_polish(day):
        days_map = {
            "monday": "Monday",
            "tuesday": "Tuesday",
            "wednesday": "Wednesday",
            "thursday": "Thursday",
            "friday": "Friday",
            "saturday": "Saturday",
            "sunday": "Sunday"
        }
        return days_map.get(day.lower(), "")

    with open('traffic_data.json', 'r', encoding='utf-8') as file:
        traffic_info = json.load(file)

    with open('archive/sequential_edges.json', 'r', encoding='utf-8') as file:
        nodes_data = json.load(file)

    now = datetime.now()
    current_day = map_day_to_polish(now.strftime('%A'))
    current_hour = now.strftime('%H:00') 

    node_colors = {}
    node_intensities = {}
    node_coords = {}
    edges = []
    with open('archive/stop_to_lines.json', 'r', encoding='utf-8') as file:
        line_info = json.load(file)
    for route_id, connections in nodes_data.items():
        for connection in connections:
            from_node = connection['from']
            to_node = connection['to']
            
            from_traffic_intensity = 0
            to_traffic_intensity = 0
            
            for location_data in traffic_info:
                if from_node.lower() in location_data['location'].lower():
                    from_traffic_intensity = get_traffic_intensity(current_day, current_hour, location_data)
                    node_coords[from_node] = location_data['coordinates']
                if to_node.lower() in location_data['location'].lower():
                    to_traffic_intensity = get_traffic_intensity(current_day, current_hour, location_data)
                    node_coords[to_node] = location_data['coordinates']
            
            from_color = percentage_to_color(from_traffic_intensity)
            to_color = percentage_to_color(to_traffic_intensity)
            
            node_colors[from_node] = from_color
            node_colors[to_node] = to_color
            node_intensities[from_node] = from_traffic_intensity
            node_intensities[to_node] = to_traffic_intensity
            edges.append((from_node, to_node, connection['weight']))

    fig = go.Figure()

    for node, coords in node_coords.items():
        lines = ', '.join(line_info[node])
        fig.add_trace(go.Scatter(
            x=[coords[1]],  # Using longitude as x
            y=[coords[0]],  # Using latitude as y
            text=f"{node}",
            marker=dict(color=node_colors[node], size=10),
            mode='markers+text',
            textposition="top center",
            hovertext=f"Przystanek: {node}<br>Natężenie ruchu: {node_intensities[node]}% <br>Linie: {lines}",
            hoverinfo="text",
            name=node
        ))

    for from_node, to_node, weight in edges:
        fig.add_trace(go.Scatter(
            x=[node_coords[from_node][1], node_coords[to_node][1]],
            y=[node_coords[from_node][0], node_coords[to_node][0]],
            mode='lines',
            line=dict(width=weight, color='black'),
            opacity=0.6,
            name=f"{from_node} to {to_node}"
        ))

    fig.update_layout(
        title=f"Natężenie ruchu w dniu {current_day.capitalize()} o godzinie {current_hour}",
        xaxis_title="Długość geograficzna",
        yaxis_title="Szerokość geograficzna",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        plot_bgcolor='white'
    )

    fig.show()
