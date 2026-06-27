"""
core/sf2_parser.py — Parsea SoundFont (.sf2) para extraer samples,
metadatos de instrumentos y mapeo MIDI (programa → sample).

Estructura SF2 relevante:
  LIST/sdta
    smpl   — sample data (16-bit signed PCM, little-endian)
  LIST/pdta
    phdr   — preset headers (128 entries × 38 bytes): nombre, bank, program, ...
    pbag   — preset bags (links presets to generators)
    pmod   — preset modulators
    pgen   — preset generators (key ranges, vel ranges, instrument link)
    inst   — instruments (link to samples)
    ibag   — instrument bags
    imod   — instrument modulators
    igen   — instrument generators (sample link)
    shdr   — sample headers (name, start, end, loop, rate, key, etc)
"""
import struct


# ─── IT format constants (sample flags) ─────────────────────────────────
IT_SMP_EXISTS    = 0x01
IT_SMP_16BIT     = 0x02
IT_SMP_LOOP      = 0x10
IT_SMP_SUSTAIN   = 0x20
IT_SMP_IT214     = 0x04  # IT 2.14 sample compression


def _parse_pdta_chunks(data, pdta_pos):
    """Devuelve dict con los sub-chunks del pdta parseados."""
    pos = pdta_pos + 12  # saltar 'LIST' + 'pdta' + size(4)
    end = pdta_pos + 8 + struct.unpack('<I', data[pdta_pos+4:pdta_pos+8])[0]
    chunks = {}
    while pos < end - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        chunks[cid] = (pos + 8, csz)
        pos += 8 + csz
    return chunks


def _read_smpl(data, sdta_pos):
    """Extrae el bloque smpl (raw sample data)."""
    pos = sdta_pos + 12
    end = sdta_pos + 8 + struct.unpack('<I', data[sdta_pos+4:sdta_pos+8])[0]
    while pos < end - 8:
        cid = data[pos:pos+4]
        csz = struct.unpack('<I', data[pos+4:pos+8])[0]
        if cid == b'smpl':
            return data[pos+8:pos+8+csz]
        pos += 8 + csz
    return None


# ─── Public API ────────────────────────────────────────────────────────

