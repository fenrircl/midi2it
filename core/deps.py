"""
core/deps.py — Detección e instalación de dependencias multiplataforma.

La GUI usa esto para mostrar qué herramientas faltan y ofrecer instalarlas
sin que el usuario salga de la aplicación.

Herramientas:
  - mido       (Python, REQUERIDA)  — parsing MIDI            → pip
  - fluidsynth (nativa, opcional)   — render de preview        → winget/choco/brew/apt
  - ffmpeg     (nativa, opcional)   — reproduce preview (ffplay)→ winget/choco/brew/apt
  - smconv     (manual, opcional)   — IT→.bnk (audio SNES)     → PVSNESlib (manual)
"""
import os, sys, shutil, subprocess, importlib.util

IS_WINDOWS = os.name == 'nt'
IS_MAC = sys.platform == 'darwin'

PVSNESLIB_RELEASES = "https://github.com/alekmaul/pvsneslib/releases"
FLUIDSYNTH_RELEASES = "https://github.com/FluidSynth/fluidsynth/releases"
FFMPEG_DOWNLOAD = "https://www.gyan.dev/ffmpeg/builds/"

# Frases (cualquier idioma) que indican "ya instalado / sin actualización":
# winget devuelve código != 0 en estos casos, pero NO es un fallo real.
_ALREADY_MARKERS = [
    'already installed', 'ya instalado', 'no applicable update',
    'no hay versiones', 'no newer version', 'no se ha encontrado ninguna actualiz',
    'no available upgrade', 'sin actualiz',
]
_SUCCESS_MARKERS = [
    'successfully installed', 'instalado correctamente', 'installation successful',
]


def _module_present(name):
    return importlib.util.find_spec(name) is not None


def _smconv_present():
    try:
        from core.smconv_runner import find_smconv
        return find_smconv() is not None
    except Exception:
        return False


def check():
    """Devuelve el estado de cada dependencia.

    Returns:
        dict[str, dict]: clave=tool, valor={ok, required, kind, desc}
    """
    return {
        'mido': {
            'ok': _module_present('mido'),
            'required': True, 'kind': 'python',
            'desc': 'Parsing de archivos MIDI',
        },
        'fluidsynth': {
            'ok': bool(shutil.which('fluidsynth')),
            'required': False, 'kind': 'native',
            'desc': 'Render de audio para el preview',
        },
        'ffmpeg': {
            'ok': bool(shutil.which('ffplay') or shutil.which('ffmpeg')),
            'required': False, 'kind': 'native',
            'desc': 'Reproduce el preview (ffplay)',
        },
        'smconv': {
            'ok': _smconv_present(),
            'required': False, 'kind': 'manual',
            'desc': 'Convierte IT → .bnk (audio SNES real)',
        },
    }


def install_plan(tool):
    """Lista ordenada de comandos candidatos para instalar `tool`.

    Cada entrada es (etiqueta, [args...]). Se prueban en orden hasta que uno
    tenga éxito. Solo se incluyen comandos cuyo gestor está disponible en PATH.
    Devuelve [] si no hay instalación automática (p.ej. smconv).
    """
    plan = []

    if tool == 'mido':
        # pip siempre disponible junto al intérprete actual
        plan.append(("pip", [sys.executable, '-m', 'pip', 'install', '--user', 'mido']))
        return plan

    if tool == 'fluidsynth':
        if IS_WINDOWS:
            # FluidSynth NO está en el repo Community de winget.
            if shutil.which('choco'):
                plan.append(("choco", ['choco', 'install', '-y', 'fluidsynth']))
            if shutil.which('scoop'):
                plan.append(("scoop", ['scoop', 'install', 'fluidsynth']))
            # Sin choco/scoop → instalación manual (ver manual_hint)
        elif IS_MAC:
            if shutil.which('brew'):
                plan.append(("brew", ['brew', 'install', 'fluid-synth']))
        else:
            plan += _linux_apt('fluidsynth')
        return plan

    if tool == 'ffmpeg':
        if IS_WINDOWS:
            if shutil.which('winget'):
                plan.append(("winget", ['winget', 'install', '-e', '--id',
                                        'Gyan.FFmpeg',
                                        '--accept-package-agreements',
                                        '--accept-source-agreements']))
            if shutil.which('choco'):
                plan.append(("choco", ['choco', 'install', '-y', 'ffmpeg']))
            if shutil.which('scoop'):
                plan.append(("scoop", ['scoop', 'install', 'ffmpeg']))
        elif IS_MAC:
            if shutil.which('brew'):
                plan.append(("brew", ['brew', 'install', 'ffmpeg']))
        else:
            plan += _linux_apt('ffmpeg')
        return plan

    # smconv: no hay instalación automática fiable (forma parte de PVSNESlib)
    return plan


