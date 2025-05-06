import tkinter as tk
from tkinter import filedialog
import shutil
import os
from ecstract_graph_edges import prepare
from gui_general import rounded_rectangle, font_label, font_button, font_entry

def file_import():

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

        print(f"File 1: {stops_dest}")
        print(f"Directory 2: {timetables_dest}")
        files_preparation()
        window.quit()
        window.destroy()

    def files_preparation():
        prepare()

    def gui_insert_files():
        window1 = tk.Tk()
        window1.title("System optymalizacji sieci tramwajowej")
        window1.geometry("1200x766")
        window1.configure(bg="#BDD280")

        canvas = tk.Canvas(window1, bg="#BDD280", height=766, width=1200, bd=0, highlightthickness=0, relief="ridge")
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        canvas.create_text(240, 80, anchor="nw", text="System optymalizacji sieci tramwajowej", fill="#ffffff", font=("Inter", 30, "bold"))

        x1, y1, x2, y2 = 300, 200, 900, 600
        rounded_rectangle(canvas, x1, y1, x2, y2, fill="#F8F8F8", outline="#38761D", width=2, radius=20)
        label = tk.Label(window1, text="Wprowadź pliki danych:", fg="#467D48", font=("Helvetica", 15, "bold"))
        canvas.create_window(x1 + 180, y1 + 30, window=label, anchor="nw")

        label1 = tk.Label(window1, text="Lista przystanków:", bg="#F8F8F8", font=font_label)
        canvas.create_window(x1 + 80, y1 + 100, window=label1, anchor="nw")

        entry1 = tk.Entry(window1, width=50, font=font_entry)
        canvas.create_window(x1 + 80, y1 + 130, window=entry1, anchor="nw")

        button1 = tk.Button(window1, text="Wybierz plik", command=lambda: browse_files(entry1), font=font_button, bg="#467D48", fg="white")
        canvas.create_window(x1 + 450, y1 + 125, window=button1, anchor="nw")

        label2 = tk.Label(window1, text="Rozkłady jazdy:", bg="#F8F8F8", font=font_label)
        canvas.create_window(x1 + 80, y1 + 210, window=label2, anchor="nw")

        entry2 = tk.Entry(window1, width=50, font=font_entry)
        canvas.create_window(x1 + 80, y1 + 240, window=entry2, anchor="nw")

        button2 = tk.Button(window1, text="Wybierz folder", command=lambda: browse_files(entry2, folder=True), font=font_button, bg="#467D48", fg="white")
        canvas.create_window(x1 + 450, y1 + 225, window=button2, anchor="nw")

        button3 = tk.Button(window1, text="Wgraj oba pliki", font=font_button, bg="#467D48", fg="white",
                            command=lambda: load_files(entry1, entry2, window1))
        canvas.create_window((x1 + x2) // 2, y2 - 80, window=button3, anchor="n")

        window1.resizable(False, False)
        window1.mainloop()

    gui_insert_files()
