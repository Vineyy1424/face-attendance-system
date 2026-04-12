import os
import sys
import math
import time
from collections import deque
import threading
import subprocess
from datetime import datetime, date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import cv2
import mysql.connector
from PIL import Image, ImageDraw, ImageTk

from db_schema import ensure_schema
from migration_runner import run_migrations
from student_attendance_ui import StudentAttendanceUI


DEFAULT_TEACHER_USERNAME = "admin"
DEFAULT_TEACHER_PASSWORD = "admin"


def mix_hex_color(color_a, color_b, amount):
    amount = max(0.0, min(1.0, amount))
    a_r, a_g, a_b = int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16)
    b_r, b_g, b_b = int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16)
    out_r = int(a_r + (b_r - a_r) * amount)
    out_g = int(a_g + (b_g - a_g) * amount)
    out_b = int(a_b + (b_b - a_b) * amount)
    return f"#{out_r:02x}{out_g:02x}{out_b:02x}"


def remove_dark_edge_background(image):
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width < 2 or height < 2:
        return rgba

    pixels = rgba.load()
    corner_points = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    ]

    sum_r, sum_g, sum_b = 0, 0, 0
    for x, y in corner_points:
        r, g, b, _ = pixels[x, y]
        sum_r += r
        sum_g += g
        sum_b += b

    bg_r = sum_r // len(corner_points)
    bg_g = sum_g // len(corner_points)
    bg_b = sum_b // len(corner_points)
    tolerance = 42

    def is_background(px, py):
        r, g, b, _ = pixels[px, py]
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        close_to_bg = (
            abs(r - bg_r) <= tolerance
            and abs(g - bg_g) <= tolerance
            and abs(b - bg_b) <= tolerance
        )
        return close_to_bg and luma < 95

    queue = deque()
    visited = set()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))

        if not is_background(x, y):
            continue

        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)

        if x > 0:
            queue.append((x - 1, y))
        if x < width - 1:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y < height - 1:
            queue.append((x, y + 1))

    return rgba


def prepare_logo_image(image, size):
    if "A" in image.getbands():
        alpha_min, _ = image.getchannel("A").getextrema()
        if alpha_min < 250:
            return image.resize((size, size), Image.LANCZOS)

    image = remove_dark_edge_background(image)
    return image.resize((size, size), Image.LANCZOS)


def find_logo_candidates(base_dir):
    assets_dir = os.path.join(base_dir, "assets")
    candidates = [
        os.path.join(assets_dir, "image-removebg-preview.png"),
        os.path.join(assets_dir, "truevision_logo.png"),
        os.path.join(assets_dir, "truevision_logo.jpg"),
        os.path.join(assets_dir, "truevision_logo.jpeg"),
        os.path.join(assets_dir, "truevision_ai_logo.png"),
        os.path.join(assets_dir, "image.png"),
        os.path.join(assets_dir, "logo.png"),
        os.path.join(assets_dir, "logo.jpg"),
        os.path.join(base_dir, "logo.png"),
    ]

    if os.path.isdir(assets_dir):
        for file_name in os.listdir(assets_dir):
            lower_name = file_name.lower()
            if lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
                candidates.append(os.path.join(assets_dir, file_name))

    unique_candidates = []
    seen = set()
    for path in candidates:
        if path not in seen:
            unique_candidates.append(path)
            seen.add(path)
    return unique_candidates


def open_db_connection():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="smart_attendance",
    )
    cursor = db.cursor()
    ensure_schema(db, cursor)
    return db, cursor


