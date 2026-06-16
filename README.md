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
- `openmpt123` — para validación de archivos .it
- `smconv` (PVSNESlib) — para convertir .it → soundbank SNES

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
│   ├── midi_parser.py  # Parsing MIDI
│   ├── sf2_parser.py   # Parsing SoundFont
│   └── it_builder.py   # Construcción de .it
├── gui/
│   ├── piano_roll.py   # Widget piano roll
│   ├── track_panel.py  # Panel de pistas
│   └── preview.py      # Preview y exportación
└── templates/
    └── bgm.it          # Template estructural
```

## 📝 Licencia

MIT
