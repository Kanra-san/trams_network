import networkx as nx
from db_handler import TramDatabase


class TramNetwork:
    def __init__(self, db_file='tram_data2.db'):
        self.db = TramDatabase(db_file)
        self.graph = self.db.create_network_graph()

    def find_shortest_path(self, start_stop: str, end_stop: str, return_names=False):
        start_stop = start_stop
        end_stop = end_stop

        # Check if stops exist in the graph
        if start_stop not in self.graph or end_stop not in self.graph:
            return None, "One or both stops don't exist"

        # Check if stops are active
        if not self.graph.nodes[start_stop].get('active', False):
            return None, f"Start stop {start_stop} is not active"
        if not self.graph.nodes[end_stop].get('active', False):
            return None, f"End stop {end_stop} is not active"

        try:
            active_nodes = [n for n in self.graph.nodes if self.graph.nodes[n].get('active', False)]
            active_edges = [(u, v) for u, v in self.graph.edges if self.graph.nodes[u].get('active', False)
                            and self.graph.nodes[v].get('active', False)]
            subgraph = self.graph.subgraph(active_nodes).edge_subgraph(active_edges)

            path = nx.dijkstra_path(subgraph, start_stop, end_stop, weight='weight')
            length = nx.dijkstra_path_length(subgraph, start_stop, end_stop, weight='weight')

            if return_names:
                path = [self.graph.nodes[stop_id]['name'] for stop_id in path]

            return path, f"{length:.1f} min"
        except nx.NetworkXNoPath:
            return None, "No path exists between stops"