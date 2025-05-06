import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx

def percentage_to_color(percentage):
    norm = mcolors.Normalize(vmin=0, vmax=100)
    cmap = plt.get_cmap('coolwarm')
    return mcolors.to_hex(cmap(norm(percentage)))

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
        "monday": "poniedziałek",
        "tuesday": "wtorek",
        "wednesday": "środa",
        "thursday": "czwartek",
        "friday": "piątek",
        "saturday": "sobota",
        "sunday": "niedziela"
    }
    return days_map.get(day.lower(), "")

# Load traffic data
with open('traffic_data.json', 'r', encoding='utf-8') as file:
    traffic_info = json.load(file)

# Load nodes data
with open('sequential_edges.json', 'r', encoding='utf-8') as file:
    nodes_data = json.load(file)

# Get current day and time
now = datetime.now()
current_day = map_day_to_polish(now.strftime('%A'))  # Map to Polish day
current_hour = now.strftime('%H:00') 

node_colors = {}
node_intensities = {}
edges = []

# Process each connection in nodes_data
for route_id, connections in nodes_data.items():
    for connection in connections:
        from_node = connection['from']
        to_node = connection['to']
        
        from_traffic_intensity = 0
        to_traffic_intensity = 0
        
        # Get traffic intensity for each stop
        for location_data in traffic_info:
            if from_node.lower() in location_data['location'].lower():
                from_traffic_intensity = get_traffic_intensity(current_day, current_hour, location_data)
            if to_node.lower() in location_data['location'].lower():
                to_traffic_intensity = get_traffic_intensity(current_day, current_hour, location_data)
        
        # Set colors for nodes
        from_color = percentage_to_color(from_traffic_intensity)
        to_color = percentage_to_color(to_traffic_intensity)
        
        node_colors[from_node] = from_color
        node_colors[to_node] = to_color
        node_intensities[from_node] = from_traffic_intensity
        node_intensities[to_node] = to_traffic_intensity
        edges.append((from_node, to_node, connection['weight']))

# Print colors and intensities for each stop
for node, color in node_colors.items():
    intensity = node_intensities[node]
    print(f"Stop: {node}, Intensity: {intensity}%, Color: {color}")

# Create graph
G = nx.DiGraph()

# Add nodes and edges to graph
for node, color in node_colors.items():
    G.add_node(node, color=color)
    
for from_node, to_node, weight in edges:
    G.add_edge(from_node, to_node, weight=weight)

# Draw graph
pos = nx.spring_layout(G)  # Position nodes

node_colors_list = [node_colors[node] for node in G.nodes()]
weights = [G[u][v]['weight'] for u, v in G.edges()]

plt.figure(figsize=(10, 8))
nx.draw(G, pos, node_color=node_colors_list, edge_color='black', width=weights, with_labels=True, node_size=500)
plt.title(f"Traffic Intensity Graph for {current_day.capitalize()} at {current_hour}")
plt.show()