def _linux_apt(pkg):
    """Comandos apt para Linux usando pkexec/sudo según disponibilidad."""
    cmds = []
    if shutil.which('apt-get'):
        if shutil.which('pkexec'):
            cmds.append(("pkexec apt", ['pkexec', 'apt-get', 'install', '-y', pkg]))
        if shutil.which('sudo'):
            cmds.append(("sudo apt", ['sudo', 'apt-get', 'install', '-y', pkg]))
    return cmds


def manual_hint(tool):
    """Instrucción manual / enlace de descarga por herramienta."""
    if tool == 'smconv':
        return ("smconv forma parte de PVSNESlib. Descárgalo desde:\n"
                f"  {PVSNESLIB_RELEASES}\n"
                "Luego define la variable de entorno PVSNESLIB_HOME apuntando "
                "a la carpeta de instalación, o copia smconv(.exe) a "
                "midi2it/bin/.")
    if tool == 'fluidsynth':
        msg = ("FluidSynth no está en winget. Opciones:\n")
        if IS_WINDOWS:
            msg += ("  • Instala Chocolatey o Scoop y vuelve a pulsar Instalar.\n"
                    "  • O descarga el zip de Windows desde:\n"
                    f"      {FLUIDSYNTH_RELEASES}\n"
                    "    Descomprímelo y añade su carpeta 'bin' al PATH.")
        else:
            msg += f"  Descárgalo desde: {FLUIDSYNTH_RELEASES}"
        return msg
    if tool == 'ffmpeg':
        return ("Descarga FFmpeg (incluye ffplay) desde:\n"
                f"  {FFMPEG_DOWNLOAD}\n"
                "Descomprime y añade la carpeta 'bin' al PATH. En Windows también: "
                "winget install -e --id Gyan.FFmpeg")
    if IS_WINDOWS and not shutil.which('winget'):
        return ("No se encontró 'winget'. Instálalo desde Microsoft Store "
                "(App Installer) o instala la herramienta manualmente.")
    return ("No se encontró un gestor de paquetes para instalación automática. "
            "Instala la herramienta manualmente.")


def classify_result(rc, output):
    """Clasifica el resultado de una instalación.

    Returns: 'ok' | 'already' | 'fail'
      - 'ok'      : instalado correctamente (rc 0 o marcador de éxito).
      - 'already' : ya estaba instalado / sin actualización (no es fallo;
                    puede requerir reiniciar la app para detectarlo en PATH).
      - 'fail'    : fallo real.
    """
    t = (output or '').lower()
    if rc == 0 or any(m in t for m in _SUCCESS_MARKERS):
        return 'ok'
    if any(m in t for m in _ALREADY_MARKERS):
        return 'already'
    return 'fail'


def run_install(cmd, on_line=None):
    """Ejecuta un comando de instalación, transmitiendo salida línea a línea.

    Returns:
        (rc, output): código de retorno (-1 si el ejecutable no existe) y la
        salida completa concatenada (para clasificar con classify_result).
    """
    lines = []

    def emit(s):
        lines.append(s)
        if on_line:
            on_line(s)

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, encoding='utf-8', errors='replace',
        )
    except FileNotFoundError:
        emit(f"✖ No se encontró: {cmd[0]}")
        return -1, "\n".join(lines)

    if proc.stdout is not None:
        for line in proc.stdout:
            emit(line.rstrip('\n'))
    proc.wait()
    return proc.returncode, "\n".join(lines)
