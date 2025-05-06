document.addEventListener('DOMContentLoaded', function() {
    // Initialize network graph
    let network = null;
    let allStops = [];
    let activeStops = [];

    // Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Load initial data
    loadNetworkStats();
    loadAllStops();
    initializeNetworkGraph();

    // Event listeners
    document.getElementById('refresh-btn').addEventListener('click', refreshNetwork);
    document.getElementById('find-path-btn').addEventListener('click', findShortestPath);
    document.getElementById('add-stop-btn').addEventListener('click', showAddStopModal);
    document.getElementById('connect-stops-btn').addEventListener('click', showConnectStopsModal);
    document.getElementById('toggle-stops-btn').addEventListener('click', showToggleStopsModal);
    document.getElementById('save-stop-btn').addEventListener('click', saveNewStop);
    document.getElementById('save-connection-btn').addEventListener('click', saveConnection);

    // Functions
    function loadNetworkStats() {
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const stats = data.data;
                    const statsHtml = `
                        <div class="stat-item">
                            <span class="stat-label">Total Stops:</span>
                            <span class="stat-value">${stats.total_stops}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Active Stops:</span>
                            <span class="stat-value">${stats.active_stops}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Total Routes:</span>
                            <span class="stat-value">${stats.total_routes}</span>
                        </div>
                    `;
                    document.getElementById('stats-container').innerHTML = statsHtml;
                }
            })
            .catch(error => console.error('Error loading stats:', error));
    }

    function loadAllStops() {
        fetch('/api/stops')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    allStops = data.data;
                    activeStops = allStops.filter(stop => stop.active);

                    // Populate stop dropdowns
                    const stopSelects = [
                        document.getElementById('start-stop'),
                        document.getElementById('end-stop'),
                        document.getElementById('from-stop'),
                        document.getElementById('to-stop')
                    ];

                    stopSelects.forEach(select => {
                        // Clear existing options except the first one
                        while (select.options.length > 1) {
                            select.remove(1);
                        }

                        // Add active stops
                        activeStops.forEach(stop => {
                            const option = document.createElement('option');
                            option.value = stop.id;
                            option.textContent = stop.name;
                            select.appendChild(option);
                        });
                    });
                }
            })
            .catch(error => console.error('Error loading stops:', error));
    }

    function initializeNetworkGraph() {
        fetch('/api/network/graph')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('network-graph');
                    const graphData = {
                        nodes: new vis.DataSet(data.data.nodes.map(node => ({
                            id: node.id,
                            label: node.label,
                            title: node.label,
                            color: node.active ? (node.label === node.label.toUpperCase() ?
                                { background: '#1a237e', border: '#0d1533', highlight: { background: '#303f9f', border: '#1a237e' } } :
                                { background: '#3949ab', border: '#1a237e', highlight: { background: '#5c6bc0', border: '#3949ab' } }) :
                                { background: '#9fa8da', border: '#7986cb', highlight: { background: '#c5cae9', border: '#9fa8da' } },
                            x: node.x,
                            y: node.y,
                            active: node.active
                        }))),
                        edges: new vis.DataSet(data.data.edges.map(edge => ({
                            from: edge.from,
                            to: edge.to,
                            label: edge.label,
                            title: `${edge.label} min`,
                            color: { color: '#5D6D7E', highlight: '#7f8c8d' },
                            arrows: 'to',
                            smooth: {
                                type: 'continuous'
                            }
                        })))
                    };

                    const options = {
                        nodes: {
                            shape: 'dot',
                            size: 16,
                            font: {
                                size: 12,
                                color: '#000000'
                            },
                            borderWidth: 2
                        },
                        edges: {
                            width: 2,
                            font: {
                                size: 10,
                                align: 'middle'
                            },
                            arrowStrikethrough: false,
                            smooth: {
                                type: 'continuous'
                            }
                        },
                        physics: {
                            stabilization: {
                                enabled: true,
                                iterations: 1000
                            },
                            barnesHut: {
                                gravitationalConstant: -2000,
                                centralGravity: 0.3,
                                springLength: 200,
                                springConstant: 0.04,
                                damping: 0.09,
                                avoidOverlap: 0.1
                            }
                        },
                        interaction: {
                            tooltipDelay: 200,
                            hideEdgesOnDrag: true,
                            multiselect: true
                        }
                    };

                    network = new vis.Network(container, graphData, options);

                    // Handle node clicks to show details
                    network.on('click', function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            showStopDetails(nodeId);
                        }
                    });
                }
            })
            .catch(error => console.error('Error loading network graph:', error));
    }

    function refreshNetwork() {
        loadNetworkStats();
        loadAllStops();

        // Show loading indicator
        const networkContainer = document.getElementById('network-graph');
        networkContainer.innerHTML = '<div class="text-center p-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';

        // Reinitialize the network
        initializeNetworkGraph();
    }

    function findShortestPath() {
        const startStop = document.getElementById('start-stop').value;
        const endStop = document.getElementById('end-stop').value;

        if (!startStop || !endStop) {
            alert('Please select both start and end stops');
            return;
        }

        fetch('/api/routes/shortest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start: startStop,
                end: endStop
            })
        })
        .then(response => response.json())
        .then(data => {
            const resultContainer = document.getElementById('path-result');

            if (data.success) {
                const path = data.data.path;
                const duration = data.data.duration;

                let pathHtml = '<div class="path-steps">';
                path.forEach((stop, index) => {
                    pathHtml += `<span class="path-step">${stop}</span>`;
                    if (index < path.length - 1) {
                        pathHtml += ' <i class="fas fa-arrow-right"></i> ';
                    }
                });
                pathHtml += `</div><div class="path-duration">Total time: ${duration}</div>`;

                resultContainer.innerHTML = pathHtml;

                // Highlight the path on the network graph
                if (network) {
                    const allNodes = network.body.data.nodes.getIds();
                    const allEdges = network.body.data.edges.getIds();

                    // Reset all nodes and edges to default appearance
                    network.body.data.nodes.update(allNodes.map(id => ({
                        id,
                        color: getDefaultNodeColor(id)
                    }));

                    network.body.data.edges.update(allEdges.map(id => ({
                        id,
                        color: { color: '#5D6D7E' }
                    })));

                    // Highlight path nodes
                    const nodeUpdates = [];
                    for (let i = 0; i < path.length; i++) {
                        const nodeId = allStops.find(stop => stop.name === path[i])?.id;
                        if (nodeId) {
                            nodeUpdates.push({
                                id: nodeId,
                                color: {
                                    background: '#28a745',
                                    border: '#1e7e34',
                                    highlight: {
                                        background: '#34ce57',
                                        border: '#28a745'
                                    }
                                }
                            });
                        }
                    }
                    network.body.data.nodes.update(nodeUpdates);

                    // Highlight path edges
                    const edgeUpdates = [];
                    for (let i = 0; i < path.length - 1; i++) {
                        const fromNode = allStops.find(stop => stop.name === path[i]);
                        const toNode = allStops.find(stop => stop.name === path[i + 1]);

                        if (fromNode && toNode) {
                            const edge = network.body.edges.find(edge =>
                                (edge.fromId === fromNode.id && edge.toId === toNode.id) ||
                                (edge.fromId === toNode.id && edge.toId === fromNode.id));

                            if (edge) {
                                edgeUpdates.push({
                                    id: edge.id,
                                    color: { color: '#28a745' }
                                });
                            }
                        }
                    }
                    network.body.data.edges.update(edgeUpdates);

                    // Fit the network to show the entire path
                    network.fit({
                        nodes: nodeUpdates.map(node => node.id),
                        animation: {
                            duration: 1000,
                            easingFunction: 'easeInOutQuad'
                        }
                    });
                }
            } else {
                resultContainer.innerHTML = `<div class="alert alert-danger">${data.message || 'No path found between the selected stops'}</div>`;
            }
        })
        .catch(error => {
            console.error('Error finding shortest path:', error);
            document.getElementById('path-result').innerHTML = '<div class="alert alert-danger">Error finding path. Please try again.</div>';
        });
    }

    function getDefaultNodeColor(nodeId) {
        const node = allStops.find(stop => stop.id === nodeId);
        if (!node) return { background: '#9fa8da', border: '#7986cb' };

        if (!node.active) {
            return { background: '#9fa8da', border: '#7986cb', highlight: { background: '#c5cae9', border: '#9fa8da' } };
        }

        if (node.name === node.name.toUpperCase()) {
            // Terminal stop
            return { background: '#1a237e', border: '#0d1533', highlight: { background: '#303f9f', border: '#1a237e' } };
        } else {
            // Regular stop
            return { background: '#3949ab', border: '#1a237e', highlight: { background: '#5c6bc0', border: '#3949ab' } };
        }
    }

    function showStopDetails(stopId) {
        fetch(`/api/stops/${stopId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const stopInfo = data.data.info;
                    const lines = data.data.lines;
                    const connections = data.data.connections;
                    const traffic = data.data.traffic;

                    let detailsHtml = `
                        <h4>${stopInfo.name} <span class="badge bg-${stopInfo.active ? 'success' : 'danger'}">${stopInfo.active ? 'Active' : 'Inactive'}</span></h4>
                        <p><strong>ID:</strong> ${stopInfo.id}</p>
                        <p><strong>Coordinates:</strong> ${stopInfo.lat}, ${stopInfo.lng}</p>

                        <h5 class="mt-4">Tram Lines</h5>
                        <div class="mb-3">
                    `;

                    lines.forEach(line => {
                        detailsHtml += `<span class="badge bg-primary stop-line-badge">${line}</span>`;
                    });

                    detailsHtml += `
                        </div>

                        <h5 class="mt-4">Connections</h5>
                        <div class="connections-list">
                    `;

                    if (connections.length > 0) {
                        connections.forEach(conn => {
                            detailsHtml += `
                                <div class="connection-item">
                                    <strong>${conn.from_name}</strong> to <strong>${conn.to_name}</strong>
                                    <span class="badge bg-secondary float-end">${conn.weight} min</span>
                                </div>
                            `;
                        });
                    } else {
                        detailsHtml += '<p>No connections found for this stop.</p>';
                    }

                    detailsHtml += `
                        </div>

                        <h5 class="mt-4">Traffic Patterns</h5>
                    `;

                    if (traffic && traffic.length > 0) {
                        // Create a simple traffic display (could be enhanced with charts)
                        detailsHtml += '<div class="traffic-summary">';

                        // Group by day of week
                        const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
                        days.forEach(day => {
                            const dayTraffic = traffic.filter(t => t[0] === day);
                            if (dayTraffic.length > 0) {
                                detailsHtml += `<h6>${day}</h6><div class="traffic-hours">`;

                                dayTraffic.forEach(hourData => {
                                    const hour = hourData[1];
                                    const congestion = hourData[2];
                                    detailsHtml += `<span class="badge bg-${congestion > 70 ? 'danger' : congestion > 40 ? 'warning' : 'success'} me-1" title="Hour ${hour}: ${congestion}%">${hour}h</span>`;
                                });

                                detailsHtml += '</div>';
                            }
                        });

                        detailsHtml += '</div>';
                    } else {
                        detailsHtml += '<p>No traffic data available for this stop.</p>';
                    }

                    document.getElementById('stop-details').innerHTML = detailsHtml;
                } else {
                    document.getElementById('stop-details').innerHTML = `<div class="alert alert-danger">${data.message || 'Error loading stop details'}</div>`;
                }
            })
            .catch(error => {
                console.error('Error loading stop details:', error);
                document.getElementById('stop-details').innerHTML = '<div class="alert alert-danger">Error loading stop details. Please try again.</div>';
            });
    }

    function showAddStopModal() {
        const modal = new bootstrap.Modal(document.getElementById('addStopModal'));
        modal.show();
    }

    function saveNewStop() {
        const stopId = document.getElementById('stop-id').value.trim().toUpperCase();
        const stopName = document.getElementById('stop-name').value.trim();
        const latitude = document.getElementById('latitude').value;
        const longitude = document.getElementById('longitude').value;

        if (!stopId || !stopName || !latitude || !longitude) {
            alert('Please fill in all fields');
            return;
        }

        fetch('/api/stops', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: stopId,
                name: stopName,
                lat: parseFloat(latitude),
                lng: parseFloat(longitude)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Stop added successfully');
                document.getElementById('add-stop-form').reset();
                bootstrap.Modal.getInstance(document.getElementById('addStopModal')).hide();
                refreshNetwork();
            } else {
                alert(data.message || 'Error adding stop');
            }
        })
        .catch(error => {
            console.error('Error adding stop:', error);
            alert('Error adding stop. Please try again.');
        });
    }

    function showConnectStopsModal() {
        const modal = new bootstrap.Modal(document.getElementById('connectStopsModal'));
        modal.show();
    }

    function saveConnection() {
        const fromStop = document.getElementById('from-stop').value;
        const toStop = document.getElementById('to-stop').value;
        const travelTime = document.getElementById('travel-time').value;

        if (!fromStop || !toStop || !travelTime) {
            alert('Please fill in all fields');
            return;
        }

        if (fromStop === toStop) {
            alert('Cannot connect a stop to itself');
            return;
        }

        fetch('/api/connections', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from: fromStop,
                to: toStop,
                weight: parseInt(travelTime)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Connection added successfully');
                document.getElementById('connect-stops-form').reset();
                bootstrap.Modal.getInstance(document.getElementById('connectStopsModal')).hide();
                refreshNetwork();
            } else {
                alert(data.message || 'Error adding connection');
            }
        })
        .catch(error => {
            console.error('Error adding connection:', error);
            alert('Error adding connection. Please try again.');
        });
    }

    function showToggleStopsModal() {
        fetch('/api/stops/status')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const activeList = document.getElementById('active-stops-list');
                    const inactiveList = document.getElementById('inactive-stops-list');

                    // Clear existing lists
                    activeList.innerHTML = '';
                    inactiveList.innerHTML = '';

                    // Populate active stops
                    data.data.active.forEach(stop => {
                        const item = document.createElement('button');
                        item.type = 'button';
                        item.className = 'list-group-item list-group-item-action';
                        item.textContent = stop.name;
                        item.addEventListener('click', () => toggleStopStatus(stop.id, false));
                        activeList.appendChild(item);
                    });

                    // Populate inactive stops
                    data.data.inactive.forEach(stop => {
                        const item = document.createElement('button');
                        item.type = 'button';
                        item.className = 'list-group-item list-group-item-action';
                        item.textContent = stop.name;
                        item.addEventListener('click', () => toggleStopStatus(stop.id, true));
                        inactiveList.appendChild(item);
                    });

                    const modal = new bootstrap.Modal(document.getElementById('toggleStopsModal'));
                    modal.show();
                }
            })
            .catch(error => {
                console.error('Error loading stop status:', error);
                alert('Error loading stop status. Please try again.');
            });
    }

    function toggleStopStatus(stopId, activate) {
        fetch(`/api/stops/${stopId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                active: activate
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToggleStopsModal(); // Refresh the modal
                refreshNetwork();
            } else {
                alert(data.message || 'Error toggling stop status');
            }
        })
        .catch(error => {
            console.error('Error toggling stop status:', error);
            alert('Error toggling stop status. Please try again.');
        });
    }
});