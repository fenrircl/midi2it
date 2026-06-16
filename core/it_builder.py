"""
core/it_builder.py — Construye archivos .it compatibles con smconv de PVSNESlib.
Usa bgm.it como template estructural para mantener compatibilidad.
"""
import struct, os, sys

# Ruta al template bgm.it (se configura desde afuera si es necesario)
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'templates', 'bgm.it')


def _bundle_template():
    """Ruta al template cuando la app está empaquetada con PyInstaller."""
    base = getattr(sys, '_MEIPASS', None)
    return os.path.join(base, 'templates', 'bgm.it') if base else None


def find_template(path=None):
    """Busca el template bgm.it en varias ubicaciones."""
    paths = [
        path,
        _bundle_template(),                       # PyInstaller (.exe onefile)
        TEMPLATE_PATH,
        '/tmp/vs-snes/mvp/res/bgm.it',
        os.path.expanduser('~/.midi2it/templates/bgm.it'),
    ]
    for p in paths:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError(
        "No se encontró bgm.it template. "
        "Descárgalo o cópialo desde un proyecto PVSNESlib existente."
    )


def _parse_instrument_key(cfg, keys):
    """Resuelve la clave de sample a usar para una pista.

    Acepta cfg['instrument'] con formato "<idx>: nombre" (lo que envía la GUI)
    o cfg['program'] entero. Cae al sample más cercano por número de programa.
    """
    if not keys:
        return 0
    instr = cfg.get('instrument')
    if isinstance(instr, str) and ':' in instr:
        head = instr.split(':', 1)[0].strip()
        if head.isdigit():
            k = int(head)
            return k if k in keys else min(keys, key=lambda x: abs(x - k))
    program = cfg.get('program', 0) or 0
    return min(keys, key=lambda k: abs(k - program))


