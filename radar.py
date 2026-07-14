"""Compact glass-style Codex Radar desktop dashboard."""

from __future__ import annotations

import ctypes
import colorsys
import json
import statistics
import tkinter as tk
from tkinter import colorchooser
import urllib.request
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageTk


APP_DIR = Path(__file__).resolve().parent
DATA_URL = "https://codexradar.com/current.json"
CACHE_PATH = APP_DIR / "current.cache.json"
DISMISS_FLAG = APP_DIR / ".dismissed_for_codex_session"
BACKGROUND = APP_DIR / "assets" / "radar-background.png"
CELESTIAL_ASSETS = {
    "sol": APP_DIR / "assets" / "celestial" / "sol.png",
    "terra": APP_DIR / "assets" / "celestial" / "terra.png",
    "luna": APP_DIR / "assets" / "celestial" / "luna.png",
}
REFRESH_MS = 30 * 60 * 1000

SURFACE = "#0c192c"
HEADER = "#0a1627"
CARD = "#10223a"
CARD_2 = "#142944"
LINE = "#4f89b9"
TEXT = "#f0f7ff"
MUTED = "#a6b9d1"
DIM = "#6d89aa"
GREEN = "#68efb6"
CYAN = "#69d2ff"
GOLD = "#ffd36a"
RED = "#ff8091"
SERIES = ("#ff718c", "#6fa8ff", "#ffd166", "#b58cff", "#55d6ff", "#ff9f55", "#a7df62", "#f17de1", "#54c9c0")


def hsv_hex(hue: float, saturation: float, value: float) -> str:
    red, green, blue = colorsys.hsv_to_rgb((hue % 360) / 360, saturation, value)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def color_variant(value: str, *, saturation: float | None = None, brightness: float = 1.0, hue_shift: float = 0.0) -> str:
    """Create a readable palette variant while preserving a picked base color."""
    red, green, blue = ImageColor.getrgb(value)
    hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    sat = sat if saturation is None else max(0.0, min(1.0, saturation))
    return hsv_hex((hue * 360 + hue_shift) % 360, sat, max(0.02, min(1.0, val * brightness)))


def recolor_by_hue(value: str, hue: float) -> str:
    red, green, blue = ImageColor.getrgb(value)
    _, saturation, brightness = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    return hsv_hex(hue, saturation, brightness)


def fetch_data() -> dict:
    request = urllib.request.Request(DATA_URL, headers={"User-Agent": "CodexDesktopRadar/1.1"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload
    except Exception:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        raise


def candidates(payload: dict) -> list[dict]:
    model_iq = payload["model_iq"]
    rows: list[dict] = []
    primary = dict(model_iq["latest"])
    primary["label"] = f"{primary.get('model', 'Sol').replace('gpt-5.6-', '').title()} {primary.get('reasoning_effort', 'max')}"
    primary["series"] = model_iq.get("recent_days", [])
    rows.append(primary)
    for entry in model_iq.get("comparisons", {}).values():
        row = dict(entry["latest"])
        row["label"] = entry["label"].replace("GPT-5.6 ", "")
        row["series"] = entry.get("recent_days", [])
        rows.append(row)
    return rows


def choose_recommendation(rows: list[dict]) -> tuple[dict, float, list[dict]]:
    median_iq = statistics.median(float(row["score"]) for row in rows)
    eligible = [row for row in rows if float(row["score"]) >= median_iq and float(row.get("cost_usd", 0)) > 0]
    return max(eligible, key=lambda row: float(row["score"]) / float(row["cost_usd"])), median_iq, eligible


def compact(value: str, limit: int = 47) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def utc8_tick(batch: str) -> str:
    parts = batch.split("-")
    if len(parts) < 4:
        return batch
    month, day, slot = parts[1], parts[2], parts[3]
    hour = "08:00" if slot.startswith("am") else "15:00" if slot == "pm_2" else "14:00" if slot.startswith("pm") else "23:00"
    return f"{month}/{day}\n{hour}"


def batch_sort_key(batch: str) -> datetime:
    parts = batch.split("-")
    try:
        slot = parts[3]
        hour = 8 if slot.startswith("am") else 15 if slot == "pm_2" else 14 if slot.startswith("pm") else 23
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]), hour)
    except (IndexError, ValueError):
        return datetime.min


