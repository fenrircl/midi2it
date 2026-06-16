"""
core/it_builder.py — Construye archivos .it compatibles con smconv de PVSNESlib.
Modifica el template bgm.it en su lugar, escribe PCM en espacio libre,
pero NO actualiza los punteros data_off (smconv escanea el archivo).
"""
import struct, os, sys

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'templates', 'bgm.it')

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


def build(midi_data, samples_data, output_path, template_path=None,
          track_config=None, tempo_override=None, max_sample_sec=3.0,
          max_total_pcm_kb=96):
    tp = find_template(template_path)
    bgm = open(tp, 'rb').read()
    it = bytearray(bgm)

    tpb = midi_data['ticks_per_beat']
    tempo = tempo_override or midi_data['tempo']
    tracks = midi_data['tracks']

    # Leer tablas de offset del template
    smp_num  = struct.unpack('<H', bgm[36:38])[0]  # 11
    pat_num  = struct.unpack('<H', bgm[38:40])[0]  # 12
    off_smpls = 192 + 13 + 1 * 4  # orders(13) + ins ptr(4)
    off_pats  = off_smpls + smp_num * 4
    samp_hdr_offsets = list(struct.unpack(f'<{smp_num}I', bgm[off_smpls:off_smpls+smp_num*4]))
    pat_ptrs = list(struct.unpack(f'<{pat_num}I', bgm[off_pats:off_pats+pat_num*4]))
    last_pat_end = max(p + struct.unpack('<H', bgm[p:p+2])[0] for p in pat_ptrs)

    # ─── 1. Orders ───
    it[192] = 0  # orden 0 = patrón 0
    for i in range(193, 205):
        it[i] = 0xFF  # stop

    # ─── 2. Tempo ───
    it[51] = int(tempo * 2) if tempo < 128 else 240

    # ─── 3. Preparar samples ───
    sample_list = list(samples_data.items()) if samples_data else []
    max_data = len(bgm) - last_pat_end  # ~33KB
    used = 0
    snes_samples = []

    for sk, sv in sample_list:
        sd = sv['data']
        sr = sv['rate']
        max_frames = int(sr * max_sample_sec)
        if len(sd) // 2 > max_frames:
            sd = sd[:max_frames * 2]
        if used + len(sd) > max_data:
            allowed = max_data - used
            if allowed >= 256:
                sd = sd[:allowed]
            else:
                continue
        used += len(sd)
        snes_samples.append((sv['name'].encode('ascii', errors='replace'), sr, sd))

    if not snes_samples:
        snes_samples.append((b'Silence', 16000, b'\x00\x02'))

    max_smp = min(len(snes_samples), smp_num)
    actual = snes_samples[:max_smp]

    print(f"   Samples: {len(actual)}/{smp_num}, PCM: {sum(len(s[2]) for s in actual)/1024:.1f}/{max_data/1024:.1f} KB")

    # ─── 4. Sample headers (flags + IMPS, pero NO tocamos data_off original) ───
    for si in range(smp_num):
        soff = samp_hdr_offsets[si]
        if si < len(actual):
            name, rate, sd = actual[si]
            sl = len(sd) // 2
            it[soff+16:soff+18] = struct.pack('<H', 0xE000)  # present + data + 16bit
            it[soff+18] = 64
            it[soff+20:soff+46] = (name + b' SNES').ljust(26, b'\x00')[:26]
            it[soff+48:soff+50] = struct.pack('<H', rate)
            it[soff+50] = 64
            it[soff+52] = 32
            it[soff+54:soff+58] = struct.pack('<I', sl)
            it[soff+58:soff+62] = struct.pack('<I', 0)
            it[soff+62:soff+66] = struct.pack('<I', sl)
        else:
            it[soff+16:soff+18] = struct.pack('<H', 0x0000)
            it[soff+18] = 0
            it[soff+20:soff+46] = b'Empty\0'.ljust(26, b'\x00')
            it[soff+48:soff+50] = struct.pack('<H', 8000)
            it[soff+54:soff+58] = struct.pack('<I', 1)
            it[soff+62:soff+66] = struct.pack('<I', 1)
        # IMPS siempre presente
        it[soff+66:soff+70] = b'IMPS'
        it[soff+70:soff+80] = f"S{si:03d}SMP\0\0\0\0\0".encode()[:10]
        # NO tocamos data_off (soff+78:soff+82) — smconv escanea

    # ─── 5. Escribir PCM en espacio libre ───
    data_ptr = last_pat_end
    for name, rate, sd in actual:
        end_needed = data_ptr + len(sd)
        if end_needed > len(it):
            it.extend(b'\x00' * (end_needed - len(it)))
        it[data_ptr:data_ptr+len(sd)] = sd
        data_ptr += len(sd)

    # ─── 6. Note map ───
    bi = bgm.find(b'IMPI')
    for i in range(120):
        it[bi+47+i] = 0

    # ─── 7. Patrón 0 con notas MIDI ───
    pat0_off = pat_ptrs[0]
    cn = bytearray()
    for ch in range(6):
        cn.extend(f"ch{ch}\0".encode().ljust(8, b'\x00'))

    pattern_rows = {}
    for ti, trk in enumerate(tracks[:6]):
        for event in trk['events']:
            if event['type'] == 'note_on' and event['velocity'] > 0:
                beat = event['abs_ticks'] / tpb
                row = int(beat)
                if row < 64:
                    if row not in pattern_rows:
                        pattern_rows[row] = []
                    it_note = event['note'] + 1
                    pattern_rows[row].append({
                        'channel': ti % 6,
                        'note': max(1, min(it_note, 120)),
                        'instrument': 1,
                        'volume': 64,
                    })

    pk = bytearray()
    for row in range(64):
        events = pattern_rows.get(row, [])
        if events:
            pk.append(len(events))
            for re in events:
                pk.extend([re['channel'], 0x07, re['note'], re['instrument'], re['volume']])
        else:
            pk.append(0)

    pl = 4 + len(cn) + len(pk)
    new_pat = bytearray(struct.pack('<HBB', pl, 64, 0))
    new_pat.extend(cn)
    new_pat.extend(pk)
    for i in range(len(new_pat)):
        if pat0_off + i < len(it):
            it[pat0_off + i] = new_pat[i]

    # ─── Escribir ───
    with open(output_path, 'wb') as f:
        f.write(it)
    print(f"✅ IT: {output_path} ({len(it)} bytes, {len(actual)} samples)")
    return output_path
