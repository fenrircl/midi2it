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
import urllib.request, json, zipfile, tarfile

IS_WINDOWS = os.name == 'nt'
IS_MAC = sys.platform == 'darwin'

GITHUB_LATEST = "https://api.github.com/repos/{}/{}/releases/latest"

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


# ─── Herramientas portátiles (descarga + descompresión, sin instalar nada) ────

def tools_dir():
    """Carpeta local donde se descomprimen las herramientas portátiles."""
    return os.path.join(os.path.expanduser('~'), '.midi2it', 'tools')


def _exe(name):
    """Nombre del binario con extensión según plataforma."""
    if IS_WINDOWS and not name.lower().endswith('.exe'):
        return name + '.exe'
    return name


def portable_binary(name):
    """Ruta absoluta a un binario descargado de forma portátil, o None.

    Busca bajo ~/.midi2it/tools/ sin tocar el PATH del sistema.
    """
    base = tools_dir()
    if not os.path.isdir(base):
        return None
    target = _exe(name).lower()
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.lower() == target:
                return os.path.join(root, f)
    return None


def executable(name):
    """Resuelve un binario: portátil primero (ruta absoluta), luego el PATH.

    No modifica el entorno. Devuelve ruta absoluta o None.
    """
    return portable_binary(name) or shutil.which(name)


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
            'ok': bool(executable('fluidsynth')),
            'required': False, 'kind': 'native',
            'desc': 'Render de audio para el preview',
        },
        'ffmpeg': {
            'ok': bool(executable('ffplay') or executable('ffmpeg')),
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


def _portable_spec(tool):
    """Define cómo obtener cada herramienta de forma portátil.

    'direct': URL fija al archivo. 'github': (owner, repo) + 'match' para elegir
    el asset del último release. 'exe': nombre del binario a localizar tras extraer.
    Devuelve None si no hay soporte portátil para la plataforma actual.
    """
    if tool == 'ffmpeg' and IS_WINDOWS:
        return {'direct': 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
                'exe': 'ffplay.exe'}
    if tool == 'fluidsynth' and IS_WINDOWS:
        return {'github': ('FluidSynth', 'fluidsynth'),
                'match': lambda n: 'win10-x64' in n.lower() and n.lower().endswith('.zip'),
                'exe': 'fluidsynth.exe'}
    if tool == 'smconv':
        # PVSNESlib trae smconv dentro de su release (multiplataforma vía .zip)
        exe = 'smconv.exe' if IS_WINDOWS else 'smconv'
        return {'github': ('alekmaul', 'pvsneslib'),
                'match': _smconv_asset_match, 'exe': exe}
    return None


def _smconv_asset_match(name):
    n = name.lower()
    if not n.endswith(('.zip', '.tgz', '.tar.gz')):
        return False
    if 'source' in n:
        return False
    # Elegir el build del SO actual (PVSNESlib publica win/linux/darwin)
    if IS_WINDOWS:
        return 'win' in n
    if IS_MAC:
        return any(x in n for x in ('darwin', 'mac', 'osx'))
    return 'linux' in n


def has_portable(tool):
    return _portable_spec(tool) is not None


def _log(cb, msg):
    if cb:
        cb(msg)


def _download(url, path, on_line=None):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'midi2it'})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f:
            total = int(r.headers.get('Content-Length', 0) or 0)
            done = 0
            last = -1
            while True:
                b = r.read(262144)
                if not b:
                    break
                f.write(b)
                done += len(b)
                if total:
                    pct = done * 100 // total
                    if pct != last and pct % 5 == 0:
                        _log(on_line, f"  {pct}% ({done // 1048576} MB / {total // 1048576} MB)")
                        last = pct
        _log(on_line, f"  descargado ({done // 1048576} MB)")
        return True
    except Exception as e:
        _log(on_line, f"Error de descarga: {e}")
        return False


def _latest_asset_url(owner, repo, match, on_line=None):
    api = GITHUB_LATEST.format(owner, repo)
    try:
        req = urllib.request.Request(
            api, headers={'User-Agent': 'midi2it', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as e:
        _log(on_line, f"Error consultando GitHub: {e}")
        return None
    cands = [a for a in data.get('assets', []) if match(a.get('name', ''))]
    if not cands:
        return None
    if IS_WINDOWS:  # preferir asset de Windows si hay varios
        cands.sort(key=lambda a: ('win' not in a['name'].lower(), len(a['name'])))
    return cands[0].get('browser_download_url')


def _extract(archive, dest, on_line=None):
    try:
        if archive.lower().endswith(('.tgz', '.tar.gz')):
            with tarfile.open(archive) as t:
                t.extractall(dest)
        else:
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        return True
    except Exception as e:
        _log(on_line, f"Error al descomprimir: {e}")
        return False


def _find_exe(root, exe_name):
    target = exe_name.lower()
    for dp, _dirs, files in os.walk(root):
        for f in files:
            if f.lower() == target:
                return os.path.join(dp, f)
    return None


def portable_install(tool, on_line=None):
    """Descarga y descomprime una herramienta de forma portátil (sin instalar).

    Returns:
        (status, path): status 'ok'|'fail'; path al binario si 'ok'.
    """
    spec = _portable_spec(tool)
    if not spec:
        _log(on_line, f"No hay versión portátil de {tool} para esta plataforma.")
        return ('fail', None)

    dest = os.path.join(tools_dir(), tool)
    os.makedirs(dest, exist_ok=True)

    url = spec.get('direct')
    if not url:
        owner, repo = spec['github']
        _log(on_line, f"Buscando último release de {owner}/{repo}...")
        url = _latest_asset_url(owner, repo, spec['match'], on_line)
        if not url:
            _log(on_line, "No se encontró un archivo descargable en el release.")
            return ('fail', None)

    archive = os.path.join(dest, os.path.basename(url.split('?')[0]) or 'download.zip')
    _log(on_line, f"Descargando: {url}")
    if not _download(url, archive, on_line):
        return ('fail', None)

    _log(on_line, "Descomprimiendo...")
    if not _extract(archive, dest, on_line):
        return ('fail', None)
    try:
        os.remove(archive)
    except OSError:
        pass

    exe = _find_exe(dest, spec['exe'])
    if not exe:
        _log(on_line, f"Se descargó pero no se encontró {spec['exe']} dentro.")
        return ('fail', None)

    # En Unix, asegurar permiso de ejecución
    if not IS_WINDOWS:
        try:
            os.chmod(exe, 0o755)
        except OSError:
            pass

    _log(on_line, f"✅ {tool} listo: {exe}")
    return ('ok', exe)


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
