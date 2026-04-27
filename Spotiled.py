#!/usr/bin/env python3
"""
Spotiled  —  Spotify Album Colour 
Full GUI + System Tray Application

Dependencies:
    pip install customtkinter pystray pyaudiowpatch openrgb-python
                spotipy python-dotenv numpy requests pillow
"""

import os, sys, time, threading, math
import numpy as np
import requests
from io import BytesIO
from collections import deque

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import pyaudiowpatch as pyaudio
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pystray

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PATHS & ENV
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
load_dotenv()
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "spotiled_logo.png")
ICON_PATH = os.path.join(BASE_DIR, "spotiled_icon.png")

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHARED SETTINGS — GUI writes, engine reads live
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
settings = {
    "beat_multiplier": 1.5,
    "attack":          0.90,
    "decay":           0.18,
    "w_bass":          0.70,
    "w_mid":           0.20,
    "w_high":          0.10,
    "color_lerp":      0.12,
    "device_index":    0,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COLOURS  (GUI theme)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BG       = "#07070F"
SURFACE  = "#0F0F1C"
SURFACE2 = "#181830"
ACCENT   = "#7B3FE4"
ACCENT2  = "#3FA4E4"
TEXT     = "#D8D8EE"
TEXT_DIM = "#6060A0"
GREEN    = "#1D6B2E"
GREEN_H  = "#25923D"
RED      = "#6B1D1D"
RED_H    = "#943030"
BLUE     = "#1A3B72"
BLUE_H   = "#2554A8"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGO + TRAY ICON GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_PALETTE = [
    (255, 60,  60),
    (255, 140, 30),
    (230, 210,  0),
    (50,  220, 80),
    (0,   200, 255),
    (40,  110, 255),
    (170,  60, 255),
    (255,  55, 200),
]

def _best_font(size: int, bold=True):
    """Return the best available truetype font at a given size."""
    suffix = "-Bold" if bold else "-Regular"
    candidates = [
        # Windows
        "C:/Windows/Fonts/GOTHICB.TTF",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        # Linux
        f"/usr/share/fonts/truetype/crosextra/Carlito{suffix}.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _rainbow_at(t: float):
    a = t * 2 * math.pi
    r = int(127.5 + 127.5 * math.cos(a))
    g = int(127.5 + 127.5 * math.cos(a - 2.094))
    b = int(127.5 + 127.5 * math.cos(a - 4.189))
    return r, g, b


def generate_logo() -> Image.Image:
    """Generate the Spotiled wordmark; save to LOGO_PATH and return the image."""
    W, H = 560, 160
    bg   = Image.new("RGBA", (W, H), (6, 6, 14, 255))

    # subtle centre glow
    for y in range(H):
        for x in range(W):
            dx = (x - W / 2) / (W / 2)
            dy = (y - H / 2) / (H / 2)
            gv = max(0, 1 - (dx * dx + dy * dy * 3) ** 0.5) * 16
            px = bg.getpixel((x, y))
            bg.putpixel((x, y), (
                min(255, px[0] + int(gv)),
                min(255, px[1] + int(gv * 0.4)),
                min(255, px[2] + int(gv * 1.6)),
                255,
            ))

    font_lg = _best_font(74)
    font_sm = _best_font(11, bold=False)
    TEXT_STR = "SPOTILED"

    probe = ImageDraw.Draw(bg)
    bb = probe.textbbox((0, 0), TEXT_STR, font=font_lg)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x0 = (W - tw) // 2
    y0 = (H - th) // 2 - 14

    # glow layers
    for radius in (18, 9):
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd   = ImageDraw.Draw(glow)
        cx   = x0
        for i, ch in enumerate(TEXT_STR):
            r, g, b = _PALETTE[i]
            cb  = gd.textbbox((0, 0), ch, font=font_lg)
            cw  = cb[2] - cb[0]
            for ox, oy in [(-3,0),(3,0),(0,-3),(0,3),(0,0)]:
                gd.text((cx+ox, y0+oy), ch, font=font_lg, fill=(r, g, b, 65))
            cx += cw
        blurred = glow.filter(ImageFilter.GaussianBlur(radius))
        bg.paste(blurred, (0, 0), blurred)

    # main characters
    draw = ImageDraw.Draw(bg)
    cx   = x0
    for i, ch in enumerate(TEXT_STR):
        r, g, b = _PALETTE[i]
        cb  = draw.textbbox((0, 0), ch, font=font_lg)
        cw  = cb[2] - cb[0]
        # base colour
        tmp  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td   = ImageDraw.Draw(tmp)
        td.text((cx, y0), ch, font=font_lg, fill=(r, g, b, 255))
        bg.paste(tmp, (0, 0), tmp)
        # top highlight
        hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hi)
        hd.text((cx, y0), ch, font=font_lg, fill=(
            min(255, r + 70), min(255, g + 70), min(255, b + 70), 110))
        region = hi.crop((cx, y0, cx + cw, y0 + th // 3))
        bg.paste(region, (cx, y0), region)
        cx += cw

    # tagline
    tag = " "
    tb  = draw.textbbox((0, 0), tag, font=font_sm)
    tx  = (W - (tb[2] - tb[0])) // 2
    draw.text((tx, y0 + th + 7), tag, font=font_sm, fill=(95, 95, 135, 185))

    # bottom rainbow bar
    BAR_Y = H - 8
    for xi in range(W):
        rr, gg, bb = _rainbow_at(xi / (W - 1))
        for dy, al in enumerate([90, 170, 240, 255, 255, 200, 130, 60]):
            yy = BAR_Y + dy - 2
            if 0 <= yy < H:
                draw.point((xi, yy), fill=(rr, gg, bb, al))

    # top rainbow line
    for xi in range(W):
        rr, gg, bb = _rainbow_at(xi / (W - 1) + 0.5)
        draw.point((xi, 0), fill=(rr, gg, bb, 200))
        draw.point((xi, 1), fill=(rr, gg, bb, 110))
        draw.point((xi, 2), fill=(rr, gg, bb, 45))

    # corner accents
    for cx2, cy2 in [(5, 5), (W-6, 5), (5, H-7), (W-6, H-7)]:
        draw.ellipse([cx2-3, cy2-3, cx2+3, cy2+3], fill=(55, 55, 100, 190))

    bg.save(LOGO_PATH)
    return bg


def generate_tray_icon() -> Image.Image:
    S    = 64
    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, S-1, S-1], fill=(9, 9, 17, 255))
    for xi in range(S):
        for yi in range(S):
            dx, dy = xi - S/2, yi - S/2
            d = math.hypot(dx, dy)
            if 26 <= d <= 30:
                t = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                r, g, b = _rainbow_at(t)
                img.putpixel((xi, yi), (r, g, b, 255))
    font = _best_font(30)
    bb   = draw.textbbox((0, 0), "S", font=font)
    sx   = (S - (bb[2] - bb[0])) // 2 - bb[0]
    sy   = (S - (bb[3] - bb[1])) // 2 - bb[1]
    draw.text((sx, sy), "S", font=font, fill=(240, 240, 255, 235))
    img.save(ICON_PATH)
    return img


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ALBUM COLOUR  (saturation-aware — ignores white text etc.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_color_cache: dict = {}

def get_album_color(url: str) -> np.ndarray:
    if url in _color_cache:
        return _color_cache[url]
    try:
        img    = Image.open(BytesIO(requests.get(url, timeout=3).content)).convert("RGB")
        img    = img.resize((100, 100))
        pixels = np.array(img).reshape(-1, 3).astype(float)

        cmax  = np.max(pixels / 255, axis=1)
        cmin  = np.min(pixels / 255, axis=1)
        delta = cmax - cmin
        sat   = np.where(cmax > 0, delta / cmax, 0)
        bri   = cmax

        mask    = (sat > 0.25) & (bri > 0.15) & (bri < 0.95)
        vibrant = pixels[mask]
        if len(vibrant) < 50:
            mask    = (sat > 0.10) & (bri > 0.10) & (bri < 0.97)
            vibrant = pixels[mask]
        if len(vibrant) < 20:
            vibrant = pixels

        q      = (vibrant // 24) * 24
        cols, counts = np.unique(q, axis=0, return_counts=True)
        dominant = np.clip(cols[np.argmax(counts)].astype(float) * 1.20, 0, 255)
        _color_cache[url] = dominant
        return dominant
    except Exception:
        return np.array([255.0, 255.0, 255.0])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUDIO ENGINE  (Logitech-style FFT + beat detection)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAMPLE_RATE = 44100
CHUNK       = 1024
BEAT_HIST   = 43

_FREQS    = np.fft.rfftfreq(CHUNK, d=1.0 / SAMPLE_RATE)
_BASS_M   = (_FREQS >= 20)   & (_FREQS < 250)
_MID_M    = (_FREQS >= 250)  & (_FREQS < 4000)
_HIGH_M   = (_FREQS >= 4000) & (_FREQS < 16000)
_HANN     = np.hanning(CHUNK)


class AudioEngine:
    def __init__(self, s: dict):
        self.s         = s
        self._envelope = 0.0
        self._beat_h   = deque(maxlen=BEAT_HIST)
        self._pa       = None
        self._stream   = None
        self._lock     = threading.Lock()
        self._buf      = np.zeros(CHUNK, dtype=np.float32)
        self._ready    = False
        self._ch       = 2

    def _cb(self, in_data, frame_count, time_info, status):
        audio = np.frombuffer(in_data, dtype=np.float32)
        if self._ch > 1:
            audio = audio.reshape(-1, self._ch).mean(axis=1)
        audio = audio[:CHUNK]
        if len(audio) < CHUNK:
            audio = np.pad(audio, (0, CHUNK - len(audio)))
        with self._lock:
            self._buf, self._ready = audio, True
        return (None, pyaudio.paContinue)

    def _find_loopback(self, pa):
        try:
            wapi    = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            def_out = pa.get_device_info_by_index(wapi["defaultOutputDevice"])
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice") and def_out["name"] in info["name"]:
                    return i, info
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice"):
                    return i, info
        except Exception:
            pass
        return None, None

    def start(self):
        self._pa      = pyaudio.PyAudio()
        idx, info = self._find_loopback(self._pa)
        if idx is None:
            raise RuntimeError(
                "No WASAPI loopback device found.\n"
                "Make sure you are on Windows and pyaudiowpatch is installed."
            )
        self._ch = int(info["maxInputChannels"])
        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=self._ch,
            rate=int(info["defaultSampleRate"]),
            input=True,
            input_device_index=idx,
            frames_per_buffer=CHUNK,
            stream_callback=self._cb,
        )
        self._stream.start_stream()

    def stop(self):
        for obj, method in [(self._stream, "stop_stream"),
                            (self._stream, "close"),
                            (self._pa,     "terminate")]:
            if obj:
                try: getattr(obj, method)()
                except Exception: pass

    def tick(self) -> float:
        with self._lock:
            if not self._ready:
                return self._envelope
            buf = self._buf.copy()

        s        = self.s
        spectrum = np.abs(np.fft.rfft(buf * _HANN)) / (CHUNK / 2)

        def band(m):
            sl = spectrum[m]
            return float(np.sqrt(np.mean(sl ** 2))) if sl.size else 0.0

        energy = s["w_bass"] * band(_BASS_M) + s["w_mid"] * band(_MID_M) + s["w_high"] * band(_HIGH_M)
        self._beat_h.append(energy)
        mean_e  = np.mean(self._beat_h) if len(self._beat_h) > 4 else energy
        is_beat = energy > mean_e * s["beat_multiplier"] and energy > 0.002

        target = 1.0 if is_beat else np.clip(energy * 8.0, 0.0, 1.0)
        coeff  = s["attack"] if target > self._envelope else s["decay"]
        self._envelope = np.clip(self._envelope + (target - self._envelope) * coeff, 0.0, 1.0)
        return self._envelope


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SPOTILED ENGINE  (orchestrator — runs in its own thread)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SpotiledEngine:
    def __init__(self, s: dict):
        self.s            = s
        self._stop        = threading.Event()
        self._thread: threading.Thread | None = None
        # Public state — polled by GUI
        self.status       = "Stopped"
        self.track_name   = "—"
        self.track_artist = ""
        self.color_rgb    = (60, 60, 80)
        self.brightness   = 0.0

    # ── Lifecycle ──────────────────────────────────────────
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SpotiledEngine")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.status = "Stopping…"

    def restart(self):
        self.stop()
        threading.Thread(target=self._delayed_start, daemon=True).start()

    def _delayed_start(self):
        # Wait for running thread to finish before relaunching
        if self._thread:
            self._thread.join(timeout=3.0)
        self.start()

    # ── Main loop ──────────────────────────────────────────
    def _run(self):
        self.status = "Starting…"
        audio = None
        rgb   = None
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-read-playback-state",
            ))
            rgb = OpenRGBClient("127.0.0.1", 6742)
            dev = rgb.devices[self.s["device_index"]]

            audio = AudioEngine(self.s)
            audio.start()

            target_color  = np.array([60.0, 60.0, 80.0])
            current_color = np.array([60.0, 60.0, 80.0])
            last_track    = None
            last_poll     = 0.0
            POLL           = 3.0

            self.status = "Running"

            while not self._stop.is_set():
                now = time.perf_counter()

                # Spotify poll (rate-limited)
                if now - last_poll >= POLL:
                    last_poll = now
                    try:
                        pb = sp.current_playback()
                        if pb and pb.get("is_playing"):
                            track = pb["item"]
                            tid   = track["id"]
                            if tid != last_track:
                                url          = track["album"]["images"][0]["url"]
                                target_color = get_album_color(url)
                                last_track   = tid
                            self.track_name   = track["name"]
                            self.track_artist = ", ".join(a["name"] for a in track["artists"])
                        else:
                            self.track_name   = "Paused / Not playing"
                            self.track_artist = ""
                    except Exception:
                        pass

                # Audio
                bri = audio.tick()
                self.brightness = bri

                # Colour interpolation
                current_color += (target_color - current_color) * self.s["color_lerp"]

                # RGB output
                final = np.clip(current_color * bri, 0, 255).astype(int)
                r, g, b = int(final[0]), int(final[1]), int(final[2])
                self.color_rgb = (r, g, b)
                dev.set_color(RGBColor(r, g, b))

                time.sleep(0.010)

        except Exception as e:
            self.status     = f"Error: {e}"
            self.track_name = str(e)[:60]
        finally:
            if audio:
                try: audio.stop()
                except Exception: pass
            if rgb:
                try: rgb.devices[self.s["device_index"]].set_color(RGBColor(0, 0, 0))
                except Exception: pass
            if self._stop.is_set():
                self.status = "Stopped"
            # else status already shows the error message


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GUI COMPONENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _section_header(parent, label: str):
    """Render a styled section divider with label."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=18, pady=(12, 3))
    ctk.CTkLabel(row, text=label, text_color=TEXT_DIM,
                 font=ctk.CTkFont("Consolas", 10, weight="bold")).pack(side="left")
    ctk.CTkFrame(row, height=1, fg_color=SURFACE2, corner_radius=0).pack(
        side="left", fill="x", expand=True, padx=(8, 0))


class SliderRow(ctk.CTkFrame):
    """One labelled slider that writes into the shared settings dict."""

    def __init__(self, parent, label: str, key: str,
                 lo: float, hi: float, fmt: str = "{:.2f}", **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._key = key
        self._fmt = fmt
        self._var = ctk.DoubleVar(value=settings[key])

        ctk.CTkLabel(
            self, text=label, text_color=TEXT_DIM,
            font=ctk.CTkFont("Consolas", 11), width=150, anchor="w",
        ).pack(side="left", padx=(4, 6))

        self._val = ctk.CTkLabel(
            self, text=fmt.format(settings[key]),
            text_color=TEXT, font=ctk.CTkFont("Consolas", 11), width=46,
        )
        self._val.pack(side="right", padx=(0, 4))

        ctk.CTkSlider(
            self, from_=lo, to=hi, variable=self._var,
            width=210, height=14,
            progress_color=ACCENT, button_color=ACCENT2,
            fg_color=SURFACE2, command=self._changed,
        ).pack(side="right", padx=6)

    def _changed(self, val):
        settings[self._key] = float(val)
        self._val.configure(text=self._fmt.format(float(val)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN WINDOW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SpotiledApp(ctk.CTk):
    def __init__(self, engine: SpotiledEngine):
        super().__init__()
        self.engine = engine
        self._tray: pystray.Icon | None = None

        self.title("Spotiled")
        self.geometry("530x720")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self._build()
        self._start_tray()
        self._poll()

    # ── Build UI ──────────────────────────────────────────
    def _build(self):
        # ── Logo ──────────────────────────────────────
        if os.path.exists(LOGO_PATH):
            raw = Image.open(LOGO_PATH)
        else:
            raw = generate_logo()
        self._logo_img = ctk.CTkImage(light_image=raw, dark_image=raw, size=(530, 152))
        ctk.CTkLabel(self, image=self._logo_img, text="",
                     fg_color=BG).pack(fill="x")

        # ── Status bar ────────────────────────────────
        sb = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10, height=42)
        sb.pack(fill="x", padx=14, pady=(6, 0))
        sb.pack_propagate(False)

        self._dot = ctk.CTkLabel(sb, text="●", text_color="#333",
                                  font=ctk.CTkFont("Segoe UI", 15))
        self._dot.pack(side="left", padx=(12, 3))

        self._status_lbl = ctk.CTkLabel(sb, text="Stopped", text_color=TEXT_DIM,
                                         font=ctk.CTkFont("Consolas", 11))
        self._status_lbl.pack(side="left")

        self._track_lbl = ctk.CTkLabel(sb, text="", text_color=TEXT,
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        anchor="e")
        self._track_lbl.pack(side="right", padx=12)

        # ── Colour swatch + brightness ─────────────────
        cw = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10, height=40)
        cw.pack(fill="x", padx=14, pady=(5, 0))
        cw.pack_propagate(False)

        ctk.CTkLabel(cw, text="Album Colour", text_color=TEXT_DIM,
                     font=ctk.CTkFont("Consolas", 11)).pack(side="left", padx=12)

        # Colour swatch (plain tkinter canvas sits inside ctk fine)
        import tkinter as tk
        self._swatch = tk.Canvas(cw, width=80, height=18, bg="#3C3C50",
                                  highlightthickness=1, highlightbackground=SURFACE2)
        self._swatch.pack(side="left", padx=6, pady=11)

        ctk.CTkLabel(cw, text="Brightness", text_color=TEXT_DIM,
                     font=ctk.CTkFont("Consolas", 11)).pack(side="left", padx=(14, 4))
        self._bri = ctk.CTkProgressBar(cw, width=130, height=10,
                                        progress_color=ACCENT, fg_color=SURFACE2,
                                        corner_radius=5)
        self._bri.set(0)
        self._bri.pack(side="left")

        # ── Audio settings ─────────────────────────────
        _section_header(self, "AUDIO ENGINE")
        af = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10)
        af.pack(fill="x", padx=14, pady=(2, 0))

        rows = [
            ("Beat Sensitivity",  "beat_multiplier", 1.0,  4.0, "{:.2f}"),
            ("Attack Speed",      "attack",          0.05, 1.0, "{:.2f}"),
            ("Decay Speed",       "decay",           0.01, 0.6, "{:.2f}"),
            ("Bass Weight",       "w_bass",          0.0,  1.0, "{:.2f}"),
            ("Mid Weight",        "w_mid",           0.0,  1.0, "{:.2f}"),
            ("High Weight",       "w_high",          0.0,  1.0, "{:.2f}"),
        ]
        for lbl, key, lo, hi, fmt in rows:
            SliderRow(af, lbl, key, lo, hi, fmt).pack(fill="x", padx=10, pady=3)

        # ── Visual settings ────────────────────────────
        _section_header(self, "VISUAL")
        vf = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10)
        vf.pack(fill="x", padx=14, pady=(2, 0))
        SliderRow(vf, "Colour Blend Speed", "color_lerp", 0.01, 0.5).pack(
            fill="x", padx=10, pady=3)

        # ── Control buttons ────────────────────────────
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(14, 10))

        btn_cfg = dict(font=ctk.CTkFont("Consolas", 12, weight="bold"), height=40, corner_radius=8)

        self._btn_start = ctk.CTkButton(
            btns, text="▶  START", command=self._start,
            fg_color=GREEN, hover_color=GREEN_H, **btn_cfg)
        self._btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self._btn_stop = ctk.CTkButton(
            btns, text="■  STOP", command=self._stop,
            fg_color=RED, hover_color=RED_H,
            state="disabled", **btn_cfg)
        self._btn_stop.pack(side="left", expand=True, fill="x", padx=4)

        self._btn_restart = ctk.CTkButton(
            btns, text="↺  RESTART", command=self._restart,
            fg_color=BLUE, hover_color=BLUE_H, **btn_cfg)
        self._btn_restart.pack(side="left", expand=True, fill="x", padx=(4, 0))

    # ── Button actions ─────────────────────────────────────
    def _start(self):
        self.engine.start()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")

    def _stop(self):
        self.engine.stop()
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")

    def _restart(self):
        self.engine.restart()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")

    # ── Status poll (120 ms) ───────────────────────────────
    def _poll(self):
        st = self.engine.status
        r, g, b = self.engine.color_rgb

        DOT = {"Running": "#28E060", "Stopped": "#444", "Stopping…": "#E09030"}
        dot_col = DOT.get(st, "#E04040" if "Error" in st else "#555")
        self._dot.configure(text_color=dot_col)
        self._status_lbl.configure(text=st)

        artist = self.engine.track_artist
        name   = self.engine.track_name
        label  = f"{artist} — {name}" if artist else name
        self._track_lbl.configure(text=label[:36])

        hex_c = f"#{r:02X}{g:02X}{b:02X}"
        self._swatch.configure(bg=hex_c)
        self._bri.set(self.engine.brightness)

        # Sync button states when engine crashes/stops on its own
        if "Error" in st or st == "Stopped":
            self._btn_start.configure(state="normal")
            self._btn_stop.configure(state="disabled")

        self.after(120, self._poll)

    # ── System tray ────────────────────────────────────────
    def _start_tray(self):
        icon_img = generate_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Show Spotiled",          self._show_window, default=True),
            pystray.MenuItem("Refresh (Restart Engine)", self._tray_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit",                   self._tray_exit),
        )
        self._tray = pystray.Icon("Spotiled", icon_img, "Spotiled", menu)
        threading.Thread(target=self._tray.run, daemon=True, name="TrayIcon").start()

    def _hide_to_tray(self):
        self.withdraw()

    def _show_window(self, *_):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _tray_refresh(self, *_):
        self.engine.restart()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")

    def _tray_exit(self, *_):
        self.engine.stop()
        if self._tray:
            self._tray.stop()
        self.after(0, self.destroy)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    # Generate assets if missing
    if not os.path.exists(LOGO_PATH):
        print("[Spotiled] Generating logo…")
        generate_logo()

    engine = SpotiledEngine(settings)
    app    = SpotiledApp(engine)
    app.mainloop()
