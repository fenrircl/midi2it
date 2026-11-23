import tempfile
import struct
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from core import it_writer, smconv_runner


class ITFormatTests(unittest.TestCase):
    def test_packed_pattern_uses_one_based_channels(self):
        pattern = it_writer._pack_pattern([
            {
                0: {"note": 61, "instrument": 1, "volume": 48},
                1: {"note": 65, "instrument": 2, "volume": 52},
            }
        ] + [{}] * 63, 2)

        # Skip the IT pattern header; channel IDs in packed patterns start at 1.
        events = pattern[8:]
        self.assertEqual(events[:5], bytes([0x81, 0x07, 61, 1, 48]))
        self.assertEqual(events[5:10], bytes([0x82, 0x07, 65, 2, 52]))
        self.assertNotIn(0x80, events[:10])

    def test_build_disables_unused_channels_and_keeps_real_sample(self):
        midi = {
            "filename": "tiny.mid",
            "ticks_per_beat": 480,
            "tempo": 120,
            "tracks": [{"index": 0, "name": "Piano", "notes": [
                {"pitch": 60, "start_tick": 0, "duration_tick": 480, "velocity": 100},
            ]}],
        }
        samples = {0: {
            "name": "tone", "rate": 16000, "data": b"\x10\x20" * 512,
            "has_loop": True, "loop_st": 0, "loop_en": 512,
        }}
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "tiny.it"
            it_writer.build(midi, samples, str(out), track_config=[{
                "midi_track": 0, "sample_index": 0, "volume": 100,
                "transpose": 0, "name": "Piano",
            }])

            data = out.read_bytes()
        self.assertEqual(data[:4], b"IMPM")
        self.assertEqual(data[0x40], 32)
        self.assertEqual(data[0x41], 0x80)
        self.assertEqual(data[0x80], 64)
        self.assertEqual(data[0x81], 0)
        self.assertEqual(struct.unpack_from("<H", data, 34)[0], 1)  # instruments
        self.assertEqual(struct.unpack_from("<H", data, 36)[0], 1)  # unique samples

    def test_smconv_errors_are_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(smconv_runner, "find_smconv", return_value="/fake/smconv"), \
                    patch.object(smconv_runner.subprocess, "run", return_value=SimpleNamespace(
                        returncode=0,
                        stdout="smconv: error: More than 8 channels. Found channel 64",
                        stderr="",
                    )):
                result = smconv_runner.convert_to_soundbank(
                    str(Path(temp_dir) / "bad.it"), str(Path(temp_dir) / "bank"))

        self.assertIn("error", result)
        self.assertIn("channel 64", result["error"])
