"""
MIDI parsing and manipulation utilities.

Reads MIDI files and converts them to an internal representation
suitable for Deluge song building.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from . import config


@dataclass
class Note:
    """A single note event."""
    pitch: int          # MIDI note number (0-127)
    start_tick: int     # Position in ticks from clip start
    duration_tick: int  # Length in ticks
    velocity: int       # 0-127
    channel: int = 0


@dataclass
class Track:
    """A track containing notes and metadata."""
    name: str
    notes: List[Note] = field(default_factory=list)
    channel: int = 0
    is_drum: bool = False
    program: int = 0  # MIDI program number


@dataclass
class Song:
    """Parsed song data with tracks, tempo, and timing info."""
    tracks: List[Track] = field(default_factory=list)
    tempo_bpm: float = config.DEFAULT_TEMPO_BPM
    ticks_per_beat: int = config.TICKS_PER_QUARTER_NOTE
    time_sig_num: int = config.DEFAULT_TIME_SIG_NUM
    time_sig_den: int = config.DEFAULT_TIME_SIG_DEN
    duration_ticks: int = 0
    source_file: Optional[str] = None

    @property
    def duration_seconds(self):
        beats = self.duration_ticks / self.ticks_per_beat
        return beats * (60.0 / self.tempo_bpm)

    @property
    def duration_bars(self):
        beats = self.duration_ticks / self.ticks_per_beat
        return beats / self.time_sig_num

    @property
    def ticks_per_bar(self):
        return self.ticks_per_beat * self.time_sig_num


def parse_midi_file(midi_path):
    """
    Parse a MIDI file into our internal Song representation.

    Args:
        midi_path: Path to .mid file

    Returns:
        Song object with tracks, tempo, and timing
    """
    try:
        import mido
    except ImportError:
        raise ImportError("mido is required for MIDI parsing.\nInstall with: pip install mido")

    mid = mido.MidiFile(midi_path)

    song = Song(
        ticks_per_beat=mid.ticks_per_beat,
        source_file=midi_path,
    )

    # Extract tempo and time signature from meta messages
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                song.tempo_bpm = round(mido.tempo2bpm(msg.tempo), 2)
            elif msg.type == "time_signature":
                song.time_sig_num = msg.numerator
                song.time_sig_den = msg.denominator

    # Parse note events from each track
    for i, midi_track in enumerate(mid.tracks):
        track = Track(
            name=midi_track.name or f"Track {i + 1}",
            channel=0,
        )

        # Track active notes: (pitch, channel) -> (start_tick, velocity)
        active_notes = {}
        current_tick = 0

        for msg in midi_track:
            current_tick += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                key = (msg.note, msg.channel)
                active_notes[key] = (current_tick, msg.velocity)
                track.channel = msg.channel
                if msg.channel == 9:
                    track.is_drum = True

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.note, msg.channel)
                if key in active_notes:
                    start, vel = active_notes.pop(key)
                    duration = current_tick - start
                    if duration > 0:
                        track.notes.append(Note(
                            pitch=msg.note,
                            start_tick=start,
                            duration_tick=duration,
                            velocity=vel,
                            channel=msg.channel,
                        ))

            elif msg.type == "program_change":
                track.program = msg.program

        if track.notes:
            # Sort notes by start time, then pitch
            track.notes.sort(key=lambda n: (n.start_tick, n.pitch))
            song.tracks.append(track)

    # Calculate total duration
    if song.tracks:
        max_tick = max(
            n.start_tick + n.duration_tick
            for t in song.tracks
            for n in t.notes
        )
        song.duration_ticks = max_tick

    return song


def rescale_ticks(song, target_tpb=None):
    """
    Rescale all tick values to match the Deluge's tick resolution.

    Args:
        song: Song object to rescale (modified in place)
        target_tpb: Target ticks per beat (default: Deluge's 48)

    Returns:
        Modified Song object
    """
    target_tpb = target_tpb or config.TICKS_PER_QUARTER_NOTE

    if song.ticks_per_beat == target_tpb:
        return song

    scale = target_tpb / song.ticks_per_beat

    for track in song.tracks:
        for note in track.notes:
            note.start_tick = round(note.start_tick * scale)
            note.duration_tick = max(1, round(note.duration_tick * scale))

    song.duration_ticks = round(song.duration_ticks * scale)
    song.ticks_per_beat = target_tpb
    return song


def note_events_to_track(note_events, name="transcribed", ticks_per_beat=None):
    """
    Convert Basic Pitch note_events to our internal Track format.

    Basic Pitch note_events are lists of:
        [start_time_sec, end_time_sec, pitch, velocity, [pitch_bends]]

    Args:
        note_events: List from basic_pitch predict()
        name: Track name
        ticks_per_beat: Resolution (default: Deluge's 48)

    Returns:
        Track object
    """
    tpb = ticks_per_beat or config.TICKS_PER_QUARTER_NOTE
    # We need tempo to convert seconds to ticks; default 120 BPM
    # ticks_per_second = tpb * (tempo / 60)
    # For now we'll store the conversion factor and let the caller set tempo
    tps = tpb * (config.DEFAULT_TEMPO_BPM / 60.0)

    track = Track(name=name)

    for event in note_events:
        start_sec = event[0]
        end_sec = event[1]
        pitch = int(event[2])
        velocity = min(127, max(1, int(event[3])))

        start_tick = round(start_sec * tps)
        end_tick = round(end_sec * tps)
        duration = max(1, end_tick - start_tick)

        track.notes.append(Note(
            pitch=pitch,
            start_tick=start_tick,
            duration_tick=duration,
            velocity=velocity,
        ))

    track.notes.sort(key=lambda n: (n.start_tick, n.pitch))
    return track


def quantize_notes(track, grid_ticks=None):
    """
    Quantize note start times and durations to a grid.

    Args:
        track: Track to quantize (modified in place)
        grid_ticks: Grid size in ticks (default: 1/16 note = 12 ticks at 48 TPQN)

    Returns:
        Modified Track
    """
    grid = grid_ticks or (config.TICKS_PER_QUARTER_NOTE // 4)  # 16th note

    for note in track.notes:
        note.start_tick = round(note.start_tick / grid) * grid
        note.duration_tick = max(grid, round(note.duration_tick / grid) * grid)

    return track