class RoundedPanel(tk.Canvas):
    def __init__(self, master: tk.Misc, width: int, height: int, radius: int = 13) -> None:
        super().__init__(master, width=width, height=height, bg=SURFACE, bd=0, highlightthickness=0)
        self.panel_color = CARD
        r = radius
        self.create_rectangle(r, 1, width - r, height - 1, fill=CARD, outline="", tags=("panel_fill",))
        self.create_rectangle(1, r, width - 1, height - r, fill=CARD, outline="", tags=("panel_fill",))
        for x, y in ((1, 1), (width - 2 * r - 1, 1), (1, height - 2 * r - 1), (width - 2 * r - 1, height - 2 * r - 1)):
            self.create_oval(x, y, x + 2 * r, y + 2 * r, fill=CARD, outline="", tags=("panel_fill",))
        self.create_line(r, 1, width - r, 1, fill="#47759f", tags=("panel_border",))
        self.create_line(r, height - 1, width - r, height - 1, fill="#31567c", tags=("panel_border",))
        self.create_line(1, r, 1, height - r, fill="#47759f", tags=("panel_border",))
        self.create_line(width - 1, r, width - 1, height - r, fill="#31567c", tags=("panel_border",))
        self.create_arc(1, 1, 2 * r + 1, 2 * r + 1, start=90, extent=90, style="arc", outline="#47759f", tags=("panel_border",))
        self.create_arc(width - 2 * r - 1, 1, width - 1, 2 * r + 1, start=0, extent=90, style="arc", outline="#47759f", tags=("panel_border",))
        self.create_arc(1, height - 2 * r - 1, 2 * r + 1, height - 1, start=180, extent=90, style="arc", outline="#31567c", tags=("panel_border",))
        self.create_arc(width - 2 * r - 1, height - 2 * r - 1, width - 1, height - 1, start=270, extent=90, style="arc", outline="#31567c", tags=("panel_border",))

    def set_backdrop(self, image: Image.Image, radius: int = 13) -> None:
        backdrop = image.copy().convert("RGBA")
        mask = Image.new("L", backdrop.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((1, 1, backdrop.width - 2, backdrop.height - 2), radius=radius, fill=255)
        backdrop.putalpha(ImageChops.multiply(backdrop.getchannel("A"), mask))
        self.backdrop_image = ImageTk.PhotoImage(backdrop)
        self.create_image(0, 0, image=self.backdrop_image, anchor="nw", tags=("panel_backdrop",))
        self.tag_raise("panel_border")


class RadarApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.width, self.expanded_height = 370, 306
        self.height = self.expanded_height
        self.collapsed = False
        self.interface_hue = 160.0
        self.background_hue = 212.0
        self.interface_color = hsv_hex(self.interface_hue, 0.55, 0.94)
        self.background_color = hsv_hex(self.background_hue, 0.50, 0.30)
        self.window_alpha = 0.90
        self.celestial_alpha = 0.50
        self.celestial_contrast = 1.0
        self.settings_window: tk.Toplevel | None = None
        self.settings_apply_job: str | None = None
        self.apply_theme_colors()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.window_alpha)
        self.root.configure(bg=SURFACE)
        screen_w = self.root.winfo_screenwidth()
        self.root.geometry(f"{self.width}x{self.height}+{max(12, screen_w - self.width - 22)}+70")
        self.drag_x = self.drag_y = 0
        self.payload: dict = {}
        self.rows: list[dict] = []
        self.recommended: dict = {}
        self.median_iq = 0.0
        self.celestial_body = Image.new("RGBA", (352, 256), (0, 0, 0, 0))
        self.chart_bg_image: ImageTk.PhotoImage | None = None
        self.make_ui()
        self.refresh()
        self.root.deiconify()
        self.root.after(80, self.round_window)
        self.root.after(1000, self.update_header_summary)

    def apply_theme_colors(self) -> None:
        global SURFACE, HEADER, CARD, CARD_2, LINE, GREEN, CYAN, DIM
        SURFACE = color_variant(self.background_color, brightness=0.62)
        HEADER = color_variant(self.background_color, brightness=0.48)
        CARD = color_variant(self.background_color, brightness=0.98)
        CARD_2 = color_variant(self.background_color, brightness=1.20)
        LINE = color_variant(self.interface_color, brightness=0.76)
        GREEN = color_variant(self.interface_color, brightness=1.08)
        CYAN = color_variant(self.interface_color, hue_shift=35, brightness=1.0)
        DIM = color_variant(self.background_color, brightness=1.65)

    def round_window(self) -> None:
        """Clip the borderless window to a soft rounded widget shape on Windows."""
        try:
            inner = self.root.winfo_id()
            outer = ctypes.windll.user32.GetParent(inner)
            for hwnd in {inner, outer}:
                if hwnd:
                    region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, self.width + 1, self.height + 1, 38, 38)
                    ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
        except Exception:
            pass

    def make_ui(self) -> None:
        self.refresh_background_image()
        self.bg_label = tk.Label(self.root, image=self.bg_image, bd=0, bg=SURFACE)
        self.bg_label.place(x=0, y=0, width=self.width, height=self.expanded_height)

        self.header = tk.Frame(self.root, bg=HEADER, height=34, highlightthickness=1, highlightbackground="#4d93c9")
        self.header.place(x=0, y=0, width=self.width, height=34)
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)
        self.header_title = tk.Label(self.header, text="Codex  雷达", bg=HEADER, fg=TEXT, font=("Microsoft YaHei UI", 10, "normal"))
        self.header_title.grid(row=0, column=0, padx=(12, 4), pady=6)
        self.status = tk.Label(self.header, text="更新 --:--", bg=HEADER, fg=GREEN, font=("Microsoft YaHei UI", 8, "normal"))
        self.status.grid(row=0, column=1, sticky="e", padx=2)
        self.settings_button = tk.Button(self.header, text="⚙", command=self.open_settings, bd=0, bg=HEADER, fg=TEXT, activebackground=CARD_2, activeforeground=TEXT, font=("Segoe UI Symbol", 10), cursor="hand2", width=2)
        self.settings_button.grid(row=0, column=2, padx=0)
        self.toggle_button = tk.Button(self.header, text="▴", command=self.toggle_collapsed, bd=0, bg=HEADER, fg=TEXT, activebackground=CARD_2, activeforeground=TEXT, font=("Segoe UI Symbol", 10), cursor="hand2", width=2)
        self.toggle_button.grid(row=0, column=3, padx=0)
        self.refresh_button = tk.Button(self.header, text="↻", command=self.refresh, bd=0, bg=HEADER, fg=TEXT, activebackground=CARD_2, activeforeground=TEXT, font=("Times New Roman", 11, "bold"), cursor="hand2", width=2)
        self.refresh_button.grid(row=0, column=4, padx=0)
        self.close_button = tk.Button(self.header, text="×", command=self.dismiss, bd=0, bg=HEADER, fg=TEXT, activebackground="#542333", activeforeground=TEXT, font=("Times New Roman", 15), cursor="hand2", width=2)
        self.close_button.grid(row=0, column=5, padx=(0, 4))
        for widget in (self.header, self.header_title, self.status):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
        self.body = tk.Frame(self.root, bg=SURFACE)
        self.body.place(x=9, y=41, width=352, height=256)

    def refresh_background_image(self) -> None:
        base = Image.open(BACKGROUND).convert("RGB").resize((self.width, self.expanded_height), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(base)
        dark = color_variant(self.background_color, brightness=0.20)
        light = color_variant(self.background_color, brightness=1.15)
        tinted = ImageOps.colorize(gray, dark, light)
        mixed = Image.blend(base, tinted, 0.65)
        self.bg_image = ImageTk.PhotoImage(mixed)

    def drag_start(self, event: tk.Event) -> None:
        self.drag_x, self.drag_y = event.x_root, event.y_root

    def drag_move(self, event: tk.Event) -> None:
        self.root.geometry(f"+{self.root.winfo_x() + event.x_root - self.drag_x}+{self.root.winfo_y() + event.y_root - self.drag_y}")
        self.drag_x, self.drag_y = event.x_root, event.y_root

    def update_header_summary(self) -> None:
        if self.collapsed and self.recommended:
            now = datetime.now().strftime("%H:%M")
            self.header_title.configure(text=f"{now} · IQ {self.recommended['score']:.0f} · {self.recommended['label']}")
        self.root.after(30_000, self.update_header_summary)

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if self.collapsed:
            self.height = 34
            self.body.place_forget()
            self.status.grid_remove()
            self.refresh_button.grid_remove()
            self.toggle_button.configure(text="▾")
            self.update_header_summary()
        else:
            self.height = self.expanded_height
            self.body.place(x=9, y=41, width=352, height=256)
            self.status.grid()
            self.refresh_button.grid()
            self.header_title.configure(text="Codex  雷达")
            self.toggle_button.configure(text="▴")
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.bg_label.place_configure(height=self.height)
        self.root.after(30, self.round_window)

    def open_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        width, height = 330, 470
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.overrideredirect(True)
        window.geometry(f"{width}x{height}+{max(0, self.root.winfo_x() - width - 12)}+{self.root.winfo_y()}")
        window.resizable(False, False)
        window.configure(bg=SURFACE)
        window.attributes("-topmost", True)
        window.attributes("-alpha", min(1.0, max(0.78, self.window_alpha + 0.06)))
        window.protocol("WM_DELETE_WINDOW", self.close_settings)

        panel = tk.Canvas(window, width=width, height=height, bg=SURFACE, bd=0, highlightthickness=0)
        panel.pack(fill="both", expand=True)
        panel.create_rectangle(15, 1, width - 15, height - 1, fill=CARD, outline="", tags=("fill",))
        panel.create_rectangle(1, 15, width - 1, height - 15, fill=CARD, outline="", tags=("fill",))
        panel.create_oval(1, 1, 29, 29, fill=CARD, outline="", tags=("fill",))
        panel.create_oval(width - 29, 1, width - 1, 29, fill=CARD, outline="", tags=("fill",))
        panel.create_oval(1, height - 29, 29, height - 1, fill=CARD, outline="", tags=("fill",))
        panel.create_oval(width - 29, height - 29, width - 1, height - 1, fill=CARD, outline="", tags=("fill",))
        panel.create_line(15, 1, width - 15, 1, fill=LINE, tags=("border",))
        panel.create_line(1, 15, 1, height - 15, fill=LINE, tags=("border",))
        panel.create_line(width - 1, 15, width - 1, height - 15, fill=LINE, tags=("border",))
        panel.create_line(15, height - 1, width - 15, height - 1, fill=LINE, tags=("border",))
        self.settings_panel = panel

        header = tk.Frame(window, bg=HEADER, height=38)
        header.place(x=1, y=1, width=width - 2, height=38)
        header.pack_propagate(False)
        self.settings_header = header
        self.settings_title = tk.Label(header, text="雷达设置", bg=HEADER, fg=TEXT, font=("Microsoft YaHei UI", 11, "normal"))
        self.settings_title.pack(side="left", padx=13, pady=8)
        self.settings_close_button = tk.Button(header, text="×", command=self.close_settings, bd=0, bg=HEADER, fg=TEXT, activebackground=CARD_2, activeforeground=TEXT, font=("Times New Roman", 15), cursor="hand2", width=2)
        self.settings_close_button.pack(side="right", padx=3)
        for widget in (header, self.settings_title):
            widget.bind("<ButtonPress-1>", self.settings_drag_start)
            widget.bind("<B1-Motion>", self.settings_drag_move)

        content = tk.Frame(window, bg=CARD)
        content.place(x=10, y=44, width=width - 20, height=height - 52)
        self.settings_content = content
        self.settings_labels: list[tk.Label] = []
        self.settings_rgb_labels: list[tk.Label] = []
        self.settings_section_labels: list[tk.Label] = []
        self.settings_scales: list[tk.Scale] = []

        color_heading = tk.Label(content, text="颜色取色器", bg=CARD, fg=CYAN, font=("Microsoft YaHei UI", 9, "normal"))
        color_heading.pack(anchor="w", padx=5, pady=(4, 1))
        self.settings_section_labels.append(color_heading)

        def add_color_row(title: str, target: str) -> None:
            frame = tk.Frame(content, bg=CARD)
            frame.pack(fill="x", padx=5, pady=1)
            label = tk.Label(frame, text=title, bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 8), width=9, anchor="w")
            label.pack(side="left")
            setattr(self, f"{target}_swatch", tk.Button(frame, text="取色", command=lambda: self.pick_color(target), bd=0, fg=TEXT, activeforeground=TEXT, font=("Microsoft YaHei UI", 8), cursor="hand2", width=6))
            swatch = getattr(self, f"{target}_swatch")
            swatch.pack(side="left", padx=(2, 8))
            rgb_label = tk.Label(frame, bg=CARD, fg=TEXT, font=("Times New Roman", 8), anchor="w")
            rgb_label.pack(side="left")
            setattr(self, f"{target}_rgb_label", rgb_label)
            self.settings_labels.extend((label, rgb_label))
            self.settings_rgb_labels.append(rgb_label)

        add_color_row("界面颜色", "interface")
        add_color_row("背景颜色", "background")
        display_heading = tk.Label(content, text="色调与显示", bg=CARD, fg=CYAN, font=("Microsoft YaHei UI", 9, "normal"))
        display_heading.pack(anchor="w", padx=5, pady=(5, 1))
        self.settings_section_labels.append(display_heading)

        def add_slider(title: str, start: float, end: float, value: float, resolution: float = 1.0) -> tk.Scale:
            frame = tk.Frame(content, bg=CARD)
            frame.pack(fill="x", padx=5, pady=0)
            label = tk.Label(frame, text=title, bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 8), anchor="w")
            label.pack(anchor="w")
            scale = tk.Scale(frame, from_=start, to=end, orient="horizontal", resolution=resolution, showvalue=True, command=self.schedule_settings_apply, bg=CARD, fg=TEXT, troughcolor=CARD_2, activebackground=GREEN, highlightthickness=0, bd=0, length=280)
            scale.set(value)
            scale.pack(fill="x", ipady=0)
            self.settings_labels.append(label)
            self.settings_scales.append(scale)
            return scale

        self.interface_hue_scale = add_slider("界面色调", 0, 360, self.interface_hue)
        self.background_hue_scale = add_slider("背景色调", 0, 360, self.background_hue)
        self.window_alpha_scale = add_slider("窗口透明度 %", 20, 100, self.window_alpha * 100)
        self.celestial_alpha_scale = add_slider("天体透明度 %", 0, 100, self.celestial_alpha * 100)
        self.celestial_contrast_scale = add_slider("天体对比度 %", 0, 100, self.celestial_contrast * 100)
        self.sync_setting_colors()
        window.after(30, self.round_settings_window)

    def round_settings_window(self) -> None:
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
        try:
            hwnd = self.settings_window.winfo_id()
            region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, 331, 471, 38, 38)
            ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
        except Exception:
            pass

    def settings_drag_start(self, event: tk.Event) -> None:
        self.settings_drag_x, self.settings_drag_y = event.x_root, event.y_root

    def settings_drag_move(self, event: tk.Event) -> None:
        if not self.settings_window:
            return
        self.settings_window.geometry(f"+{self.settings_window.winfo_x() + event.x_root - self.settings_drag_x}+{self.settings_window.winfo_y() + event.y_root - self.settings_drag_y}")
        self.settings_drag_x, self.settings_drag_y = event.x_root, event.y_root

    def sync_setting_colors(self) -> None:
        for target in ("interface", "background"):
            value = getattr(self, f"{target}_color")
            red, green, blue = ImageColor.getrgb(value)
            getattr(self, f"{target}_swatch").configure(bg=value, activebackground=value)
            getattr(self, f"{target}_rgb_label").configure(text=f"RGB {red}, {green}, {blue}  {value.upper()}")

    def pick_color(self, target: str) -> None:
        current = getattr(self, f"{target}_color")
        result = colorchooser.askcolor(color=current, title=f"选择{('界面' if target == 'interface' else '背景')}颜色", parent=self.settings_window)
        rgb, picked = result
        if not picked or not rgb:
            return
        setattr(self, f"{target}_color", picked)
        red, green, blue = (component / 255 for component in rgb)
        hue, _, _ = colorsys.rgb_to_hsv(red, green, blue)
        setattr(self, f"{target}_hue", hue * 360)
        scale = getattr(self, f"{target}_hue_scale", None)
        if scale:
            scale.set(hue * 360)
        self.sync_setting_colors()
        self.schedule_settings_apply()

    def close_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None

    def schedule_settings_apply(self, _value: str = "") -> None:
        if self.settings_apply_job:
            self.root.after_cancel(self.settings_apply_job)
        self.settings_apply_job = self.root.after(60, self.apply_visual_settings)

    def apply_visual_settings(self) -> None:
        self.settings_apply_job = None
        self.interface_hue = float(self.interface_hue_scale.get())
        self.background_hue = float(self.background_hue_scale.get())
        self.interface_color = recolor_by_hue(self.interface_color, self.interface_hue)
        self.background_color = recolor_by_hue(self.background_color, self.background_hue)
        self.window_alpha = float(self.window_alpha_scale.get()) / 100
        self.celestial_alpha = float(self.celestial_alpha_scale.get()) / 100
        self.celestial_contrast = float(self.celestial_contrast_scale.get()) / 100
        self.apply_theme_colors()
        self.root.attributes("-alpha", self.window_alpha)
        self.root.configure(bg=SURFACE)
        self.refresh_background_image()
        self.bg_label.configure(image=self.bg_image, bg=SURFACE)
        self.header.configure(bg=HEADER, highlightbackground=LINE)
        for widget in (self.header_title, self.status, self.settings_button, self.toggle_button, self.refresh_button, self.close_button):
            widget.configure(bg=HEADER)
        self.status.configure(fg=GREEN)
        for widget in (self.settings_button, self.toggle_button, self.refresh_button):
            widget.configure(fg=TEXT)
        self.body.configure(bg=SURFACE)
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.configure(bg=SURFACE)
            self.settings_window.attributes("-alpha", min(1.0, max(0.78, self.window_alpha + 0.06)))
            self.settings_panel.configure(bg=SURFACE)
            self.settings_panel.itemconfigure("fill", fill=CARD)
            self.settings_panel.itemconfigure("border", fill=LINE)
            self.settings_header.configure(bg=HEADER)
            self.settings_title.configure(bg=HEADER, fg=TEXT)
            self.settings_close_button.configure(bg=HEADER, fg=TEXT, activebackground=CARD_2)
            self.settings_content.configure(bg=CARD)
            for child in self.settings_content.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=CARD)
                    for nested in child.winfo_children():
                        if isinstance(nested, (tk.Label, tk.Scale)):
                            nested.configure(bg=CARD)
            for label in self.settings_labels:
                label.configure(bg=CARD, fg=MUTED)
            for label in self.settings_rgb_labels:
                label.configure(bg=CARD, fg=TEXT)
            for label in self.settings_section_labels:
                label.configure(bg=CARD, fg=CYAN)
            for scale in self.settings_scales:
                scale.configure(bg=CARD, fg=TEXT, troughcolor=CARD_2, activebackground=GREEN)
            self.sync_setting_colors()
        if self.rows:
            _, _, eligible = choose_recommendation(self.rows)
            self.render(eligible)
        self.update_header_summary()

    def label(self, parent: tk.Misc, text: str, *, x: int, y: int, size: int = 9, color: str = TEXT, bold: bool = False, width: int | None = None) -> tk.Label | int:
        if isinstance(parent, tk.Canvas):
            options: dict = {
                "text": text,
                "fill": color,
                "font": ("Microsoft YaHei UI", size, "bold" if bold else "normal"),
                "anchor": "nw",
                "justify": "left",
            }
            if width:
                options["width"] = width
            return parent.create_text(x, y, **options)
        label = tk.Label(parent, text=text, bg=getattr(parent, "panel_color", parent.cget("bg")), fg=color, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"), anchor="w", justify="left", wraplength=width or 1000)
        label.place(x=x, y=y)
        return label

    def panel(self, y: int, height: int) -> RoundedPanel:
        panel = RoundedPanel(self.body, 352, height)
        panel.set_backdrop(self.celestial_body.crop((0, y, 352, y + height)))
        panel.place(x=0, y=y, width=352, height=height)
        return panel

    def prepare_celestial(self, best: dict) -> None:
        model_key = str(best.get("model", "")).rsplit("-", 1)[-1].lower()
        asset_path = CELESTIAL_ASSETS.get(model_key)
        body = Image.new("RGBA", (352, 256), (0, 0, 0, 0))
        if asset_path and asset_path.exists():
            source = Image.open(asset_path).convert("RGBA")
            bbox = source.getbbox()
            if bbox:
                source = source.crop(bbox)
            source.thumbnail((245, 245), Image.Resampling.LANCZOS)
            alpha = source.getchannel("A")
            rgb = ImageEnhance.Contrast(source.convert("RGB")).enhance(self.celestial_contrast).convert("RGBA")
            rgb.putalpha(alpha.point(lambda value: round(value * self.celestial_alpha)))
            source = rgb
            body.alpha_composite(source, (352 - source.width + 22, 6))
        self.celestial_body = body

    def clear_body(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def refresh(self) -> None:
        self.status.configure(text="更新中", fg=GOLD)
        self.root.update_idletasks()
        try:
            self.payload = fetch_data()
            self.rows = candidates(self.payload)
            self.recommended, self.median_iq, eligible = choose_recommendation(self.rows)
            self.status.configure(text=datetime.now().strftime("更新 %H:%M"), fg=GREEN)
            self.render(eligible)
        except Exception:
            self.status.configure(text="离线", fg=RED)
            self.clear_body()
            self.label(self.body, "无法读取雷达数据", x=14, y=16, size=10, color=RED, bold=True)
        self.root.after(REFRESH_MS, self.refresh)

    def render(self, eligible: list[dict]) -> None:
        self.clear_body()
        best = self.recommended
        self.prepare_celestial(best)
        cost = float(best["cost_usd"])
        hero = self.panel(0, 60)
        hero.create_text(10, 7, text="当前平衡首选", fill=GREEN, font=("Microsoft YaHei UI", 7, "normal"), anchor="nw")
        self.label(hero, best["label"], x=10, y=19, size=14, color=TEXT, bold=True)
        self.label(hero, f"IQ {best['score']:.0f}", x=201, y=10, size=11, color=GREEN, bold=True)
        self.label(hero, f"${cost:.2f}", x=201, y=30, size=9, color=GOLD, bold=True)
        self.label(hero, f"中位数 {self.median_iq:.0f} 以上 · 单位费用 IQ 最优", x=10, y=43, size=7, color=MUTED)

        chart_panel = self.panel(66, 116)
        chart_panel.create_text(10, 7, text="IQ 趋势", fill=TEXT, font=("Microsoft YaHei UI", 8, "normal"), anchor="nw")
        chart_panel.create_text(213, 8, text=f"推荐：{best['label']}", fill=GREEN, font=("Microsoft YaHei UI", 7, "normal"), anchor="nw")
        chart = tk.Canvas(chart_panel, width=338, height=88, bg=CARD, highlightthickness=0)
        chart.place(x=6, y=23)
        chart_backdrop = self.celestial_body.crop((6, 89, 344, 177))
        self.chart_bg_image = ImageTk.PhotoImage(chart_backdrop)
        chart.create_image(0, 0, image=self.chart_bg_image, anchor="nw")
        self.draw_chart(chart)

        advice = self.panel(188, 68)
        high_iq = max(eligible, key=lambda row: (float(row["score"]), -float(row["cost_usd"])))
        # wall_seconds is the elapsed time for the benchmark batch.  The feed
        # does not expose per-request latency, so present the honest derived
        # metric: average elapsed benchmark time per task (using all tasks).
        task_count = max(1, int(best.get("tasks") or best.get("valid_tasks") or 1))
        average_benchmark_minutes = float(best.get("wall_seconds", 0)) / task_count / 60
        advice.create_text(10, 7, text="使用建议", fill=CYAN, font=("Microsoft YaHei UI", 7, "normal"), anchor="nw")
        level = {"low": "低", "medium": "中", "high": "高"}.get(self.payload.get("prediction", {}).get("level"), "—")
        self.label(advice, f"日常使用：{best['label']}", x=10, y=24, size=7, color=TEXT)
        self.label(advice, f"高难度使用：{high_iq['label']} · IQ {high_iq['score']:.0f}", x=178, y=24, size=7, color=TEXT)
        self.label(advice, f"平均评测耗时：{average_benchmark_minutes:.1f} 分/任务", x=10, y=44, size=7, color=MUTED)
        self.label(advice, f"近期自动重置概率：{level}", x=178, y=44, size=7, color=GOLD)

    def draw_chart(self, canvas: tk.Canvas) -> None:
        left, top, right, bottom = 22, 7, 225, 61
        legend_x = 241
        for score in (60, 90, 120):
            y = bottom - score / 150 * (bottom - top)
            canvas.create_line(left, y, right, y, fill=TEXT, dash=(2, 3))
            canvas.create_text(left - 5, y, text=str(score), fill=TEXT, font=("Times New Roman", 7), anchor="e")
        histories: dict[str, list[tuple[datetime, float]]] = {}
        for row in self.rows:
            history = sorted(
                [(batch_sort_key(point.get("date", "")), float(point.get("score", 0))) for point in row.get("series", [])],
                key=lambda item: item[0],
            )
            history = [item for item in history if item[0] != datetime.min]
            if history:
                histories[row["label"]] = history
        if not histories:
            return
        # A one-sample series is a current snapshot, not a useful chart origin.
        # Use the nearest shared start among histories with real trend data so
        # a newly added model cannot collapse every other line to one point.
        trend_histories = [history for history in histories.values() if len(history) >= 3]
        origin_histories = trend_histories or list(histories.values())
        common_start = max(history[0][0] for history in origin_histories)
        common_end = max(history[-1][0] for history in histories.values())
        span_seconds = max(1.0, (common_end - common_start).total_seconds())

        for step in range(5):
            tick_time = common_start + (common_end - common_start) * (step / 4)
            x = left + (right - left) * (step / 4)
            canvas.create_line(x, bottom + 1, x, bottom + 4, fill=TEXT)
            canvas.create_text(x, bottom + 5, text=tick_time.strftime("%m/%d\n%H:%M"), fill=TEXT, font=("Times New Roman", 6), justify="center", anchor="n")

        def catmull_rom(points: list[tuple[float, float]], steps: int = 24) -> list[tuple[float, float]]:
            if len(points) < 3:
                return points
            output: list[tuple[float, float]] = []
            for i in range(len(points) - 1):
                p0 = points[max(0, i - 1)]
                p1 = points[i]
                p2 = points[i + 1]
                p3 = points[min(len(points) - 1, i + 2)]
                for step in range(steps):
                    t = step / steps
                    t2, t3 = t * t, t * t * t
                    x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                    y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                    output.append((x, max(top, min(bottom, y))))
            output.append(points[-1])
            return output

        scale = 4
        layer = Image.new("RGBA", (338 * scale, 88 * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        featured_curve: list[tuple[float, float]] = []
        for index, row in enumerate(self.rows):
            history = histories.get(row["label"], [])
            samples = [(time, value) for time, value in history if time >= common_start]
            if samples and samples[0][0] > common_start:
                before = max((item for item in history if item[0] <= common_start), default=None, key=lambda item: item[0])
                after = min((item for item in history if item[0] >= common_start), default=None, key=lambda item: item[0])
                if before and after:
                    interval = max(1.0, (after[0] - before[0]).total_seconds())
                    ratio = (common_start - before[0]).total_seconds() / interval
                    start_value = before[1] + (after[1] - before[1]) * ratio
                    samples.insert(0, (common_start, start_value))
            points: list[tuple[float, float]] = []
            for time, value in samples:
                elapsed = (time - common_start).total_seconds()
                x = left + (right - left) * (elapsed / span_seconds)
                y = bottom - min(150, value) / 150 * (bottom - top)
                points.append((x, y))
            if not points:
                continue
            curve = catmull_rom(points) if len(points) >= 2 else points
            scaled_curve = [(round(x * scale), round(y * scale)) for x, y in curve]
            featured = row["label"] == self.recommended["label"]
            color = GREEN if featured else SERIES[index % len(SERIES)]
            if featured:
                featured_curve = curve
            else:
                rgb = ImageColor.getrgb(color)
                if len(scaled_curve) >= 2:
                    draw.line(scaled_curve, fill=(*rgb, 220), width=6, joint="curve")
                else:
                    x, y = scaled_curve[0]
                    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(*rgb, 220))

            legend_y = 4 + index * 9
            canvas.create_line(legend_x, legend_y + 3, legend_x + 11, legend_y + 3, fill=color, width=3 if featured else 2)
            canvas.create_text(legend_x + 15, legend_y + 3, text=row["label"], fill=color, font=("Microsoft YaHei UI", 6), anchor="w")

        if featured_curve:
            scaled_featured = [(round(x * scale), round(y * scale)) for x, y in featured_curve]
            glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow, "RGBA")
            green = ImageColor.getrgb(GREEN)
            glow_draw.line(scaled_featured, fill=(*green, 155), width=22, joint="curve")
            glow = glow.filter(ImageFilter.GaussianBlur(11))
            layer.alpha_composite(glow)
            draw = ImageDraw.Draw(layer, "RGBA")
            if len(scaled_featured) >= 2:
                draw.line(scaled_featured, fill=(*green, 255), width=12, joint="curve")
            x, y = scaled_featured[-1]
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(*green, 255), outline=(220, 255, 239, 255), width=3)

        layer = layer.resize((338, 88), Image.Resampling.LANCZOS)
        self.chart_curve_image = ImageTk.PhotoImage(layer)
        canvas.create_image(0, 0, image=self.chart_curve_image, anchor="nw")

    def dismiss(self) -> None:
        DISMISS_FLAG.write_text("manual close", encoding="utf-8")
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    RadarApp().run()
