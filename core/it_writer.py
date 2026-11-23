"""Writer mínimo de Impulse Tracker 2.14 para el pipeline MIDI → SNES."""

from __future__ import annotations

import math
import os
import struct

HEADER_SIZE = 0xC0
INSTRUMENT_SIZE = 554
SAMPLE_HEADER_SIZE = 80
MAX_CHANNELS = 8
MAX_PATTERNS = 64
MAX_ORDERS = 200


def _ascii(value, size):
    return str(value or "").encode("ascii", errors="replace")[:size].ljust(size, b"\0")


def _u16(value):
    return struct.pack("<H", int(value) & 0xFFFF)


def _u32(value):
    return struct.pack("<I", int(value) & 0xFFFFFFFF)


def _instrument_header(name, sample_number):
    """Create an IT 2.14 instrument with all notes mapped to one sample."""
    h = bytearray(INSTRUMENT_SIZE)
    h[0:4] = b"IMPI"
    h[4:16] = _ascii("MIDI2IT", 12)
    h[17] = 0  # NNA: cut
    h[18] = 0  # duplicate check: off
    h[19] = 0  # duplicate action: cut
    h[20:22] = _u16(128)  # short fadeout for note-off/release
    h[24] = 128  # full instrument volume; preserve MIDI dynamics per note
    h[25] = 32  # default pan, centered
    h[28:30] = _u16(0x0214)  # tracker version
    h[30] = 1  # number of samples
    h[32:58] = _ascii(name, 26)

    # Keyboard map at 0x40: 120 pairs of (mapped note, 1-based sample number).
    for note in range(120):
        pos = 0x40 + note * 2
        h[pos] = note
        h[pos + 1] = sample_number
    # Envelopes remain disabled (zeroed 82-byte structures).
    return bytes(h)


def _sample_header(sample, pcm_offset):
    h = bytearray(SAMPLE_HEADER_SIZE)
    h[0:4] = b"IMPS"
    h[4:16] = _ascii(sample["name"], 12)
    h[17] = 64  # global volume
    h[18] = 0x01 | 0x02 | (0x10 if sample["has_loop"] else 0)
    h[19] = 64  # sample volume
    h[20:46] = _ascii(sample["name"], 26)
    h[46] = 1  # signed PCM
    h[47] = 32  # centered, sample pan disabled
    h[48:52] = _u32(sample["frames"])
    h[52:56] = _u32(sample["loop_start"] if sample["has_loop"] else 0)
    h[56:60] = _u32(sample["loop_end"] if sample["has_loop"] else 0)
    h[60:64] = _u32(sample["rate"])
    h[72:76] = _u32(pcm_offset)
    return bytes(h)


def _pack_pattern(rows, channels):
    packed = bytearray()
    for row in rows:
        for channel in range(channels):
            event = row.get(channel)
            if event is None:
                continue
            # New-channel mask followed by note, instrument, and volume fields.
            # IT packed-pattern channel numbers are 1-based. smconv decodes
            # the low 6 bits as ``channel_id - 1``; zero wraps to channel 64.
            packed.extend((0x80 | (channel + 1), 0x07, event["note"],
                           event["instrument"], event["volume"]))
        packed.append(0)  # end of row
    return _u16(len(packed)) + _u16(64) + b"\0\0\0\0" + packed


