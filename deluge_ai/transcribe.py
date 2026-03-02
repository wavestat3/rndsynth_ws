"""
Audio-to-MIDI transcription using Spotify's Basic Pitch.

Converts audio stems to MIDI files with note detection and pitch bend.
"""

import os
from . import config


def audio_to_midi(audio_path, output_path=None, min_note_length=0.05, min_frequency=None, max_frequency=None):
    """
    Transcribe an audio file to MIDI using Basic Pitch.

    Args:
        audio_path: Path to input audio file
        output_path: Path to save MIDI file (default: same name with .mid extension)
        min_note_length: Minimum note duration in seconds
        min_frequency: Minimum frequency to detect (Hz), None for default
        max_frequency: Maximum frequency to detect (Hz), None for default

    Returns:
        tuple of (output_path, midi_data, note_events)
    """
    try:
        from basic_pitch.inference import predict, Model
        from basic_pitch import ICASSP_2022_MODEL_PATH
    except ImportError:
        raise ImportError(
            "Basic Pitch is required for audio-to-MIDI transcription.\n"
            "Install with: pip install basic-pitch"
        )

    if output_path is None:
        base = os.path.splitext(audio_path)[0]
        output_path = base + ".mid"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    stem_name = os.path.splitext(os.path.basename(audio_path))[0]
    print(f"  Transcribing {stem_name} to MIDI...")

    model_output, midi_data, note_events = predict(audio_path)

    midi_data.write(output_path)
    n_notes = len(note_events)
    print(f"    -> {os.path.basename(output_path)} ({n_notes} notes)")

    return output_path, midi_data, note_events


def transcribe_stems(stem_paths, output_dir):
    """
    Transcribe all stems to MIDI.

    Args:
        stem_paths: dict of stem_name -> audio file path
        output_dir: Directory to save MIDI files

    Returns:
        dict of stem_name -> {"midi_path": str, "midi_data": obj, "note_events": list}
    """
    os.makedirs(output_dir, exist_ok=True)

    results = {}
    for stem_name, audio_path in stem_paths.items():
        midi_path = os.path.join(output_dir, f"{stem_name}.mid")
        try:
            path, midi_data, note_events = audio_to_midi(audio_path, midi_path)
            results[stem_name] = {
                "midi_path": path,
                "midi_data": midi_data,
                "note_events": note_events,
            }
        except Exception as e:
            print(f"    Warning: Could not transcribe {stem_name}: {e}")
            results[stem_name] = None

    return results


def check_basic_pitch_available():
    """Check if Basic Pitch is installed and available."""
    try:
        import basic_pitch  # noqa: F401
        return True
    except ImportError:
        return False