def parse(sf2_path, max_samples=64):
    """Extrae hasta `max_samples` samples utilizables del SF2.

    Returns:
        dict[int, dict]: {sample_index: {name, rate, data, loop_st, loop_en, okey, dur}}
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

    smpl = _read_smpl(data, sdta_pos)
    if not smpl:
        raise ValueError("No se encontró smpl en el SF2")

    chunks = _parse_pdta_chunks(data, pdta_pos)

    # Parsear shdr (sample headers)
    samples = {}
    if b'shdr' in chunks:
        shdr_off, shdr_size = chunks[b'shdr']
        n = shdr_size // 46
        for i in range(n):
            off = shdr_off + i * 46
            name = data[off:off+20].decode('ascii', errors='replace').rstrip('\x00').strip()
            start = struct.unpack('<I', data[off+20:off+24])[0]
            end_s = struct.unpack('<I', data[off+24:off+28])[0]
            sls   = struct.unpack('<I', data[off+28:off+32])[0]
            sle   = struct.unpack('<I', data[off+32:off+36])[0]
            sr    = struct.unpack('<I', data[off+36:off+40])[0]
            okey  = data[off+40]
            # Excluir el sample terminal vacío (name == 'EOS')
            if name == 'EOS':
                break
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
                    'has_loop': sle > sls and sle <= end_s,
                }
                if len(samples) >= max_samples:
                    break

    return samples


def extract_instrument_programs(sf2_path, max_samples=64):
    """Devuelve mapeo {program_number (0-127): sample_index} usando phdr+pbag+pgen+inst+ibag+igen.

    Flujo: preset (program X) → pbag → pgen(instrument=N) → inst(N) → ibag → igen(sampleID=N) → sample

    Returns:
        dict[int, int]: {program_number: sf2_sample_index}
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

    chunks = _parse_pdta_chunks(data, pdta_pos)

    # 1) phdr — 128 presets × 38 bytes
    #     fields: name(20), preset(2), bank(2), pbagNdx(4), library(4), genre(4), morphology(4)
    if b'phdr' not in chunks:
        return {}
    phdr_off, phdr_size = chunks[b'phdr']
    n_presets = phdr_size // 38
    presets = []
    for i in range(n_presets):
        off = phdr_off + i * 38
        name = data[off:off+20].decode('ascii', errors='replace').rstrip('\x00').strip()
        if name == 'EOP':
            break
        program = struct.unpack('<H', data[off+20:off+22])[0]
        bank    = struct.unpack('<H', data[off+22:off+24])[0]
        pbag_idx = struct.unpack('<I', data[off+24:off+28])[0]
        presets.append({
            'name': name, 'program': program, 'bank': bank, 'pbag_idx': pbag_idx
        })

    # 2) pbag — links presets to generators
    pbag_n = chunks.get(b'pbag', (0, 0))[1] // 4
    pbag_idxs = []
    if pbag_n:
        pbag_off = chunks[b'pbag'][0]
        for i in range(pbag_n):
            pbag_idxs.append(struct.unpack('<H', data[pbag_off + i*4: pbag_off + i*4 + 2])[0])

    # 3) pgen — generators; we look for op=41 (instrument)
    if b'pgen' not in chunks:
        return {}
    pgen_off, pgen_size = chunks[b'pgen']
    pgen_n = pgen_size // 4
    pgen_by_bag = {}  # bag_index -> gen dict
    for i in range(pgen_n):
        off = pgen_off + i * 4
        op  = struct.unpack('<h', data[off:off+2])[0]
        val = struct.unpack('<h', data[off+2:off+4])[0]
        # busco qué bag apunta este gen (asumimos orden)
        # un truco: agrupo por bag contando el flag "terminal"
        pass

    # SF2 pgen layout: cada bag tiene N generators hasta el siguiente bag.
    # El último pbag_idx apunta al terminator. Re-parseo correctamente:
    pgen_by_bag = {}
    if pbag_idxs:
        # Re-leer pgen agrupando por rango [start, next_start)
        # Necesito un array con todos los pgen (op, val) en orden
        all_pgens = []
        for i in range(pgen_n):
            off = pgen_off + i * 4
            op  = struct.unpack('<h', data[off:off+2])[0]
            val = struct.unpack('<h', data[off+2:off+4])[0]
            all_pgens.append((op, val))
        for bag_i, start in enumerate(pbag_idxs):
            end = pbag_idxs[bag_i + 1] if bag_i + 1 < len(pbag_idxs) else len(all_pgens)
            gens = {}
            for j in range(start, end):
                op, val = all_pgens[j]
                if op == 41:  # instrument index
                    gens['instrument'] = val
                elif op == 43:  # keyRange
                    gens['key_lo'] = val & 0xFF
                    gens['key_hi'] = (val >> 8) & 0xFF
            pgen_by_bag[bag_i] = gens

    # 4) inst — instruments; instN referencia un ibagNdx (NO consecutivos: 1 inst puede usar N bags)
    if b'inst' not in chunks:
        return {}
    inst_off, inst_size = chunks[b'inst']
    n_inst = inst_size // 22
    inst_ibag = []
    for i in range(n_inst):
        off = inst_off + i * 22
        name = data[off:off+20].decode('ascii', errors='replace').rstrip('\x00').strip()
        if name == 'EOI':
            break
        ibag_ndx = struct.unpack('<H', data[off+20:off+22])[0]
        inst_ibag.append(ibag_ndx)

    # 5) ibag + igen — find sampleID (op 53)
    # ibag_starts[i] = offset en igen donde empieza el bag i
    # Para un inst que empieza en inst_ibag[inst_i], el rango de bags es
    # [inst_ibag[inst_i], inst_ibag[inst_i+1]) → sus offsets en igen son
    # [ibag_starts[bag_i] for bag_i in that range], no consecutivos en igen
    if b'ibag' not in chunks or b'igen' not in chunks:
        return {}
    ibag_off, ibag_size = chunks[b'ibag']
    ibag_n = ibag_size // 4
    ibag_starts = []
    for i in range(ibag_n):
        ibag_starts.append(struct.unpack('<H', data[ibag_off + i*4: ibag_off + i*4 + 2])[0])

    igen_off, igen_size = chunks[b'igen']
    igen_n = igen_size // 4
    all_igens = []
    for i in range(igen_n):
        off = igen_off + i * 4
        op  = struct.unpack('<h', data[off:off+2])[0]
        val = struct.unpack('<h', data[off+2:off+4])[0]
        all_igens.append((op, val))

    # Para cada inst: sus bags van desde inst_ibag[inst_i] hasta inst_ibag[inst_i+1]
    # (o hasta el final). Para cada bag, miramos su rango de igen [ibag_starts[bag], ibag_starts[bag+1])
    # y buscamos sampleID (op=53).
    sample_for_inst = {}  # inst_index -> sample_index
    for inst_i, bag_start in enumerate(inst_ibag):
        bag_end = inst_ibag[inst_i + 1] if inst_i + 1 < len(inst_ibag) else len(ibag_starts) - 1
        for bag_i in range(bag_start, bag_end):
            if bag_i >= len(ibag_starts) - 1:
                break
            igen_start = ibag_starts[bag_i]
            igen_end   = ibag_starts[bag_i + 1]
            for j in range(igen_start, igen_end):
                op, val = all_igens[j]
                if op == 53:  # sampleID
                    sample_for_inst[inst_i] = val
                    break
            if inst_i in sample_for_inst:
                break  # primer sampleID del primer bag es suficiente

    # 6) Map preset program → sample
    result = {}
    for p in presets:
        gens = pgen_by_bag.get(p['pbag_idx'], {})
        inst_idx = gens.get('instrument')
        if inst_idx is None:
            continue
        sample_idx = sample_for_inst.get(inst_idx)
        if sample_idx is None:
            continue
        # SF2 program is 0-127; MIDI program_change also 0-127
        result[p['program']] = sample_idx

    return result


def get_program_list(sf2_path):
    """Devuelve lista [(program, name)] de los presets del SF2, útil para el dropdown de GUI.

    Returns:
        list[tuple[int, str]]: [(0, 'Piano',), (8, 'Celesta',), ...]
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
        return []

    chunks = _parse_pdta_chunks(data, pdta_pos)
    if b'phdr' not in chunks:
        return []

    phdr_off, phdr_size = chunks[b'phdr']
    n = phdr_size // 38
    out = []
    for i in range(n):
        off = phdr_off + i * 38
        name = data[off:off+20].decode('ascii', errors='replace').rstrip('\x00').strip()
        if name == 'EOP':
            break
        program = struct.unpack('<H', data[off+20:off+22])[0]
        bank    = struct.unpack('<H', data[off+22:off+24])[0]
        # Prefijo del banco para diferenciar (drum kits en bank 128)
        prefix = f"[{bank:3d}] " if bank > 0 else ""
        out.append((program, f"{prefix}{program:3d} {name}"))
    return out