def build(midi_data, samples_data, output_path, template_path=None,
          track_config=None, tempo_override=None):
    """Construye un archivo .it a partir de datos MIDI + samples.
    
    Args:
        midi_data: dict de parse_midi()
        samples_data: dict de sf2_parser.parse()
        output_path: ruta del .it de salida
        template_path: ruta al bgm.it template
        track_config: list[dict] con configuración por pista (instrumento, transposición, etc.)
        tempo_override: float, tempo forzado (BPM)
    """
    tp = find_template(template_path)
    bgm = open(tp, 'rb').read()
    
    tpb = midi_data['ticks_per_beat']
    tempo = tempo_override or midi_data['tempo']
    
    # Preparar configuración de pistas
    tracks = midi_data['tracks']
    track_config = track_config or [{} for _ in tracks]
    
    # Determinar si hay pistas en solo (anula al resto)
    any_solo = any((c or {}).get('solo') for c in track_config)

    # Mapear sample index para cada pista
    track_samples = []
    for i, trk in enumerate(tracks):
        cfg = track_config[i] if i < len(track_config) else {}
        transp = cfg.get('transpose', 0)
        volume = cfg.get('volume', 100)

        # ¿Esta pista suena? mute la silencia; si hay solo, solo suenan las solo.
        muted = bool(cfg.get('mute'))
        active = (not muted) and (cfg.get('solo') if any_solo else True)

        # Selección de sample: 'instrument' ("idx: nombre") o 'program' (entero)
        sample_idx = 0
        if samples_data:
            keys = list(samples_data.keys())
            target_key = _parse_instrument_key(cfg, keys)
            sample_idx = keys.index(target_key) if target_key in keys else 0

        track_samples.append({
            'sample_idx': sample_idx,
            'transpose': transp,
            'volume': volume,
            'active': bool(active),
        })
    
    # ========================================================
    # CONSTRUIR IT: usar bgm.it como template
    # ========================================================
    new_it = bytearray(bgm)
    
    # 1. Simplificar órdenes (solo patrón 0, luego stop)
    for i in range(193, 205):
        new_it[i] = 0xFF
    new_it[192] = 0  # orden 0 = patrón 0
    
    # 2. Reemplazar sample 0 con los datos del primer sample disponible
    s0 = 981  # sample 0 header
    pcm_data = b'\x00\x02'  # silencio por defecto
    sample_rate = 16000
    
    if samples_data:
        first_key = list(samples_data.keys())[0]
        first = samples_data[first_key]
        # Convertir sample a 16-bit si es necesario
        pcm_data = first['data']
        sample_rate = first['rate']
    
    smp_len = len(pcm_data) // 2
    new_it[s0+16:s0+18] = struct.pack('<H', 0x8012)
    new_it[s0+18] = 64
    new_it[s0+20:s0+46] = f"Sample {0}".ljust(26)[:26].encode()
    new_it[s0+48:s0+50] = struct.pack('<H', sample_rate)
    new_it[s0+50] = 64
    new_it[s0+54:s0+58] = struct.pack('<I', smp_len)
    new_it[s0+58:s0+62] = struct.pack('<I', 0)
    new_it[s0+62:s0+66] = struct.pack('<I', smp_len)
    new_it[s0+70:s0+80] = b'001MainSamp'
    
    # Puntero de datos al final del archivo
    data_ptr = len(new_it)
    new_it[s0+78:s0+82] = struct.pack('<I', data_ptr)
    new_it.extend(pcm_data)
    
    # 3. Múltiples samples: sample 1+ para tracks adicionales
    sample_offsets = []
    sample_offsets.append(data_ptr)
    for si, (sk, sv) in enumerate(list(samples_data.items())[1:], start=1):
        if si >= 9:  # máximo samples para no saturar
            break
        soff = 981 + si * 80
        sd = sv['data']
        sr = sv['rate']
        sl = len(sd) // 2
        new_it[soff+16:soff+18] = struct.pack('<H', 0x8012)
        new_it[soff+18] = 64
        new_it[soff+20:soff+46] = sv['name'][:26].ljust(26).encode()
        new_it[soff+48:soff+50] = struct.pack('<H', sr)
        new_it[soff+50] = 64
        new_it[soff+54:soff+58] = struct.pack('<I', sl)
        new_it[soff+58:soff+62] = struct.pack('<I', 0)
        new_it[soff+62:soff+66] = struct.pack('<I', sl)
        new_it[soff+70:soff+80] = f"{si:03d}Sample".encode()
        sp = len(new_it)
        new_it[soff+78:soff+82] = struct.pack('<I', sp)
        new_it.extend(sd)
        sample_offsets.append(sp)
    
    # 4. Actualizar note map del instrumento para mapear notas a samples
    bi = bgm.find(b'IMPI')
    note_map_start = bi + 47
    for i in range(120):
        # Determinar qué sample usar para cada nota
        # Simplificación: sample 0 para todas las notas
        new_it[note_map_start + i] = 0
    
    # 5. Construir patrón con notas del MIDI
    # Calcular patrón de notas: hasta 64 filas
    pattern_rows = {}
    for ti, trk in enumerate(tracks[:8]):  # máx 8 canales SNES
        ts = track_samples[ti] if ti < len(track_samples) else {'sample_idx': 0, 'transpose': 0, 'volume': 64, 'active': True}

        if not ts.get('active', True):  # respeta solo/mute
            continue

        for event in trk['events']:
            if event['type'] == 'note_on' and event['velocity'] > 0:
                beat = event['abs_ticks'] / tpb
                row = int(beat)
                if row < 64:
                    if row not in pattern_rows:
                        pattern_rows[row] = []
                    it_note = event['note'] + 1 + ts.get('transpose', 0)
                    it_note = max(1, min(it_note, 120))
                    vol = min(64, int(ts.get('volume', 100) * 64 / 100))
                    pattern_rows[row].append({
                        'channel': ts['sample_idx'],
                        'note': it_note,
                        'instrument': 1,
                        'volume': vol,
                    })
    
    # 6. Reemplazar pattern 0
    # Encontrar dónde empieza el patrón 0 en bgm.it
    pat_start = None
    for off in range(len(bgm)):
        if bgm[off+2] == 64 and bgm[off+3] == 0:
            dlen = struct.unpack('<H', bgm[off:off+2])[0]
            if 10 < dlen < 5000:
                pat_start = off
                break
    
    if pat_start and pat_start < len(new_it):
        # Construir channel names (8 canales)
        cn = bytearray()
        for ch in range(8):
            for c in f"ch{ch}\x00".ljust(8, '\x00'):
                cn.append(ord(c))
        
        # Construir packed data
        pk = bytearray()
        for row in range(64):
            row_events = pattern_rows.get(row, [])
            if row_events:
                pk.append(len(row_events))
                for re in row_events:
                    pk.append(re['channel'])
                    pk.append(0x07)  # mask: note + inst + vol
                    pk.append(re['note'])
                    pk.append(re['instrument'])
                    pk.append(re['volume'])
            else:
                pk.append(0)
        
        # Reemplazar patrón
        pl = 4 + len(cn) + len(pk)
        new_pat = bytearray(struct.pack('<HBB', pl, 64, 0))
        new_pat.extend(cn)
        new_pat.extend(pk)
        
        # Reemplazar en el archivo
        for i in range(len(new_pat)):
            if pat_start + i < len(new_it):
                new_it[pat_start + i] = new_pat[i]
    
    # 7. Actualizar tempo en header
    new_it[51] = int(tempo * 2) if tempo < 128 else 240
    
    # Escribir
    with open(output_path, 'wb') as f:
        f.write(new_it)
    
    return output_path
