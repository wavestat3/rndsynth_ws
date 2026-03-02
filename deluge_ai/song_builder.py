"""
Deluge Song XML builder.

Generates Deluge-compatible song XML files with instrument clips (MIDI notes),
audio clips (WAV references), and song arrangement data.

Target format: Deluge firmware v3+/v4+ (uses XML attributes).
"""

import os
import math
from lxml import etree as ET
from . import config
from .midi_utils import Song, Track


def hex_string(x):
    """Convert integer to Deluge hex format (0xNNNNNNNN)."""
    h = hex(x & 0xFFFFFFFF)
    if len(h) < 10:
        h = "0x" + "0" * (10 - len(h)) + h[2:]
    return h


def value_to_deluge_hex(value, min_val=0.0, max_val=1.0):
    """
    Map a normalized float value to a Deluge 32-bit signed hex integer.

    Deluge uses 0x80000000 (-2147483648) to 0x7FFFFFFF (2147483647).
    """
    clamped = max(min_val, min(max_val, value))
    normalized = (clamped - min_val) / (max_val - min_val)
    int_val = int(config.SINT_MIN + normalized * (config.SINT_MAX - config.SINT_MIN))
    return hex_string(int_val)


def build_song_xml(song_data, stem_paths=None, synth_patches=None, output_path="SONG.XML"):
    """
    Build a complete Deluge song XML file.

    Args:
        song_data: Song object with tracks and timing info
        stem_paths: dict of stem_name -> WAV path for audio clips (optional)
        synth_patches: dict of track_name -> synth patch filename (optional)
        output_path: Path to write the XML file

    Returns:
        Path to the written XML file
    """
    stem_paths = stem_paths or {}
    synth_patches = synth_patches or {}

    song = ET.Element("song")
    song.set("firmwareVersion", config.FIRMWARE_VERSION)
    song.set("earliestCompatibleFirmware", "3.0.0")
    song.set("previewNumPads", "128")

    # Tempo - Deluge stores tempo as BPM float
    song.set("tempo", str(song_data.tempo_bpm))
    song.set("rootNote", "0")
    song.set("inputTickMagnitude", "1")
    song.set("swingAmount", "0")
    song.set("swingInterval", "8")

    # Calculate total clip length (snap to bars)
    ticks_per_bar = song_data.ticks_per_bar
    total_bars = max(1, math.ceil(song_data.duration_ticks / ticks_per_bar))
    clip_length = total_bars * ticks_per_bar

    # --- Session Clips ---
    session_clips = ET.SubElement(song, "sessionClips")

    clip_index = 0

    # 1. Add instrument clips for MIDI tracks
    for track in song_data.tracks:
        track_key = track.name.lower()

        if not track.notes:
            continue

        inst_clip = ET.SubElement(session_clips, "instrumentClip")
        inst_clip.set("length", str(clip_length))
        inst_clip.set("colourOffset", str((clip_index * 7) % 72))
        inst_clip.set("section", "0")
        inst_clip.set("isPlaying", "1")
        inst_clip.set("yScroll", str(max(0, _median_pitch(track) - 8)))

        if track.is_drum:
            inst_clip.set("instrumentType", "kit")
            inst_clip.set("instrumentPresetSlot", "0")
        else:
            inst_clip.set("instrumentType", "synth")
            # Reference a synth preset if we have one
            if track_key in synth_patches:
                inst_clip.set("instrumentPresetName", synth_patches[track_key])
            else:
                inst_clip.set("instrumentPresetSlot", str(clip_index))
                inst_clip.set("instrumentPresetSubSlot", "-1")

        # Build the inline sound if no preset reference
        if track_key not in synth_patches and not track.is_drum:
            _add_default_sound(inst_clip, track)

        # --- Note Rows ---
        _add_note_rows(inst_clip, track, clip_length)

        clip_index += 1

    # 2. Add audio clips for stems
    for stem_name, stem_path in stem_paths.items():
        audio_clip = ET.SubElement(session_clips, "audioClip")
        audio_clip.set("length", str(clip_length))
        audio_clip.set("colourOffset", str((clip_index * 7) % 72))
        audio_clip.set("section", "0")
        audio_clip.set("isPlaying", "1")

        # File path relative to SD card root
        relative_path = os.path.join(config.DELUGE_STEMS_SUBDIR, os.path.basename(stem_path))
        audio_clip.set("filePath", relative_path)

        clip_index += 1

    # Write the XML
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tree = ET.ElementTree(song)
    tree.write(output_path, pretty_print=True, encoding="UTF-8", xml_declaration=True)

    print(f"  -> Song XML: {output_path}")
    return output_path


