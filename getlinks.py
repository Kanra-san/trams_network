import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def read_bus_stops(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        stops = []
        for line in file:
            if "Przystanek -" in line:
                stop_name = line.strip()  # Use strip to remove any extra spaces or newline characters
                stop_name = stop_name.replace('"', '')  # Remove any quotation marks
                formatted_stop_name = f"{stop_name}, Wrocław"  # Append the city name
                stops.append(formatted_stop_name)
    return stops

def fetch_google_maps_urls(stops):
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 30)
    urls = {}

    try:
        driver.get("https://www.google.com/maps")
        for stop in stops:
            try:
                search_box = wait.until(EC.presence_of_element_located((By.ID, "searchboxinput")))
                search_box.clear()
                search_box.send_keys(stop + Keys.RETURN)

                time.sleep(3)  # Allow time for search results to load
                search_results = driver.find_elements(By.CSS_SELECTOR, "div.section-result-content")

                found_tram_stop = False
                for result in search_results:
                    if 'tram' in result.text.lower():
                        result.click()  # Click the result with 'tram' in its description
                        WebDriverWait(driver, 30).until(EC.url_contains('place'))
                        found_tram_stop = True
                        break

                if not found_tram_stop and search_results:
                    search_results[0].click()  # Fallback to the first result if no tram specific result is found

                current_url = driver.current_url
                urls[stop] = current_url
                print(f"URL for {stop}: {current_url}")

                # Reset for the next search
                driver.get("https://www.google.com/maps")
            except Exception as e:
                print(f"Error processing {stop}: {str(e)}")
                urls[stop] = "Error fetching URL"
    finally:
        driver.quit()

    return urls

# Path to the file containing bus stops
file_path = 'przystanki.csv'

# Read bus stops from the file
stops = read_bus_stops(file_path)

# Fetch links for each bus stop
urls = fetch_google_maps_urls(stops)
for stop, url in urls.items():
    print(f"{stop}: {url}")
    with open('links.csv', 'a', encoding='utf-8') as f:
        f.write(f"{url}\n")
    print("Data has been saved to file links.csv.")
