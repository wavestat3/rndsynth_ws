"""
Local audio playback for previewing stems and mixes.

Play generated stems individually or mixed before pushing to the Deluge.
Uses sounddevice for cross-platform audio output.
"""

import os
import sys
import threading
import numpy as np
from . import config


# Playback state
_playback_thread = None
_stop_event = threading.Event()


def play_file(path, block=True):
    """
    Play a single WAV file.

    Args:
        path: Path to WAV file
        block: If True, wait for playback to finish
    """
    import soundfile as sf
    import sounddevice as sd

    data, sr = sf.read(path, dtype="float32")
    print(f"  Playing: {os.path.basename(path)} ({sr}Hz, {len(data)/sr:.1f}s)")

    _stop_event.clear()

    if block:
        sd.play(data, sr)
        sd.wait()
    else:
        sd.play(data, sr)


def stop():
    """Stop any currently playing audio."""
    import sounddevice as sd
    _stop_event.set()
    sd.stop()
    print("  Stopped.")


def play_stems_mixed(stem_dir, normalize=True):
    """
    Mix and play all stems from a directory.

    Args:
        stem_dir: Directory containing stem WAV files
        normalize: Normalize the mix to prevent clipping
    """
    import soundfile as sf
    import sounddevice as sd

    stem_files = _find_stems(stem_dir)
    if not stem_files:
        print("  No stems found to play.")
        return

    print(f"  Mixing {len(stem_files)} stems...")

    mixed = None
    sr = None

    for name, path in stem_files:
        data, file_sr = sf.read(path, dtype="float32")
        sr = file_sr

        if data.ndim == 1:
            data = np.column_stack([data, data])

        if mixed is None:
            mixed = data.copy()
        else:
            # Pad to same length
            if len(data) > len(mixed):
                pad = np.zeros((len(data) - len(mixed), mixed.shape[1]), dtype="float32")
                mixed = np.concatenate([mixed, pad])
            elif len(mixed) > len(data):
                pad = np.zeros((len(mixed) - len(data), data.shape[1]), dtype="float32")
                data = np.concatenate([data, pad])
            mixed += data

    if normalize and mixed is not None:
        peak = np.max(np.abs(mixed))
        if peak > 0:
            mixed = mixed / peak * 0.95

    duration = len(mixed) / sr
    print(f"  Playing mix ({duration:.1f}s) - Press Ctrl+C to stop")

    sd.play(mixed, sr)
    try:
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
        print("\n  Stopped.")


def play_stems_interactive(stem_dir):
    """
    Interactive stem player - choose which stems to preview.

    Args:
        stem_dir: Directory containing stem WAV files
    """
    import soundfile as sf
    import sounddevice as sd

    stem_files = _find_stems(stem_dir)
    if not stem_files:
        print("  No stems found.")
        return

    while True:
        print("\n  Available stems:")
        print("  ----------------")
        for i, (name, path) in enumerate(stem_files):
            info = sf.info(path)
            print(f"  [{i + 1}] {name:10s} ({info.duration:.1f}s)")
        print(f"  [m] Mix all stems")
        print(f"  [q] Quit player")
        print()

        try:
            choice = input("  Choose (1-{}, m, q): ".format(len(stem_files))).strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "q":
            break
        elif choice == "m":
            play_stems_mixed(stem_dir)
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(stem_files):
                name, path = stem_files[idx]
                print(f"\n  Playing {name} - Press Ctrl+C to stop")
                data, sr = sf.read(path, dtype="float32")
                sd.play(data, sr)
                try:
                    sd.wait()
                except KeyboardInterrupt:
                    sd.stop()
                    print("\n  Stopped.")
            else:
                print("  Invalid selection.")
        else:
            print("  Invalid selection.")


def _find_stems(stem_dir):
    """Find WAV stem files in a directory."""
    stems = []
    for name in config.STEM_NAMES:
        path = os.path.join(stem_dir, f"{name}.wav")
        if os.path.exists(path):
            stems.append((name, path))

    # Also check for any other WAV files
    for f in sorted(os.listdir(stem_dir)):
        if f.endswith(".wav"):
            name = os.path.splitext(f)[0]
            path = os.path.join(stem_dir, f)
            if not any(p == path for _, p in stems):
                stems.append((name, path))

    return stems


def check_audio_available():
    """Check if audio playback libraries are available."""
    try:
        import sounddevice  # noqa: F401
        import soundfile  # noqa: F401
        return True
    except ImportError:
        return False
