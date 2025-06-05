import pandas as pd
import xml.etree.ElementTree as ET

# Load and parse the XML file
xml_path = "xmls/0004/0004.xml"  # replace with your path
tree = ET.parse(xml_path)
root = tree.getroot()

# Extract schedule data
schedule_data = []

# Traverse all <wariant> (variant) elements
for wariant in root.findall(".//wariant"):
    variant_id = wariant.attrib.get("id")
    variant_name = wariant.attrib.get("nazwa")

    # Traverse each <przystanek> (stop) in the variant
    for przystanek in wariant.findall("przystanek"):
        stop_id = przystanek.attrib.get("id")
        stop_name = przystanek.attrib.get("nazwa")

        # Traverse each <tabliczka> (schedule board)
        for tabliczka in przystanek.findall("tabliczka"):
            timetable_id = tabliczka.attrib.get("id")

            # Traverse each <dzien> (day type)
            for dzien in tabliczka.findall("dzien"):
                day_type = dzien.attrib.get("nazwa")

                # Traverse each <godz> (hour)
                for godz in dzien.findall("godz"):
                    hour = int(godz.attrib.get("h"))

                    # Traverse each <min> (minute)
                    for min_el in godz.findall("min"):
                        minute = int(min_el.attrib.get("m"))
                        ozn = min_el.attrib.get("ozn")
                        przyp = min_el.attrib.get("przyp")

                        # Add row to data list
                        schedule_data.append({
                            "variant_id": variant_id,
                            "variant_name": variant_name,
                            "stop_id": stop_id,
                            "stop_name": stop_name,
                            "timetable_id": timetable_id,
                            "day_type": day_type,
                            "hour": hour,
                            "minute": minute,
                            "oznaczenie": ozn,
                            "przypis": przyp
                        })

# Convert list of rows to a DataFrame
schedule_df = pd.DataFrame(schedule_data)
print(schedule_df.to_markdown())

print(schedule_df.head(10))