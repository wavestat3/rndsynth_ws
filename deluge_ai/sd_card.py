"""
Deluge SD card packager.

Assembles all generated files into the correct folder structure
for the Deluge's SD card (FAT32).
"""

import os
import shutil
from . import config


def package_for_deluge(project_dir, output_dir, song_name="SONG001"):
    """
    Package generated files into Deluge SD card folder structure.

    Creates:
        output_dir/
        ├── SONGS/SONG001.XML
        ├── SYNTHS/SYNT_AI_*.XML
        ├── KITS/
        ├── SAMPLES/
        │   └── STEMS/
        │       ├── drums.wav
        │       ├── bass.wav
        │       ├── vocals.wav
        │       └── other.wav

    Args:
        project_dir: Directory containing generated stems, MIDI, and XML files
        output_dir: Target directory (SD card root or staging area)
        song_name: Base name for the song file

    Returns:
        dict with paths to all packaged files
    """
    packaged = {"songs": [], "synths": [], "kits": [], "samples": []}

    # Create Deluge folder structure
    songs_dir = os.path.join(output_dir, config.DELUGE_SONGS_DIR)
    synths_dir = os.path.join(output_dir, config.DELUGE_SYNTHS_DIR)
    kits_dir = os.path.join(output_dir, config.DELUGE_KITS_DIR)
    stems_dir = os.path.join(output_dir, config.DELUGE_STEMS_SUBDIR)

    for d in [songs_dir, synths_dir, kits_dir, stems_dir]:
        os.makedirs(d, exist_ok=True)

    # 1. Copy song XML
    song_xml = _find_file(project_dir, "*.XML", subdir="deluge")
    if not song_xml:
        song_xml = _find_file(project_dir, "SONG*.XML")
    if song_xml:
        dst = os.path.join(songs_dir, f"{song_name}.XML")
        shutil.copy2(song_xml, dst)
        packaged["songs"].append(dst)
        print(f"  -> {config.DELUGE_SONGS_DIR}/{song_name}.XML")

    # 2. Copy synth patches
    synth_files = _find_files(project_dir, "SYNT*.XML")
    for sf_path in synth_files:
        dst = os.path.join(synths_dir, os.path.basename(sf_path))
        shutil.copy2(sf_path, dst)
        packaged["synths"].append(dst)
        print(f"  -> {config.DELUGE_SYNTHS_DIR}/{os.path.basename(sf_path)}")

    # 3. Copy kit patches
    kit_files = _find_files(project_dir, "KIT*.XML")
    for kf_path in kit_files:
        dst = os.path.join(kits_dir, os.path.basename(kf_path))
        shutil.copy2(kf_path, dst)
        packaged["kits"].append(dst)

    # 4. Copy audio stems
    stems_source = os.path.join(project_dir, "stems")
    if os.path.isdir(stems_source):
        for f in os.listdir(stems_source):
            if f.endswith(".wav"):
                src = os.path.join(stems_source, f)
                dst = os.path.join(stems_dir, f)
                shutil.copy2(src, dst)
                packaged["samples"].append(dst)
                print(f"  -> {config.DELUGE_STEMS_SUBDIR}/{f}")

    # Also check for stems directly in project dir
    for stem_name in config.STEM_NAMES:
        src = os.path.join(project_dir, f"{stem_name}.wav")
        if os.path.exists(src):
            dst = os.path.join(stems_dir, f"{stem_name}.wav")
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                packaged["samples"].append(dst)
                print(f"  -> {config.DELUGE_STEMS_SUBDIR}/{stem_name}.wav")

    return packaged


def verify_sd_card(sd_path):
    """
    Verify that a path looks like a Deluge SD card.

    Args:
        sd_path: Path to check

    Returns:
        bool indicating if this looks like a valid Deluge SD card
    """
    if not os.path.isdir(sd_path):
        return False

    # Check for common Deluge directories
    deluge_markers = [
        config.DELUGE_SONGS_DIR,
        config.DELUGE_SYNTHS_DIR,
        config.DELUGE_SAMPLES_DIR,
    ]

    found = sum(1 for d in deluge_markers if os.path.isdir(os.path.join(sd_path, d)))
    return found >= 2


def _find_file(directory, pattern, subdir=None):
    """Find a single file matching a pattern."""
    import glob
    search_dir = os.path.join(directory, subdir) if subdir else directory
    if not os.path.isdir(search_dir):
        search_dir = directory
    matches = glob.glob(os.path.join(search_dir, pattern))
    return matches[0] if matches else None


def _find_files(directory, pattern):
    """Find all files matching a pattern, recursively."""
    import glob
    results = []
    for root, dirs, files in os.walk(directory):
        matches = glob.glob(os.path.join(root, pattern))
        results.extend(matches)
    return results
