import tkinter as tk
from tkinter import ttk, messagebox

import mysql.connector

from db_schema import ensure_schema


class StudentAttendanceUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Student Attendance")
        self.root.geometry("860x560")
        self.root.minsize(760, 500)
        self.root.configure(bg="#0f172a")

        self.bg = "#0f172a"
        self.panel = "#111c34"
        self.text = "#e8edf7"
        self.muted = "#9fb2d8"
        self.accent = "#4cc9f0"

        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Main.TFrame", background=self.bg)
        style.configure("Panel.TFrame", background=self.panel)

        style.configure(
            "Title.TLabel",
            background=self.bg,
            foreground=self.text,
            font=("Segoe UI Semibold", 19),
        )
        style.configure(
            "Muted.TLabel",
            background=self.bg,
            foreground=self.muted,
            font=("Segoe UI", 10),
        )

        style.configure(
            "Accent.TButton",
            background=self.accent,
            foreground="#05101f",
            padding=(10, 7),
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#80def8")],
            foreground=[("active", "#05101f")],
        )

        style.configure(
            "Treeview",
            background="#0b1428",
            fieldbackground="#0b1428",
            foreground="#e4edff",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#25385d",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
        )

    def _build_ui(self):
        outer = ttk.Frame(self.root, style="Main.TFrame", padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Student Attendance", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Enter roll number and birthdate to view attendance table.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        form = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        form.pack(fill="x")

        tk.Label(
            form,
            text="Roll Number",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="w")

        self.roll_entry = tk.Entry(
            form,
            bg="#0b1428",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11),
        )
        self.roll_entry.grid(row=1, column=0, sticky="ew", ipady=8)

        tk.Label(
            form,
            text="Birthdate (YYYY-MM-DD)",
            bg=self.panel,
            fg=self.muted,
            font=("Segoe UI", 10),
        ).grid(row=0, column=1, sticky="w", padx=(14, 0))

        self.birthdate_entry = tk.Entry(
            form,
            bg="#0b1428",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11),
        )
        self.birthdate_entry.grid(row=1, column=1, sticky="ew", padx=(14, 0), ipady=8)

        ttk.Button(
            form,
            text="Load Attendance",
            style="Accent.TButton",
            command=self.load_attendance,
        ).grid(row=1, column=2, padx=(14, 0), sticky="ew")

        form.columnconfigure(0, weight=2)
        form.columnconfigure(1, weight=2)
        form.columnconfigure(2, weight=1)

        table_card = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        table_card.pack(fill="both", expand=True, pady=(14, 0))

        columns = ("date", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        self.tree.heading("date", text="Date")
        self.tree.heading("status", text="Status")
        self.tree.column("date", width=220, anchor="center")
        self.tree.column("status", width=220, anchor="center")
        self.tree.pack(fill="both", expand=True)

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

    def load_attendance(self):
        roll = self.roll_entry.get().strip()
        birthdate = self.birthdate_entry.get().strip()

        if not roll or not birthdate:
            messagebox.showerror("Missing Data", "Please enter roll number and birthdate.")
            return

        for row in self.tree.get_children():
            self.tree.delete(row)

        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()
            cursor.execute(
                "SELECT student_id FROM students WHERE roll_no=%s AND birthdate=%s",
                (roll, birthdate),
            )
            student = cursor.fetchone()

            if not student:
                messagebox.showerror("Login Failed", "Invalid roll number or birthdate.")
                return

            cursor.execute(
                """
                SELECT date, status
                FROM attendance
                WHERE student_id = %s
                ORDER BY date DESC
                """,
                (student[0],),
            )
            records = cursor.fetchall()

            if not records:
                messagebox.showinfo("No Records", "No attendance records found.")
                return

            for record in records:
                self.tree.insert("", tk.END, values=record)

        except Exception as exc:
            messagebox.showerror("Error", str(exc))

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()


def main():
    root = tk.Tk()
    StudentAttendanceUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
