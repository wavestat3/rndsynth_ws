"""
Deluge synth patch XML generator.

Refactored from the original rndsynth.py to be importable as a module.
Generates random or configured synth patches for Deluge tracks.
"""

import os
import random
import math
from lxml import etree as ET
from . import config


def hex_string(x):
    """Convert integer to Deluge hex format."""
    h = hex(x & 0xFFFFFFFF)
    if len(h) < 10:
        h = "0x" + "0" * (10 - len(h)) + h[2:]
    return h


# Pre-computed value ranges (matching original rndsynth.py)
_SINT_RANGE = abs(config.SINT_MIN) + config.SINT_MAX
_SINT_STEP = int(_SINT_RANGE / 50)
_INT_STEP = int(config.SINT_MAX / 50)

SINT50 = [hex_string(i) for i in range(config.SINT_MIN, config.SINT_MAX, _SINT_STEP)]
INT50 = [hex_string(i) for i in range(0, config.SINT_MAX, _INT_STEP)]

# Modulation ranges (biased toward higher values)
M_MIN = -1073741800
M_MAX = 1073741800
M_INT = [hex_string(i) for i in range(M_MIN, M_MAX, _INT_STEP)]

# Envelope ranges (biased toward lower values)
E_MIN = config.SINT_MIN
E_MAX = 0
E_INT_STEP = int((abs(E_MIN) + E_MAX) / 50)
E_INT = [hex_string(i) for i in range(E_MIN, E_MAX, E_INT_STEP)]


PATCH_CABLE_SOURCES = [
    "lfo1", "lfo2", "envelope1", "envelope2",
    "velocity", "note", "random", "aftertouch",
]

PATCH_CABLE_DESTINATIONS = [
    "oscAVolume", "oscBVolume", "noiseVolume", "range",
    "oscAPhaseWidth", "oscBPhaseWidth", "lpfResonance", "hpfResonance",
    "pan", "modulator1Volume", "modulator2Volume", "lpfFrequency",
    "pitch", "oscAPitch", "oscBPitch", "modulator1Pitch",
    "modulator2Pitch", "hpfFrequency", "lfo2Rate",
    "env1Attack", "env1Decay", "env1Sustain", "env1Release",
    "env2Attack", "env2Decay", "env2Sustain", "env2Release",
    "lfo1Rate", "volumePostFX", "volumePostReverbSend",
    "delayRate", "delayFeedback", "reverbAmount",
    "modFXRate", "modFXDepth", "arpRate",
    "modulator1Feedback", "modulator2Feedback",
    "carrier1Feedback", "carrier2Feedback",
]


