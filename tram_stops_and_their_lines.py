import json

def get_lines():
    tram_routes_path = 'archive/tram_routes.json'
    with open(tram_routes_path, 'r', encoding='utf-8') as file:
        tram_routes = json.load(file)


    stop_to_lines = {}
    for line_number, routes in tram_routes.items():
        for route in routes:
            for stop in route:
                if stop not in stop_to_lines:
                    stop_to_lines[stop.upper()] = []
                if line_number not in stop_to_lines[stop.upper()]:
                    stop_to_lines[stop.upper()].append(line_number)


    for stops in stop_to_lines:
        stop_to_lines[stops].sort()


    output_path = 'archive/stop_to_lines.json'
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(stop_to_lines, file, ensure_ascii=False, indent=4)
