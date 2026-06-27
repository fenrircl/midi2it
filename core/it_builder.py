"""
core/it_builder.py — Construye archivos .it compatibles con smconv de PVSNESlib.

ARQUITECTURA v2 (per-track):
  - track_config: lista de dicts con {program, sample_index, volume, transpose, solo, mute, name}
  - Genera 1 IMPI (IT instrument) por pista activa (max 8)
  - Cada instrument referencia 1 sample del SF2
  - Aplica mute/solo y limita a 8 canales
  - Loop points del SF2 se traducen a IT_SMP_LOOP
"""
import struct, os, sys

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'templates', 'bgm.it')

# IT format constants
IT_SMP_EXISTS = 0x01
IT_SMP_16BIT  = 0x02
IT_SMP_LOOP   = 0x10
IT_SMP_SUSTAIN= 0x20


def _bundle_template():
    base = getattr(sys, '_MEIPASS', None)
    return os.path.join(base, 'templates', 'bgm.it') if base else None


def find_template(path=None):
    paths = [path, _bundle_template(), TEMPLATE_PATH,
             '/tmp/vs-snes/mvp/res/bgm.it',
             os.path.expanduser('~/.midi2it/templates/bgm.it')]
    for p in paths:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError("No se encontró bgm.it template.")


# ─── Helpers ───────────────────────────────────────────────────────────

def _filter_tracks(track_config):
    """Aplica mute/solo y limita a 8 pistas (limite SPC700)."""
    has_solo = any(t.get('solo') for t in track_config)
    result = []
    for t in track_config:
        if t.get('mute'):
            continue
        if has_solo and not t.get('solo'):
            continue
        result.append(t)
        if len(result) >= 8:
            break
    return result


def _make_sample_header(sidx, name, rate, length, loop_st=0, loop_en=0,
                        has_loop=False, has_data=True):
    """Genera un sample header IT (80 bytes).

    Args:
        sidx: indice del sample (0-99)
        name: nombre del sample (max 26 chars)
        rate: sample rate en Hz
        length: longitud en samples (NO bytes)
        loop_st, loop_en: puntos de loop en samples
        has_loop: si tiene loop
        has_data: si tiene datos reales (no vacio)
    """
    h = bytearray(80)
    h[0:13] = name.encode('ascii', errors='replace')[:13].ljust(13, b'\x00')
    h[14]   = 64  # default volume

    flags = 0
    if has_data:
        flags |= IT_SMP_EXISTS
    flags |= IT_SMP_16BIT  # siempre 16-bit
    if has_loop:
        flags |= IT_SMP_LOOP
    h[16:18] = struct.pack('<H', flags)

    h[18]   = 64  # global vol
    h[20:46] = (name.encode('ascii', errors='replace') + b' SNES').ljust(26, b'\x00')[:26]
    h[48:50] = struct.pack('<H', rate)
    h[50]   = 64
    h[52]   = 32

    h[54:58] = struct.pack('<I', length)         # length in samples
    h[58:62] = struct.pack('<I', loop_st)        # loop start
    h[62:66] = struct.pack('<I', loop_en)        # loop end

    h[66:70] = b'IMPS'  # IT sample marker
    h[70:80] = f"S{sidx:03d}SMPDATA\x00".encode()[:10]
    return bytes(h)


def _make_instrument_header(name, sample_idx, default_note=60):
    """Genera un IT instrument header (482 bytes) que referencia 1 sample."""
    h = bytearray(482)
    h[0:4]   = b'IMPI'  # IT instrument marker
    h[4:28]  = name.encode('ascii', errors='replace')[:26].ljust(26, b'\x00')
    h[32:34] = struct.pack('<H', 1)  # NumSamples
    h[41:43] = struct.pack('<H', 1)  # also 1 (redundant)

    # Note map: all 120 notes -> this sample
    # Offset 47 + 120 bytes (1 byte per note: sample index, hi bit = "use default")
    for i in range(120):
        h[47 + i] = sample_idx & 0xFF

    h[167:169] = struct.pack('<H', 60)   # default fadeout
    h[169]     = 1                       # NNA: continue
    h[170:172] = struct.pack('<H', 0xFF00)  # DCT: note off
    h[172:174] = struct.pack('<H', 0xFF00)  # DCA: note off

    return bytes(h)


# ─── Main build ────────────────────────────────────────────────────────