class SynthPatchBuilder:
    """Builds Deluge synth patch XML files."""

    def __init__(self, **kwargs):
        self.octave_range = kwargs.get("octave_range", 4)
        self.semitones = kwargs.get("semitones", False)
        self.patch_limit = kwargs.get("patch_limit", 8)
        self.unison_limit = kwargs.get("unison_limit", 4)
        self.delay_limit = kwargs.get("delay_limit", 10)
        self.reverb_limit = kwargs.get("reverb_limit", 25)
        self.lpf_minimum = kwargs.get("lpf_minimum", 25)
        self.hpf_maximum = kwargs.get("hpf_maximum", 25)
        self.res_limit = kwargs.get("res_limit", 20)
        self.noise_limit = kwargs.get("noise_limit", 20)
        self.srr_limit = kwargs.get("srr_limit", 2)
        self.brr_limit = kwargs.get("brr_limit", 2)
        self.saturation_limit = kwargs.get("saturation_limit", 2)
        self.rnd_arpeggiator = kwargs.get("rnd_arpeggiator", False)
        self.rnd_mod_fx = kwargs.get("rnd_mod_fx", False)

    def generate_patch(self, output_path=None, mode=None):
        """
        Generate a random Deluge synth patch.

        Args:
            output_path: Path to write XML file (optional)
            mode: Force synth mode ("subtractive", "fm", "ringmod") or None for random

        Returns:
            ElementTree of the generated patch
        """
        sound = ET.Element("sound")

        # Oscillators
        osc1 = ET.SubElement(sound, "osc1")
        self._set(osc1, "type", random.choice(config.OSC_TYPES_SUBTRACTIVE))
        self._set_transpose(osc1)
        self._set(osc1, "cents", str(random.randint(-99, 99)))
        self._set(osc1, "retrigPhase", str(random.randint(-1, 270)))

        osc2 = ET.SubElement(sound, "osc2")
        self._set(osc2, "type", random.choice(config.OSC_TYPES_SUBTRACTIVE))
        self._set_transpose(osc2)
        self._set(osc2, "cents", str(random.randint(-99, 99)))
        self._set(osc2, "retrigPhase", str(random.randint(-1, 270)))

        # Voice settings
        self._set(sound, "polyphonic", random.choice(config.POLYPHONY_MODES))
        self._set(sound, "clippingAmount", str(random.randint(0, self.saturation_limit)))
        self._set(sound, "voicePriority", str(random.randint(0, 2)))

        # LFOs
        lfo1 = ET.SubElement(sound, "lfo1")
        self._set(lfo1, "lfoType", random.choice(config.LFO_TYPES))
        self._set(lfo1, "lfoSyncLevel", str(random.randint(0, 9)))
        lfo2 = ET.SubElement(sound, "lfo2")
        self._set(lfo2, "lfoType", random.choice(config.LFO_TYPES))

        # Synth mode
        current_mode = mode or random.choice(config.SYNTH_MODES)
        self._set(sound, "mode", current_mode)

        # Unison
        unison = ET.SubElement(sound, "unison")
        self._set(unison, "num", str(random.randint(1, self.unison_limit)))
        self._set(unison, "detune", str(random.randint(0, 50)))

        # Filter
        self._set(sound, "lpfMode", random.choice(config.LPF_MODES))

        # Mod FX
        if self.rnd_mod_fx:
            self._set(sound, "modFXType", random.choice(["off", "flanger", "chorus", "phaser"]))
        else:
            self._set(sound, "modFXType", "off")

        # Delay
        delay = ET.SubElement(sound, "delay")
        self._set(delay, "delayPingPong", str(random.randint(0, 1)))
        self._set(delay, "delayAnalog", str(random.randint(0, 1)))
        self._set(delay, "delaySyncLevel", str(random.randint(0, 9)))

        # Default parameters
        params = ET.SubElement(sound, "defaultParams")
        self._set(params, "arpeggiatorGate", random.choice(SINT50))
        self._set(params, "portamento", random.choice(SINT50))
        self._set(params, "oscAVolume", random.choice(INT50))
        self._set(params, "oscAPulseWidth", random.choice(INT50))
        self._set(params, "oscBVolume", random.choice(INT50))
        self._set(params, "oscBPulseWidth", random.choice(INT50))
        self._set(params, "noiseVolume", random.choice(SINT50[: self.noise_limit + 1]))
        self._set(params, "volume", random.choice(INT50))
        self._set(params, "pan", random.choice(SINT50))
        self._set(params, "lpfFrequency", random.choice(SINT50[self.lpf_minimum:]))
        self._set(params, "lpfResonance", random.choice(SINT50[: self.res_limit + 1]))
        self._set(params, "hpfFrequency", random.choice(SINT50[: self.hpf_maximum + 1]))
        self._set(params, "hpfResonance", random.choice(SINT50[: self.res_limit + 1]))

        # Envelopes
        for env_name in ["envelope1", "envelope2"]:
            env = ET.SubElement(params, env_name)
            self._set(env, "attack", random.choice(SINT50))
            self._set(env, "decay", random.choice(SINT50))
            self._set(env, "sustain", random.choice(SINT50))
            self._set(env, "release", random.choice(SINT50))

        # LFO rates
        self._set(params, "lfo1Rate", random.choice(INT50))
        self._set(params, "lfo2Rate", random.choice(INT50))

        # FM parameters
        self._set(params, "modulator1Amount", random.choice(SINT50))
        self._set(params, "modulator2Amount", random.choice(SINT50))
        self._set(params, "modulator1Feedback", random.choice(SINT50))
        self._set(params, "modulator2Feedback", random.choice(SINT50))
        self._set(params, "carrier1Feedback", random.choice(SINT50))
        self._set(params, "carrier2Feedback", random.choice(SINT50))

        # Effects
        if self.rnd_mod_fx:
            self._set(params, "modFXRate", random.choice(INT50))
            self._set(params, "modFXDepth", random.choice(INT50))
        else:
            self._set(params, "modFXRate", "0")
            self._set(params, "modFXDepth", "0")

        self._set(params, "delayRate", random.choice(INT50))
        self._set(params, "delayFeedback", random.choice(SINT50[: self.delay_limit + 1]))
        self._set(params, "reverbAmount", random.choice(SINT50[: self.reverb_limit + 1]))

        # Patch cables (modulation routing)
        cables = ET.SubElement(params, "patchCables")
        # Default: velocity -> volume
        cable = ET.SubElement(cables, "patchCable")
        self._set(cable, "source", "velocity")
        self._set(cable, "destination", "volume")
        self._set(cable, "amount", "1073741800")

        for _ in range(self.patch_limit):
            cable = ET.SubElement(cables, "patchCable")
            self._set(cable, "source", random.choice(PATCH_CABLE_SOURCES))
            self._set(cable, "destination", random.choice(PATCH_CABLE_DESTINATIONS))
            self._set(cable, "amount", random.choice(M_INT))

        # Effects (cont.)
        self._set(params, "stutterRate", random.choice(INT50))
        self._set(params, "sampleRateReduction", random.choice(SINT50[: self.srr_limit + 1]))
        self._set(params, "bitCrush", random.choice(SINT50[: self.brr_limit + 1]))

        # Arpeggiator
        if self.rnd_arpeggiator:
            arp_mode = random.choice([0, "up", "down", "both", "random"])
            if arp_mode != 0:
                arp = ET.SubElement(sound, "arpeggiator")
                self._set(arp, "mode", str(arp_mode))
                self._set(arp, "numOctaves", str(random.randint(1, 4)))
                self._set(arp, "syncLevel", str(random.randint(0, 9)))

        # Mod knobs
        mod_knobs = ET.SubElement(sound, "modKnobs")
        mod_knobs.text = ""

        # Write if output path given
        tree = ET.ElementTree(sound)
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            tree.write(output_path, pretty_print=True, encoding="UTF-8", xml_declaration=True)

        return tree

    def generate_patches_for_stems(self, output_dir, stem_names=None):
        """
        Generate synth patches for each stem track.

        Args:
            output_dir: Directory to write patch files
            stem_names: List of stem names (default: bass, other)

        Returns:
            dict of stem_name -> patch filename
        """
        stem_names = stem_names or ["bass", "other"]
        patches = {}

        for i, name in enumerate(stem_names):
            filename = f"SYNT_AI_{name.upper()}.XML"
            path = os.path.join(output_dir, filename)

            mode = config.STEM_TRACK_MAP.get(name, {}).get("mode", "subtractive")
            self.generate_patch(output_path=path, mode=mode)
            patches[name] = filename
            print(f"    -> {filename}")

        return patches

    def _set(self, element, tag_or_attr, value):
        """Set a value as either a child element text or attribute."""
        # Use attributes for Deluge v3+ format
        element.set(tag_or_attr, str(value))

    def _set_transpose(self, osc_element):
        """Set random transpose value."""
        o_max = self.octave_range * 12
        o_min = -self.octave_range * 12
        if self.semitones:
            val = random.randrange(o_min, o_max, 1)
        else:
            val = random.randrange(o_min, o_max, 12)
        self._set(osc_element, "transpose", str(val))
