"""
Main pipeline orchestrator for Deluge AI.

Coordinates the full workflow:
  Input (audio/MIDI/AI) -> Tear Apart -> Reassemble -> Preview -> Deluge
"""

import os
import json
import time
from . import config
from .midi_utils import Song, rescale_ticks, note_events_to_track, quantize_notes


class Pipeline:
    """
    Orchestrates the full audio-to-Deluge pipeline.

    Workflow:
      1. Input: audio file, MIDI file, or AI-generated content
      2. Stem separation: Demucs splits audio into drums/bass/vocals/other
      3. Transcription: Basic Pitch converts each stem to MIDI
      4. Song building: Assemble Deluge song XML with clips and notes
      5. Synth patches: Generate random or configured patches per track
      6. Preview: Play locally before pushing to Deluge
      7. Package: Build SD card folder structure
    """

    def __init__(self, output_dir=None, tempo_bpm=None):
        self.output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        self.tempo_bpm = tempo_bpm
        self.stems_dir = os.path.join(self.output_dir, "stems")
        self.midi_dir = os.path.join(self.output_dir, "midi")
        self.deluge_dir = os.path.join(self.output_dir, "deluge")
        self.project_info = {}

    def process_audio(self, input_audio, skip_transcribe=False, quantize=True):
        """
        Full pipeline: audio -> stems -> MIDI -> Deluge.

        Args:
            input_audio: Path to input audio file
            skip_transcribe: If True, only create audio clips (no MIDI transcription)
            quantize: If True, quantize transcribed notes to 16th note grid

        Returns:
            dict with paths to all generated files
        """
        from . import stems as stems_mod
        from . import audio as audio_mod

        result = {
            "input": input_audio,
            "stems": {},
            "midi": {},
            "song_xml": None,
            "synth_patches": {},
            "deluge_stems": {},
        }

        os.makedirs(self.output_dir, exist_ok=True)

        # --- Step 1: Detect tempo from audio ---
        audio_duration = audio_mod.get_duration_seconds(input_audio)
        detected_tempo = self.tempo_bpm or config.DEFAULT_TEMPO_BPM
        print(f"\n{'='*60}")
        print(f"  DELUGE AI - Processing: {os.path.basename(input_audio)}")
        print(f"  Duration: {audio_duration:.1f}s | Tempo: {detected_tempo} BPM")
        print(f"{'='*60}\n")

        # --- Step 2: Separate stems ---
        print("[1/5] Separating stems...")
        stem_paths = stems_mod.separate_stems(input_audio, self.stems_dir)
        result["stems"] = stem_paths
        print(f"  Done: {len(stem_paths)} stems separated.\n")

        # --- Step 3: Convert stems to Deluge-compatible WAV ---
        print("[2/5] Converting stems to Deluge format (44.1kHz/16-bit)...")
        for name, path in stem_paths.items():
            deluge_path = os.path.join(self.stems_dir, f"{name}.wav")
            audio_mod.convert_to_deluge_wav(path, deluge_path)
            result["deluge_stems"][name] = deluge_path
            print(f"    -> {name}.wav")
        print()

        # --- Step 4: Transcribe stems to MIDI ---
        song_data = Song(tempo_bpm=detected_tempo)

        if not skip_transcribe:
            print("[3/5] Transcribing stems to MIDI...")
            from . import transcribe as transcribe_mod

            transcription = transcribe_mod.transcribe_stems(stem_paths, self.midi_dir)

            for stem_name, tr_result in transcription.items():
                if tr_result and tr_result["note_events"]:
                    track = note_events_to_track(
                        tr_result["note_events"],
                        name=stem_name,
                        ticks_per_beat=config.TICKS_PER_QUARTER_NOTE,
                    )
                    if stem_name == "drums":
                        track.is_drum = True
                    if quantize:
                        quantize_notes(track)
                    song_data.tracks.append(track)
                    result["midi"][stem_name] = tr_result["midi_path"]

            # Calculate total duration
            if song_data.tracks:
                song_data.duration_ticks = max(
                    n.start_tick + n.duration_tick
                    for t in song_data.tracks
                    for n in t.notes
                ) if any(t.notes for t in song_data.tracks) else 0

            print(f"  Done: {len(song_data.tracks)} tracks with MIDI data.\n")
        else:
            print("[3/5] Skipping MIDI transcription (audio-only mode).\n")

        # --- Step 5: Generate synth patches ---
        print("[4/5] Generating synth patches...")
        from .synth_builder import SynthPatchBuilder

        os.makedirs(self.deluge_dir, exist_ok=True)
        builder = SynthPatchBuilder()
        synth_stems = [n for n in stem_paths if config.STEM_TRACK_MAP.get(n, {}).get("type") == "synth"]
        if synth_stems:
            result["synth_patches"] = builder.generate_patches_for_stems(self.deluge_dir, synth_stems)
        print()

        # --- Step 6: Build Deluge song XML ---
        print("[5/5] Building Deluge song XML...")
        from .song_builder import build_song_xml

        song_xml_path = os.path.join(self.deluge_dir, "SONG001.XML")
        build_song_xml(
            song_data,
            stem_paths=result["deluge_stems"],
            synth_patches=result["synth_patches"],
            output_path=song_xml_path,
        )
        result["song_xml"] = song_xml_path

        # --- Save project info ---
        self.project_info = {
            "input": input_audio,
            "tempo_bpm": detected_tempo,
            "duration_seconds": audio_duration,
            "stems": list(result["stems"].keys()),
            "midi_tracks": [t.name for t in song_data.tracks],
            "output_dir": self.output_dir,
        }

        info_path = os.path.join(self.output_dir, "project.json")
        with open(info_path, "w") as f:
            json.dump(self.project_info, f, indent=2)

        print(f"\n{'='*60}")
        print(f"  DONE! Output: {self.output_dir}")
        print(f"  Stems:  {self.stems_dir}")
        print(f"  MIDI:   {self.midi_dir}")
        print(f"  Deluge: {self.deluge_dir}")
        print(f"{'='*60}\n")

        return result

    def process_midi(self, input_midi):
        """
        Process a MIDI file directly into a Deluge song.

        Args:
            input_midi: Path to input MIDI file

        Returns:
            dict with paths to generated files
        """
        from .midi_utils import parse_midi_file, rescale_ticks
        from .song_builder import build_song_xml
        from .synth_builder import SynthPatchBuilder

        result = {"input": input_midi, "song_xml": None, "synth_patches": {}}

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.deluge_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  DELUGE AI - Processing MIDI: {os.path.basename(input_midi)}")
        print(f"{'='*60}\n")

        # Parse MIDI
        print("[1/3] Parsing MIDI file...")
        song_data = parse_midi_file(input_midi)
        rescale_ticks(song_data)

        if self.tempo_bpm:
            song_data.tempo_bpm = self.tempo_bpm

        print(f"  Tempo: {song_data.tempo_bpm} BPM")
        print(f"  Tracks: {len(song_data.tracks)}")
        for t in song_data.tracks:
            print(f"    - {t.name}: {len(t.notes)} notes {'(drums)' if t.is_drum else ''}")
        print()

        # Generate synth patches
        print("[2/3] Generating synth patches...")
        builder = SynthPatchBuilder()
        track_names = [t.name for t in song_data.tracks if not t.is_drum]
        if track_names:
            result["synth_patches"] = builder.generate_patches_for_stems(
                self.deluge_dir, track_names
            )
        print()

        # Build song XML
        print("[3/3] Building Deluge song XML...")
        song_xml_path = os.path.join(self.deluge_dir, "SONG001.XML")
        build_song_xml(
            song_data,
            synth_patches=result["synth_patches"],
            output_path=song_xml_path,
        )
        result["song_xml"] = song_xml_path

        print(f"\n{'='*60}")
        print(f"  DONE! Output: {self.deluge_dir}")
        print(f"{'='*60}\n")

        return result

    def preview(self, interactive=False):
        """Play back the generated stems locally."""
        from . import player

        if not player.check_audio_available():
            print("  Audio playback requires: pip install sounddevice soundfile")
            return

        if interactive:
            player.play_stems_interactive(self.stems_dir)
        else:
            player.play_stems_mixed(self.stems_dir)

    def package(self, sd_card_path=None, song_name="SONG001"):
        """Package everything for the Deluge SD card."""
        from . import sd_card

        target = sd_card_path or os.path.join(self.output_dir, "DELUGE_SD")
        print(f"\n  Packaging for Deluge -> {target}")

        if sd_card_path and sd_card.verify_sd_card(sd_card_path):
            print("  Detected existing Deluge SD card structure.")

        packaged = sd_card.package_for_deluge(
            self.output_dir, target, song_name=song_name
        )

        total = sum(len(v) for v in packaged.values())
        print(f"\n  Packaged {total} files for Deluge.")
        return packaged
