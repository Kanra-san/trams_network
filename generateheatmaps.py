import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import json 

# Funkcja do ładowania danych z pliku JSON
def load_data_from_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

file_path = 'traffic_data.json'
data = load_data_from_json(file_path)

def get_traffic_data_for_location(location_name, data):
    for location_data in data:
        if location_data['location'].lower() == location_name.lower():
            return location_data['traffic_data']
    return None

# Użytkownik wpisuje nazwę lokalizacji
# location_name = input("Wpisz nazwę przystanku: ")
# traffic_data = get_traffic_data_for_location(location_name, data)
#
# if traffic_data is not None:
#     days = [day[0] for day in traffic_data]  # Lista dni
#     hours = [f"{hour:02d}:00" for hour in range(24)]  # Lista godzin
#     traffic_matrix = np.array([[int(hour.split(': ')[1].strip('%.')) for hour in day[1]] for day in traffic_data])
#
#     plt.figure(figsize=(12, 7))
#     sns.heatmap(traffic_matrix, annot=True, fmt="d", cmap="coolwarm", xticklabels=hours, yticklabels=days)
#     plt.title(f'Traffic Intensity Heatmap for {location_name}')
#     plt.xlabel('Hour of the Day')
#     plt.ylabel('Day of the Week')
#     plt.show()
# else:
#     print("Nie znaleziono danych dla wybranej lokalizacji.")
