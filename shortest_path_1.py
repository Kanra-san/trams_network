import networkx as nx
from db_handler import TramDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class TramNetwork:
    def __init__(self, db_file='tram_data2.db'):
        self.db = TramDatabase(db_file)
        self.graph = self.db.create_network_graph()

    def find_shortest_path(self, start_stop: str, end_stop: str, return_names=False):
        logging.debug(f"Finding shortest path from {start_stop} to {end_stop}")

        # Check if stops exist in the graph
        if start_stop not in self.graph or end_stop not in self.graph:
            logging.warning(f"One or both stops don't exist: {start_stop}, {end_stop}")
            return None, "One or both stops don't exist"

        # Check if stops are active
        if not self.graph.nodes[start_stop].get('active', False):
            logging.warning(f"Start stop {start_stop} is not active")
            return None, f"Start stop {start_stop} is not active"
        if not self.graph.nodes[end_stop].get('active', False):
            logging.warning(f"End stop {end_stop} is not active")
            return None, f"End stop {end_stop} is not active"

        try:
            active_nodes = [n for n in self.graph.nodes if self.graph.nodes[n].get('active', False)]
            active_edges = [(u, v) for u, v in self.graph.edges if self.graph.nodes[u].get('active', False)
                            and self.graph.nodes[v].get('active', False)]
            #logging.debug(f"Active nodes: {active_nodes}")
            #logging.debug(f"Active edges: {active_edges}")

            subgraph = self.graph.subgraph(active_nodes).edge_subgraph(active_edges)
            #logging.debug(f"Subgraph nodes: {subgraph.nodes}")
            #logging.debug(f"Subgraph edges: {subgraph.edges}")

            path = nx.dijkstra_path(subgraph, start_stop, end_stop, weight='weight')
            length = nx.dijkstra_path_length(subgraph, start_stop, end_stop, weight='weight')

            logging.info(f"Shortest path: {path}, Length: {length:.1f} min")

            if return_names:
                path = [self.graph.nodes[stop_id]['name'] for stop_id in path]

            return path, f"{length:.1f} min"
        except nx.NetworkXNoPath:
            logging.error(f"No path exists between {start_stop} and {end_stop}")
            return None, "No path exists between stops"