def _median_pitch(track):
    """Get the median pitch of notes in a track (for yScroll)."""
    if not track.notes:
        return config.MIDI_MIDDLE_C
    pitches = sorted(n.pitch for n in track.notes)
    return pitches[len(pitches) // 2]


def _add_note_rows(clip_element, track, clip_length):
    """Add noteRows to an instrumentClip element."""
    note_rows_elem = ET.SubElement(clip_element, "noteRows")

    # Group notes by pitch
    notes_by_pitch = {}
    for note in track.notes:
        if note.pitch not in notes_by_pitch:
            notes_by_pitch[note.pitch] = []
        notes_by_pitch[note.pitch].append(note)

    # Create a noteRow for each pitch
    for pitch in sorted(notes_by_pitch.keys()):
        note_row = ET.SubElement(note_rows_elem, "noteRow")
        note_row.set("y", str(pitch))
        note_row.set("colourOffset", "0")

        notes_elem = ET.SubElement(note_row, "notes")

        for note in notes_by_pitch[pitch]:
            # Ensure note fits within clip
            if note.start_tick >= clip_length:
                continue

            note_elem = ET.SubElement(notes_elem, "note")
            note_elem.set("pos", str(note.start_tick))
            note_elem.set("length", str(min(note.duration_tick, clip_length - note.start_tick)))
            note_elem.set("velocity", str(note.velocity))
            note_elem.set("probability", "255")

    return note_rows_elem


def _add_default_sound(clip_element, track):
    """Add a default inline sound/synth to an instrument clip."""
    sound = ET.SubElement(clip_element, "sound")
    sound.set("polyphonic", "poly")
    sound.set("voicePriority", "1")
    sound.set("mode", "subtractive")

    osc1 = ET.SubElement(sound, "osc1")
    osc1.set("type", "saw")
    osc1.set("transpose", "0")
    osc1.set("cents", "0")
    osc1.set("retrigPhase", "-1")

    osc2 = ET.SubElement(sound, "osc2")
    osc2.set("type", "square")
    osc2.set("transpose", "0")
    osc2.set("cents", "0")
    osc2.set("retrigPhase", "-1")

    unison = ET.SubElement(sound, "unison")
    unison.set("num", "1")
    unison.set("detune", "8")

    # Default params
    params = ET.SubElement(sound, "defaultParams")
    params.set("oscAVolume", hex_string(config.SINT_MAX))
    params.set("oscBVolume", hex_string(config.SINT_MIN))
    params.set("volume", hex_string(config.SINT_MAX))
    params.set("pan", hex_string(0))
    params.set("lpfFrequency", hex_string(config.SINT_MAX))
    params.set("lpfResonance", hex_string(config.SINT_MIN))
    params.set("hpfFrequency", hex_string(config.SINT_MIN))
    params.set("hpfResonance", hex_string(config.SINT_MIN))
    params.set("noiseVolume", hex_string(config.SINT_MIN))

    env1 = ET.SubElement(params, "envelope1")
    env1.set("attack", hex_string(0))
    env1.set("decay", hex_string(int(config.SINT_MAX * 0.7)))
    env1.set("sustain", hex_string(int(config.SINT_MAX * 0.6)))
    env1.set("release", hex_string(0))

    env2 = ET.SubElement(params, "envelope2")
    env2.set("attack", hex_string(int(config.SINT_MAX * 0.3)))
    env2.set("decay", hex_string(int(config.SINT_MAX * 0.5)))
    env2.set("sustain", hex_string(int(config.SINT_MAX * 0.5)))
    env2.set("release", hex_string(int(config.SINT_MAX * 0.3)))

    params.set("lfo1Rate", hex_string(429496702))
    params.set("lfo2Rate", hex_string(429496702))
    params.set("delayRate", hex_string(0))
    params.set("delayFeedback", hex_string(config.SINT_MIN))
    params.set("reverbAmount", hex_string(config.SINT_MIN))

    # Default velocity -> volume patch cable
    cables = ET.SubElement(params, "patchCables")
    cable = ET.SubElement(cables, "patchCable")
    cable.set("source", "velocity")
    cable.set("destination", "volume")
    cable.set("amount", hex_string(1073741800))

    return sound


def build_audio_only_song(stem_paths, tempo_bpm, output_path):
    """
    Build a simple Deluge song with only audio clips (no MIDI).

    This is the simplest, most reliable mode - just references WAV stems
    as audio clips in the Deluge song.

    Args:
        stem_paths: dict of stem_name -> WAV path
        tempo_bpm: Song tempo in BPM
        output_path: Path to write the XML file

    Returns:
        Path to written XML file
    """
    song_data = Song(tempo_bpm=tempo_bpm)
    return build_song_xml(song_data, stem_paths=stem_paths, output_path=output_path)
