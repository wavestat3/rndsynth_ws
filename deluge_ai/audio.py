"""
Audio utilities for Deluge AI.

Handles WAV format conversion, stem mixing, and audio info extraction.
All output is Deluge-compatible: 44.1kHz, 16-bit stereo WAV.
"""

import os
import numpy as np
from . import config


def convert_to_deluge_wav(input_path, output_path):
    """Convert any audio file to Deluge-compatible WAV (44.1kHz, 16-bit stereo)."""
    import soundfile as sf

    data, sr = sf.read(input_path, dtype="float32")

    # Convert mono to stereo
    if data.ndim == 1:
        data = np.column_stack([data, data])

    # Resample if needed
    if sr != config.DELUGE_SAMPLE_RATE:
        data = _resample(data, sr, config.DELUGE_SAMPLE_RATE)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sf.write(output_path, data, config.DELUGE_SAMPLE_RATE, subtype=config.DELUGE_WAV_SUBTYPE)
    return output_path


def _resample(data, orig_sr, target_sr):
    """Simple linear interpolation resampling."""
    if orig_sr == target_sr:
        return data

    ratio = target_sr / orig_sr
    n_samples = int(len(data) * ratio)
    indices = np.linspace(0, len(data) - 1, n_samples)
    indices_floor = np.floor(indices).astype(int)
    indices_ceil = np.minimum(indices_floor + 1, len(data) - 1)
    frac = indices - indices_floor

    if data.ndim == 2:
        frac = frac[:, np.newaxis]

    return data[indices_floor] * (1 - frac) + data[indices_ceil] * frac


def mix_stems(stem_paths, output_path, normalize=True):
    """Mix multiple WAV stems into a single stereo WAV file."""
    import soundfile as sf

    mixed = None
    max_len = 0

    # First pass: find the longest stem
    for path in stem_paths:
        info = sf.info(path)
        samples = int(info.duration * info.samplerate)
        max_len = max(max_len, samples)

    # Second pass: mix
    sr = None
    for path in stem_paths:
        data, file_sr = sf.read(path, dtype="float32")
        sr = file_sr

        if data.ndim == 1:
            data = np.column_stack([data, data])

        # Pad to max length
        if len(data) < max_len:
            pad = np.zeros((max_len - len(data), data.shape[1]), dtype="float32")
            data = np.concatenate([data, pad])

        if mixed is None:
            mixed = data.copy()
        else:
            mixed += data

    if mixed is None:
        raise ValueError("No stems to mix")

    if normalize:
        peak = np.max(np.abs(mixed))
        if peak > 0:
            mixed = mixed / peak * 0.95

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sf.write(output_path, mixed, sr, subtype=config.DELUGE_WAV_SUBTYPE)
    return output_path


def get_audio_info(path):
    """Get audio file metadata."""
    import soundfile as sf

    info = sf.info(path)
    return {
        "path": path,
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "duration": info.duration,
        "frames": info.frames,
        "format": info.subtype,
    }


def get_duration_seconds(path):
    """Get audio duration in seconds."""
    import soundfile as sf
    info = sf.info(path)
    return info.duration
