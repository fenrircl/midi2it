"""
core/smconv_runner.py — Ejecuta smconv de PVSNESlib para convertir IT→soundbank.
Busca smconv en ubicaciones comunes y permite exportación directa a .bnk.
"""
import subprocess, os, shutil, struct, sys, re

IS_WINDOWS = os.name == 'nt'
# En Windows el ejecutable es smconv.exe
SMCONV_EXE = 'smconv.exe' if IS_WINDOWS else 'smconv'

# Ubicaciones comunes de smconv (sin extensión; se prueban variantes .exe en Windows)
SMCONV_LOCATIONS = [
    # Variable de entorno
    lambda: os.path.join(os.environ.get('PVSNESLIB_HOME', ''), 'devkitsnes', 'tools', 'smconv'),
    # Sistema (PATH) — shutil.which ya resuelve .exe en Windows
    lambda: shutil.which('smconv') or '',
    # Rutas comunes de instalación (Unix)
    lambda: os.path.expanduser('~/snesdev/pvsneslib/devkitsnes/tools/smconv'),
    lambda: os.path.expanduser('~/pvsneslib/devkitsnes/tools/smconv'),
    lambda: '/opt/pvsneslib/devkitsnes/tools/smconv',
    # Rutas comunes de instalación (Windows)
    lambda: os.path.join(os.environ.get('PVSNESLIB_HOME', r'C:\pvsneslib'),
                         'devkitsnes', 'tools', 'smconv'),
    # Relativo al proyecto
    lambda: os.path.join(os.path.dirname(__file__), '..', 'bin', 'smconv'),
    lambda: os.path.join(os.path.dirname(__file__), '..', 'tools', 'smconv'),
    # Descarga portátil (~/.midi2it/tools/smconv/**) — ver core/deps.py
    lambda: _portable_smconv(),
]


def _portable_smconv():
    """Busca smconv descargado de forma portátil bajo ~/.midi2it/tools/."""
    base = os.path.join(os.path.expanduser('~'), '.midi2it', 'tools')
    target = SMCONV_EXE.lower()
    if not os.path.isdir(base):
        return ''
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.lower() == target:
                return os.path.join(root, f)
    return ''


def _is_exec(path):
    """Verifica que la ruta sea un ejecutable. os.access(X_OK) no es fiable en Windows."""
    if not path or not os.path.isfile(path):
        return False
    if IS_WINDOWS:
        return True  # en Windows un .exe presente es suficiente
    return os.access(path, os.X_OK)


def find_smconv():
    """Busca smconv en ubicaciones comunes (incluye variante .exe en Windows)."""
    for loc_fn in SMCONV_LOCATIONS:
        base = loc_fn()
        if not base:
            continue
        # Probar la ruta tal cual y, en Windows, también con .exe añadido
        candidates = [base]
        if IS_WINDOWS and not base.lower().endswith('.exe'):
            candidates.append(base + '.exe')
        for path in candidates:
            if _is_exec(path):
                return os.path.abspath(path)
    return None


def convert_to_soundbank(it_path, output_base=None, bank=5):
    """Convierte .it a soundbank SNES usando smconv.
    
    Args:
        it_path: Ruta al archivo .it
        output_base: Base para archivos de salida (sin extensión)
                     Si es None, usa el nombre del .it
        bank: Número de banco (default 5)
    
    Returns:
        dict con rutas a los archivos generados (.bnk, .asm, .h)
        o None si smconv no está disponible
    """
    smconv = find_smconv()
    if not smconv:
        return None
    
    output_base = output_base or it_path.replace('.it', '')
    
    try:
        result = subprocess.run(
            [smconv, '-s', '-o', output_base, '-V', '-b', str(bank), it_path],
            capture_output=True, text=True, timeout=120
        )
        
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
        # smconv currently returns exit code 0 even after rejecting pattern
        # channels. Never report a bank as usable when diagnostics contain an
        # error, and don't treat a segmentation fault (139) as success.
        if result.returncode != 0 or re.search(r"\b(?:fatal\s+)?error\b", clean_output, re.I):
            errors = clean_output.strip()
            return {'error': errors[:1500] if errors else f"smconv exited with code {result.returncode}"}

        if result.returncode == 0:
            files = {
                'bnk': output_base + '.bnk',
                'asm': output_base + '.asm',
                'h': output_base + '.h',
            }
            generated = {k: v for k, v in files.items()
                         if os.path.isfile(v) and os.path.getsize(v) > 0}
            if 'bnk' not in generated:
                return {'error': "smconv terminó sin errores, pero no generó un .bnk válido"}
            return generated
    
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return {'error': 'smconv timed out'}


def get_pvsneslib_instructions(it_path, bnk_path):
    """Genera instrucciones para integrar en proyecto PVSNESlib."""
    name = os.path.splitext(os.path.basename(it_path))[0]
    
    return f"""
━━━ Integración en PVSNESlib ━━━

1. Copia los archivos a tu proyecto:
   cp "{bnk_path}" mvp/res/
   cp "{bnk_path.replace('.bnk', '.asm')}" mvp/res/
   cp "{bnk_path.replace('.bnk', '.h')}" mvp/res/

2. En mvp/Makefile, actualiza:
   AUDIOFILES := res/{name}.it
   export SOUNDBANK := res/soundbank

3. Compila:
   cd mvp && make clean && make

4. Prueba:
   mednafen mvp/vs-snes-mvp.sfc
"""
