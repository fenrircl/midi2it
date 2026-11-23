# midi2it

**MIDI + SoundFont → IT para SNES**  
Conversor que toma un archivo MIDI y un SoundFont (.sf2) y genera un archivo .it
compatible con **smconv** de [PVSNESlib](https://github.com/alekmaul/pvsneslib) para
reproducción en SNES real o emuladores.

## 🎯 Objetivo

Crear música para SNES usando el flujo de trabajo clásico de los juegos originales:
- MIDI define la secuencia de notas
- SoundFont (.sf2) provee los samples de instrumentos
- El resultado es un .it (Impulse Tracker) que se convierte con smconv a soundbank SPC700

> **Estado:** el exportador ahora escribe un IT desde cero, con tablas de
> offsets, patrones de 64 filas, instrumentos y samples asignados desde MIDI +
> SF2. La validación contra `smconv` y reproductores sigue pendiente. Consulta
> [el plan de implementación](docs/PLAN-IMPLEMENTACION.md) antes de usar la
> salida en una ROM.

## 📦 Instalación

```bash
git clone https://github.com/fenrircl/midi2it.git
cd midi2it
pip install mido  # para parsing MIDI
```

Dependencias opcionales:
- `fluidsynth` — para preview de audio
- `ffmpeg` (incluye `ffplay`) — para reproducir el preview
- `openmpt123` — para validación de archivos .it
- `smconv` (PVSNESlib) — para convertir .it → soundbank SNES

### Instalar dependencias desde la GUI

La interfaz incluye un gestor de dependencias: **Herramientas → Dependencias…**.
Detecta qué falta y lo resuelve desde la propia app.

**Descarga portátil (recomendado, botón "Descargar (portátil)"):** baja el binario
oficial, lo descomprime en `~/.midi2it/tools/` y lo usa por **ruta absoluta**. No
instala nada en el sistema, **no toca el PATH** y **no requiere reiniciar**:

- **ffmpeg** → build de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (incluye `ffplay`)
- **fluidsynth** → release oficial `win10-x64` de GitHub
- **smconv** → release de PVSNESlib del SO actual (win/linux/darwin)

**Alternativas (botón "Instalar (gestor)"):**
- **mido** → `pip` (requiere reiniciar la app)
- **ffmpeg / fluidsynth** → `winget` / `choco` / `scoop` (Windows), `brew` (macOS), `apt` (Linux)

midi2it busca cada herramienta primero en `~/.midi2it/tools/` (portátil) y luego en
el PATH del sistema. Al arrancar avisa si falta algo y ofrece abrir el gestor.

### Windows

Para compilar y abrir la GUI, sigue la sección [Build Windows rápido](#build-windows-rápido).
No hace falta instalar Python manualmente: el script crea `.venv-win` si no existe.

## 🚀 Uso

### CLI

```bash
python3 midi2it.py entrada.mid DraculaX.sf2 -o cancion.it
python3 midi2it.py entrada.mid DraculaX.sf2 -o cancion.it --tempo 140
```

### GUI

```bash
python3 midi2it.py -g
# o simplemente:
python3 midi2it.py
```

## 🖥️ GUI (Mini DAW)

- Piano roll visual con notas MIDI
- Control de pistas: instrumento, volumen, transposición, solo/mute
- Preview de audio con FluidSynth
- Estimación del presupuesto BRR y optimización de duración antes de exportar
- Exportación a .it compatible con SNES

## ⚙️ Pipeline

```
MIDI ──┐
       ├──▶ midi2it ──▶ .it ──▶ smconv ──▶ soundbank.bnk ──▶ SNES ROM
SF2  ──┘
```

## 🔧 Requisitos SNES

- Máximo **8 canales** (limitación del SPC700)
- Samples en **16-bit PCM** (se convierten a BRR durante smconv)
- Cada sample debe caber en la RAM del SPC700 (~64KB total)
- Tempo y notas deben adaptarse a 64 filas de patrón

## 📁 Estructura

```
midi2it/
├── midi2it.py          # CLI entry point
├── midi2it_gui.py      # GUI (tkinter)
├── core/
│   ├── midi_parser.py   # Parsing MIDI (import de mido diferido)
│   ├── sf2_parser.py    # Parsing SoundFont
│   ├── it_builder.py    # API de compatibilidad del exportador
│   ├── it_writer.py     # Escritura de .it y tablas de offsets
│   ├── smconv_runner.py # Ejecuta smconv (IT→.bnk), multiplataforma
│   └── deps.py          # Detección/instalación de dependencias
├── gui/
│   ├── piano_roll.py    # Widget piano roll
│   ├── track_panel.py   # Panel de pistas
│   ├── preview.py       # Preview y exportación
│   └── deps_dialog.py   # Gestor de dependencias (GUI)
└── templates/
    └── bgm.it           # Fixture histórica; no se usa al exportar
```

## 🏗️ Build — generar un .exe (Windows)

### Build Windows rápido

Abre PowerShell en la carpeta del repositorio. Si el proyecto está dentro de
WSL, puedes usar su ruta `\\wsl.localhost\Ubuntu\home\...`, aunque una carpeta
local de Windows (por ejemplo `C:\src\midi2it`) suele compilar más rápido.

**Primera vez o después de cambiar el código:**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1
```

El comando crea/reutiliza `.venv-win`, compila y abre la GUI. En la app, carga
el MIDI y el SF2; para habilitar audio, abre **Herramientas** y descarga
FluidSynth y FFmpeg una sola vez.

**Siguientes veces:** vuelve a ejecutar el mismo comando para recompilar y abrir.
Los paquetes Python se instalan solo si faltan. Si no cambiaste el código y solo
quieres abrir el ejecutable existente:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1 -SkipBuild
```

El gestor de dependencias instala las herramientas de audio portátiles en
`%USERPROFILE%\.midi2it\tools`; quedan disponibles al reiniciar la app y no se
descargan de nuevo en cada ejecución. Solo vuelve a instalarlas si borras esa
carpeta o cambias de perfil de Windows.

Si el entorno `.venv-win` ya está preparado y quieres saltarte también la
comprobación de paquetes Python:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1 -SkipInstall
```

Para generar solo el build sin abrir la GUI, agrega `-BuildOnly`. Para probar
la conversión con un SF2 concreto, usa:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1 `
  -Sf2Path "C:\SoundFonts\mi-soundfont.sf2"
```

### Opciones adicionales

Se usa [PyInstaller](https://pyinstaller.org/) para empaquetar la aplicación.
Variantes del script para abrir la GUI después de indicar un SF2, o generar un
ejecutable único:

```powershell
# Abrir la GUI aunque también se pase un SF2.
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1 -Gui

# Generar un único .exe en vez de la carpeta onedir.
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_test_windows.ps1 `
  -BuildMode onefile -BuildOnly
```

El build queda en `dist\onedir`. Con `-Sf2Path`, el script prueba la conversión
por CLI desde Python y desde el ejecutable. Si `openmpt123` o `smconv` están en
`PATH`, valida la salida. El build GUI es sin consola; el de conversión conserva
la consola para mostrar errores.

Alternativa manual para generar un único ejecutable GUI. El separador de datos
de PyInstaller en Windows es `;` (en Linux/macOS es `:`):

```powershell
# 1. Instalar dependencias de build
pip install pyinstaller mido

# 2. Generar el .exe (un solo archivo, sin consola)
#    El separador de --add-data en Windows es ';'  (en Linux/macOS es ':')
pyinstaller --onefile --windowed ^
  --name midi2it ^
  --paths . ^
  --collect-submodules core ^
  --collect-submodules gui ^
  --hidden-import midi2it_gui ^
  --hidden-import mido ^
  midi2it.py
```

El ejecutable queda en `dist\midi2it.exe`.

Notas:
- `--windowed` evita que se abra una consola junto a la GUI. Quítalo si quieres
  ver mensajes de error en una terminal.
- El writer genera el archivo IT sin depender del template `bgm.it`.
- `fluidsynth`, `ffmpeg` y `smconv` **no** se empaquetan (son binarios externos);
  el usuario los instala desde **Herramientas → Dependencias…** en la app.
- Para un icono propio: añade `--icon=icono.ico`.

### Build en Linux/macOS

Mismo comando, cambiando el separador de `--add-data` a `:` y el `^` por `\`:

```bash
pip install pyinstaller mido
pyinstaller --onefile --windowed \
  --name midi2it \
  --paths . \
  --collect-submodules core \
  --collect-submodules gui \
  --hidden-import midi2it_gui \
  --hidden-import mido \
  midi2it.py
```

(Un binario generado en Linux solo corre en Linux; para un `.exe` de Windows hay
que compilar en Windows, p.ej. con una VM o GitHub Actions con runner `windows-latest`.)

### Release automático con el .exe

El repo incluye `.github/workflows/release.yml`: al empujar un tag de versión,
GitHub Actions compila el `.exe` en Windows y crea un release con el binario adjunto.

```bash
git tag v0.1.0
git push origin v0.1.0
```

El `.exe` queda en la pestaña **Releases** del repo. También puede lanzarse a mano
desde **Actions → Build Windows EXE & Release** (botón *Run workflow*); en ese caso
sube el `.exe` como *artifact* sin crear release.

El release publica **dos** descargas:
- `midi2it.exe` — ejecutable único (cómodo).
- `midi2it-windows-folder.zip` — versión en carpeta (menos falsos positivos).

### ⚠️ Falso positivo de antivirus (Wacatac.B!ml)

Windows Defender u otros antivirus pueden marcar el `.exe` como
`Trojan:Win32/Wacatac.B!ml`. Es un **falso positivo** heurístico (`!ml` = modelo
de machine-learning) muy común en ejecutables PyInstaller `--onefile`: el
bootloader se auto-extrae en disco y eso dispara la detección. El código es
abierto, sin acceso a red ni payload.

Soluciones:
- Usa `midi2it-windows-folder.zip` (build `--onedir`): mucho menos detectado.
- Restaura el archivo: *Seguridad de Windows → Protección contra virus →
  Historial de protección → Permitir en el dispositivo*.
- Reporta el falso positivo a Microsoft:
  [microsoft.com/wdsi/filesubmission](https://www.microsoft.com/en-us/wdsi/filesubmission).
- Solución definitiva: firmar el `.exe` con un certificado de *code signing*.

## 📝 Licencia

MIT