def _prepare_sample(sample, fallback_name, max_sample_sec):
    pcm = bytes(sample.get("data", b""))
    pcm = pcm[:len(pcm) & ~1]  # IT 16-bit samples must contain whole frames.
    rate = max(1, int(sample.get("rate", 16000)))
    if max_sample_sec is not None:
        max_frames = max(1, int(rate * max_sample_sec))
        pcm = pcm[:max_frames * 2]
    frames = len(pcm) // 2
    has_loop = bool(sample.get("has_loop"))
    loop_start = max(0, min(int(sample.get("loop_st", 0)), frames))
    loop_end = max(0, min(int(sample.get("loop_en", frames)), frames))

    # smconv encodes BRR in blocks of 16 frames. Align and keep a usable loop.
    if has_loop:
        loop_start = (loop_start // 16) * 16
        loop_end = (loop_end // 16) * 16
        if loop_end <= loop_start:
            has_loop = False
    if frames == 0:
        pcm = b"\0\0" * 16
        frames = 16
        has_loop = True
        loop_start, loop_end = 0, 16
    return {
        "name": sample.get("name") or fallback_name,
        "rate": rate,
        "data": pcm,
        "frames": frames,
        "has_loop": has_loop,
        "loop_start": loop_start,
        "loop_end": loop_end,
    }


def _active_tracks(track_config):
    solo = any(t.get("solo") for t in track_config)
    return [t for t in track_config
            if not t.get("mute") and (not solo or t.get("solo"))]


def _prepare_unique_samples(active, samples_data, max_sample_sec):
    prepared_samples = []
    sample_numbers = []
    sample_cache = {}
    for index, config in enumerate(active):
        sample = (samples_data or {}).get(config.get("sample_index"))
        if sample is None:
            sample = {"name": f"Silence{index}", "rate": 16000,
                      "data": b"\0\0" * 16, "has_loop": True,
                      "loop_st": 0, "loop_en": 16}
        prepared = _prepare_sample(sample, f"Sample{index}", max_sample_sec)
        # Instruments can share identical sample data instead of duplicating it.
        key = (prepared["rate"], prepared["data"], prepared["frames"],
               prepared["has_loop"], prepared["loop_start"], prepared["loop_end"])
        sample_number = sample_cache.get(key)
        if sample_number is None:
            prepared_samples.append(prepared)
            sample_number = len(prepared_samples)
            sample_cache[key] = sample_number
        sample_numbers.append(sample_number)
    return prepared_samples, sample_numbers


def estimate_brr(midi_data, samples_data, track_config, max_sample_sec=3.0,
                 max_brr_kb=48):
    """Estimate unique sample memory for the currently active IT instruments."""
    active = _active_tracks(list(track_config or []))
    if not active:
        raise ValueError("No hay pistas activas para estimar")
    prepared, _sample_numbers = _prepare_unique_samples(
        active, samples_data, max_sample_sec)
    pcm_bytes = sum(len(sample["data"]) for sample in prepared)
    brr_bytes = sum(math.ceil(sample["frames"] / 16) * 9 for sample in prepared)
    return {
        "active_tracks": len(active),
        "unique_samples": len(prepared),
        "pcm_bytes": pcm_bytes,
        "brr_bytes": brr_bytes,
        "brr_kb": brr_bytes / 1024,
        "budget_kb": max_brr_kb,
        "fits": max_brr_kb is None or brr_bytes <= int(max_brr_kb * 1024),
    }


def suggest_max_sample_sec(midi_data, samples_data, track_config,
                           max_sample_sec=3.0, max_brr_kb=48):
    """Return the longest per-sample duration that fits the BRR budget."""
    current = estimate_brr(midi_data, samples_data, track_config,
                           max_sample_sec, max_brr_kb)
    if current["fits"]:
        return max_sample_sec
    low, high = 0.01, float(max_sample_sec)
    best = None
    for _ in range(20):
        middle = (low + high) / 2
        estimate = estimate_brr(midi_data, samples_data, track_config,
                                middle, max_brr_kb)
        if estimate["fits"]:
            best = middle
            low = middle
        else:
            high = middle
    return best


def build(midi_data, samples_data, output_path, track_config=None,
          tempo_override=None, max_sample_sec=3.0, max_total_pcm_kb=None,
          max_brr_kb=48, rows_per_beat=4):
    """Write a self-contained IT file and return its output path.

    ``track_config`` keeps the existing GUI/CLI shape. Each active MIDI track
    becomes one IT instrument, one sample, and one output channel.
    """
    midi_tracks = midi_data.get("tracks", [])
    tpb = int(midi_data.get("ticks_per_beat", 0))
    if tpb <= 0:
        raise ValueError("El MIDI debe declarar ticks_per_beat mayor que cero")
    if not 1 <= int(rows_per_beat) <= 32:
        raise ValueError("rows_per_beat debe estar entre 1 y 32")
    tempo = float(tempo_override or midi_data.get("tempo", 120))
    tempo = max(32, min(255, round(tempo)))

    if track_config is None:
        track_config = [{"midi_track": t.get("index", i), "name": t.get("name", f"Track {i}"),
                         "sample_index": None, "volume": 100, "transpose": 0}
                        for i, t in enumerate(midi_tracks)]
    active = _active_tracks(list(track_config))
    if not active:
        raise ValueError("No hay pistas activas para exportar")
    if len(active) > MAX_CHANNELS:
        raise ValueError(f"Hay {len(active)} pistas activas; IT/SNES admite máximo {MAX_CHANNELS}. "
                         "Silencia o elimina pistas antes de exportar")
    if len(active) > 64:
        raise ValueError("El formato IT admite como máximo 64 instrumentos y samples")

    prepared_samples, sample_numbers = _prepare_unique_samples(
        active, samples_data, max_sample_sec)
    source_tracks = []
    for index, config in enumerate(active):
        midi_index = config.get("midi_track", index)
        source = next((t for t in midi_tracks if t.get("index") == midi_index), None)
        if source is None and isinstance(midi_index, int) and 0 <= midi_index < len(midi_tracks):
            source = midi_tracks[midi_index]
        if source is None:
            source = {"notes": [], "events": []}
        source_tracks.append((source, config))

    pcm_bytes = sum(len(sample["data"]) for sample in prepared_samples)
    brr_bytes = sum(math.ceil(sample["frames"] / 16) * 9 for sample in prepared_samples)
    if max_total_pcm_kb is not None and pcm_bytes > int(max_total_pcm_kb * 1024):
        raise ValueError(f"Samples PCM exceden el límite configurado: {pcm_bytes / 1024:.1f} KB "
                         f"> {max_total_pcm_kb:g} KB; reduce samples o aumenta el límite")
    if max_brr_kb is not None and brr_bytes > int(max_brr_kb * 1024):
        raise ValueError(f"Samples BRR estimados exceden el presupuesto: {brr_bytes / 1024:.1f} KB "
                         f"> {max_brr_kb:g} KB. Reduce la duración de samples o el número "
                         "de instrumentos activos; usa ‘Optimizar’ en la GUI para ajustar "
                         "la duración automáticamente.")

    ticks_per_row = tpb / int(rows_per_beat)
    note_events = {}
    last_row = 0
    for channel, (source, config) in enumerate(source_tracks):
        transpose = int(config.get("transpose", 0))
        track_volume = max(0, min(64, round(float(config.get("volume", 100)) * 64 / 200)))
        notes = source.get("notes") or []
        if not notes:  # Compatibility with older parsed MIDI structures.
            notes = [{"pitch": e.get("note"), "start_tick": e.get("abs_ticks", 0),
                      "duration_tick": 1, "velocity": e.get("velocity", 100)}
                     for e in source.get("events", [])
                     if e.get("type") == "note_on" and (e.get("velocity") or 0) > 0]
        for note in notes:
            start_tick = max(0, int(note.get("start_tick", 0)))
            duration = max(1, int(note.get("duration_tick", 1)))
            start_row = max(0, round(start_tick / ticks_per_row))
            end_row = max(start_row + 1, round((start_tick + duration) / ticks_per_row))
            pitch = max(1, min(120, int(note.get("pitch", 60)) + 1 + transpose))
            velocity = max(1, min(64, round(int(note.get("velocity", 100)) * track_volume / 127)))
            start_key = (start_row, channel)
            note_events.setdefault(start_key, {
                "note": pitch, "instrument": channel + 1, "volume": velocity,
            })
            off_key = (end_row, channel)
            # IT note-off is 254. Do not erase a re-trigger on the same row.
            note_events.setdefault(off_key, {"note": 254, "instrument": channel + 1,
                                             "volume": 64})
            last_row = max(last_row, end_row)

    pattern_count = max(1, (last_row // 64) + 1)
    if pattern_count > MAX_PATTERNS:
        raise ValueError(f"La canción necesita {pattern_count} patterns; el límite IT es 64")
    patterns = []
    for pattern_index in range(pattern_count):
        rows = []
        for row_index in range(64):
            row_number = pattern_index * 64 + row_index
            rows.append({channel: event for (event_row, channel), event in note_events.items()
                         if event_row == row_number})
        patterns.append(_pack_pattern(rows, len(active)))

    orders = list(range(pattern_count)) + [0xFF]
    if len(orders) > MAX_ORDERS:
        raise ValueError("La secuencia excede el máximo de 200 órdenes IT")

    header = bytearray(HEADER_SIZE)
    header[0:4] = b"IMPM"
    header[4:30] = _ascii(os.path.basename(midi_data.get("filename", "midi2it")), 26)
    header[0x1E:0x20] = b"\x04\x10"  # row highlights
    header[0x20:0x28] = struct.pack(
        "<4H", len(orders), len(active), len(prepared_samples), pattern_count)
    header[0x28:0x2C] = struct.pack("<2H", 0x0214, 0x0214)
    header[0x2C:0x2E] = _u16(0x0005)  # stereo + instrument mode
    header[0x30] = 128  # global volume
    header[0x31] = 128  # full mixing volume; the previous 48 made playback very quiet
    header[0x32] = 6    # ticks per row
    header[0x33] = tempo
    # Disable unused channels in the IT header. The high bit of channel pan
    # marks a channel as disabled; leave only the channels we actually encode.
    header[0x40:0x80] = bytes([0x80] * 64)
    header[0x40:0x40 + len(active)] = bytes([32] * len(active))
    header[0x80:0xC0] = bytes(64)
    header[0x80:0x80 + len(active)] = bytes([64] * len(active))

    output = bytearray(header)
    output.extend(bytes(orders))
    instrument_table = len(output)
    output.extend(bytes(4 * len(active)))
    sample_table = len(output)
    output.extend(bytes(4 * len(prepared_samples)))
    pattern_table = len(output)
    output.extend(bytes(4 * pattern_count))

    instrument_offsets = []
    for index, config in enumerate(active):
        instrument_offsets.append(len(output))
        output.extend(_instrument_header(config.get("name", f"Track {index}"),
                                         sample_numbers[index]))
    sample_offsets = []
    for sample in prepared_samples:
        sample_offsets.append(len(output))
        output.extend(bytes(SAMPLE_HEADER_SIZE))
    pattern_offsets = []
    for pattern in patterns:
        pattern_offsets.append(len(output))
        output.extend(pattern)
    pcm_offsets = []
    for sample in prepared_samples:
        pcm_offsets.append(len(output))
        output.extend(sample["data"])

    for i, offset in enumerate(instrument_offsets):
        output[instrument_table + i * 4:instrument_table + i * 4 + 4] = _u32(offset)
    for i, offset in enumerate(sample_offsets):
        output[sample_table + i * 4:sample_table + i * 4 + 4] = _u32(offset)
        output[offset:offset + SAMPLE_HEADER_SIZE] = _sample_header(prepared_samples[i], pcm_offsets[i])
    for i, offset in enumerate(pattern_offsets):
        output[pattern_table + i * 4:pattern_table + i * 4 + 4] = _u32(offset)

    with open(output_path, "wb") as handle:
        handle.write(output)
    print(f"   Pistas activas: {len(active)}/{len(track_config)}")
    print(f"   Samples: {pcm_bytes / 1024:.1f} KB PCM, {brr_bytes / 1024:.1f} KB BRR estimado")
    print(f"✅ IT: {output_path}")
    print(f"   {len(output)} bytes, {len(active)} instrumentos, {len(prepared_samples)} samples, "
          f"{pattern_count} patterns, {last_row + 1} filas")
    return output_path
