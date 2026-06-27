"""
scripts/generate_bgm.py — Generador EXPERIMENTAL de templates/bgm.it.

⚠️  ESTADO: experimental, no se usa en el build.
    El CI usa el templates/bgm.it commiteado en el repo (Schism 0x5132,
    47975 bytes). Este script es solo referencia educativa.

PROPOSITO: mostrar cómo se ve un IT Schism 0x5132 minimo. NO genera
un template byte-a-byte identico al real porque eso requiere conocer
quirks exactos de la disposicion de offsets que openmpt123/smconv esperan.

USO:
    python scripts/generate_bgm.py              # genera un IT ejemplo
    python scripts/generate_bgm.py --check      # verifica el IT actual del repo

Para regenerar el bgm.it de verdad, la unica forma confiable es abrir
Schism Tracker 0.5132 (https://github.com/schism_tracker/schism-tracker),
crear un proyecto vacio con la configuracion exacta, y exportar.

El template real (templates/bgm.it) tiene:
  - 1 instrument (Piano 1) preconfigurado
  - 11 sample slots (uno con datos)
  - 12 patterns basicos
  - 9 channels (8 + master)
  - Magic numbers en offsets 206-498 que openmpt123 busca

Si necesitas regenerarlo, contacta al maintainer o usa Schism directamente.
"""
import os, sys, struct, argparse

SCHISM_CWT = 0x5132
SCHISM_CMWT = 0x0214

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(__file__), '..', 'templates', 'bgm.it'
)


def make_empty_it():
    """Crea un IT vacio compatible con smconv."""
    NSMP = 11
    NPAT = 12
    NORD = 13
    NINS = 1

    # ─── HEADER (192 bytes) ───
    hdr = bytearray(192)
    hdr[0:4] = b'IMPM'
    # title (26 bytes vacios)
    hdr[32:34] = struct.pack('<H', NORD)  # ordnum
    hdr[34:36] = struct.pack('<H', NINS)  # insnum
    hdr[36:38] = struct.pack('<H', NSMP)  # smpnum
    hdr[38:40] = struct.pack('<H', NPAT)  # patnum
    hdr[40:42] = struct.pack('<H', SCHISM_CWT)   # cwt
    hdr[42:44] = struct.pack('<H', SCHISM_CMWT)  # cmwt
    hdr[44:46] = struct.pack('<H', 0x004d)        # flags (instruments+vol+mix)
    hdr[46:48] = struct.pack('<H', 0x0006)        # special
    hdr[48]   = 128  # global vol
    hdr[49]   = 32   # mix volume
    hdr[50]   = 6    # initial speed (6 ticks/row)
    hdr[51]   = 240  # initial tempo
    # Pad bytes 60-67 y 124-131 con espacios (0x20) y 0x40
    for i in range(8):
        hdr[60+i] = 0x20
        hdr[124+i] = 0x40

    it = bytearray(hdr)

    # ─── ORDERS (NORD bytes) + 1 padding ───
    it.append(0)  # order 0 = pattern 0
    for _ in range(NORD - 1):
        it.append(0xFF)  # rest of orders = stop
    it.append(0)  # padding byte

    # ─── INSTRUMENT OFFSET TABLE (1 entry = 4 bytes) ───
    inst_offset = 192 + NORD + 1 + 4  # justo despues
    it.extend(struct.pack('<I', inst_offset))

    # ─── SAMPLE OFFSET TABLE (NSMP entries = 44 bytes) ───
    sample_offsets_start = len(it)
    for _ in range(NSMP):
        it.extend(b'\x00\x00\x00\x00')  # placeholder, se llena despues

    # ─── PATTERN OFFSET TABLE (NPAT entries = 48 bytes) ───
    pattern_offsets_start = len(it)
    for _ in range(NPAT):
        it.extend(b'\x00\x00\x00\x00')  # placeholder

    # ─── PADDING (hasta offset del instrument) ───
    # Alinear a 4 bytes
    while len(it) < inst_offset:
        it.append(0)

    # ─── INSTRUMENT (1, 482 bytes) ───
    inst = bytearray(482)
    inst[0:4] = b'IMPI'
    inst[4:30] = b'EmptyInst'.ljust(26, b'\x00')
    inst[32:34] = struct.pack('<H', 1)  # NumSamples = 1
    inst[41:43] = struct.pack('<H', 1)  # redundante
    # Note map: 120 bytes, todos 0xff (mapea al primer sample)
    for i in range(120):
        inst[47+i] = 0xFF
    it.extend(inst)

    # ─── SAMPLE HEADERS (NSMP * 80 bytes) ───
    sample_headers_start = len(it)
    for i in range(NSMP):
        sh = bytearray(80)
        sh[0:13] = f'EmptySmp{i}'.encode().ljust(13, b'\x00')[:13]
        sh[14] = 64  # default volume
        # flags vacias (no data, no loop)
        sh[16:18] = struct.pack('<H', 0)
        sh[20:46] = f'Empty Sample {i}'.encode().ljust(26, b'\x00')[:26]
        sh[48:50] = struct.pack('<H', 8363)  # default rate
        sh[50] = 64
        sh[52] = 32
        sh[54:58] = struct.pack('<I', 0)  # length
        sh[58:62] = struct.pack('<I', 0)  # loop start
        sh[62:66] = struct.pack('<I', 0)  # loop end
        sh[66:70] = b'IMPS'
        sh[70:80] = f"S{i:03d}SMPDATA\x00".encode()[:10]
        it.extend(sh)

    # ─── ESPACIO PARA SAMPLE DATA (al final) ───
    # 32KB de espacio para samples embebidos
    sample_data_offset = len(it)
    it.extend(b'\x00' * 32 * 1024)

    # ─── PATTERNS (NPAT patterns, cada uno vacio) ───
    # Cada pattern: 4 bytes header (length, rows, _) + 64 bytes channel mask + 64 bytes rows data
    pattern_start = len(it)
    for p in range(NPAT):
        # Pattern 0 lo dejamos vacio con 1 nota dummy en row 0 ch 0
        if p == 0:
            # 64 rows, 8 channels
            cn = bytearray()
            for ch in range(8):
                cn.extend(f"ch{ch}\x00".encode().ljust(8, b'\x00')[:8])
            # 1 nota en row 0, ch 0: C-5 (note=61), inst=1, vol=64
            pk = bytearray()
            pk.append(1)  # 1 evento en row 0
            pk.extend([0, 0x07, 61, 1, 64])  # channel, mask, note, inst, vol
            for _ in range(63):
                pk.append(0)
            pl = 4 + len(cn) + len(pk)
            it.extend(struct.pack('<HBB', pl, 64, 0))
            it.extend(cn)
            it.extend(pk)
        else:
            # Pattern vacio
            cn = bytearray()
            for ch in range(8):
                cn.extend(f"ch{ch}\x00".encode().ljust(8, b'\x00')[:8])
            pk = bytearray(64)  # 64 rows vacias
            pl = 4 + len(cn) + len(pk)
            it.extend(struct.pack('<HBB', pl, 64, 0))
            it.extend(cn)
            it.extend(pk)

    # ─── ACTUALIZAR OFFSETS ───
    # Sample offsets
    for i in range(NSMP):
        offset = sample_headers_start + i * 80
        it[sample_offsets_start + i*4 : sample_offsets_start + i*4 + 4] = struct.pack('<I', offset)
    # Pattern offsets
    pat_ptr = pattern_start
    for p in range(NPAT):
        # Calcular longitud de este pattern
        pl = struct.unpack('<H', it[pat_ptr:pat_ptr+2])[0]
        it[pattern_offsets_start + p*4 : pattern_offsets_start + p*4 + 4] = struct.pack('<I', pat_ptr)
        pat_ptr += pl

    return bytes(it)


