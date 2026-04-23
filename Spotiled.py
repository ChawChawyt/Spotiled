import time
import os
import numpy as np
import sys
import json
import requests
from io import BytesIO
from PIL import Image
from collections import deque
import threading

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import pyaudiowpatch as pyaudio  # pip install pyaudiowpatch

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

def base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = base_path()

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")

with open(SETTINGS_PATH, "r") as f:
    SETTINGS = json.load(f)

load_dotenv(ENV_PATH)

#=========================#
#          ENV            #
#=========================#
load_dotenv()

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI")

#=========================#
#      AUDIO SETTINGS     #
#=========================#

DEVICE_INDEX = SETTINGS["device_index"]

SAMPLE_RATE = SETTINGS["audio"]["sample_rate"]
CHUNK_SIZE  = SETTINGS["audio"]["chunk_size"]

BASS_LO, BASS_HI = SETTINGS["audio"]["bass_range"]
MID_LO, MID_HI   = SETTINGS["audio"]["mid_range"]
HIGH_LO, HIGH_HI = SETTINGS["audio"]["high_range"]

BEAT_MULTIPLIER  = SETTINGS["audio"]["beat_multiplier"]
BEAT_HISTORY_LEN = SETTINGS["audio"]["beat_history_len"]

ATTACK_COEFF = SETTINGS["audio"]["attack_coeff"]
DECAY_COEFF  = SETTINGS["audio"]["decay_coeff"]
BEAT_BOOST   = SETTINGS["audio"]["beat_boost"]

W_BASS = SETTINGS["audio"]["bass_weight"]
W_MID  = SETTINGS["audio"]["mid_weight"]
W_HIGH = SETTINGS["audio"]["high_weight"]

COLOR_LERP_SPEED = SETTINGS["rgb"]["color_lerp_speed"]

#=========================#
#         SPOTIFY         #
#=========================#
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-read-playback-state"
))

#=========================#
#         OPENRGB         #
#=========================#
rgb_client = OpenRGBClient("127.0.0.1", 6742)
device     = rgb_client.devices[DEVICE_INDEX]

# =========================
# ALBUM COLOR CACHE
# =========================
color_cache = {}

