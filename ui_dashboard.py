import os
import sys
import threading
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import mysql.connector

from db_schema import ensure_schema


class SmartAttendanceUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Attendance Dashboard")
        self.root.geometry("1080x720")
        self.root.minsize(960, 640)

        self.bg = "#0b132b"
        self.panel = "#1c2541"
        self.panel_alt = "#1b2f52"
        self.text = "#f3f7ff"
        self.subtext = "#b8c3d9"
        self.accent = "#5bc0be"
        self.warn = "#f4a261"

        self.root.configure(bg=self.bg)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.status_var = tk.StringVar(value="Ready")
        self.busy_var = tk.BooleanVar(value=False)

        self._configure_style()
        self._build_layout()
        self.refresh_recent_attendance()

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Base.TFrame", background=self.bg)
        style.configure("Card.TFrame", background=self.panel)
        style.configure("AltCard.TFrame", background=self.panel_alt)

        style.configure(
            "Title.TLabel",
            background=self.bg,
            foreground=self.text,
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.bg,
            foreground=self.subtext,
            font=("Segoe UI", 11),
        )
        style.configure(
            "CardTitle.TLabel",
            background=self.panel,
            foreground=self.text,
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "CardText.TLabel",
            background=self.panel,
            foreground=self.subtext,
            font=("Segoe UI", 10),
        )

        style.configure(
            "Accent.TButton",
            background=self.accent,
            foreground="#0a0f1f",
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#7de0de")],
            foreground=[("active", "#0a0f1f")],
        )

        style.configure(
            "Ghost.TButton",
            background=self.panel,
            foreground=self.text,
            borderwidth=1,
            relief="solid",
            padding=(12, 8),
            font=("Segoe UI", 10),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#2a3a63")],
            foreground=[("active", self.text)],
        )

        style.configure(
            "TNotebook",
            background=self.bg,
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )
        style.configure(
            "TNotebook.Tab",
            background="#243b64",
            foreground="#d7e2ff",
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.accent)],
            foreground=[("selected", "#0a0f1f")],
        )

        style.configure(
            "Treeview",
            background="#12213f",
            fieldbackground="#12213f",
            foreground="#dbe6ff",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#223a63",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
        )

    def _build_layout(self):
        outer = ttk.Frame(self.root, style="Base.TFrame", padding=20)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="Smart Attendance Dashboard", style="Title.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            outer,
            text="Register students, train the model, run attendance, and export reports from one place.",
            style="Subtitle.TLabel",
        )
        subtitle.pack(anchor="w", pady=(4, 16))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        self.register_tab = ttk.Frame(notebook, style="Base.TFrame", padding=16)
        self.ops_tab = ttk.Frame(notebook, style="Base.TFrame", padding=16)
        self.report_tab = ttk.Frame(notebook, style="Base.TFrame", padding=16)

        notebook.add(self.register_tab, text="Register")
        notebook.add(self.ops_tab, text="Operations")
        notebook.add(self.report_tab, text="Reports")

        self._build_register_tab()
        self._build_ops_tab()
        self._build_report_tab()

        status_bar = tk.Frame(outer, bg="#091022", height=30)
        status_bar.pack(fill="x", pady=(14, 0))

        status_label = tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg="#091022",
            fg="#d6e4ff",
            anchor="w",
            padx=10,
            font=("Segoe UI", 9),
        )
        status_label.pack(fill="x")

    def _build_register_tab(self):
        card = ttk.Frame(self.register_tab, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="Student Registration", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            card,
            text="Capture 40 face samples and auto-train model after registration.",
            style="CardText.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 16))

        self.name_entry = self._labeled_entry(card, "Name", 2)
        self.roll_entry = self._labeled_entry(card, "Roll Number", 4)
        self.birth_entry = self._labeled_entry(card, "Birthdate (YYYY-MM-DD)", 6)

        self.register_button = ttk.Button(
            card,
            text="Register + Capture + Train",
            style="Accent.TButton",
            command=self.start_registration_flow,
        )
        self.register_button.grid(row=8, column=0, pady=(18, 0), sticky="w")

        ttk.Button(
            card,
            text="Clear",
            style="Ghost.TButton",
            command=self.clear_register_fields,
        ).grid(row=8, column=1, pady=(18, 0), sticky="e")

        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

    def _build_ops_tab(self):
        grid = ttk.Frame(self.ops_tab, style="Base.TFrame")
        grid.pack(fill="both", expand=True)

        left = ttk.Frame(grid, style="Card.TFrame", padding=18)
        right = ttk.Frame(grid, style="AltCard.TFrame", padding=18)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Live Operations", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Use one-click actions to run your existing scripts.",
            style="CardText.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        ttk.Button(
            left,
            text="Start Attendance Camera",
            style="Accent.TButton",
            command=self.start_main_attendance,
        ).pack(fill="x", pady=6)

        ttk.Button(
            left,
            text="Train Model",
            style="Ghost.TButton",
            command=self.run_training,
        ).pack(fill="x", pady=6)

        ttk.Button(
            left,
            text="Open Portal (CLI)",
            style="Ghost.TButton",
            command=self.open_portal,
        ).pack(fill="x", pady=6)

        ttk.Button(
            left,
            text="Open Student Attendance Table",
            style="Ghost.TButton",
            command=self.open_student_attendance_ui,
        ).pack(fill="x", pady=6)

        ttk.Button(
            left,
            text="DB Health Check",
            style="Ghost.TButton",
            command=self.run_db_check,
        ).pack(fill="x", pady=6)

        ttk.Label(right, text="Notes", style="CardTitle.TLabel").pack(anchor="w")
        notes = [
            "Attendance runs in a separate process and opens camera window.",
            "Registration captures face images into dataset/.",
            "Model file is saved at trainer/trainer.yml.",
            "Export creates attendance_report.xlsx.",
        ]

        for note in notes:
            ttk.Label(right, text=f"- {note}", style="CardText.TLabel").pack(anchor="w", pady=2)

    def _build_report_tab(self):
        top = ttk.Frame(self.report_tab, style="Base.TFrame")
        top.pack(fill="x")

        ttk.Button(
            top,
            text="Export Attendance Report",
            style="Accent.TButton",
            command=self.export_report,
        ).pack(side="left")

        ttk.Button(
            top,
            text="Open Excel File",
            style="Ghost.TButton",
            command=self.open_report_file,
        ).pack(side="left", padx=10)

        ttk.Button(
            top,
            text="Refresh Recent Attendance",
            style="Ghost.TButton",
            command=self.refresh_recent_attendance,
        ).pack(side="left")

        table_card = ttk.Frame(self.report_tab, style="Card.TFrame", padding=14)
        table_card.pack(fill="both", expand=True, pady=(14, 0))

        ttk.Label(table_card, text="Recent Attendance", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))

        columns = ("student_id", "name", "date", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        self.tree.heading("student_id", text="Student ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("date", text="Date")
        self.tree.heading("status", text="Status")

        self.tree.column("student_id", width=110, anchor="center")
        self.tree.column("name", width=240, anchor="w")
        self.tree.column("date", width=150, anchor="center")
        self.tree.column("status", width=130, anchor="center")

        self.tree.pack(fill="both", expand=True)

    def _labeled_entry(self, parent, label_text, row):
        label = tk.Label(
            parent,
            text=label_text,
            bg=self.panel,
            fg=self.subtext,
            font=("Segoe UI", 10),
        )
        label.grid(row=row, column=0, sticky="w", pady=(8, 4))

        entry = tk.Entry(
            parent,
            bg="#0f1b35",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11),
        )
        entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", ipady=8)

        return entry

    def set_status(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        self.status_var.set(f"[{now}] {text}")

    def with_busy_state(self, is_busy):
        self.busy_var.set(is_busy)
        state = "disabled" if is_busy else "normal"
        self.register_button.configure(state=state)

    def get_db_connection(self):
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="smart_attendance",
        )
        cursor = db.cursor()
        ensure_schema(db, cursor)
        return db, cursor

    def clear_register_fields(self):
        self.name_entry.delete(0, tk.END)
        self.roll_entry.delete(0, tk.END)
        self.birth_entry.delete(0, tk.END)
        self.set_status("Registration fields cleared")

    def start_registration_flow(self):
        if self.busy_var.get():
            return

        name = self.name_entry.get().strip()
        roll_no = self.roll_entry.get().strip()
        birthdate = self.birth_entry.get().strip()

        if not name or not roll_no or not birthdate:
            messagebox.showerror("Missing Data", "Please fill Name, Roll Number, and Birthdate.")
            return

        self.with_busy_state(True)
        self.set_status("Creating student record and opening camera...")

        thread = threading.Thread(
            target=self._register_worker,
            args=(name, roll_no, birthdate),
            daemon=True,
        )
        thread.start()

    def _register_worker(self, name, roll_no, birthdate):
        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()

            cursor.execute(
                "INSERT INTO students (name, roll_no, birthdate) VALUES (%s, %s, %s)",
                (name, roll_no, birthdate),
            )
            db.commit()
            student_id = cursor.lastrowid

            self._capture_faces(student_id)

            subprocess.run(
                [sys.executable, os.path.join(self.base_dir, "train_model.py")],
                check=True,
                cwd=self.base_dir,
            )

            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Success",
                    f"Student registered (ID: {student_id}), face captured, and model trained.",
                ),
            )
            self.root.after(0, lambda: self.set_status(f"Registration complete for {name}"))
            self.root.after(0, self.clear_register_fields)

        except mysql.connector.Error as exc:
            self.root.after(0, lambda: messagebox.showerror("Database Error", str(exc)))
            self.root.after(0, lambda: self.set_status("Registration failed due to DB error"))

        except subprocess.CalledProcessError:
            self.root.after(0, lambda: messagebox.showerror("Training Error", "Training script failed."))
            self.root.after(0, lambda: self.set_status("Registration complete but training failed"))

        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("Error", str(exc)))
            self.root.after(0, lambda: self.set_status("Registration flow failed"))

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()
            self.root.after(0, lambda: self.with_busy_state(False))
            self.root.after(0, self.refresh_recent_attendance)

    def _capture_faces(self, student_id):
        dataset_dir = os.path.join(self.base_dir, "dataset")
        if not os.path.exists(dataset_dir):
            os.makedirs(dataset_dir)

        cam = cv2.VideoCapture(0)
        face_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        count = 0

        while True:
            ret, img = cam.read()
            if not ret:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                count += 1
                image_path = os.path.join(dataset_dir, f"user.{student_id}.{count}.jpg")
                cv2.imwrite(image_path, gray[y : y + h, x : x + w])
                cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
                cv2.imshow("Register Face", img)
                cv2.waitKey(120)

            if count >= 40:
                break

            if cv2.waitKey(1) == 27:
                break

        cam.release()
        cv2.destroyAllWindows()

    def start_main_attendance(self):
        try:
            subprocess.Popen(
                [sys.executable, os.path.join(self.base_dir, "Main.py")],
                cwd=self.base_dir,
            )
            self.set_status("Attendance process started")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def run_training(self):
        def worker():
            try:
                self.root.after(0, lambda: self.set_status("Training model..."))
                subprocess.run(
                    [sys.executable, os.path.join(self.base_dir, "train_model.py")],
                    check=True,
                    cwd=self.base_dir,
                )
                self.root.after(0, lambda: self.set_status("Model training complete"))
                self.root.after(0, lambda: messagebox.showinfo("Done", "Model trained successfully."))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Training Error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def open_portal(self):
        try:
            subprocess.Popen(
                [sys.executable, os.path.join(self.base_dir, "portal.py")],
                cwd=self.base_dir,
            )
            self.set_status("Portal opened in terminal process")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def open_student_attendance_ui(self):
        try:
            subprocess.Popen(
                [sys.executable, os.path.join(self.base_dir, "student_attendance_ui.py")],
                cwd=self.base_dir,
            )
            self.set_status("Student attendance table opened")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def run_db_check(self):
        try:
            db, cursor = self.get_db_connection()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            db.close()
            self.set_status("Database check passed")
            messagebox.showinfo("DB Health", "Tables found:\n" + "\n".join(tables))
        except Exception as exc:
            messagebox.showerror("DB Error", str(exc))

    def export_report(self):
        try:
            subprocess.run(
                [sys.executable, os.path.join(self.base_dir, "export_attendance.py")],
                check=True,
                cwd=self.base_dir,
            )
            self.set_status("Attendance report exported")
            messagebox.showinfo("Done", "attendance_report.xlsx generated.")
            self.refresh_recent_attendance()
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    def open_report_file(self):
        report_path = os.path.join(self.base_dir, "attendance_report.xlsx")
        if not os.path.exists(report_path):
            messagebox.showwarning("Missing File", "Run export first to create attendance_report.xlsx")
            return

        try:
            os.startfile(report_path)
            self.set_status("Opened attendance_report.xlsx")
        except Exception as exc:
            messagebox.showerror("Open File Error", str(exc))

    def refresh_recent_attendance(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            db, cursor = self.get_db_connection()
            cursor.execute(
                """
                SELECT students.student_id, students.name, attendance.date, attendance.status
                FROM attendance
                JOIN students ON students.student_id = attendance.student_id
                ORDER BY attendance.date DESC, attendance.attendance_id DESC
                LIMIT 100
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            db.close()

            for row in rows:
                self.tree.insert("", tk.END, values=row)

            self.set_status(f"Loaded {len(rows)} attendance records")

        except Exception as exc:
            self.set_status("Could not load attendance records")
            messagebox.showerror("Load Error", str(exc))


def main():
    root = tk.Tk()
    app = SmartAttendanceUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