def check_valid(path):
    """Verifica que el IT es valido (header IMPM, offsets correctos)."""
    if not os.path.exists(path):
        return False, "no existe"
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'IMPM':
        return False, "header no es IMPM"
    cwt = struct.unpack('<H', data[40:42])[0]
    if cwt != SCHISM_CWT:
        return False, f"cwt != 0x{SCHISM_CWT:04x} (es 0x{cwt:04x})"
    smpnum = struct.unpack('<H', data[36:38])[0]
    patnum = struct.unpack('<H', data[38:40])[0]
    if smpnum == 0 or patnum == 0:
        return False, f"smpnum={smpnum} patnum={patnum}"
    return True, f"IT valido: smpnum={smpnum} patnum={patnum} cwt=0x{cwt:04x}"


def main():
    parser = argparse.ArgumentParser(description='Genera/verifica templates/bgm.it')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help=f'Archivo destino (default: {DEFAULT_OUTPUT})')
    parser.add_argument('--check', action='store_true',
                        help='Solo verifica el actual sin regenerar')
    args = parser.parse_args()

    if args.check:
        ok, msg = check_valid(args.output)
        if ok:
            print(f"✅ {args.output}: {msg}")
            return 0
        else:
            print(f"❌ {args.output}: {msg}")
            return 1

    # Generar
    print(f"Generando {args.output}...")
    data = make_empty_it()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'wb') as f:
        f.write(data)
    print(f"✅ Escrito: {args.output} ({len(data)} bytes)")

    # Verificar
    ok, msg = check_valid(args.output)
    if ok:
        print(f"✅ {msg}")
    else:
        print(f"⚠️ Generado pero no valido: {msg}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