def get_album_color(url):
    if url in color_cache:
        return color_cache[url]
    try:
        img    = Image.open(BytesIO(requests.get(url, timeout=3).content)).convert("RGB")
        img    = img.resize((100, 100))   # slightly larger sample for better accuracy
        pixels = np.array(img).reshape(-1, 3).astype(float)

        # --- Convert to HSV to judge saturation and brightness ---
        r, g, b   = pixels[:, 0] / 255, pixels[:, 1] / 255, pixels[:, 2] / 255
        cmax      = np.max(pixels / 255, axis=1)
        cmin      = np.min(pixels / 255, axis=1)
        delta     = cmax - cmin

        saturation = np.where(cmax > 0, delta / cmax, 0)   # 0 = gray/white, 1 = pure color
        brightness = cmax                                    # 0 = black, 1 = white

        # Keep only pixels that are:
        #   - saturated enough  (rules out whites, grays, and black text/logos)
        #   - not too dark      (rules out near-black shadows)
        #   - not too bright    (rules out white overlays and highlights)
        mask = (saturation > 0.25) & (brightness > 0.15)

        vibrant = pixels[mask]

        # Fallback: if almost nothing passes (e.g. very desaturated artwork)
        # progressively relax the saturation threshold
        if len(vibrant) < 50:
            mask    = (saturation > 0.10) & (brightness > 0.10) & (brightness < 0.97)
            vibrant = pixels[mask]
        if len(vibrant) < 20:
            vibrant = pixels   # last resort: use everything

        # Quantize then pick the most frequent saturated color
        quantized              = (vibrant // 24) * 24          # finer bins than before
        colors, counts         = np.unique(quantized, axis=0, return_counts=True)
        dominant               = colors[np.argmax(counts)].astype(float)

        # Boost vibrancy slightly (same as before) without blowing out to white
        dominant = np.clip(dominant * 1.20, 0, 255)

        color_cache[url] = dominant
        return dominant

    except Exception:
        return np.array([255.0, 255.0, 255.0])

# =========================
# WASAPI LOOPBACK SETUP
# =========================
def find_loopback_device(pa: pyaudio.PyAudio):
    """Return (device_index, device_info) for the default WASAPI loopback output."""
    try:
        # pyaudiowpatch exposes a helper for this
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out_idx = wasapi_info["defaultOutputDevice"]
        default_out     = pa.get_device_info_by_index(default_out_idx)

        # Search for the loopback twin of the default output device
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if (info.get("isLoopbackDevice", False)
                    and default_out["name"] in info["name"]):
                return i, info

        # Fallback: any loopback device
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("isLoopbackDevice", False):
                return i, info

    except Exception as e:
        print(f"[WASAPI] Could not find loopback device: {e}")
    return None, None

# =========================
# FFT ENGINE
# =========================
class AudioEngine:
    def __init__(self):
        self.brightness  = 0.0
        self._envelope   = 0.0
        self._beat_hist  = deque(maxlen=BEAT_HISTORY_LEN)

        # Pre-build frequency-band masks once
        freqs        = np.fft.rfftfreq(CHUNK_SIZE, d=1.0 / SAMPLE_RATE)
        self._bass_m = (freqs >= BASS_LO) & (freqs < BASS_HI)
        self._mid_m  = (freqs >= MID_LO)  & (freqs < MID_HI)
        self._high_m = (freqs >= HIGH_LO) & (freqs < HIGH_HI)

        # Hann window reduces spectral leakage (same as G HUB internally)
        self._window = np.hanning(CHUNK_SIZE)

        self._pa     = None
        self._stream = None
        self._lock   = threading.Lock()
        self._buf    = np.zeros(CHUNK_SIZE, dtype=np.float32)
        self._ready  = False

    # ---- WASAPI stream callback (runs on audio thread) ----
    def _callback(self, in_data, frame_count, time_info, status):
        audio = np.frombuffer(in_data, dtype=np.float32)
        # Stereo → mono
        if self._channels > 1:
            audio = audio.reshape(-1, self._channels).mean(axis=1)
        # Trim / pad to CHUNK_SIZE
        audio = audio[:CHUNK_SIZE]
        if len(audio) < CHUNK_SIZE:
            audio = np.pad(audio, (0, CHUNK_SIZE - len(audio)))

        with self._lock:
            self._buf   = audio
            self._ready = True
        return (None, pyaudio.paContinue)

    def start(self):
        self._pa = pyaudio.PyAudio()
        dev_idx, dev_info = find_loopback_device(self._pa)

        if dev_idx is None:
            raise RuntimeError(
                "No WASAPI loopback device found.\n"
                "Make sure you are on Windows and pyaudiowpatch is installed.\n"
                "pip install pyaudiowpatch"
            )

        self._channels = int(dev_info["maxInputChannels"])
        sr = int(dev_info["defaultSampleRate"])

        print(f"[Audio] Loopback device : {dev_info['name']}")
        print(f"[Audio] Channels        : {self._channels}  |  Sample rate: {sr}")

        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=self._channels,
            rate=sr,
            input=True,
            input_device_index=dev_idx,
            frames_per_buffer=CHUNK_SIZE,
            stream_callback=self._callback,
        )
        self._stream.start_stream()

    def stop(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    # ---- Called every main-loop tick ----
    def tick(self) -> float:
        """Return smoothed brightness 0–1 using beat detection."""
        with self._lock:
            if not self._ready:
                return self._envelope
            buf = self._buf.copy()

        # --- FFT ---
        spectrum = np.abs(np.fft.rfft(buf * self._window))
        spectrum /= (CHUNK_SIZE / 2)         # normalise to 0-1 amplitude range

        def band_energy(mask):
            s = spectrum[mask]
            return float(np.sqrt(np.mean(s ** 2))) if s.size else 0.0

        e_bass = band_energy(self._bass_m)
        e_mid  = band_energy(self._mid_m)
        e_high = band_energy(self._high_m)

        # Weighted total energy (bass-heavy, like )
        energy = W_BASS * e_bass + W_MID * e_mid + W_HIGH * e_high

        # --- Beat detection (dynamic threshold on rolling mean) ---
        self._beat_hist.append(energy)
        mean_energy = np.mean(self._beat_hist) if len(self._beat_hist) > 4 else energy
        is_beat     = energy > mean_energy * BEAT_MULTIPLIER and energy > 0.002

        # --- Attack / decay envelope ---
        target = BEAT_BOOST if is_beat else np.clip(energy * 8.0, 0.0, 1.0)

        if target > self._envelope:
            self._envelope += (target - self._envelope) * ATTACK_COEFF
        else:
            self._envelope += (target - self._envelope) * DECAY_COEFF

        self._envelope = np.clip(self._envelope, 0.0, 1.0)
        return self._envelope

# =========================
# STATE
# =========================
target_color  = np.array([255.0, 255.0, 255.0])
current_color = np.array([255.0, 255.0, 255.0])
last_track    = None

audio_engine = AudioEngine()
audio_engine.start()

print("=" * 50)
print("  Spotiled BETA")
print("=" * 50)

# =========================
# MAIN LOOP
# =========================
SPOTIFY_POLL_INTERVAL = 3.0   # seconds between Spotify API calls
last_spotify_poll     = 0.0

try:
    while True:
        now = time.perf_counter()

        # ---- Spotify poll (rate-limited) ----
        if now - last_spotify_poll >= SPOTIFY_POLL_INTERVAL:
            last_spotify_poll = now
            try:
                playback = sp.current_playback()
                if playback and playback.get("is_playing"):
                    track    = playback["item"]
                    track_id = track["id"]
                    if track_id != last_track:
                        img_url      = track["album"]["images"][0]["url"]
                        target_color = get_album_color(img_url)
                        last_track   = track_id
                        print(f"[Spotify] Now playing: {track['name']} → color {target_color.astype(int)}")
            except Exception as e:
                print(f"[Spotify] Error: {e}")

        # ---- Audio (every tick) ----
        brightness = audio_engine.tick()

        # ---- Smooth color interpolation ----
        current_color += (target_color - current_color) * COLOR_LERP_SPEED

        # ---- Final RGB output ----
        final    = current_color * brightness
        r, g, b  = np.clip(final, 0, 255).astype(int)
        device.set_color(RGBColor(r, g, b))

        time.sleep(0.010)   # ~100 fps main loop

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    audio_engine.stop()
    device.set_color(RGBColor(0, 0, 0))
    print("Done.")
