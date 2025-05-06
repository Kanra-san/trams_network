import xml.etree.ElementTree as ET
import json
def prepare():
    def extract_sequential_edges_from_xml(xml_file_path, edges_dict, line_number):
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        przystanki = root.find(".//czasy").findall("przystanek")
        previous = None

        for przystanek in przystanki:
            nazwa = przystanek.get('nazwa')
            czas = przystanek.get('czas')

            if nazwa is None or czas is None:
                continue

            nazwa = nazwa.upper()  # Optional: convert name to upper case
            czas = int(czas)

            if previous is not None:
                prev_nazwa, prev_czas = previous
                weight = czas - prev_czas
                edges_dict.setdefault(line_number, []).append({
                    "from": prev_nazwa,
                    "to": nazwa,
                    "weight": weight
                })

            previous = (nazwa, czas)

    def save_edges_to_json(edges_dict, output_file_path):
        with open(output_file_path, 'w', encoding='utf-8') as file:
            json.dump(edges_dict, file, indent=4, ensure_ascii=False)

    edges_dict = {}
    output_file_path = 'sequential_edges.json'

    for i in range(1, 24):
        xml_file_path = f'xmls/tramwaj{i}.xml'
        print(xml_file_path)
        extract_sequential_edges_from_xml(xml_file_path, edges_dict, i)

    save_edges_to_json(edges_dict, output_file_path)