class SplashScreen:
    def __init__(self, root, base_dir, on_done):
        self.root = root
        self.base_dir = base_dir
        self.on_done = on_done
        self.progress = 0
        self.dot_count = 0
        self.glow_phase = 0.0

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.configure(bg="#020814")

        width, height = 760, 420
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x_pos = (screen_w - width) // 2
        y_pos = (screen_h - height) // 2
        self.window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        container = tk.Frame(self.window, bg="#020814", padx=40, pady=32)
        container.pack(fill="both", expand=True)

        self.logo_image = self._load_logo_image(160)
        self.logo_canvas = tk.Canvas(
            container,
            width=188,
            height=188,
            bg="#020814",
            highlightthickness=0,
            bd=0,
        )
        self.logo_canvas.pack(pady=(16, 12))
        self.logo_outer_ring = self.logo_canvas.create_oval(8, 8, 180, 180, outline="#123763", width=2)
        self.logo_inner_ring = self.logo_canvas.create_oval(20, 20, 168, 168, outline="#0a2a45", width=1)
        self.logo_canvas.create_image(94, 94, image=self.logo_image)

        tk.Label(
            container,
            text="TrueVision",
            bg="#020814",
            fg="#eaf8ff",
            font=("Segoe UI Semibold", 30),
        ).pack()

        tk.Label(
            container,
            text="Smart Face Attendance App",
            bg="#020814",
            fg="#8cc8ea",
            font=("Segoe UI", 12),
        ).pack(pady=(8, 22))

        self.loading_text = tk.Label(
            container,
            text="Loading",
            bg="#020814",
            fg="#cdeeff",
            font=("Segoe UI", 11),
        )
        self.loading_text.pack()

        self.progress_wrap = tk.Frame(container, bg="#10203f", height=14)
        self.progress_wrap.pack(fill="x", pady=(10, 0))
        self.progress_fill = tk.Frame(self.progress_wrap, bg="#00d9ff", width=0, height=14)
        self.progress_fill.place(x=0, y=0, relheight=1)

        self._animate()

    def _load_logo_image(self, size):
        candidates = find_logo_candidates(self.base_dir)

        logo_image = None
        for path in candidates:
            if os.path.exists(path):
                try:
                    logo_image = Image.open(path).convert("RGBA")
                    break
                except Exception:
                    logo_image = None

        if logo_image is None:
            logo_image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(logo_image)
            draw.ellipse((8, 8, size - 8, size - 8), fill=(64, 201, 198, 255))
            draw.ellipse((24, 24, size - 24, size - 24), fill=(10, 19, 41, 255))
            draw.text((size // 2 - 26, size // 2 - 20), "TV", fill=(232, 241, 255, 255))
        else:
            logo_image = prepare_logo_image(logo_image, size)

        return ImageTk.PhotoImage(logo_image)

    def _animate(self):
        self.progress += 2
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.loading_text.config(text=f"Loading{dots}")

        glow_strength = (math.sin(self.glow_phase) + 1) / 2
        outer_color = mix_hex_color("#123763", "#00d9ff", glow_strength)
        inner_color = mix_hex_color("#0a2a45", "#50e8ff", glow_strength)
        self.logo_canvas.itemconfigure(self.logo_outer_ring, outline=outer_color, width=2 + int(glow_strength * 2))
        self.logo_canvas.itemconfigure(self.logo_inner_ring, outline=inner_color, width=1 + int(glow_strength))
        self.glow_phase += 0.2

        total_width = self.progress_wrap.winfo_width() or 680
        fill_width = int((self.progress / 100) * total_width)
        self.progress_fill.config(width=max(0, fill_width))

        if self.progress < 100:
            self.window.after(40, self._animate)
            return

        self.window.after(220, self._finish)

    def _finish(self):
        self.window.destroy()
        self.on_done()


class RoleSelectionUI:
    def __init__(self, root, on_teacher, on_student):
        self.root = root
        self.on_teacher = on_teacher
        self.on_student = on_student

        self.bg = "#020814"
        self.card = "#091a35"
        self.text = "#eaf8ff"
        self.subtext = "#8cc8ea"
        self.accent = "#00d9ff"
        self.glow_phase = 0.0

        self.root.title("TrueVision - Select Role")
        self.root.configure(bg=self.bg)

        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Role.Base.TFrame", background=self.bg)
        style.configure("Role.Card.TFrame", background=self.card)
        style.configure(
            "Role.Title.TLabel",
            background=self.bg,
            foreground=self.text,
            font=("Segoe UI Semibold", 24),
        )
        style.configure(
            "Role.Subtitle.TLabel",
            background=self.bg,
            foreground=self.subtext,
            font=("Segoe UI", 11),
        )
        style.configure(
            "Role.CardTitle.TLabel",
            background=self.card,
            foreground=self.text,
            font=("Segoe UI Semibold", 15),
        )
        style.configure(
            "Role.CardText.TLabel",
            background=self.card,
            foreground=self.subtext,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Role.Accent.TButton",
            background=self.accent,
            foreground="#02101f",
            borderwidth=0,
            padding=(12, 9),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Role.Accent.TButton",
            background=[("active", "#50e8ff")],
            foreground=[("active", "#02101f")],
        )

    def _build_ui(self):
        wrapper = ttk.Frame(self.root, style="Role.Base.TFrame", padding=28)
        wrapper.pack(fill="both", expand=True)

        self.role_logo = self._load_role_logo(82)
        self.role_logo_canvas = tk.Canvas(
            wrapper,
            width=110,
            height=110,
            bg=self.bg,
            highlightthickness=0,
            bd=0,
        )
        self.role_logo_canvas.pack(pady=(2, 4))
        self.role_outer_ring = self.role_logo_canvas.create_oval(8, 8, 102, 102, outline="#123763", width=2)
        self.role_inner_ring = self.role_logo_canvas.create_oval(16, 16, 94, 94, outline="#0a2a45", width=1)
        self.role_logo_canvas.create_image(55, 55, image=self.role_logo)
        self._animate_role_glow()

        ttk.Label(wrapper, text="TrueVision", style="Role.Title.TLabel").pack(anchor="center")
        ttk.Label(
            wrapper,
            text="Login as Teacher to manage attendance or as Student to check attendance.",
            style="Role.Subtitle.TLabel",
        ).pack(anchor="center", pady=(6, 24))

        cards = ttk.Frame(wrapper, style="Role.Base.TFrame")
        cards.pack(fill="both", expand=True)

        teacher_card = ttk.Frame(cards, style="Role.Card.TFrame", padding=20)
        student_card = ttk.Frame(cards, style="Role.Card.TFrame", padding=20)

        teacher_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        student_card.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ttk.Label(teacher_card, text="Teacher Login", style="Role.CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            teacher_card,
            text="Add students, train model, and mark attendance using camera.",
            style="Role.CardText.TLabel",
        ).pack(anchor="w", pady=(8, 16))
        ttk.Button(
            teacher_card,
            text="Continue as Teacher",
            style="Role.Accent.TButton",
            command=self._teacher_login_flow,
        ).pack(anchor="w")

        ttk.Label(student_card, text="Student Login", style="Role.CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            student_card,
            text="Check your attendance records using roll number and birthdate.",
            style="Role.CardText.TLabel",
        ).pack(anchor="w", pady=(8, 16))
        ttk.Button(
            student_card,
            text="Continue as Student",
            style="Role.Accent.TButton",
            command=self._show_student_portal_splash,
        ).pack(anchor="w")

    def _load_role_logo(self, size):
        for path in find_logo_candidates(os.path.dirname(os.path.abspath(__file__))):
            if os.path.exists(path):
                try:
                    image = Image.open(path).convert("RGBA")
                    image = prepare_logo_image(image, size)
                    return ImageTk.PhotoImage(image)
                except Exception:
                    continue

        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, size - 1, size - 1), fill=(0, 217, 255, 255))
        inset = max(8, size // 5)
        draw.ellipse((inset, inset, size - inset, size - inset), fill=(2, 8, 20, 255))
        draw.text((size // 2 - 11, size // 2 - 9), "TV", fill=(234, 248, 255, 255))
        return ImageTk.PhotoImage(image)

    def _animate_role_glow(self):
        glow_strength = (math.sin(self.glow_phase) + 1) / 2
        outer_color = mix_hex_color("#123763", "#00d9ff", glow_strength)
        inner_color = mix_hex_color("#0a2a45", "#50e8ff", glow_strength)
        self.role_logo_canvas.itemconfigure(self.role_outer_ring, outline=outer_color, width=2 + int(glow_strength * 2))
        self.role_logo_canvas.itemconfigure(self.role_inner_ring, outline=inner_color, width=1 + int(glow_strength))
        self.glow_phase += 0.16
        self.root.after(60, self._animate_role_glow)

    def _teacher_login_flow(self):
        entered_username = simpledialog.askstring(
            "Teacher Login",
            "Enter teacher username:",
            parent=self.root,
        )

        if entered_username is None:
            return

        entered_username = entered_username.strip()
        if not entered_username:
            messagebox.showerror("Missing Data", "Teacher username is required.")
            return

        entered_password = simpledialog.askstring(
            "Teacher Login",
            f"Enter password for username '{entered_username}':",
            show="*",
            parent=self.root,
        )

        if entered_password is None:
            return

        teacher_info = self._verify_teacher_credentials(entered_username, entered_password)
        if teacher_info:
            self._show_teacher_portal_splash(teacher_info)
            return

        messagebox.showerror("Access Denied", "Incorrect teacher password.")

    def _verify_teacher_credentials(self, username, password):
        db = None
        cursor = None
        try:
            db, cursor = open_db_connection()
            cursor.execute(
                """
                SELECT teacher_id, username, full_name, last_login_at
                FROM teachers
                WHERE username=%s AND password=%s
                """,
                (username, password),
            )
            teacher = cursor.fetchone()

            if teacher:
                teacher_id, teacher_username, full_name, last_login_at = teacher
                cursor.execute(
                    "UPDATE teachers SET last_login_at=NOW() WHERE teacher_id=%s",
                    (teacher_id,),
                )
                db.commit()
                return {
                    "teacher_id": teacher_id,
                    "username": teacher_username,
                    "full_name": full_name or teacher_username,
                    "last_login_at": last_login_at,
                }

            return None

        except Exception:
            if password == DEFAULT_TEACHER_PASSWORD:
                return {
                    "teacher_id": None,
                    "username": DEFAULT_TEACHER_USERNAME,
                    "full_name": "Administrator",
                    "last_login_at": None,
                }
            return None

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    def _show_teacher_portal_splash(self, teacher_info):
        self._show_portal_splash(
            title="Entering Teacher Portal",
            subtitle="Preparing dashboard and attendance modules...",
            on_done=lambda: self.on_teacher(teacher_info),
        )

    def _show_student_portal_splash(self):
        self._show_portal_splash(
            title="Entering Student Portal",
            subtitle="Loading attendance viewer...",
            on_done=self.on_student,
        )

    def _show_portal_splash(self, title, subtitle, on_done):
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.configure(bg="#020814")

        width, height = 640, 360
        screen_w = splash.winfo_screenwidth()
        screen_h = splash.winfo_screenheight()
        x_pos = (screen_w - width) // 2
        y_pos = (screen_h - height) // 2
        splash.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        container = tk.Frame(splash, bg="#020814", padx=28, pady=26)
        container.pack(fill="both", expand=True)

        card = tk.Frame(container, bg="#091a35", highlightthickness=1, highlightbackground="#143a61")
        card.pack(fill="both", expand=True)

        body = tk.Frame(card, bg="#091a35", padx=28, pady=24)
        body.pack(fill="both", expand=True)

        logo_canvas = tk.Canvas(
            body,
            width=112,
            height=112,
            bg="#091a35",
            highlightthickness=0,
            bd=0,
        )
        logo_canvas.pack(pady=(2, 8))

        logo_image = self._load_role_logo(76)
        logo_outer_ring = logo_canvas.create_oval(8, 8, 104, 104, outline="#123763", width=2)
        logo_inner_ring = logo_canvas.create_oval(18, 18, 94, 94, outline="#0a2a45", width=1)
        logo_canvas.create_image(56, 56, image=logo_image)
        logo_canvas.image = logo_image

        tk.Label(
            body,
            text=title,
            bg="#091a35",
            fg="#eaf8ff",
            font=("Segoe UI Semibold", 22),
        ).pack(pady=(4, 4))

        subtitle_label = tk.Label(
            body,
            text=subtitle,
            bg="#091a35",
            fg="#8cc8ea",
            font=("Segoe UI", 10),
        )
        subtitle_label.pack(pady=(0, 14))

        progress_wrap = tk.Frame(body, bg="#10203f", height=12)
        progress_wrap.pack(fill="x", padx=8)
        progress_fill = tk.Frame(progress_wrap, bg="#00d9ff", width=0, height=12)
        progress_fill.place(x=0, y=0, relheight=1)

        percent_label = tk.Label(
            body,
            text="0%",
            bg="#091a35",
            fg="#cfefff",
            font=("Segoe UI Semibold", 10),
        )
        percent_label.pack(anchor="e", pady=(8, 0))

        detail_messages = [
            "Validating profile",
            "Loading interface components",
            "Syncing recent attendance",
            "Finalizing workspace",
        ]
        detail_var = tk.StringVar(value=detail_messages[0])
        tk.Label(
            body,
            textvariable=detail_var,
            bg="#091a35",
            fg="#6eb9de",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        state = {"value": 0, "phase": 0.0}

        def animate():
            state["value"] = min(100, state["value"] + 3)
            state["phase"] += 0.22

            glow_strength = (math.sin(state["phase"]) + 1) / 2
            outer_color = mix_hex_color("#123763", "#00d9ff", glow_strength)
            inner_color = mix_hex_color("#0a2a45", "#50e8ff", glow_strength)
            logo_canvas.itemconfigure(logo_outer_ring, outline=outer_color, width=2 + int(glow_strength * 2))
            logo_canvas.itemconfigure(logo_inner_ring, outline=inner_color, width=1 + int(glow_strength))

            total_width = progress_wrap.winfo_width() or 460
            fill_width = int((state["value"] / 100) * total_width)
            progress_fill.config(width=max(0, fill_width))
            percent_label.config(text=f"{state['value']}%")

            message_index = min(len(detail_messages) - 1, state["value"] // 25)
            detail_var.set(detail_messages[message_index])

            if state["value"] < 100:
                splash.after(24, animate)
                return

            splash.destroy()
            on_done()

        animate()


class SmartAttendanceUI:
    def __init__(self, root, on_back=None, teacher_info=None):
        self.root = root
        self.on_back = on_back
        self.teacher_info = teacher_info or {
            "username": DEFAULT_TEACHER_USERNAME,
            "full_name": "Administrator",
            "last_login_at": None,
        }
        self.root.title("TrueVision - Smart Attendance Dashboard")
        self.root.geometry("1080x720")
        self.root.minsize(960, 640)

        self.bg = "#020814"
        self.panel = "#091a35"
        self.panel_alt = "#0f274a"
        self.text = "#eaf8ff"
        self.subtext = "#8cc8ea"
        self.accent = "#00d9ff"
        self.warn = "#31d9ff"

        self.root.configure(bg=self.bg)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.status_var = tk.StringVar(value="Ready")
        self.busy_var = tk.BooleanVar(value=False)
        self.students_count_var = tk.StringVar(value="--")
        self.today_present_var = tk.StringVar(value="--")
        self.last_export_var = tk.StringVar(value="Not generated")
        self.attendance_rate_var = tk.StringVar(value="--")
        self.weekly_trend_var = tk.StringVar(value="--")
        self.teacher_session_var = tk.StringVar(value=self._build_teacher_session_text())

        self._configure_style()
        self._build_layout()
        self.refresh_dashboard_metrics()
        self.refresh_recent_attendance()

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Base.TFrame", background=self.bg)
        style.configure("Card.TFrame", background=self.panel)
        style.configure("AltCard.TFrame", background=self.panel_alt)
        style.configure("MetricCard.TFrame", background="#0c2244")

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
            "MetricLabel.TLabel",
            background="#0c2244",
            foreground="#95d9f5",
            font=("Segoe UI", 9),
        )
        style.configure(
            "MetricValue.TLabel",
            background="#0c2244",
            foreground="#eaf8ff",
            font=("Segoe UI Semibold", 18),
        )
        style.configure(
            "MetricBadge.TLabel",
            background="#0c2244",
            foreground="#5ce8ff",
            font=("Segoe UI Semibold", 8),
        )

        style.configure(
            "Accent.TButton",
            background=self.accent,
            foreground="#02101f",
            borderwidth=0,
            padding=(12, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#50e8ff")],
            foreground=[("active", "#02101f")],
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
            background=[("active", "#123763")],
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
            background="#123766",
            foreground="#d7f2ff",
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.accent)],
            foreground=[("selected", "#02101f")],
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

    def _build_layout(self):
        outer = ttk.Frame(self.root, style="Base.TFrame", padding=20)
        outer.pack(fill="both", expand=True)

        brand_row = ttk.Frame(outer, style="Base.TFrame")
        brand_row.pack(fill="x")

        self.brand_logo_image = self._load_header_logo(52)
        tk.Label(brand_row, image=self.brand_logo_image, bg=self.bg).pack(side="left", padx=(0, 12))

        if self.on_back:
            ttk.Button(
                brand_row,
                text="Back To Role Select",
                style="Ghost.TButton",
                command=self.on_back,
            ).pack(side="right")

        title_group = ttk.Frame(brand_row, style="Base.TFrame")
        title_group.pack(side="left", fill="x", expand=True)

        ttk.Label(
            title_group,
            text="TrueVision",
            style="Title.TLabel",
        ).pack(anchor="w")

        title = ttk.Label(
            title_group,
            text="Smart Attendance Dashboard",
            style="Subtitle.TLabel",
        )
        title.pack(anchor="w", pady=(2, 0))

        ttk.Label(
            title_group,
            textvariable=self.teacher_session_var,
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        subtitle = ttk.Label(
            outer,
            text="Register students, train the model, run attendance, and export reports from one place.",
            style="Subtitle.TLabel",
        )
        subtitle.pack(anchor="w", pady=(8, 16))

        stats_row = ttk.Frame(outer, style="Base.TFrame")
        stats_row.pack(fill="x", pady=(0, 14))

        self._create_metric_card(stats_row, "Total Students", self.students_count_var, "STU").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._create_metric_card(stats_row, "Present Today", self.today_present_var, "TOD").pack(
            side="left", fill="x", expand=True, padx=8
        )
        self._create_metric_card(stats_row, "Last Export", self.last_export_var, "XLS").pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

        analytics_row = ttk.Frame(outer, style="Base.TFrame")
        analytics_row.pack(fill="x", pady=(0, 14))

        self._create_metric_card(analytics_row, "Overall Present %", self.attendance_rate_var, "AVG").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._create_metric_card(analytics_row, "7-Day Trend", self.weekly_trend_var, "7D").pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

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

        status_bar = tk.Frame(outer, bg="#050f20", height=30)
        status_bar.pack(fill="x", pady=(14, 0))

        status_label = tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg="#050f20",
            fg="#cfefff",
            anchor="w",
            padx=10,
            font=("Segoe UI", 9),
        )
        status_label.pack(fill="x")

    def _create_metric_card(self, parent, label, value_var, badge):
        card = ttk.Frame(parent, style="MetricCard.TFrame", padding=12)
        ttk.Label(card, text=badge, style="MetricBadge.TLabel").pack(anchor="ne")
        ttk.Label(card, text=label, style="MetricLabel.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 0))
        return card

    def _create_scroll_container(self, parent):
        holder = ttk.Frame(parent, style="Base.TFrame")
        holder.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            holder,
            bg=self.bg,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(canvas, style="Base.TFrame")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scrollregion(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_content_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")

        def on_linux_scroll_up(_event):
            canvas.yview_scroll(-1, "units")

        def on_linux_scroll_down(_event):
            canvas.yview_scroll(1, "units")

        def bind_mousewheel(_event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_linux_scroll_up)
            canvas.bind_all("<Button-5>", on_linux_scroll_down)

        def unbind_mousewheel(_event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", update_content_width)
        content.bind("<Enter>", bind_mousewheel)
        content.bind("<Leave>", unbind_mousewheel)

        return content

    def _load_header_logo(self, size):
        candidates = find_logo_candidates(self.base_dir)

        for path in candidates:
            if os.path.exists(path):
                try:
                    logo = Image.open(path).convert("RGBA")
                    logo = prepare_logo_image(logo, size)
                    return ImageTk.PhotoImage(logo)
                except Exception:
                    continue

        logo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(logo)
        draw.ellipse((0, 0, size - 1, size - 1), fill=(91, 192, 190, 255))
        inset = max(6, size // 6)
        draw.ellipse(
            (inset, inset, size - inset, size - inset),
            fill=(11, 19, 43, 255),
        )
        draw.text((size // 2 - 10, size // 2 - 8), "TV", fill=(243, 247, 255, 255))
        return ImageTk.PhotoImage(logo)

    def _build_register_tab(self):
        content = self._create_scroll_container(self.register_tab)

        card = ttk.Frame(content, style="Card.TFrame", padding=18)
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
        content = self._create_scroll_container(self.ops_tab)

        grid = ttk.Frame(content, style="Base.TFrame")
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

        ttk.Button(
            left,
            text="Run DB Migrations",
            style="Ghost.TButton",
            command=self.run_db_migrations,
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

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=(14, 12))

        ttk.Label(right, text="Teacher Account", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            right,
            text="Create a new teacher or update an existing teacher password.",
            style="CardText.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        self.teacher_username_entry = self._packed_labeled_entry(right, "Teacher Username")
        self.teacher_name_entry = self._packed_labeled_entry(right, "Teacher Full Name")
        self.teacher_password_entry = self._packed_labeled_entry(right, "Teacher Password")
        self.teacher_password_entry.config(show="*")

        self.teacher_username_entry.insert(0, str(self.teacher_info.get("username", "admin")))
        self.teacher_name_entry.insert(0, str(self.teacher_info.get("full_name", "Administrator")))

        ttk.Button(
            right,
            text="Create / Update Teacher",
            style="Accent.TButton",
            command=self.save_teacher_account,
        ).pack(anchor="w", pady=(10, 0))

        teacher_actions = ttk.Frame(right, style="AltCard.TFrame")
        teacher_actions.pack(fill="x", pady=(10, 6))

        ttk.Button(
            teacher_actions,
            text="Load Selected",
            style="Ghost.TButton",
            command=self.load_selected_teacher,
        ).pack(side="left")

        ttk.Button(
            teacher_actions,
            text="Delete Selected",
            style="Ghost.TButton",
            command=self.delete_selected_teacher,
        ).pack(side="left", padx=8)

        ttk.Button(
            teacher_actions,
            text="Refresh Teachers",
            style="Ghost.TButton",
            command=self.refresh_teachers_list,
        ).pack(side="left")

        teacher_table_card = ttk.Frame(right, style="AltCard.TFrame", padding=8)
        teacher_table_card.pack(fill="both", expand=True, pady=(4, 0))

        teacher_columns = ("username", "full_name", "created_at", "last_login")
        self.teacher_tree = ttk.Treeview(teacher_table_card, columns=teacher_columns, show="headings", height=8)
        self.teacher_tree.heading("username", text="Username")
        self.teacher_tree.heading("full_name", text="Full Name")
        self.teacher_tree.heading("created_at", text="Created")
        self.teacher_tree.heading("last_login", text="Last Login")

        self.teacher_tree.column("username", width=110, anchor="w")
        self.teacher_tree.column("full_name", width=170, anchor="w")
        self.teacher_tree.column("created_at", width=130, anchor="center")
        self.teacher_tree.column("last_login", width=130, anchor="center")

        self.teacher_tree.pack(fill="both", expand=True)
        self.refresh_teachers_list()

    def _build_report_tab(self):
        content = self._create_scroll_container(self.report_tab)

        top = ttk.Frame(content, style="Base.TFrame")
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

        table_card = ttk.Frame(content, style="Card.TFrame", padding=14)
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
            bg="#071428",
            fg="#eaf8ff",
            insertbackground="#eaf8ff",
            relief="flat",
            font=("Segoe UI", 11),
        )
        entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", ipady=8)

        return entry

    def _packed_labeled_entry(self, parent, label_text):
        tk.Label(
            parent,
            text=label_text,
            bg=self.panel_alt,
            fg=self.subtext,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(8, 4))

        entry = tk.Entry(
            parent,
            bg="#071428",
            fg="#eaf8ff",
            insertbackground="#eaf8ff",
            relief="flat",
            font=("Segoe UI", 11),
        )
        entry.pack(fill="x", ipady=8)
        return entry

    def set_status(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        self.status_var.set(f"[{now}] {text}")

    def with_busy_state(self, is_busy):
        self.busy_var.set(is_busy)
        state = "disabled" if is_busy else "normal"
        self.register_button.configure(state=state)

    def get_db_connection(self):
        return open_db_connection()

    def clear_register_fields(self):
        self.name_entry.delete(0, tk.END)
        self.roll_entry.delete(0, tk.END)
        self.birth_entry.delete(0, tk.END)
        self.set_status("Registration fields cleared")

    def _build_teacher_session_text(self):
        full_name = self.teacher_info.get("full_name") or self.teacher_info.get("username") or "Teacher"
        last_login = self.teacher_info.get("last_login_at")
        if isinstance(last_login, datetime):
            last_login_text = last_login.strftime("%d %b %Y %H:%M")
        else:
            last_login_text = "first login"
        return f"Signed in as {full_name} | Last login: {last_login_text}"

    def save_teacher_account(self):
        username = self.teacher_username_entry.get().strip()
        full_name = self.teacher_name_entry.get().strip()
        password = self.teacher_password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Missing Data", "Username and password are required.")
            return

        if not full_name:
            full_name = "Teacher"

        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()
            cursor.execute("SELECT teacher_id FROM teachers WHERE username=%s", (username,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    "UPDATE teachers SET password=%s, full_name=%s WHERE username=%s",
                    (password, full_name, username),
                )
                action = "updated"
            else:
                cursor.execute(
                    "INSERT INTO teachers (username, password, full_name) VALUES (%s, %s, %s)",
                    (username, password, full_name),
                )
                action = "created"

            db.commit()
            self.teacher_password_entry.delete(0, tk.END)
            self.set_status(f"Teacher account {action}: {username}")
            messagebox.showinfo("Teacher Account", f"Teacher account {action} successfully.")
            self.refresh_teachers_list()

        except Exception as exc:
            messagebox.showerror("Teacher Account Error", str(exc))

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    def refresh_teachers_list(self):
        if not hasattr(self, "teacher_tree"):
            return

        for item in self.teacher_tree.get_children():
            self.teacher_tree.delete(item)

        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()
            cursor.execute(
                """
                SELECT username, full_name, created_at, last_login_at
                FROM teachers
                ORDER BY username ASC
                """
            )
            rows = cursor.fetchall()

            for row in rows:
                username, full_name, created_at, last_login = row
                self.teacher_tree.insert(
                    "",
                    tk.END,
                    values=(
                        username,
                        full_name or "Teacher",
                        self._format_timestamp(created_at),
                        self._format_timestamp(last_login),
                    ),
                )

        except Exception as exc:
            self.set_status("Could not load teachers list")
            messagebox.showerror("Teacher List Error", str(exc))

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    def load_selected_teacher(self):
        if not hasattr(self, "teacher_tree"):
            return

        selected = self.teacher_tree.selection()
        if not selected:
            messagebox.showwarning("Select Teacher", "Please select a teacher from the table.")
            return

        values = self.teacher_tree.item(selected[0], "values")
        username = values[0]
        full_name = values[1]

        self.teacher_username_entry.delete(0, tk.END)
        self.teacher_name_entry.delete(0, tk.END)
        self.teacher_password_entry.delete(0, tk.END)

        self.teacher_username_entry.insert(0, username)
        self.teacher_name_entry.insert(0, full_name)
        self.set_status(f"Loaded teacher: {username}")

    def delete_selected_teacher(self):
        if not hasattr(self, "teacher_tree"):
            return

        selected = self.teacher_tree.selection()
        if not selected:
            messagebox.showwarning("Select Teacher", "Please select a teacher from the table.")
            return

        values = self.teacher_tree.item(selected[0], "values")
        username = values[0]
        current_username = str(self.teacher_info.get("username", ""))

        if username == current_username:
            messagebox.showwarning("Action Blocked", "You cannot delete the currently logged-in teacher.")
            return

        if username == DEFAULT_TEACHER_USERNAME:
            messagebox.showwarning("Action Blocked", "Default admin account cannot be deleted.")
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete teacher account '{username}'?",
        )
        if not confirm:
            return

        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()
            cursor.execute("DELETE FROM teachers WHERE username=%s", (username,))
            db.commit()
            self.refresh_teachers_list()
            self.set_status(f"Deleted teacher: {username}")

        except Exception as exc:
            messagebox.showerror("Delete Error", str(exc))

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    def _format_timestamp(self, value):
        if isinstance(value, datetime):
            return value.strftime("%d %b %H:%M")
        if value is None:
            return "-"
        return str(value)

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

            self._capture_faces_on_ui_thread(student_id)

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

    def _capture_faces_on_ui_thread(self, student_id):
        capture_complete = threading.Event()
        state = {"error": None}

        def run_capture():
            try:
                self._capture_faces(student_id)
            except Exception as exc:
                state["error"] = exc
            finally:
                capture_complete.set()

        self.root.after(0, run_capture)
        capture_complete.wait()

        if state["error"]:
            raise state["error"]

    def _open_camera(self):
        backends = [None]
        if sys.platform == "darwin":
            backends = [cv2.CAP_AVFOUNDATION, None]
        elif sys.platform.startswith("win"):
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]

        for backend in backends:
            cam = cv2.VideoCapture(0) if backend is None else cv2.VideoCapture(0, backend)
            if cam is not None and cam.isOpened():
                return cam
            if cam is not None:
                cam.release()

        return None

    def _capture_faces(self, student_id):
        dataset_dir = os.path.join(self.base_dir, "dataset")
        if not os.path.exists(dataset_dir):
            os.makedirs(dataset_dir)

        cam = self._open_camera()
        if cam is None:
            raise RuntimeError(
                "Unable to open the camera. On macOS, allow camera access for Terminal/Python from System Settings."
            )

        face_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if face_detector.empty():
            cam.release()
            raise RuntimeError("Failed to load Haar cascade for face detection.")

        count = 0
        failed_reads = 0

        while True:
            ret, img = cam.read()
            if not ret or img is None:
                failed_reads += 1
                if failed_reads > 60:
                    raise RuntimeError("Camera is open but frames cannot be read.")
                time.sleep(0.03)
                continue

            failed_reads = 0

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

    def run_db_migrations(self):
        try:
            applied = run_migrations(self.base_dir)
            if applied:
                self.set_status(f"Applied {len(applied)} migration(s)")
                messagebox.showinfo("Migrations", "Applied migrations:\n" + "\n".join(applied))
            else:
                self.set_status("No pending migrations")
                messagebox.showinfo("Migrations", "No pending migrations.")

            self.refresh_teachers_list()
            self.refresh_dashboard_metrics()

        except Exception as exc:
            messagebox.showerror("Migration Error", str(exc))

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
            self.refresh_dashboard_metrics()

        except Exception as exc:
            self.set_status("Could not load attendance records")
            messagebox.showerror("Load Error", str(exc))

    def refresh_dashboard_metrics(self):
        db = None
        cursor = None
        try:
            db, cursor = self.get_db_connection()

            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (date.today(),))
            present_today = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*), SUM(status='Present') FROM attendance")
            total_rows, present_rows = cursor.fetchone()
            present_rows = present_rows or 0
            if total_rows:
                overall_rate = (present_rows / total_rows) * 100
                overall_rate_text = f"{overall_rate:.1f}%"
            else:
                overall_rate_text = "0.0%"

            today = date.today()
            current_start = today - timedelta(days=6)
            prev_start = today - timedelta(days=13)
            prev_end = today - timedelta(days=7)

            cursor.execute(
                "SELECT COUNT(*), SUM(status='Present') FROM attendance WHERE date BETWEEN %s AND %s",
                (current_start, today),
            )
            current_total, current_present = cursor.fetchone()
            current_total = current_total or 0
            current_present = current_present or 0

            cursor.execute(
                "SELECT COUNT(*), SUM(status='Present') FROM attendance WHERE date BETWEEN %s AND %s",
                (prev_start, prev_end),
            )
            prev_total, prev_present = cursor.fetchone()
            prev_total = prev_total or 0
            prev_present = prev_present or 0

            current_rate = ((current_present / current_total) * 100) if current_total else 0.0
            prev_rate = ((prev_present / prev_total) * 100) if prev_total else 0.0
            trend_delta = current_rate - prev_rate
            trend_arrow = "up" if trend_delta >= 0 else "down"
            trend_text = f"{trend_arrow} {abs(trend_delta):.1f}%"

            report_path = os.path.join(self.base_dir, "attendance_report.xlsx")
            if os.path.exists(report_path):
                export_time = datetime.fromtimestamp(os.path.getmtime(report_path)).strftime("%d %b %H:%M")
            else:
                export_time = "Not generated"

            self.students_count_var.set(str(total_students))
            self.today_present_var.set(str(present_today))
            self.last_export_var.set(export_time)
            self.attendance_rate_var.set(overall_rate_text)
            self.weekly_trend_var.set(trend_text)

        except Exception:
            self.students_count_var.set("--")
            self.today_present_var.set("--")
            self.last_export_var.set("Unavailable")
            self.attendance_rate_var.set("--")
            self.weekly_trend_var.set("--")

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()


def main():
    root = tk.Tk()

    root.withdraw()

    def clear_root_window():
        for widget in root.winfo_children():
            widget.destroy()

    def launch_teacher_ui(teacher_info=None):
        clear_root_window()
        SmartAttendanceUI(root, on_back=launch_role_selection, teacher_info=teacher_info)

    def launch_student_ui():
        clear_root_window()
        StudentAttendanceUI(root, on_back=launch_role_selection)

    def launch_role_selection():
        root.deiconify()
        clear_root_window()
        RoleSelectionUI(root, on_teacher=launch_teacher_ui, on_student=launch_student_ui)

    SplashScreen(
        root=root,
        base_dir=os.path.dirname(os.path.abspath(__file__)),
        on_done=launch_role_selection,
    )

    root.mainloop()


if __name__ == "__main__":
    main()
