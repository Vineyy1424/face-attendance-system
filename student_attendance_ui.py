import tkinter as tk
from tkinter import ttk, messagebox

import mysql.connector

from db_schema import ensure_schema


class StudentAttendanceUI:
    def __init__(self, root, on_back=None):
        self.root = root
        self.on_back = on_back
        self.root.title("TrueVision - Student Attendance")
        self.root.geometry("860x560")
        self.root.minsize(760, 500)
        self.root.configure(bg="#020814")

        self.bg = "#020814"
        self.panel = "#091a35"
        self.text = "#eaf8ff"
        self.muted = "#8cc8ea"
        self.accent = "#00d9ff"
        self.summary_var = tk.StringVar(value="No records loaded")

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
            foreground="#02101f",
            padding=(10, 7),
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Ghost.TButton",
            background=self.panel,
            foreground=self.text,
            borderwidth=1,
            relief="solid",
            padding=(10, 7),
            font=("Segoe UI", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#50e8ff")],
            foreground=[("active", "#02101f")],
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#123763")],
            foreground=[("active", self.text)],
        )

        style.configure(
            "Treeview",
            background="#071428",
            fieldbackground="#071428",
            foreground="#dcf3ff",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#113965",
            foreground="#eaf8ff",
            font=("Segoe UI Semibold", 10),
        )

    def _build_ui(self):
        outer = ttk.Frame(self.root, style="Main.TFrame", padding=18)
        outer.pack(fill="both", expand=True)

        header_card = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        header_card.pack(fill="x", pady=(0, 12))

        ttk.Label(header_card, text="Student Attendance Portal", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header_card,
            text="Enter roll number and birthdate to securely view your attendance timeline.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 2))
        ttk.Label(
            header_card,
            textvariable=self.summary_var,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        if self.on_back:
            ttk.Button(
                header_card,
                text="Back To Role Select",
                style="Ghost.TButton",
                command=self.on_back,
            ).pack(anchor="e", pady=(8, 0))

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
            bg="#071428",
            fg="#eaf8ff",
            insertbackground="#eaf8ff",
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
            bg="#071428",
            fg="#eaf8ff",
            insertbackground="#eaf8ff",
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

        ttk.Button(
            form,
            text="Clear",
            style="Ghost.TButton",
            command=self.clear_form,
        ).grid(row=1, column=3, padx=(8, 0), sticky="ew")

        form.columnconfigure(0, weight=2)
        form.columnconfigure(1, weight=2)
        form.columnconfigure(2, weight=1)
        form.columnconfigure(3, weight=1)

        table_card = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        table_card.pack(fill="both", expand=True, pady=(14, 0))

        columns = ("date", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        self.tree.heading("date", text="Date")
        self.tree.heading("status", text="Status")
        self.tree.column("date", width=220, anchor="center")
        self.tree.column("status", width=220, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("even", background="#071428")
        self.tree.tag_configure("odd", background="#0a1a31")

    def clear_form(self):
        self.roll_entry.delete(0, tk.END)
        self.birthdate_entry.delete(0, tk.END)
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.summary_var.set("No records loaded")

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
                self.summary_var.set("Login failed. Try correct roll number and birthdate.")
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
                self.summary_var.set("No attendance records found for this account.")
                return

            for index, record in enumerate(records):
                row_tag = "even" if index % 2 == 0 else "odd"
                self.tree.insert("", tk.END, values=record, tags=(row_tag,))

            self.summary_var.set(f"Loaded {len(records)} attendance entries")

        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self.summary_var.set("Unable to load attendance due to an unexpected error")

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
