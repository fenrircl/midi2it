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
Detecta qué falta y lo instala desde la propia app:

- **mido** → `pip` (siempre disponible)
- **fluidsynth / ffmpeg** → `winget` o `choco` (Windows), `brew` (macOS), `apt` (Linux)
- **smconv** → enlace de descarga de PVSNESlib (instalación manual)

Al arrancar, la GUI avisa si falta algo y ofrece abrir este gestor.

### Windows

1. Instala Python desde [python.org](https://www.python.org/downloads/) marcando
   **"tcl/tk and IDLE"** (tkinter) y **"Add python.exe to PATH"**.
2. `pip install mido`
3. `python midi2it.py` (abre la GUI). Usa **Herramientas → Dependencias…** para
   instalar fluidsynth/ffmpeg con `winget`.

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
│   ├── it_builder.py    # Construcción de .it
│   ├── smconv_runner.py # Ejecuta smconv (IT→.bnk), multiplataforma
│   └── deps.py          # Detección/instalación de dependencias
├── gui/
│   ├── piano_roll.py    # Widget piano roll
│   ├── track_panel.py   # Panel de pistas
│   ├── preview.py       # Preview y exportación
│   └── deps_dialog.py   # Gestor de dependencias (GUI)
└── templates/
    └── bgm.it           # Template estructural
```

## 🏗️ Build — generar un .exe (Windows)

Se usa [PyInstaller](https://pyinstaller.org/) para empaquetar todo (incluido
el intérprete de Python y el template `bgm.it`) en un único ejecutable.

```powershell
# 1. Instalar dependencias de build
pip install pyinstaller mido

# 2. Generar el .exe (un solo archivo, sin consola)
#    El separador de --add-data en Windows es ';'  (en Linux/macOS es ':')
pyinstaller --onefile --windowed ^
  --name midi2it ^
  --paths . ^
  --add-data "templates/bgm.it;templates" ^
  --collect-submodules core ^
  --collect-submodules gui ^
  --hidden-import midi2it_gui ^
  midi2it.py
```

El ejecutable queda en `dist\midi2it.exe`.

Notas:
- `--windowed` evita que se abra una consola junto a la GUI. Quítalo si quieres
  ver mensajes de error en una terminal.
- El template `bgm.it` se incluye con `--add-data`; en tiempo de ejecución se
  localiza vía `sys._MEIPASS` (ya soportado en `core/it_builder.py`).
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
  --add-data "templates/bgm.it:templates" \
  --collect-submodules core \
  --collect-submodules gui \
  --hidden-import midi2it_gui \
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

## 📝 Licencia

MIT
