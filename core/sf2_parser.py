"""
core/sf2_parser.py — Parsea SoundFont (.sf2) para extraer samples,
metadatos de instrumentos y mapeo MIDI.
"""
import struct

def parse(sf2_path, max_samples=16):
    """Extrae hasta `max_samples` samples utilizables del SF2.
    
    Returns:
        dict[int, dict]: {sample_index: {name, rate, data, loop_st, loop_en, dur, okey}}
    """
    with open(sf2_path, 'rb') as f:
        data = f.read()

    # Localizar chunks principales
    pos = 12
    pdta_pos = sdta_pos = None
    while pos < len(data) - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        if cid == b'LIST':
            lt = data[pos+8:pos+12]
            if lt == b'pdta':
                pdta_pos = pos
            elif lt == b'sdta':
                sdta_pos = pos
        pos += 8 + csz

    if not pdta_pos or not sdta_pos:
        raise ValueError("Formato SF2 inválido: faltan pdta/sdta")

    # Extraer sample data (smpl)
    pos = sdta_pos + 12
    end = sdta_pos + 8 + struct.unpack('<I', data[sdta_pos+4:sdta_pos+8])[0]
    smpl = None
    while pos < end - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        if cid == b'smpl':
            smpl = data[pos+8:pos+8+csz]
            break
        pos += 8 + csz
    if not smpl:
        raise ValueError("No se encontró smpl en el SF2")

    # Parsear pdta
    pos = pdta_pos + 12
    end = pdta_pos + 8 + struct.unpack('<I', data[pdta_pos+4:pdta_pos+8])[0]

    samples = {}
    while pos < end - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        sp = pos + 8

        if cid == b'shdr':
            n = csz // 46
            for i in range(n):
                off = sp + i * 46
                name = data[off:off+20].decode('ascii', errors='replace').rstrip('\x00').strip()
                start = struct.unpack('<I', data[off+20:off+24])[0]
                end_s = struct.unpack('<I', data[off+24:off+28])[0]
                sls = struct.unpack('<I', data[off+28:off+32])[0]
                sle = struct.unpack('<I', data[off+32:off+36])[0]
                sr = struct.unpack('<I', data[off+36:off+40])[0]
                okey = data[off+40]

                sd = smpl[start*2:min(end_s*2, len(smpl))]
                if sr > 0 and end_s > start and len(sd) > 64:
                    samples[i] = {
                        'name': name,
                        'rate': sr,
                        'okey': okey,
                        'data': sd,
                        'loop_st': max(0, sls - start),
                        'loop_en': end_s - start,
                        'dur': (end_s - start) / sr,
                    }
                    if len(samples) >= max_samples:
                        break

        pos += 8 + csz

    return samples


def extract_instrument_programs(sf2_path):
    """Retorna dict {sample_index: program_number} desde SF2.
    Útil para mapear canales MIDI a samples.
    """
    with open(sf2_path, 'rb') as f:
        data = f.read()

    pos = 12
    pdta_pos = None
    while pos < len(data) - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        if cid == b'LIST' and data[pos+8:pos+12] == b'pdta':
            pdta_pos = pos
            break
        pos += 8 + csz

    if not pdta_pos:
        return {}

    pos = pdta_pos + 12
    end = pdta_pos + 8 + struct.unpack('<I', data[pdta_pos+4:pdta_pos+8])[0]

    # Parsear pbag, pgen, inst para mapear preset → instrument → sample
    # Por ahora devolvemos mapping básico: sample i → programa i
    samples = parse(sf2_path, max_samples=128)
    result = {}
    for i, s in enumerate(samples.values()):
        result[i] = i
    return result
