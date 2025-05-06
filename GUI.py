import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Canvas
from pathlib import Path

import datetime
from PIL import Image, ImageTk
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.backends.backend_tkagg as backend_tkagg
import networkx as nx
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.lines import Line2D

import timeintegration_plotly
from GUI_WGRAJ_PLIK import file_import
from shortest_path_1 import TramNetwork
from db_handler import TramDatabase
from db_operations import TramDatabaseOperations


def gui_main():
    global G, db, db_ops
    db = TramDatabase()
    db_ops = TramDatabaseOperations()

    G = db.create_network_graph()
    network = TramNetwork()
    G = network.graph

    TITLE_FONT = ('Inter', 24, 'bold')
    HEADER_FONT = ('Inter', 18, 'bold')
    BODY_FONT = ('Inter', 14)
    BUTTON_FONT = ('Inter', 14, 'bold')
    SMALL_FONT = ('Inter', 12)


    def on_tram_line_select(event):
        line = tram_line_cb.get()
        variants = db.get_line_variants(line)

        variant_window = tk.Toplevel(window)
        variant_window.title(f"Route variants - line {line}")
        variant_window.geometry("900x600")
        variant_window.configure(bg="#E6F2FF")

        text_widget = tk.Text(variant_window, wrap=tk.WORD, bg="#E6F2FF", font=BODY_FONT)
        text_widget.pack(expand=True, fill='both', padx=20, pady=20)

        for i, variant in enumerate(variants, 1):
            text_widget.insert(tk.END, f"Variant {i}:\n")
            text_widget.insert(tk.END, " → ".join(variant) + "\n\n")

        close_button = tk.Button(variant_window, text="Close",
                               command=variant_window.destroy,
                               bg="#3A7CA5", fg="white",
                               font=BUTTON_FONT)
        close_button.pack(pady=20)

    def on_stop_select(event):
        selected = stop_cb.get()
        stop_id = selected.split('(')[-1].rstrip(')')
        stop_name = selected.split('(')[0].strip()

        lines = stop_to_lines.get(stop_id, [])
        lines_str = ', '.join(sorted(lines))

        stop_window = tk.Toplevel(window)
        stop_window.title(f"{stop_name} ({stop_id})")
        stop_window.geometry("1000x800")
        stop_window.configure(bg="#E6F2FF")

        stops_edges = list(G.edges(stop_id))
        state = "active" if len(stops_edges) > 0 else "inactive"

        tk.Label(stop_window, text=f"{stop_name} ({stop_id})",
                font=TITLE_FONT, bg="#3A7CA5", fg="white").pack(pady=20)
        tk.Label(stop_window, text=f"Lines: {lines_str}",
                font=HEADER_FONT, bg="#81B3E8").pack(pady=10)
        tk.Label(stop_window, text=f"State: {state}",
                font=HEADER_FONT, bg="#81B3E8").pack(pady=10)

        heatmap_path = generate_heatmap_for_stop(stop_id)
        if heatmap_path:
            heatmap_img = Image.open(heatmap_path)
            heatmap_img = heatmap_img.resize((960, 600), Image.Resampling.LANCZOS)
            heatmap_photo = ImageTk.PhotoImage(heatmap_img)
            heatmap_label = tk.Label(stop_window, image=heatmap_photo)
            heatmap_label.image = heatmap_photo
            heatmap_label.pack(pady=20)

        tk.Button(stop_window, text="Close", command=stop_window.destroy,
                 font=BUTTON_FONT, bg="#3A7CA5", fg="white").pack(pady=20)

    def open_shortest_path_window():
        path_window = tk.Toplevel(window)
        path_window.title("Find Shortest Path")
        path_window.geometry("800x500")  # Increased size
        path_window.configure(bg="#E6F2FF")

        stops_data = db.get_stops_with_names_and_ids()
        active_stops = [f"{name} ({id})" for id, name in stops_data
                       if db_ops.is_stop_active(id)]
        active_stops.sort(key=lambda x: x.split('(')[0].strip().lower())

        # Start stop selection
        tk.Label(path_window, text="Start Stop:",
                font=HEADER_FONT, bg="#E6F2FF").pack(pady=(30, 10))
        start_var = tk.StringVar()
        start_cb = ttk.Combobox(path_window, textvariable=start_var,
                               values=active_stops, font=BODY_FONT, state='normal')
        start_cb.pack()
        start_cb.bind('<KeyRelease>', lambda event: search_combobox(event, start_cb, active_stops))

        # End stop selection
        tk.Label(path_window, text="End Stop:",
                font=HEADER_FONT, bg="#E6F2FF").pack(pady=(30, 10))
        end_var = tk.StringVar()
        end_cb = ttk.Combobox(path_window, textvariable=end_var,
                             values=active_stops, font=BODY_FONT, state='normal')
        end_cb.pack()
        end_cb.bind('<KeyRelease>', lambda event: search_combobox(event, end_cb, active_stops))

        # Result display
        result_label = tk.Label(path_window, text="",
                              font=BODY_FONT, wraplength=700, bg="#E6F2FF")
        result_label.pack(pady=30)

        def calculate_path():
            start = start_var.get()
            end = end_var.get()

            if not start or not end:
                result_label.config(text="Please select both start and end stops")
                return

            start_id = start.split('(')[-1].rstrip(')')
            end_id = end.split('(')[-1].rstrip(')')

            try:
                path, duration = db_ops.find_shortest_path(start_id, end_id)
                if path:
                    result_text = f"Shortest path: {' → '.join(path)}\nDuration: {duration}"
                    result_label.config(text=result_text)
                else:
                    result_label.config(text="No path found between these stops")
            except Exception as e:
                result_label.config(text=f"Error finding path: {str(e)}")

        tk.Button(path_window, text="Find Path", command=calculate_path,
                bg="#3A7CA5", fg="white", font=BUTTON_FONT).pack(pady=20)



    def rounded_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
        points = [x1 + radius, y1,
                x1 + radius, y1,
                x2 - radius, y1,
                x2 - radius, y1,
                x2, y1,
                x2, y1 + radius,
                x2, y1 + radius,
                x2, y2 - radius,
                x2, y2 - radius,
                x2, y2,
                x2 - radius, y2,
                x2 - radius, y2,
                x1 + radius, y2,
                x1 + radius, y2,
                x1, y2,
                x1, y2 - radius,
                x1, y2 - radius,
                x1, y1 + radius,
                x1, y1 + radius,
                x1, y1]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def on_button_click(button_text):
        print(f"{button_text} clicked")

    def search_combobox(event, combobox, values):
        """Filter combobox values based on typed text"""
        typed = combobox.get()
        if not typed:
            combobox['values'] = values
            return

        filtered = [v for v in values if v.lower().startswith(typed.lower())]
        combobox['values'] = filtered

        if filtered:
            combobox.event_generate('<Down>')

    def search_list(event, listbox, values):
        """Filter listbox values based on typed text"""
        typed = event.widget.get().lower()
        if not typed:
            listbox.delete(0, tk.END)
            for item in values:
                listbox.insert(tk.END, item)
            return

        listbox.delete(0, tk.END)
        for item in values:
            if typed in item.lower():
                listbox.insert(tk.END, item)

    #def start_dash():
        #open_search_window()

    #def start_dash_app():
        #threading.Thread(target=lambda: subprocess.run(["python", "clicks.py"])).start()
        #webbrowser.open("http://127.0.0.1:8050")

    def realtime_map():
        timeintegration_plotly.generate_live()

    def load_tram_data():
        return db.get_all_tram_routes()

    def load_stop_to_lines_data():
        return db.get_stop_to_lines_mapping()

    tram_routes = load_tram_data()
    stop_to_lines = load_stop_to_lines_data()

    def on_stop_select(event):
        selected = stop_cb.get()
        # Extract stop ID from the displayed text (format: "Name (ID)")
        stop_id = selected.split('(')[-1].rstrip(')')
        stop_name = selected.split('(')[0].strip()

        lines = stop_to_lines.get(stop_id, [])
        lines_str = ', '.join(sorted(lines))  # Sort lines alphabetically

        stop_window = tk.Toplevel(window)
        stop_window.title(f"{stop_name} ({stop_id})")
        stop_window.geometry("1000x800")
        stop_window.configure(bg="#C4D8F2")

        stops_edges = list(G.edges(stop_id))
        state = "active" if len(stops_edges) > 0 else "inactive"

        tk.Label(stop_window, text=f"{stop_name} ({stop_id})", font=('Inter', 24, 'bold'), bg="#C4D8F2").pack(pady=10)
        tk.Label(stop_window, text=f"Lines: {lines_str}", font=('Inter', 16, 'bold'), bg="#C4D8F2").pack(pady=5)
        tk.Label(stop_window, text=f"State: {state}", font=('Inter', 16, 'bold'), bg="#C4D8F2").pack(pady=5)

        heatmap_path = generate_heatmap_for_stop(stop_id)
        if heatmap_path:
            heatmap_img = Image.open(heatmap_path)
            heatmap_img = heatmap_img.resize((960, 600), Image.Resampling.LANCZOS)
            heatmap_photo = ImageTk.PhotoImage(heatmap_img)
            heatmap_label = tk.Label(stop_window, image=heatmap_photo)
            heatmap_label.image = heatmap_photo
            heatmap_label.pack(pady=10)

        #tk.Button(stop_window, text="Close", command=stop_window.destroy,
                  #font=('Inter', 16), bg="#467D48", fg="white").pack(pady=10)

    def create_tram_line_selector(window):
        line_frame = ttk.Frame(window)
        line_frame.place(x=1320, y=100)

        line_label = tk.Label(line_frame, text="Lines:", font=('Inter', 15, 'bold'))
        line_label.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        global tram_line_cb
        tram_line_cb = ttk.Combobox(line_frame, values=list(tram_routes.keys()),
                                    state='normal', width=15, style="Info.TCombobox")
        tram_line_cb.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        tram_line_cb.bind("<<ComboboxSelected>>", on_tram_line_select)
        tram_line_cb.bind('<KeyRelease>', lambda event: search_combobox(event, tram_line_cb, list(tram_routes.keys())))

    def create_stop_selector(window):
        stop_frame = ttk.Frame(window)
        stop_frame.place(x=1320, y=160)

        stop_label = tk.Label(stop_frame, text="Stops:", font=('Inter', 15, 'bold'))
        stop_label.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        stops_data = db.get_stops_with_names_and_ids()
        stop_display_names = [f"{name} ({id})" for id, name in stops_data]

        global stop_cb
        stop_cb = ttk.Combobox(stop_frame, values=stop_display_names,
                               state='normal', width=15, style="Info.TCombobox")
        stop_cb.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        stop_cb.bind("<<ComboboxSelected>>", on_stop_select)
        stop_cb.bind('<KeyRelease>', lambda event: search_combobox(event, stop_cb, stop_display_names))

    def optimize_stop():
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta

        def load_file(entry):
            file_path = filedialog.askopenfilename()
            if file_path:
                entry.delete(0, tk.END)
                entry.insert(0, file_path)
                return file_path
            return None

        # this is not needed anymore
        day_map = {
            "Monday": "Monday",
            "Tuesday": "Tuesday",
            "Wednesday": "Wednesday",
            "Thursday": "Thursday",
            "Friday": "Friday",
            "Saturday": "Saturday",
            "Sunday": "Sunday"
        }

        def get_days_of_interest(period):
            today = datetime.today()
            if period == "today":
                days_of_interest = [day_map[today.strftime("%A")]]
            elif period == "tomorrow":
                tomorrow = today + timedelta(days=1)
                days_of_interest = [day_map[tomorrow.strftime("%A")]]
            elif period == "week":
                days_of_interest = [day_map[(today + timedelta(days=i)).strftime("%A")] for i in range(7)]
            elif period == "month":
                days_of_interest = [day_map[(today + timedelta(days=i)).strftime("%A")] for i in range(30)]
            else:
                raise ValueError("Invalid period specified. Use 'today', 'tomorrow', 'week', or 'month'.")
            return days_of_interest

        def normalize_traffic(data):
            min_traffic = data['traffic_percent'].min()
            max_traffic = data['traffic_percent'].max()
            data['normalized_traffic'] = (data['traffic_percent'] - min_traffic) / (max_traffic - min_traffic)
            return data

        def allocate_trips(data, max_trips_per_hour=7):
            data = normalize_traffic(data)
            total_trips_per_day = data.groupby('Line no.')['No. of courses'].sum().to_dict()
            allocated_trips = []
            for line in data['Line no.'].unique():
                line_data = data[data['Line no.'] == line]
                total_available_trips = total_trips_per_day[line]
                line_data['allocated_trips'] = (line_data['normalized_traffic'] * max_trips_per_hour).round().astype(int)
                line_data['allocated_trips'] = line_data['allocated_trips'].clip(upper=max_trips_per_hour)
                total_allocated_trips = line_data['allocated_trips'].sum()
                if total_allocated_trips > total_available_trips:
                    scaling_factor = total_available_trips / total_allocated_trips
                    line_data['allocated_trips'] = (line_data['allocated_trips'] * scaling_factor).round().astype(int)
                while line_data['allocated_trips'].sum() > total_available_trips:
                    over_allocated_indices = line_data[line_data['allocated_trips'] > 1].index
                    line_data.loc[over_allocated_indices, 'allocated_trips'] -= 1
                    line_data['allocated_trips'] = line_data['allocated_trips'].clip(upper=max_trips_per_hour)
                allocated_trips.append(line_data)
            return pd.concat(allocated_trips)

        def process_data(traffic_data, tram_data, period, line_numbers=None, hours=None):
            days_of_interest = get_days_of_interest(period)
            filtered_data = traffic_data[traffic_data['day'].isin(days_of_interest)]
            if line_numbers:
                filtered_data = filtered_data[filtered_data['Line no.'].isin(line_numbers)]
            if hours:
                filtered_data = filtered_data[filtered_data['Hour'].isin(hours)]
            filtered_data = filtered_data.dropna(subset=['traffic_percent'])  # Ensure there are no NaNs in 'traffic_percent'
            filtered_data = filtered_data[filtered_data['traffic_percent'].apply(lambda x: np.isfinite(x))]
            optimized_data = allocate_trips(filtered_data)
            optimized_data = optimized_data[['Line no.', 'Hour', 'day', 'No. of courses', 'allocated_trips']]
            optimized_data.columns = ['Line no.', 'Hour', 'Day of the week', 'Current No. of courses', 'New No. of courses']
            return optimized_data

        def gui_opt():
            def run_optimization():
                traffic_file_path = traffic_file_entry.get()
                tram_file_path = tram_file_entry.get()
                if not traffic_file_path or not tram_file_path:
                    messagebox.showerror("Error", "Please upload both traffic data and tram hours files.")
                    return
                try:
                    traffic_data = pd.read_csv(traffic_file_path)
                    tram_data = pd.read_csv(tram_file_path, delimiter=';')
                    period = day_combo.get()
                    lines = line_entry.get()
                    hour = hour_combo.get()

                    if lines:
                        try:
                            lines = [int(x.strip()) for x in lines.split(',') if x.strip()]
                        except:
                            lines = [lines]
                            return
                    else:
                        lines = None

                    hours = [f"{int(hour):02d}:00:00"] if hour != 'None' else None

                    global optimized_data
                    optimized_data = process_data(traffic_data, tram_data, period, lines, hours)
                    for widget in result_frame.winfo_children():
                        widget.destroy()
                    create_table(result_frame, optimized_data)
                    download_button.config(state=tk.NORMAL)
                except Exception as e:
                    messagebox.showerror("Optimization failed", str(e))

            def create_table(parent, data):
                tree = ttk.Treeview(parent, columns=list(data.columns), show='headings')
                tree.pack(fill="both", expand=True)
                for col in data.columns:
                    tree.heading(col, text=col)
                    tree.column(col, anchor='center')

                for index, row in data.iterrows():
                    tags = ()
                    if row['Current No. of courses'] != row['New No. of courses']:
                        tags = ('diff',)
                    tree.insert("", "end", values=list(row), tags=tags)

                tree.tag_configure('diff', background='lightgreen', foreground='black')

            def download_report():
                period = day_combo.get()
                filepath = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f'Optimized_Traffic_Data_{period}.csv')
                if filepath:
                    optimized_data.to_csv(filepath, index=False)
                    messagebox.showinfo("Success", f"Report saved as {filepath}")

            window = tk.Tk()
            window.title("Tram traffic optimization")
            window.geometry("1000x800")

            ttk.Label(window, text="Choose time period:").pack(pady=(20, 0))
            day_combo = ttk.Combobox(window, values=["today", "tomorrow", "week", "month"])
            day_combo.pack()
            day_combo.set("today")

            ttk.Label(window, text="Enter line numbers (e.g. 1,2,3):").pack(pady=(20, 0))
            line_entry = ttk.Entry(window, width=50)
            line_entry.pack()

            ttk.Label(window, text="Choose hour (optional):").pack(pady=(20, 0))
            hour_combo = ttk.Combobox(window, values=[f"{i:02d}" for i in range(24)] + ["Brak"])
            hour_combo.pack()
            hour_combo.set("Brak")

            ttk.Label(window, text="Upload crowd traffic data").pack(pady=(20, 0))
            traffic_file_entry = ttk.Entry(window, width=50)
            traffic_file_entry.pack()
            ttk.Button(window, text="Upload", command=lambda: load_file(traffic_file_entry)).pack(pady=(5, 0))

            ttk.Label(window, text="Upload tram schedule data:").pack(pady=(20, 0))
            tram_file_entry = ttk.Entry(window, width=50)
            tram_file_entry.pack()
            ttk.Button(window, text="Upload", command=lambda: load_file(tram_file_entry)).pack(pady=(5, 0))

            result_frame = tk.Frame(window)
            result_frame.pack(fill="both", expand=True, padx=10, pady=10)

            run_button = tk.Button(window, text="Optimize", command=run_optimization)
            run_button.pack(pady=(10, 0))

            download_button = tk.Button(window, text="Download report", state=tk.DISABLED, command=download_report)
            download_button.pack(pady=(10, 0))

            window.mainloop()

        if __name__ == "__main__":
            gui_opt()

    def generate_heatmap_for_stop(stop):
        traffic_data = db.get_traffic_data_for_stop(stop)

        if not traffic_data:
            print(f"No traffic data available for stop {stop}")
            return None
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        # Convert hours to integers and normalize values
        processed_data = []
        for day, hour, congestion in traffic_data:
            try:
                hour_int = int(float(hour))  # Handle both string and numeric hours
                # Normalize congestion values (assuming they're percentages)
                congestion_normalized = float(congestion) / 100  # Convert to 0-1 range
                processed_data.append((day, hour_int, congestion_normalized))
            except (ValueError, TypeError) as e:
                print(f"Error processing data point: {day}, {hour}, {congestion} - {e}")

        if not processed_data:
            print("No valid data points after processing")
            return None

        # Get unique days and hours
        days = sorted({day for day, hour, congestion in processed_data})
        hours = sorted({hour for day, hour, congestion in processed_data})

        # Create matrix (now with normalized 0-1 values)
        traffic_matrix = []
        for day in days:
            day_row = []
            for hour in hours:
                # Find matching record (default to 0)
                match = [c for d, h, c in processed_data if d == day and h == hour]
                day_row.append(match[0] if match else 0)
            traffic_matrix.append(day_row)

        # Create heatmap with proper formatting
        plt.figure(figsize=(15, 10))
        ax = sns.heatmap(
            traffic_matrix,
            annot=True,
            fmt=".0%",  # Format as percentages (e.g., 75%)
            cmap="coolwarm",
            vmin=0,
            vmax=1,  # Ensure color scale is 0-100%
            xticklabels=[f"{int(h):02d}:00" for h in hours],  # Ensure hours are integers
            yticklabels=day_order
        )

        # Improve visualization
        ax.set_title(f'Traffic Intensity at Stop {stop} (%)', pad=20)
        ax.set_xlabel('Hour of Day', labelpad=15)
        ax.set_ylabel('Day of Week', labelpad=15)
        plt.yticks(rotation=0)  # Keep day labels horizontal
        ax.figure.tight_layout()

        # Save with higher DPI for better quality
        heatmap_path = f'heatmap_{stop}.png'
        plt.savefig(heatmap_path, dpi=120, bbox_inches='tight')
        plt.close()

        return heatmap_path

    def add_delete_stop():
        global G  # Reference the global graph

        # Get stops sorted by name with ID in parentheses
        stops_data = db.get_stops_with_names_and_ids()
        tram_stops = [f"{name} ({id})" for id, name in stops_data]
        tram_stops.sort(key=lambda x: x.split('(')[0].strip().lower())

        add_delete_window = tk.Toplevel(window)
        add_delete_window.title("Add/remove stops")
        add_delete_window.geometry("500x400")

        tab_control = ttk.Notebook(add_delete_window)

        # Add Stop Tab
        add_tab = ttk.Frame(tab_control)
        tab_control.add(add_tab, text='Add stop')

        def add_stop():
            global G
            stop_name = name_entry.get().strip().upper()
            if not stop_name:
                messagebox.showerror("Error", "Name of the stop is required")
                return

            latitude = latitude_entry.get().strip()
            longitude = longitude_entry.get().strip()

            try:
                # Add to database
                db_ops.add_stop(
                    stop_id=stop_name,
                    stop_name=stop_name,
                    latitude=float(latitude),
                    longitude=float(longitude)
                )

                # Update the global graph
                G.add_node(stop_name, pos=(float(latitude), float(longitude)))
                refresh_graph()

                messagebox.showinfo("Info", f"New stop added: {stop_name}.")

                # Update the stops list for the delete tab
                tram_stops.append(f"{stop_name} ({stop_name})")
                delete_combobox['values'] = sorted(tram_stops, key=lambda x: x.split('(')[0].strip().lower())

            except ValueError:
                messagebox.showerror("Error", "Incorrect coordinates")
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Stop not found: {e}")

        # Add stop UI elements
        tk.Label(add_tab, text="Name of the new stop").grid(row=0, column=0, padx=10, pady=5)
        name_entry = tk.Entry(add_tab)
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(add_tab, text="Latitude").grid(row=1, column=0, padx=10, pady=5)
        latitude_entry = tk.Entry(add_tab)
        latitude_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(add_tab, text="Longitude").grid(row=2, column=0, padx=10, pady=5)
        longitude_entry = tk.Entry(add_tab)
        longitude_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Button(add_tab, text="Add", command=add_stop).grid(row=3, column=1, padx=10, pady=5)

        # Delete Stop Tab
        delete_tab = ttk.Frame(tab_control)
        tab_control.add(delete_tab, text='Remove stop')

        def delete_stop():
            global G
            selected = stop_to_delete.get().strip()
            stop_id = selected.split('(')[-1].rstrip(')')

            if not stop_id:
                messagebox.showerror("Error", "Name of the stop to remove is required.")
                return

            try:
                # Remove from database
                db_ops.delete_stop(stop_id)

                # Update the global graph
                if stop_id in G.nodes:
                    G.remove_node(stop_id)
                    refresh_graph()

                # Update the stops list
                updated_stops = [s for s in tram_stops if not s.endswith(f"({stop_id})")]
                delete_combobox['values'] = updated_stops
                if updated_stops:  # Set to first stop if list not empty
                    stop_to_delete.set(updated_stops[0])
                else:
                    stop_to_delete.set("")

                messagebox.showinfo("Info", f"Stop removed: {stop_id}.")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Stop not found: {e}")

        stop_to_delete = tk.StringVar(delete_tab)
        stop_to_delete.set(tram_stops[0] if tram_stops else "")

        tk.Label(delete_tab, text="Choose the stop to remove").grid(row=0, column=0, padx=10, pady=5)
        delete_combobox = ttk.Combobox(delete_tab, textvariable=stop_to_delete, values=tram_stops)
        delete_combobox.grid(row=0, column=1, padx=10, pady=5)

        tk.Button(delete_tab, text="Remove", command=delete_stop).grid(row=1, column=1, padx=10, pady=5)

        tab_control.pack(expand=1, fill='both')

    def turn_off_on_the_stops():
        stops_data = db.get_stops_with_names_and_ids()
        stop_display_names = [f"{name} ({id})" for id, name in stops_data]
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stop_id FROM stops WHERE active_status = 'yes'")
        active_stop_ids = {row[0] for row in cursor.fetchall()}

        active_tram_stops = sorted(
            [f"{name} ({id})" for id, name in stops_data if id in active_stop_ids],
            key=lambda x: x.split('(')[0].strip().lower()
        )
        inactive_tram_stops = sorted(
            [f"{name} ({id})" for id, name in stops_data if id not in active_stop_ids],
            key=lambda x: x.split('(')[0].strip().lower()
        )

        turn_off_window = tk.Toplevel(window)
        turn_off_window.title("Turn off/on")
        turn_off_window.geometry("500x400")
        turn_off_window.configure(bg="#D7E3B5")

        tab_control = ttk.Notebook(turn_off_window)
        tab_off = ttk.Frame(tab_control)
        tab_on = ttk.Frame(tab_control)
        tab_control.add(tab_off, text='Turn off')
        tab_control.add(tab_on, text='Turn on')
        tab_control.pack(expand=1, fill="both")

        label_font = ('Arial', 15, 'bold')

        # Active stops list
        tk.Label(tab_off, text="Choose the stop to turn off", font=label_font).grid(row=0, column=0, padx=10,
                                                                                         pady=5)
        listbox_active = tk.Listbox(tab_off, height=10, width=50)
        scrollbar_active = tk.Scrollbar(tab_off, orient="vertical", command=listbox_active.yview)
        listbox_active.configure(yscrollcommand=scrollbar_active.set)
        listbox_active.grid(row=1, column=0, rowspan=4, padx=10, pady=5, sticky='nsew')
        scrollbar_active.grid(row=1, column=1, rowspan=4, sticky='ns')
        for stop in active_tram_stops:
            listbox_active.insert(tk.END, stop)

        # Inactive stops list
        tk.Label(tab_on, text="Choose the stop to turn on", font=label_font).grid(row=0, column=0, padx=10, pady=5)
        listbox_inactive = tk.Listbox(tab_on, height=10, width=50)
        scrollbar_inactive = tk.Scrollbar(tab_on, orient="vertical", command=listbox_inactive.yview)
        listbox_inactive.configure(yscrollcommand=scrollbar_inactive.set)
        listbox_inactive.grid(row=1, column=0, rowspan=4, padx=10, pady=5, sticky='nsew')
        scrollbar_inactive.grid(row=1, column=1, rowspan=4, sticky='ns')
        for stop in inactive_tram_stops:
            listbox_inactive.insert(tk.END, stop)

        def turn_the_stop_off():
            selected_index = listbox_active.curselection()
            if selected_index:
                selected_stop = listbox_active.get(selected_index)
                stop_id = selected_stop.split('(')[-1].rstrip(')')
                try:
                    # Deactivate the stop in database
                    success = db_ops.set_stop_active_status(stop_id, False)

                    if success:
                        # Update the UI
                        active_tram_stops.remove(selected_stop)
                        inactive_tram_stops.append(selected_stop)
                        listbox_active.delete(selected_index)
                        listbox_inactive.insert(tk.END, selected_stop)

                        # Refresh the graph
                        global G
                        G = db.create_network_graph()
                        refresh_graph()  # No parameter needed now

                        show_notification(f"Turned OFF {selected_stop}")
                    else:
                        messagebox.showerror("Error", "Stop NOT turned off")
                except Exception as e:
                    messagebox.showerror("Error", f"Turning off not possible: {e}")

        def turn_on_the_stop():
            selected_index = listbox_inactive.curselection()
            if selected_index:
                selected_stop = listbox_inactive.get(selected_index)
                stop_id = selected_stop.split('(')[-1].rstrip(')')
                try:
                    # Activate the stop in database
                    success = db_ops.set_stop_active_status(stop_id, True)

                    if success:
                        # Update the UI
                        inactive_tram_stops.remove(selected_stop)
                        active_tram_stops.append(selected_stop)
                        active_tram_stops.sort()
                        listbox_inactive.delete(selected_index)
                        listbox_active.insert(tk.END, selected_stop)

                        # Refresh the graph
                        global G
                        G = db.create_network_graph()
                        refresh_graph()  # No parameter needed now

                        show_notification(f"Turned ON {selected_stop}")
                    else:
                        messagebox.showerror("Błąd", "Stop NOT turned on")
                except Exception as e:
                    messagebox.showerror("Błąd", f"Turning on not possible: {e}")

        def finish():
            turn_off_window.destroy()

        def show_notification(message):
            notification_label.config(text=message)
            notification_label.place(relx=1.0, rely=1.0, anchor='se')
            turn_off_window.after(5000, clear_notification)

        def clear_notification():
            notification_label.place_forget()

        # Buttons
        tk.Button(tab_off, text="Finish", command=finish).grid(row=7, column=1, padx=10, pady=5)
        tk.Button(tab_off, text="Turn off", command=turn_the_stop_off).grid(row=7, column=0, padx=10, pady=5)

        tk.Button(tab_on, text="Finish", command=finish).grid(row=7, column=1, padx=10, pady=5)
        tk.Button(tab_on, text="Turn on", command=turn_on_the_stop).grid(row=7, column=0, padx=10, pady=5)

        notification_label = tk.Label(turn_off_window, text="", fg="red")
        notification_label.grid(row=3, column=0, columnspan=3, pady=5)

    def connect_stops():
        global G

        # Get data from database
        stops_data = db.get_stops_with_names_and_ids()
        tram_stops = [f"{name} ({id})" for id, name in stops_data]
        tram_stops.sort(key=lambda x: x.split('(')[0].strip().lower())

        connecting_window = tk.Toplevel(window)
        connecting_window.title("Connect stops")
        connecting_window.geometry("500x400")

        conn_tab_control = ttk.Notebook(connecting_window)
        conn_tab_control.pack(expand=1, fill="both")

        # Direct Connection Tab
        direct_conn_tab = ttk.Frame(conn_tab_control)
        conn_tab_control.add(direct_conn_tab, text='Connect together')

        tk.Label(direct_conn_tab, text="Stop").pack(pady=(20, 0))
        name_entry = ttk.Combobox(direct_conn_tab, values=tram_stops)
        name_entry.pack()

        tk.Label(direct_conn_tab, text="Connect with").pack(pady=(20, 0))
        neighbour_combobox = ttk.Combobox(direct_conn_tab, values=tram_stops)
        neighbour_combobox.pack()

        tk.Label(direct_conn_tab, text="Time of travel").pack(pady=(20, 0))
        time_entry = tk.Entry(direct_conn_tab)
        time_entry.pack()

        # Delete Connection Tab
        del_conn_tab = ttk.Frame(conn_tab_control)
        conn_tab_control.add(del_conn_tab, text='Remove connection')

        tk.Label(del_conn_tab, text="Stop").pack(pady=(20, 0))
        del_name_entry = ttk.Combobox(del_conn_tab, values=tram_stops)
        del_name_entry.pack()

        tk.Label(del_conn_tab, text="Connected with").pack(pady=(20, 0))
        del_neighbour_combobox = ttk.Combobox(del_conn_tab, values=tram_stops)
        del_neighbour_combobox.pack()

        notification_label = tk.Label(connecting_window, text="", fg="red")
        notification_label.pack()

        def show_notification(message):
            notification_label.config(text=message)
            notification_label.place(relx=1.0, rely=1.0, anchor='se')
            connecting_window.after(5000, clear_notification)

        def clear_notification():
            notification_label.place_forget()

        def connect():
            global G
            stop1_display = name_entry.get().strip()
            stop2_display = neighbour_combobox.get().strip()
            time = time_entry.get().strip()

            if not stop1_display or not stop2_display or not time:
                show_notification('All fields are required')
                return

            try:
                time = int(time)
                if time <= 0:
                    raise ValueError("Time cannot be negative")

                # Extract stop IDs
                stop1 = stop1_display.split('(')[-1].rstrip(')')
                stop2 = stop2_display.split('(')[-1].rstrip(')')

                # Check if connection exists in either direction
                if G.has_edge(stop1, stop2) or G.has_edge(stop2, stop1):
                    show_notification('Connection already exists')
                    return

                # Add to database
                db_ops.add_connection(
                    line_number="MANUAL",
                    from_stop=stop1,
                    to_stop=stop2,
                    weight=time
                )

                # Update global graph
                G.add_edge(stop1, stop2, weight=time)
                refresh_graph()

                show_notification(f"Added connection: {stop1_display} - {stop2_display} ({time} min)")

            except ValueError as e:
                show_notification(f"Error: {str(e)}")
            except sqlite3.Error as e:
                show_notification(f"Database error: {str(e)}")

        def delete_connection():
            global G
            stop1_display = del_name_entry.get().strip()
            stop2_display = del_neighbour_combobox.get().strip()

            if not stop1_display or not stop2_display:
                show_notification('Choose both of the stops')
                return

            # Extract stop IDs
            stop1 = stop1_display.split('(')[-1].rstrip(')')
            stop2 = stop2_display.split('(')[-1].rstrip(')')

            # Check if connection exists
            if not G.has_edge(stop1, stop2) and not G.has_edge(stop2, stop1):
                show_notification('This connection does not exist')
                return

            try:
                # Remove from database
                db_ops.delete_connection(stop1, stop2)

                # Update global graph
                if G.has_edge(stop1, stop2):
                    G.remove_edge(stop1, stop2)
                if G.has_edge(stop2, stop1):
                    G.remove_edge(stop2, stop1)
                refresh_graph()

                show_notification(f"Removed connection: {stop1_display} - {stop2_display}")

            except sqlite3.Error as e:
                show_notification(f"Database error: {str(e)}")

        # Buttons
        tk.Button(direct_conn_tab, text="Add connection", command=connect).pack()
        tk.Button(del_conn_tab, text="Remove connection", command=delete_connection).pack()

    def refresh_graph():
        global G, toolbar

        for widget in graph_frame.winfo_children():
            widget.destroy()

        try:
            G = db.create_network_graph()
            fig = plt.figure(figsize=(12, 9), dpi=100)
            ax = fig.add_subplot(111)

            ax.set_axis_off()
            plt.axis('off')
            plt.tight_layout(pad=0)

            pos = {n: data['pos'] for n, data in G.nodes(data=True) if 'pos' in data and data['pos'] is not None}

            if not pos:
                pos = nx.spring_layout(G, k=0.7, iterations=50, seed=42)
            else:
                pos = {n: (lon, lat) for n, (lat, lon) in pos.items()}

            active_nodes = [n for n in G.nodes if G.nodes[n]['active']]
            inactive_nodes = [n for n in G.nodes if not G.nodes[n]['active']]
            active_edges = [e for e in G.edges if G.edges[e].get('active', False)]

            terminal_nodes = [n for n in active_nodes if G.nodes[n]['name'].isupper()]
            other_nodes = [n for n in active_nodes if not G.nodes[n]['name'].isupper()]

            nx.draw_networkx_nodes(G, pos, nodelist=inactive_nodes, node_size=100,
                                   node_color='#1a237e', alpha=0.5, node_shape='s', ax=ax)
            nx.draw_networkx_nodes(G, pos, nodelist=other_nodes, node_size=150,
                                   node_color='#1a237e', alpha=0.8, node_shape='o', ax=ax)
            nx.draw_networkx_nodes(G, pos, nodelist=terminal_nodes, node_size=200,
                                   node_color='#1a237e', alpha=1.0, node_shape='o', ax=ax)

            nx.draw_networkx_edges(G, pos, edgelist=active_edges, width=1.5,
                                   edge_color='#5D6D7E', alpha=0.8, arrows=True, arrowsize=10, ax=ax)

            labels = {n: G.nodes[n]['name'] for n in terminal_nodes}
            nx.draw_networkx_labels(G, pos, labels=labels,
                                    font_size=7, font_weight='bold', ax=ax,
                                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='none',
                                              boxstyle='round,pad=0.2'))

            def hover(event):
                if event.inaxes == ax:
                    for node, (x, y) in pos.items():
                        if ((x - event.xdata) ** 2 + (y - event.ydata) ** 2) < 0.0003:
                            full_name = G.nodes[node]['name']
                            annotation = ax.annotate(full_name,
                                                     xy=(x, y),
                                                     xytext=(10, 10),
                                                     textcoords='offset points',
                                                     bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                                                     arrowprops=dict(arrowstyle='->'))
                            fig.canvas.draw_idle()
                            return
                    for child in ax.get_children():
                        if isinstance(child, plt.Annotation):
                            child.remove()
                            fig.canvas.draw_idle()

            # Connect the hover function to the figure
            #fig.canvas.mpl_connect('motion_notify_event', hover)

            legend_elements = [
                Line2D([0], [0], marker='o', color='w', label='Terminal Stop',
                       markerfacecolor='#1a237e', markersize=8),
                Line2D([0], [0], marker='o', color='w', label='Regular Stop',
                       markerfacecolor='#1a237e', markersize=8, alpha=0.8),
                Line2D([0], [0], marker='s', color='w', label='Inactive Stop',
                       markerfacecolor='#1a237e', markersize=8, alpha=0.5),
                Line2D([0], [0], color='#5D6D7E', lw=1.5, label='Active Connection')
            ]
            ax.legend(handles=legend_elements, loc='upper right', fontsize=7)
            ax.set_title(f"Tram Network (Status: {len(active_nodes)}/{len(G.nodes())} active stops)",
                         fontsize=9, pad=12)

            if pos:
                x_vals = [p[0] for p in pos.values()]
                y_vals = [p[1] for p in pos.values()]
                ax.set_xlim(min(x_vals) - 0.01, max(x_vals) + 0.01)
                ax.set_ylim(min(y_vals) - 0.01, max(y_vals) + 0.01)

            container = tk.Frame(graph_frame)
            container.pack(fill=tk.BOTH, expand=True)

            canvas = backend_tkagg.FigureCanvasTkAgg(fig, master=container)
            canvas.draw()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, container, pack_toolbar=False)
            toolbar.update()
            toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        except Exception as e:
            print(f"Graph error: {e}")
            container = tk.Frame(graph_frame)
            container.pack(fill=tk.BOTH, expand=True)
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, f"Błąd: {str(e)}", ha='center', va='center', fontsize=12)
            ax.set_axis_off()
            canvas = backend_tkagg.FigureCanvasTkAgg(fig, master=container)
            canvas.draw()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    OUTPUT_PATH = Path(__file__).parent
    ASSETS_PATH = OUTPUT_PATH / Path("./assets")

    window = tk.Tk()
    window.title("Tram network management and optimization")
    window.geometry("1600x1000")
    window.configure(bg="#C4D8F2")

    style = ttk.Style()
    style.theme_use('clam')

    # Main button style
    style.configure('TButton', font=BUTTON_FONT,
                    foreground='white', background='#3A7CA5', borderwidth=0)
    style.map('TButton', background=[('active', '#2C5F8A')])

    # Info panel style
    style.configure("Blue.TFrame", background="#E6F2FF")
    style.configure("Info.TLabelframe", font=HEADER_FONT,
                    background="#F0F8FF", relief="flat")
    style.configure("Info.TCombobox", font=BODY_FONT,
                    fieldbackground="#E6F2FF", background="#E6F2FF")

    canvas = tk.Canvas(window, bg="#C4D8F2", height=900, width=1400,
                       bd=0, highlightthickness=0, relief="ridge")
    canvas.place(x=0, y=0, relwidth=1, relheight=1)

    graph_frame = tk.Frame(window, bg="#F0F8FF", height=850, width=1200)
    graph_frame.place(x=50, y=50)

    rounded_rectangle(canvas, 1300, 25, 1580, 875, fill="#F0F8FF",
                      outline="#3A7CA5", width=2, radius=20)

    canvas.create_text(1320, 50, anchor="nw", text="General info",
                       fill="#000000", font=TITLE_FONT)
    canvas.create_text(1360, 300, anchor="nw", text="Manage",
                       fill="#000000", font=TITLE_FONT)

    button_texts = ["Upload files", "Turn off/on stops", "Add/remove stops",
                    "Connect stops", "Find Path", "Optimize", "Live view"]
    button_coords = [(1320, 750, 240, 48), (1320, 350, 240, 35), (1320, 400, 240, 35),
                     (1320, 450, 240, 35), (1320, 500, 240, 35), (1320, 550, 240, 35), (1350, 600, 180, 50)]
    buttons = {}
    for i, (x, y, w, h) in enumerate(button_coords):
        if button_texts[i] == "Find Path":
            button_command = open_shortest_path_window
        elif button_texts[i] == "Optimize":
            button_command = optimize_stop
        elif button_texts[i] == "Live view":
            button_command = realtime_map
        elif button_texts[i] == "Turn off/on stops":
            button_command = turn_off_on_the_stops
        elif button_texts[i] == "Add/remove stops":
            button_command = add_delete_stop
        elif button_texts[i] == "Connect stops":
            button_command = connect_stops
        elif button_texts[i] == "Upload files":
            button_command = file_import
        else:
            button_command = lambda text=button_texts[i]: on_button_click(text)
        buttons[i] = ttk.Button(window, text=button_texts[i], style='TButton', command=button_command)
        buttons[i].place(x=x, y=y, width=w, height=h)

    style.configure('OpenGraph.TButton', font=('Inter', 16, 'bold'),
                    foreground='white', background='#2C5F8A', borderwidth=0)
    style.map('OpenGraph.TButton', background=[('active', '#3A7CA5')])

    style.configure("Info.TLabelframe", font=('Inter', 16, 'bold'),
                    background="#F0F8FF", relief="flat")
    style.configure("Info.TCombobox", font=('Inter', 10),
                    fieldbackground="#E6F2FF", background="#E6F2FF")

    create_tram_line_selector(window)
    create_stop_selector(window)
    refresh_graph()

    window.resizable(False, False)
    window.mainloop()

gui_main()