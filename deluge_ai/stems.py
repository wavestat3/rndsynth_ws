"""
Stem separation using Meta's Demucs.

Splits audio into 4 stems: drums, bass, vocals, other.
Each stem is saved as a WAV file.
"""

import os
import shutil
from . import config


def separate_stems(input_audio, output_dir, model=None):
    """
    Separate an audio file into stems using Demucs.

    Args:
        input_audio: Path to input audio file (WAV, MP3, FLAC, etc.)
        output_dir: Directory to save separated stems
        model: Demucs model name (default: htdemucs)

    Returns:
        dict mapping stem name -> file path
        e.g. {"drums": "/output/stems/drums.wav", "bass": "/output/stems/bass.wav", ...}
    """
    model = model or config.DEMUCS_MODEL
    os.makedirs(output_dir, exist_ok=True)

    try:
        import demucs.separate
    except ImportError:
        raise ImportError(
            "Demucs is required for stem separation.\n"
            "Install with: pip install demucs"
        )

    # Demucs outputs to: output_dir/model_name/track_name/stem.wav
    # We'll move them to a flat structure after
    temp_out = os.path.join(output_dir, "_demucs_temp")

    args = [
        "--out", temp_out,
        "-n", model,
        "--two-stems" if False else "",  # use all 4 stems
        input_audio,
    ]
    # Filter empty strings
    args = [a for a in args if a]

    print(f"  Separating stems with Demucs ({model})...")
    demucs.separate.main(args)

    # Find the output files and move them to our output_dir
    track_name = os.path.splitext(os.path.basename(input_audio))[0]
    demucs_output = os.path.join(temp_out, model, track_name)

    stem_paths = {}
    for stem_name in config.STEM_NAMES:
        src = os.path.join(demucs_output, f"{stem_name}.wav")
        dst = os.path.join(output_dir, f"{stem_name}.wav")
        if os.path.exists(src):
            shutil.move(src, dst)
            stem_paths[stem_name] = dst
            print(f"    -> {stem_name}.wav")

    # Clean up temp directory
    shutil.rmtree(temp_out, ignore_errors=True)

    return stem_paths


def check_demucs_available():
    """Check if Demucs is installed and available."""
    try:
        import demucs  # noqa: F401
        return True
    except ImportError:
        return False
