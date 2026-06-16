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
            if shutil.which('winget'):
                plan.append(("winget", ['winget', 'install', '-e', '--id',
                                        'FluidSynth.FluidSynth',
                                        '--accept-package-agreements',
                                        '--accept-source-agreements']))
            if shutil.which('choco'):
                plan.append(("choco", ['choco', 'install', '-y', 'fluidsynth']))
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
    """Instrucción manual para herramientas sin instalador automático."""
    if tool == 'smconv':
        return ("smconv forma parte de PVSNESlib. Descárgalo desde:\n"
                f"  {PVSNESLIB_RELEASES}\n"
                "Luego define la variable de entorno PVSNESLIB_HOME apuntando "
                "a la carpeta de instalación, o copia smconv(.exe) a "
                "midi2it/bin/.")
    if not shutil.which('winget') and IS_WINDOWS:
        return ("No se encontró 'winget'. Instálalo desde Microsoft Store "
                "(App Installer) o instala la herramienta manualmente.")
    return ("No se encontró un gestor de paquetes para instalación automática. "
            "Instala la herramienta manualmente.")


def run_install(cmd, on_line=None):
    """Ejecuta un comando de instalación, transmitiendo salida línea a línea.

    Args:
        cmd: lista de args.
        on_line: callback(str) opcional por cada línea de salida.

    Returns:
        int: código de retorno (0 = éxito). -1 si el ejecutable no existe.
    """
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
    except FileNotFoundError:
        if on_line:
            on_line(f"✖ No se encontró: {cmd[0]}")
        return -1

    if proc.stdout is not None:
        for line in proc.stdout:
            if on_line:
                on_line(line.rstrip('\n'))
    proc.wait()
    return proc.returncode
