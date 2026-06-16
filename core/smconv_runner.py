"""
core/smconv_runner.py — Ejecuta smconv de PVSNESlib para convertir IT→soundbank.
Busca smconv en ubicaciones comunes y permite exportación directa a .bnk.
"""
import subprocess, os, shutil, struct

# Ubicaciones comunes de smconv
SMCONV_LOCATIONS = [
    # Variable de entorno
    lambda: os.path.join(os.environ.get('PVSNESLIB_HOME', ''), 'devkitsnes', 'tools', 'smconv'),
    # Sistema (PATH)
    lambda: shutil.which('smconv') or '',
    # Rutas comunes de instalación
    lambda: os.path.expanduser('~/snesdev/pvsneslib/devkitsnes/tools/smconv'),
    lambda: os.path.expanduser('~/pvsneslib/devkitsnes/tools/smconv'),
    lambda: '/opt/pvsneslib/devkitsnes/tools/smconv',
    # Relativo al proyecto
    lambda: os.path.join(os.path.dirname(__file__), '..', 'bin', 'smconv'),
    lambda: os.path.join(os.path.dirname(__file__), '..', 'tools', 'smconv'),
]


def find_smconv():
    """Busca smconv en ubicaciones comunes."""
    for loc_fn in SMCONV_LOCATIONS:
        path = loc_fn()
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
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
        
        if result.returncode == 0 or result.returncode == 139:  # 139 = segfault but may have output
            files = {
                'bnk': output_base + '.bnk',
                'asm': output_base + '.asm',
                'h': output_base + '.h',
            }
            # Verificar qué archivos se generaron
            return {k: v for k, v in files.items() if os.path.exists(v)}
        
        # Si falló, reportar error
        errors = result.stderr or result.stdout
        return {'error': errors[:500] if errors else 'Unknown error'}
    
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
