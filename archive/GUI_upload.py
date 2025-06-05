import tkinter as tk
from tkinter import filedialog, ttk
import shutil
import os
from ecstract_graph_edges import prepare
from pathlib import Path


def file_import():
    TITLE_FONT = ('Inter', 24, 'bold')
    HEADER_FONT = ('Inter', 18, 'bold')
    BODY_FONT = ('Inter', 14)
    BUTTON_FONT = ('Inter', 14, 'bold')

    def browse_files(entry, folder=False):
        if folder:
            directory = filedialog.askdirectory(initialdir="/", title="Select a Directory")
            entry.delete(0, tk.END)
            entry.insert(0, directory)
        else:
            filename = filedialog.askopenfilename(initialdir="/", title="Select a File",
                                                  filetypes=(("JSON files", "*.json*"), ("all files", "*.*")))
            entry.delete(0, tk.END)
            entry.insert(0, filename)

    def load_files(entry1, entry2, window):
        stops = entry1.get()
        timetables_dir = entry2.get()

        program_directory = os.path.dirname(os.path.abspath(__file__))

        stops_dest = os.path.join(program_directory, os.path.basename(stops))
        timetables_dest = os.path.join(program_directory, os.path.basename(timetables_dir))

        shutil.copy(stops, stops_dest)
        if os.path.isdir(timetables_dir):
            timetables_dest = os.path.join(program_directory, os.path.basename(timetables_dir))
            if not os.path.exists(timetables_dest):
                os.makedirs(timetables_dest)
            for item in os.listdir(timetables_dir):
                s = os.path.join(timetables_dir, item)
                d = os.path.join(timetables_dest, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, False, None)
                else:
                    shutil.copy2(s, d)
        else:
            shutil.copy(timetables_dir, timetables_dest)

        files_preparation()
        window.quit()
        window.destroy()

    def files_preparation():
        prepare()

    def gui_insert_files():
        window1 = tk.Tk()
        window1.title("Tram Network Data Import")
        window1.geometry("800x600")
        window1.configure(bg="#C4D8F2")

        style = ttk.Style()
        style.theme_use('clam')

        # Configure styles to match main GUI
        style.configure('TButton', font=BUTTON_FONT,
                        foreground='white', background='#3A7CA5', borderwidth=0)
        style.map('TButton', background=[('active', '#2C5F8A')])
        style.configure("Blue.TFrame", background="#E6F2FF")
        style.configure("Info.TLabelframe", font=HEADER_FONT,
                        background="#F0F8FF", relief="flat")
        style.configure("Info.TCombobox", font=BODY_FONT,
                        fieldbackground="#E6F2FF", background="#E6F2FF")

        canvas = tk.Canvas(window1, bg="#C4D8F2", height=600, width=800,
                           bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Title
        #canvas.create_text(400, 50, anchor="center",
                           #text="Tram Network Data Import",
                           #fill="#000000", font=TITLE_FONT)

        # Main container
        container = ttk.Frame(window1, style="Blue.TFrame")
        container.place(relx=0.5, rely=0.5, anchor="center", width=600, height=400)

        # Labels and entries
        label = ttk.Label(container, text="Import Data Files:", font=HEADER_FONT)
        label.pack(pady=(20, 20))

        # Stops file selection
        stops_frame = ttk.Frame(container)
        stops_frame.pack(pady=10, padx=20, fill='x')

        ttk.Label(stops_frame, text="Stops File:", font=BODY_FONT).pack(side='left', padx=5)
        stops_entry = ttk.Entry(stops_frame, font=BODY_FONT, width=30)
        stops_entry.pack(side='left', padx=5, expand=True, fill='x')
        browse_stops = ttk.Button(stops_frame, text="Browse",
                                  command=lambda: browse_files(stops_entry))
        browse_stops.pack(side='left', padx=5)

        # Timetables directory selection
        timetables_frame = ttk.Frame(container)
        timetables_frame.pack(pady=10, padx=20, fill='x')

        ttk.Label(timetables_frame, text="Timetables Directory:", font=BODY_FONT).pack(side='left', padx=5)
        timetables_entry = ttk.Entry(timetables_frame, font=BODY_FONT, width=30)
        timetables_entry.pack(side='left', padx=5, expand=True, fill='x')
        browse_timetables = ttk.Button(timetables_frame, text="Browse",
                                       command=lambda: browse_files(timetables_entry, folder=True))
        browse_timetables.pack(side='left', padx=5)

        # Upload button
        upload_btn = ttk.Button(container, text="Upload Files",
                                command=lambda: load_files(stops_entry, timetables_entry, window1))
        upload_btn.pack(pady=30)

        window1.resizable(False, False)
        window1.mainloop()

    gui_insert_files()
