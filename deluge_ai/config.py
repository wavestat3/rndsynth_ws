"""
Configuration constants for Deluge AI.

Defines Deluge hardware specs, audio format requirements, default paths,
and timing resolution constants.
"""

import os

# --- Deluge Audio Format Requirements ---
DELUGE_SAMPLE_RATE = 44100
DELUGE_BIT_DEPTH = 16
DELUGE_CHANNELS = 2  # stereo
DELUGE_WAV_SUBTYPE = "PCM_16"

# --- Deluge Timing ---
TICKS_PER_QUARTER_NOTE = 48
DEFAULT_TEMPO_BPM = 120.0
DEFAULT_TIME_SIG_NUM = 4
DEFAULT_TIME_SIG_DEN = 4

# --- Deluge SD Card Folder Structure ---
DELUGE_SONGS_DIR = "SONGS"
DELUGE_SYNTHS_DIR = "SYNTHS"
DELUGE_KITS_DIR = "KITS"
DELUGE_SAMPLES_DIR = "SAMPLES"
DELUGE_STEMS_SUBDIR = os.path.join(DELUGE_SAMPLES_DIR, "STEMS")

# --- Demucs Stem Separation ---
DEMUCS_MODEL = "htdemucs"
STEM_NAMES = ["drums", "bass", "vocals", "other"]

# --- Deluge Synth Modes ---
SYNTH_MODES = ["subtractive", "fm", "ringmod"]

# --- Deluge Oscillator Types ---
OSC_TYPES_SUBTRACTIVE = ["square", "analogSquare", "saw", "analogSaw", "sine", "triangle"]
OSC_TYPES_FM = ["sine"]

# --- Deluge Filter Modes ---
LPF_MODES = ["24db", "12db", "drive"]

# --- Deluge LFO Types ---
LFO_TYPES = ["triangle", "sine", "square", "saw"]

# --- Deluge Polyphony Modes ---
POLYPHONY_MODES = ["poly", "mono", "legato", "auto"]

# --- Deluge Value Ranges (32-bit signed integer) ---
SINT_MIN = -2147483648  # 0x80000000
SINT_MAX = 2147483647   # 0x7FFFFFFF

# --- MIDI Constants ---
MIDI_NOTE_MIN = 0
MIDI_NOTE_MAX = 127
MIDI_VELOCITY_MIN = 0
MIDI_VELOCITY_MAX = 127
MIDI_MIDDLE_C = 60

# --- Default Output Paths ---
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_STEMS_DIR = "stems"
DEFAULT_MIDI_DIR = "midi"
DEFAULT_DELUGE_DIR = "deluge"

# --- Stem-to-Track Mapping ---
# Maps Demucs stem names to Deluge track types and default synth modes
STEM_TRACK_MAP = {
    "drums": {"type": "kit", "mode": None},
    "bass": {"type": "synth", "mode": "subtractive"},
    "vocals": {"type": "audio", "mode": None},
    "other": {"type": "synth", "mode": "subtractive"},
}

# --- Deluge Firmware Target ---
FIRMWARE_VERSION = "4.1.0"

# --- Cable Colors for VCV Rack (if generating .vcv patches) ---
VCV_CABLE_COLORS = [
    "#c91847", "#0986ad", "#c9b70e", "#0c8e15",
    "#c35c00", "#7b3f95", "#d50bd5", "#0986ad",
]