def build(midi_data, samples_data, output_path, template_path=None,
          track_config=None, tempo_override=None, max_sample_sec=3.0,
          max_total_pcm_kb=96):
    """Genera el archivo .it.

    Args:
        midi_data: dict del midi_parser (tracks, tempo, ticks_per_beat)
        samples_data: dict[int, sample] del sf2_parser
        output_path: ruta del .it a escribir
        track_config: lista de dicts {program, sample_index, volume (0-200), transpose (-24..24),
                                     solo, mute, name}
                      Si es None, usa tracks del MIDI sin editar.
        tempo_override: BPM forzado (None = usar del MIDI)
        max_sample_sec: duracion maxima por sample en segundos
        max_total_pcm_kb: presupuesto total PCM en KB
    """
    tp = find_template(template_path)
    bgm = open(tp, 'rb').read()
    it = bytearray(bgm)

    tpb = midi_data['ticks_per_beat']
    tempo = tempo_override or midi_data['tempo']
    tracks = midi_data['tracks']

    # ─── Resolver track_config vs pistas del MIDI ───
    # Si no hay track_config, auto-generarlo: 1 pista MIDI = 1 track_config
    if not track_config:
        track_config = []
        for ti, trk in enumerate(tracks):
            track_config.append({
                'midi_track': ti,
                'program': None,  # se asigna despues
                'sample_index': None,
                'volume': 100,
                'transpose': 0,
                'solo': False,
                'mute': False,
                'name': trk.get('name', f'Track {ti}'),
            })

    # Filtrar por mute/solo y limitar a 8
    active_tracks = _filter_tracks(track_config)
    if not active_tracks:
        raise ValueError("Todas las pistas están muteadas o no hay pistas activas")

    # ─── Preparar samples por pista ───
    # Cada pista activa = 1 sample del SF2 (o silencio si no hay)
    track_samples = []  # list of (name, rate, pcm_data, has_loop, loop_st, loop_en)
    for ti, tc in enumerate(active_tracks):
        sidx = tc.get('sample_index')
        if sidx is not None and samples_data and sidx in samples_data:
            s = samples_data[sidx]
            sd = s['data']
            sr = s['rate']
            # Truncar a max_sample_sec
            max_frames = int(sr * max_sample_sec)
            if len(sd) // 2 > max_frames:
                sd = sd[:max_frames * 2]
            has_loop = s.get('has_loop', False)
            loop_st = s.get('loop_st', 0)
            loop_en = s.get('loop_en', len(sd) // 2)
            # Si hay loop, limitar a 16KB por sample (limite practico smconv)
            max_bytes = 16 * 1024
            if len(sd) > max_bytes:
                sd = sd[:max_bytes]
                loop_en = min(loop_en, len(sd) // 2)
            track_samples.append({
                'name': f"{tc.get('name', f'CH{ti}')[:20]}",
                'rate': sr,
                'data': sd,
                'has_loop': has_loop,
                'loop_st': loop_st,
                'loop_en': loop_en,
                'volume': tc.get('volume', 100),
                'transpose': tc.get('transpose', 0),
            })
        else:
            # Silencio (4 samples = 8 bytes de ceros)
            track_samples.append({
                'name': f"Silence{ti}",
                'rate': 16000,
                'data': b'\x00\x00' * 4,
                'has_loop': False,
                'loop_st': 0,
                'loop_en': 0,
                'volume': 0,
                'transpose': 0,
            })

    # ─── Presupuesto total PCM ───
    max_total_bytes = int(max_total_pcm_kb * 1024)
    total_pcm = sum(len(s['data']) for s in track_samples)
    if total_pcm > max_total_bytes:
        # Escalar: truncar samples proporcionalmente
        factor = max_total_bytes / total_pcm
        for s in track_samples:
            allowed = int(len(s['data']) * factor)
            s['data'] = s['data'][:allowed]
            s['loop_en'] = min(s['loop_en'], allowed // 2)

    print(f"   Pistas activas: {len(active_tracks)}/{len(track_config)}")
    print(f"   Total PCM: {sum(len(s['data']) for s in track_samples)/1024:.1f}KB / {max_total_pcm_kb}KB")

    # ─── Escribir samples en el IT ───
    # El template bgm.it tiene espacio para samples embebidos.
    # Estrategia: appendear todo al final del archivo (despues de patterns).
    # smconv escanea buscando IMPS/IMPI markers, asi que el offset es flexible.

    # Calcular sample headers
    num_samples = len(track_samples)
    sample_headers = []
    for si, s in enumerate(track_samples):
        name = s['name']
        rate = s['rate']
        slen = len(s['data']) // 2  # en samples (16-bit)
        sh = _make_sample_header(
            sidx=si, name=name, rate=rate, length=slen,
            loop_st=s['loop_st'] if s['has_loop'] else 0,
            loop_en=s['loop_en'] if s['has_loop'] else 0,
            has_loop=s['has_loop'],
            has_data=slen > 0,
        )
        sample_headers.append(sh)

    # Calcular instrument headers (1 por pista activa)
    num_instruments = len(active_tracks)
    instrument_headers = []
    for ii, tc in enumerate(active_tracks):
        name = f"CH{ii}-{tc.get('name', 'Inst')[:20]}"
        ih = _make_instrument_header(name, sample_idx=ii)
        instrument_headers.append(ih)

    # ─── Actualizar HEADER del IT ───
    # smconv necesita ver: ordnum, insnum, smpnum, patnum
    # Vamos a appendear, no a modificar offsets del template (smconv escanea)
    # Header en offset 0..191
    it[34:36] = struct.pack('<H', num_instruments)  # insnum
    it[36:38] = struct.pack('<H', num_samples)       # smpnum
    # patnum: mantenemos 12 (suficiente para SNES)
    # ordnum: mantenemos 13

    # ─── Tempo ───
    it[51] = max(32, min(int(tempo), 255)) if tempo < 256 else 240

    # ─── Appendear: sample headers, instrument headers, sample data ───
    # smconv escanea el archivo, asi que appendear funciona
    base_offset = len(it)

    # Append sample headers
    for sh in sample_headers:
        it.extend(sh)

    # Append instrument headers
    for ih in instrument_headers:
        it.extend(ih)

    # Append sample data (PCM 16-bit LE)
    for s in track_samples:
        it.extend(s['data'])

    # ─── Pattern 0 con notas MIDI ───
    # Distribuir pistas en canales SNES (8 max)
    pattern_rows = {}  # row -> [(channel, note, inst, vol), ...]
    for ti, tc in enumerate(active_tracks):
        midi_ti = tc.get('midi_track', ti)
        if midi_ti is None or midi_ti >= len(tracks):
            continue
        trk = tracks[midi_ti]
        channel = ti  # canal SNES = posicion en active_tracks
        transpose = tc.get('transpose', 0)
        volume = max(1, min(tc.get('volume', 100) // 2, 64))  # IT vol 0-64
        for event in trk['events']:
            if event['type'] == 'note_on' and event['velocity'] and event['velocity'] > 0:
                beat = event['abs_ticks'] / tpb
                row = int(beat)
                if row < 64:
                    if row not in pattern_rows:
                        pattern_rows[row] = []
                    it_note = max(1, min(event['note'] + 1 + transpose, 120))
                    pattern_rows[row].append({
                        'channel': channel,
                        'note': it_note,
                        'instrument': ti + 1,  # IT instruments son 1-based
                        'volume': volume,
                    })

    # Construir pattern 0 raw
    # 64 rows, 8 channels
    # Para cada row: lista de channels con eventos
    pk = bytearray()
    for row in range(64):
        events = pattern_rows.get(row, [])
        # Agrupar: si hay eventos en el mismo channel, solo el primero (IT limita a 1 evento/channel/row)
        used_channels = set()
        compact = []
        for e in events:
            if e['channel'] in used_channels:
                continue
            used_channels.add(e['channel'])
            compact.append(e)
        if compact:
            pk.append(len(compact))
            for e in compact:
                pk.extend([e['channel'], 0x07, e['note'], e['instrument'], e['volume']])
        else:
            pk.append(0)

    # Channel names (32 bytes para 8 channels)
    cn = bytearray()
    for ch in range(8):
        ch_name = f"CH{ch}\x00".encode().ljust(8, b'\x00')[:8]
        cn.extend(ch_name)

    # Append pattern 0 al final
    pl = 4 + len(cn) + len(pk)
    it.extend(struct.pack('<HBB', pl, 64, 0))
    it.extend(cn)
    it.extend(pk)

    # ─── Escribir ───
    with open(output_path, 'wb') as f:
        f.write(it)
    print(f"✅ IT: {output_path}")
    print(f"   {len(it)} bytes, {num_instruments} instruments, {num_samples} samples, "
          f"64-row pattern con {sum(1 for r in pattern_rows if pattern_rows[r])} filas activas")
    return output_path
