"""
CLI interface for Deluge AI.

Usage:
    # Process an audio file (full pipeline: stems -> MIDI -> Deluge)
    python -m deluge_ai process song.wav

    # Process a MIDI file directly
    python -m deluge_ai process song.mid

    # Process audio, stems only (no MIDI transcription)
    python -m deluge_ai process song.wav --audio-only

    # Process and preview locally
    python -m deluge_ai process song.wav --play

    # Process and package for Deluge SD card
    python -m deluge_ai process song.wav --sd-card /media/DELUGE

    # Preview stems from a previous run
    python -m deluge_ai play ./output/stems

    # Package previous output for Deluge
    python -m deluge_ai package ./output --sd-card /media/DELUGE

    # Generate random synth patches (original rndsynth functionality)
    python -m deluge_ai synth --base 250
"""

import argparse
import os
import sys


def create_parser():
    parser = argparse.ArgumentParser(
        prog="deluge_ai",
        description="AI-powered music generation and conversion for the Synthstrom Deluge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s process song.wav                    Full pipeline: stems + MIDI + Deluge
  %(prog)s process song.wav --play             Process and preview locally
  %(prog)s process song.wav --audio-only       Stems only, no MIDI transcription
  %(prog)s process song.mid                    Convert MIDI to Deluge song
  %(prog)s process song.wav --sd-card /mnt/sd  Process and copy to SD card
  %(prog)s play ./output/stems                 Preview stems from previous run
  %(prog)s package ./output --sd-card /mnt/sd  Package output for Deluge
  %(prog)s synth --base 250                    Generate random synth patches
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- process command ---
    proc = subparsers.add_parser("process", help="Process audio or MIDI into Deluge format")
    proc.add_argument("input", help="Input audio file (WAV/MP3/FLAC) or MIDI file (.mid)")
    proc.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
    proc.add_argument("--tempo", type=float, help="Override tempo in BPM")
    proc.add_argument("--audio-only", action="store_true", help="Audio clips only, skip MIDI transcription")
    proc.add_argument("--no-quantize", action="store_true", help="Don't quantize transcribed notes")
    proc.add_argument("--play", action="store_true", help="Preview stems after processing")
    proc.add_argument("--interactive", action="store_true", help="Interactive stem player (with --play)")
    proc.add_argument("--sd-card", metavar="PATH", help="Copy output to Deluge SD card at PATH")
    proc.add_argument("--song-name", default="SONG001", help="Song name for Deluge (default: SONG001)")
    proc.add_argument("--demucs-model", default=None, help="Demucs model (default: htdemucs)")

    # --- play command ---
    play = subparsers.add_parser("play", help="Preview stems from a previous run")
    play.add_argument("stems_dir", help="Directory containing stem WAV files")
    play.add_argument("--interactive", action="store_true", help="Interactive stem player")
    play.add_argument("--mix", action="store_true", help="Play all stems mixed (default)")

    # --- package command ---
    pkg = subparsers.add_parser("package", help="Package output for Deluge SD card")
    pkg.add_argument("project_dir", help="Project output directory to package")
    pkg.add_argument("--sd-card", metavar="PATH", required=True, help="Target SD card or directory path")
    pkg.add_argument("--song-name", default="SONG001", help="Song name for Deluge (default: SONG001)")

    # --- synth command (original rndsynth functionality) ---
    synth = subparsers.add_parser("synth", help="Generate random Deluge synth patches")
    synth.add_argument("--base", required=True, help="3-digit patch number base (e.g. 250)")
    synth.add_argument("--count", type=int, default=26, help="Number of patches (default: 26, A-Z)")
    synth.add_argument("--semitones", action="store_true", help="Use semitone intervals")
    synth.add_argument("--octave-range", type=int, default=4, help="Octave range (1-8)")
    synth.add_argument("--patch-limit", type=int, default=8, help="Modulation connections limit")
    synth.add_argument("--output", "-o", default=".", help="Output directory")

    # --- info command ---
    info = subparsers.add_parser("info", help="Show dependency status and system info")

    return parser


def cmd_process(args):
    """Handle the 'process' command."""
    from .pipeline import Pipeline

    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    pipeline = Pipeline(output_dir=args.output, tempo_bpm=args.tempo)

    # Detect input type
    ext = os.path.splitext(args.input)[1].lower()

    if ext in (".mid", ".midi"):
        result = pipeline.process_midi(args.input)
    elif ext in (".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif"):
        result = pipeline.process_audio(
            args.input,
            skip_transcribe=args.audio_only,
            quantize=not args.no_quantize,
        )
    else:
        print(f"Error: Unsupported file type: {ext}")
        print("Supported: .wav, .mp3, .flac, .ogg, .aiff, .mid, .midi")
        sys.exit(1)

    # Preview if requested
    if args.play:
        pipeline.preview(interactive=args.interactive)

    # Package for SD card if requested
    if args.sd_card:
        pipeline.package(sd_card_path=args.sd_card, song_name=args.song_name)


def cmd_play(args):
    """Handle the 'play' command."""
    from . import player

    if not player.check_audio_available():
        print("Audio playback requires: pip install sounddevice soundfile")
        sys.exit(1)

    if not os.path.isdir(args.stems_dir):
        print(f"Error: Directory not found: {args.stems_dir}")
        sys.exit(1)

    if args.interactive:
        player.play_stems_interactive(args.stems_dir)
    else:
        player.play_stems_mixed(args.stems_dir)


def cmd_package(args):
    """Handle the 'package' command."""
    from . import sd_card

    if not os.path.isdir(args.project_dir):
        print(f"Error: Project directory not found: {args.project_dir}")
        sys.exit(1)

    print(f"Packaging {args.project_dir} for Deluge...")
    sd_card.package_for_deluge(args.project_dir, args.sd_card, song_name=args.song_name)
    print("Done!")


def cmd_synth(args):
    """Handle the 'synth' command (random patch generation)."""
    from .synth_builder import SynthPatchBuilder

    if len(args.base) != 3 or not args.base.isdigit():
        print("Error: --base must be 3 digits (e.g. 250)")
        sys.exit(1)

    builder = SynthPatchBuilder(
        semitones=args.semitones,
        octave_range=args.octave_range,
        patch_limit=args.patch_limit,
    )

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: args.count]
    os.makedirs(args.output, exist_ok=True)

    print(f"Generating {len(letters)} random synth patches...")
    for letter in letters:
        filename = f"SYNT{args.base}{letter}.XML"
        path = os.path.join(args.output, filename)
        builder.generate_patch(output_path=path)
        print(f"  -> {filename}")

    print(f"Done! {len(letters)} patches written to {args.output}")


def cmd_info(args):
    """Handle the 'info' command."""
    from . import __version__

    print(f"Deluge AI v{__version__}")
    print(f"{'='*40}")

    deps = [
        ("lxml", "XML generation (Deluge patches)"),
        ("numpy", "Audio processing"),
        ("soundfile", "WAV file I/O"),
        ("sounddevice", "Audio playback"),
        ("mido", "MIDI parsing"),
        ("demucs", "Stem separation (Meta)"),
        ("basic_pitch", "Audio-to-MIDI (Spotify)"),
    ]

    print("\nDependencies:")
    for mod_name, desc in deps:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", "?")
            print(f"  [OK] {mod_name:15s} {ver:10s}  {desc}")
        except ImportError:
            print(f"  [--] {mod_name:15s} {'missing':10s}  {desc}")

    print(f"\nRequired for full pipeline: demucs, basic_pitch")
    print(f"Minimum for MIDI->Deluge:  lxml, mido")
    print(f"For local playback:        sounddevice, soundfile")


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "process": cmd_process,
        "play": cmd_play,
        "package": cmd_package,
        "synth": cmd_synth,
        "info": cmd_info,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
