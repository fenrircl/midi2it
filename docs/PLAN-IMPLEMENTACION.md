# Plan de implementación — midi2it

**Objetivo:** convertir MIDI + SoundFont en un `.it` **válido** para `smconv`
de PVSNESlib, con presupuesto SNES (8 canales, ≤58 KB de samples BRR, loops
alineados, echo opcional y SFX), para que VS-SNES pueda generar su música desde
MIDI en vez de editar un `.it` a mano.

**Estado actual (2026-11-23):** el writer basado en template fue reemplazado
por `core/it_writer.py`, que construye headers, offsets, instrumentos, samples
y patterns. El CLI asigna samples SF2 por programa MIDI y la GUI conserva el
SoundFont de origen al combinar bibliotecas. La implementación aún requiere
validación con un parser IT independiente, `openmpt123` y `smconv`; por eso no
se considera completada la fase M0/M1.

Los apartados de diagnóstico y evidencia siguientes describen el estado
anterior al cambio y se conservan como registro de por qué se reemplazó el
writer.

**Revisión:** 2026-11-23, contra `01f0294` (main local, un commit de CI sobre
`8d0a9db`).

---

## 1. Resumen ejecutivo

`midi2it` tiene una buena idea y una GUI útil (multi-SF2, edición por pista,
preview), pero el núcleo de exportación está construido sobre una premisa
frágil: *"smconv escanea el archivo, así que puedo appendear headers y samples
al final del template"*. Eso es falso. El formato IT usa **tablas de offsets**
en el header; si cambias `insnum`/`smpnum`/`patnum` sin reescribir las tablas,
el lector calcula las tablas en otra posición y lee basura. El resultado es un
híbrido: el pattern 0 del template sigue byte-idéntico, los instrumentos nuevos
no se referencian y `smconv` reporta `Instrument data: 0 bytes` y canales fuera
de rango.

La solución no es seguir parchando offsets. Es escribir un **IT writer propio**
(`core/it_writer.py`) que arme el archivo en dos pasadas: primero reserva y
calcula bloques, después parchea las tablas. Es un módulo de ~400 líneas, con
spec pública y tests que comparan notas, samples y salida de `smconv`.

Orden recomendado:

1. Writer IT válido + tests que fallen con el código actual.
2. Fidelidad musical: tempo, filas, duración, velocity, pan, canales, drums.
3. Presupuesto SNES: BRR, loops, 7+1 canales, echo, SFX.
4. Integración con VS-SNES y validación con `smconv`.
5. Ruta alternativa MSU-1 (render directo a PCM) para emulador/FXPAK.

---

## 2. Estado verificado (evidencia)

### 2.1 CLI con MIDI + SF2

```bash
/usr/bin/python3.12 midi2it.py \
  examples/forest-night-fever.mid \
  examples/soundfonts/Rockman_X1_X2.sf2 \
  -o test.it
```

Salida:

```
Pistas activas: 2/2
Total PCM: 0.0KB / 96KB
✅ IT: test.it
   49856 bytes, 2 instruments, 2 samples, 64-row pattern con 64 filas activas
```

`Total PCM: 0.0KB` significa que **no se asignó ningún sample del SF2**. El CLI
llama a `it_builder.build()` sin `track_config`; el builder autogenera pistas
con `sample_index=None` y usa samples de silencio (`it_builder.py:143-204`).

### 2.2 `openmpt123 --info`

| Archivo | Duración | Instrumentos | Samples |
|---|---:|---:|---:|
| `templates/bgm.it` | 01:30.750 | 1 | 11 |
| `test.it` generado | 01:04.000 | 2 | 2 |

El archivo generado reporta 2 samples, pero son los dos samples de silencio
del builder, no los del SF2. La duración cambia porque se modificó el byte de
tempo, no porque haya una secuencia nueva.

### 2.3 `smconv`

```bash
smconv -s -o sb -V -b 5 test.it
```

```
smconv: error: More than 8 channels. Found channel 15   (x8)
smconv: error: More than 8 channels. Found channel 9
Instrument data: [    0 bytes]     Instruments: [2/64]
Pattern data:    [ 3603 bytes]     Patterns:    [12/64]
Sample data:     [15075 bytes]     Samples:     [2/64]
```

`Instrument data: 0 bytes` confirma que los instrumentos nuevos no están
referenciados. Los 12 patterns y los 15 KB de samples son del template, no del
MIDI. `smconv` sale con código 0, así que un CI que solo mire el exit code no
detecta el problema.

### 2.4 Tablas de offsets

El header IT tiene contadores y, después de las órdenes, tres tablas de offsets:

```
0xC0 + ordnum                 → órdenes
       + 4*insnum             → offsets de instrumentos
       + 4*smpnum             → offsets de samples
       + 4*patnum             → offsets de patterns
```

En el template: `ordnum=13`, `insnum=1`, `smpnum=11`, `patnum=12`, y los offsets
del primer sample/instrumento/pattern apuntan a `1053/499/1933`.

En el generado: `insnum=2`, `smpnum=2`, pero los offsets leídos son
`1133/1213/1293…`, que caen dentro de headers de sample, no en patterns. El
builder cambió los contadores (`it_builder.py:253-254`) pero no reescribió las
tablas ni las órdenes. El pattern 0 del template sigue byte-idéntico en el
archivo generado; el pattern nuevo se appendea al final sin entrada en la tabla.

### 2.5 Tests

`pytest` local: 7 passed. Pero:

- `test_it_builder` solo verifica que el archivo exista, pese >1000 bytes y que
  `openmpt123 --info` muestre `Instruments:`/`Samples....:` >0. El template ya
  cumple eso (`tests/test_e2e.py:107-130`).
- `test_mute_solo` compara tamaños de archivo, no contenido musical
  (`tests/test_e2e.py:165-167`).
- Los `.sf2` están en `.gitignore`; solo `examples/forest-night-fever.mid` está
  versionado. En CI, los tests que dependen de SF2 se saltan; no se valida el
  camino MIDI+SF2.

Conclusión: los tests dan falsa confianza. Hay que testear el **contenido** del
IT (notas, samples, offsets) y la salida de `smconv`, no el tamaño.

---

## 3. Especificación mínima IT 2.14

Esta es la referencia que debe implementar el writer. Está resumida de
`ITTECH.TXT` y verificada contra el template (`insnum=1`, `smpnum=11`,
`patnum=12`, `cmwt=0x0214`).

### 3.1 Header (0x00–0xBF)

| Offset | Tamaño | Campo |
|---:|---:|---|
| 0x00 | 4 | `IMPM` |
| 0x04 | 26 | nombre de la canción |
| 0x1E | 1 | highlight menor |
| 0x1F | 1 | highlight mayor |
| 0x20 | 2 | `ordnum` |
| 0x22 | 2 | `insnum` |
| 0x24 | 2 | `smpnum` |
| 0x26 | 2 | `patnum` |
| 0x28 | 2 | `cwtv` (0x0214) |
| 0x2A | 2 | `cmwt` (0x0214) |
| 0x2C | 2 | flags (stereo, instruments, linear) |
| 0x2E | 2 | special |
| 0x30 | 1 | global volume |
| 0x31 | 1 | mix volume |
| 0x32 | 1 | speed (ticks por fila) |
| 0x33 | 1 | tempo (BPM) |
| 0x34 | 1 | separación |
| 0x35 | 1 | pitch wheel depth |
| 0x36 | 2 | largo del mensaje |
| 0x38 | 4 | offset del mensaje |
| 0x3C | 4 | reservado |
| 0x40 | 64 | pan por canal (0–64, 32 = centro) |
| 0x80 | 64 | volumen por canal (0–64) |
| 0xC0 | `ordnum` | órdenes (255 = fin) |

Después de las órdenes: `insnum` offsets (u32), `smpnum` offsets (u32),
`patnum` offsets (u32). Todos son **offsets absolutos desde el inicio del
archivo**.

### 3.2 Sample header (80 bytes)

| Offset | Tamaño | Campo |
|---:|---:|---|
| 0x00 | 4 | `IMPS` |
| 0x04 | 12 | nombre DOS |
| 0x10 | 1 | 0 |
| 0x11 | 1 | GvL (0–64) |
| 0x12 | 1 | flags |
| 0x13 | 1 | volumen (0–64) |
| 0x14 | 26 | nombre |
| 0x2E | 1 | Cvt |
| 0x2F | 1 | pan (bit 7 = usar) |
| 0x30 | 4 | largo en frames |
| 0x34 | 4 | loop begin |
| 0x38 | 4 | loop end (exclusivo) |
| 0x3C | 4 | C5 speed (Hz) |
| 0x40 | 4 | sustain begin |
| 0x44 | 4 | sustain end |
| 0x48 | 4 | **offset absoluto del PCM** |
| 0x4C | 4 | vibrato |

Flags: `0x01` existe, `0x02` 16-bit, `0x10` loop, `0x20` sustain loop,
`0x40` bidi loop, `0x80` bidi sustain. Para SNES: 16-bit mono, loop si aplica.

### 3.3 Instrument header (554 bytes)

| Offset | Tamaño | Campo |
|---:|---:|---|
| 0x00 | 4 | `IMPI` |
| 0x04 | 12 | nombre DOS |
| 0x10 | 1 | 0 |
| 0x11 | 1 | NNA |
| 0x12 | 1 | DCT |
| 0x13 | 1 | DCA |
| 0x14 | 2 | fadeout |
| 0x16 | 1 | PPS |
| 0x17 | 1 | PPC |
| 0x18 | 1 | volumen global |
| 0x19 | 1 | pan por defecto |
| 0x1A | 1 | random volume |
| 0x1B | 1 | random pan |
| 0x1C | 2 | tracker version |
| 0x1E | 1 | número de samples |
| 0x1F | 1 | 0 |
| 0x20 | 26 | nombre |
| 0x3A | 1 | filtro inicial |
| 0x3B | 1 | resonancia |
| 0x3C | 1 | canal MIDI |
| 0x3D | 1 | programa MIDI |
| 0x3E | 2 | banco MIDI |
| 0x40 | 240 | mapa de teclado: 120 × (nota, sample) |
| 0x130 | 82 | envelope de volumen |
| 0x182 | 82 | envelope de pan |
| 0x1D4 | 82 | envelope de pitch |
| 0x226 | 4 | padding |

Para SNES alcanza con: NNA/DCT/DCA en 0, fadeout corto, volumen 64, pan 32,
mapa de teclado completo apuntando al sample 1, envelopes apagados. Si se
quieren envelopes, implementarlos después; el template no los usa.

### 3.4 Pattern (8 bytes de header + datos)

| Offset | Tamaño | Campo |
|---:|---:|---|
| 0x00 | 2 | largo de los datos empaquetados (sin header) |
| 0x02 | 2 | filas (64 para SNES) |
| 0x04 | 4 | reservado |

Empaquetado por fila:

- Un byte de máscara de canal: bit 7 = 1 indica "canal nuevo"; bits 0–6 =
  número de canal (0–63).
- Bits de la máscara: `0x01` nota, `0x02` instrumento, `0x04` volumen,
  `0x08` efecto.
- Luego, los bytes de los campos presentes, en ese orden.
- `0x00` termina la fila.

El builder actual escribe `[canal, 0x07, nota, instrumento, volumen]` sin el
bit 7 en el canal y sin el header de pattern de 8 bytes
(`it_builder.py:303-334`). Por eso el pattern no se decodifica.

### 3.5 Reglas de `smconv` / SNESMOD

| Regla | Valor |
|---|---|
| Canales | ≤8; el 8 (índice 7) lo roba SNESMOD para SFX |
| Patterns | ≤64 patterns, 64 filas recomendadas |
| Órdenes | ≤200 |
| Samples | ≤64; datos BRR ≤58 KB (incluye driver/echo) |
| Instrumentos | ≤64 |
| Samples | 16-bit mono; loops alineados a 16 frames |
| BRR | `ceil(frames/16)*9` bytes (9/32 del PCM 16-bit) |
| Echo | cada paso de EDL = 2 KB de ARAM; EDL 5 = 10 KB |
| Efectos IT | sin filtros, sin tremolo/panbrello, sin envelopes complejos |
| Canal 8 | no poner melodía; reservarlo para SFX |

---

## 4. Bugs y deuda técnica

### P0 — bloquean la exportación

| ID | Bug | Ubicación | Evidencia |
|---|---|---|---|
| IT-01 | `_make_sample_header` escribe el nombre en el offset 0 (borra `IMPS`) y todos los campos corridos | `core/it_builder.py:54-91` | `h[0:13]=name`, `h[16:18]=flags`, `h[48:50]=rate`, `h[66:70]="IMPS"` |
| IT-02 | `_make_instrument_header` usa 482 bytes; el formato nuevo son 554, con mapa de teclado en `0x40` (2 bytes por nota) | `core/it_builder.py:94-112` | template: `IMPI` en 499, siguiente `IMPS` en 1053 → 554 bytes |
| IT-03 | Cambia `insnum`/`smpnum` pero no reescribe las tablas de offsets ni las órdenes | `core/it_builder.py:249-256` | offsets leídos caen en headers, no en patterns |
| IT-04 | Appendea headers/samples/pattern al final sin registrar sus offsets | `core/it_builder.py:261-334` | `smconv`: `Instrument data: 0 bytes` |
| IT-05 | Pattern header de 4 bytes + 32 bytes de "channel names"; el header IT son 8 bytes y no lleva nombres | `core/it_builder.py:330-334` | datos desplazados |
| IT-06 | Canal sin bit 7 en la máscara de pattern | `core/it_builder.py:320` | patrón inválido |
| IT-07 | El CLI no asigna samples del SF2 | `midi2it.py:79`, `it_builder.py:143-155` | `Total PCM: 0.0KB` |
| IT-08 | Canales fuera de rango en el template | `templates/bgm.it` | `smconv`: canales 9/10/21/35/41/64 |
| IT-09 | `max_total_pcm_kb=96` no es un presupuesto SNES; el límite es BRR | `midi2it.py:34`, `it_builder.py:119` | 58 KB BRR, no 96 KB PCM |

### P1 — fidelidad musical

| ID | Limitación | Impacto |
|---|---|---|
| MU-01 | `row = int(beat)` y `row < 64` | Cuantiza a negras, colapsa notas del mismo beat y corta la canción a 64 beats |
| MU-02 | Un solo pattern | No hay canción de 1:30–2:00; no hay orden/loop |
| MU-03 | Sin note-off/duración | Los samples sostenidos se pisan; no hay staccato |
| MU-04 | Sin velocity por nota | Todo suena al volumen de la pista |
| MU-05 | Sin CC7/CC10/CC11, sin pitch bend | Sin dinámica ni pan; sin expresividad |
| MU-06 | Solo el primer `set_tempo` global | Ignora cambios de tempo |
| MU-07 | Sin compás/time signature | No cuantiza compases correctamente |
| MU-08 | MIDI tipo 0: una pista con varios canales se colapsa | Pierde instrumentos |
| MU-09 | Sin drums (canal 10 / banco 128) | Los kits se mapean como programas melódicos |
| MU-10 | `extract_instrument_programs` ignora el banco | Colisión entre programas y kits |
| MU-11 | Sin selección de sample por rango de teclas/velocity | Un SF2 multizona suena con un solo sample |

### P2 — calidad y mantenimiento

| ID | Deuda |
|---|---|
| MT-01 | `scripts/generate_bgm.py` produce un IT inválido; el template no se puede regenerar |
| MT-02 | `templates/bgm.it` es una dependencia binaria frágil; el writer nuevo la reemplaza |
| MT-03 | `examples/test_output.it` (3,3 MB) y `test_output_rockman.it` son artefactos |
| MT-04 | `examples/soundfonts/*.sf2` no están versionados; CI no prueba el camino real |
| MT-05 | `graphify-out/`, `.pytest_cache/`, `__init__.py` raíz: ruido |
| MT-06 | GUI y CLI no comparten el mismo `track_config`; el CLI no mapea samples |
| MT-07 | Sin `--check` de presupuesto (BRR, canales, loop alignment) |
| MT-08 | Sin export de SFX ni de echo |

---

## 5. Diseño propuesto

### 5.1 `core/it_writer.py` (nuevo)

Responsabilidad única: recibir un modelo de canción y escribir un `.it` válido.

```python
@dataclass
class Sample:
    name: str
    pcm: bytes          # s16le mono
    rate: int           # C5 speed
    loop_start: int = 0 # frames
    loop_end: int = 0   # frames, exclusivo
    loop: bool = False
    volume: int = 64
    pan: int = 32

@dataclass
class Instrument:
    name: str
    sample_index: int   # 1-based
    fadeout: int = 64

@dataclass
class Note:
    row: int            # fila absoluta en la canción
    pitch: int          # 0-119
    instrument: int     # 1-based
    volume: int = 64    # 0-64
    pan: int | None = None

@dataclass
class Song:
    name: str
    speed: int          # ticks por fila
    tempo: int          # BPM
    channels: int       # ≤8
    patterns: list[list[Note]]  # 64 filas cada uno
    orders: list[int]
    samples: list[Sample]
    instruments: list[Instrument]
    message: str = ""   # [[SNESMOD]] ...
```

Implementación en dos pasadas:

1. Calcular posiciones: header + órdenes + tablas; patterns; instrumentos;
   samples; PCM. Guardar cada offset.
2. Escribir el archivo y parchear contadores/tablas/pointers.

Validaciones internas (fallar antes de escribir):

- `len(patterns) ≤ 64`, `len(orders) ≤ 200`, `channels ≤ 8`.
- Cada `instrument.sample_index` existe.
- Cada `sample.loop_start/end` está alineado a 16 frames y dentro del PCM.
- `brr_size(samples) + echo_kb*1024 + driver_kb ≤ 58*1024`.
- Cada nota tiene `0 ≤ row < 64*len(patterns)`.
- Ningún canal ≥8.

### 5.2 Parser MIDI v3

- Parsear por **canal**, no por track. Un MIDI tipo 0 con 8 canales debe
  producir 8 pistas.
- Soportar tipo 0/1/2; usar `mido.merge_tracks` solo para el tempo map.
- Tempo map: lista `(tick, bpm)`, no un solo tempo.
- Time signature: `(tick, numerador, denominador)`.
- CC7 (volumen), CC10 (pan), CC11 (expresión), CC64 (sustain), pitch bend.
- Program change + bank select (CC0/CC32) para drums (banco 128).
- Notas con `start_tick`, `duration_tick`, `velocity`, `channel`, `program`.
- Resolución: `ticks_per_beat` del MIDI; convertir a filas con
  `rows_per_beat` configurable (4 = 1/16, 8 = 1/32).

### 5.3 Mapeo SF2

- Parsear `phdr`/`pbag`/`pgen`/`inst`/`ibag`/`igen`/`shdr` (ya existe, pero
  ordenar y testear).
- Soportar bank 0 (melódico) y bank 128 (drums).
- Para cada preset, elegir sample por rango de teclas y velocity; si hay varias
  zonas, elegir la que cubre la nota (no siempre la primera).
- Respetar `loop_start/end`, `sample_rate`, `original_key`.
- Resamplear a 16–22 kHz si el sample original es más grande; conservar loop.
- Fallback: si un programa no existe, usar el sample más cercano y avisar en el
  log (no silencio).

### 5.4 Cuantización y patrones

- `ticks_per_row = ticks_per_beat // rows_per_beat`.
- `row_global = round(start_tick / ticks_per_row)`.
- `pattern = row_global // 64`, `row = row_global % 64`.
- Cada nota con `duration_tick`:
  - Si dura menos de una fila, usar `note cut` en la misma fila o al final.
  - Si dura más, emitir `note off` (255) en la fila de fin, salvo que el
    instrumento tenga loop/sustain.
- Varias notas del mismo canal en la misma fila: es imposible en tracker;
  priorizar la más fuerte o dividir en dos canales si hay libres.
- Construir `orders` con los patterns usados, en orden, y `255` al final.
- Loop: repetir el orden desde el pattern inicial; documentar el punto.

### 5.5 Presupuesto SNES

- `brr_bytes = ceil(frames / 16) * 9`.
- Presupuesto: samples ≤48 KB BRR, echo ≤10 KB (EDL 5), driver ~4–6 KB.
- Si se pasa: bajar rate, acortar loops, reducir instrumentos o bajar EDL.
- `midi2it` debe imprimir el presupuesto antes de exportar y abortar si no cabe.
- `--max-pcm-kb` debe cambiar a `--max-brr-kb` (default 48) y calcular BRR, no
  PCM.

### 5.6 Echo y SFX

- `Song.message` con:
  ```
  [[SNESMOD]]
  EDL 5
  EFB 48
  EVOL 28
  EFIR 127 0 0 0 0 0 0 0
  EON 1 2 3 4 5 6
  ```
- `--echo edl=5,efb=48,evol=28,eon=1-6` en CLI/GUI.
- `--sfx` exporta un segundo `.it` con samples cortos y canal 7; ese archivo
  debe ir **primero** en `AUDIOFILES` de vs-snes.

---

## 6. Qué eliminar

| Elemento | Acción | Motivo |
|---|---|---|
| `scripts/generate_bgm.py` | Borrar o mover a `docs/experimental/` | Produce un IT inválido; confunde |
| `examples/test_output.it` (3,3 MB) | Borrar | Artefacto generado |
| `examples/test_output_rockman.it` | Borrar | Artefacto generado |
| `templates/bgm.it` | Mantener como fixture hasta que el writer pase los tests; después borrar la dependencia | Hoy es el corazón del problema |
| `graphify-out/` | Borrar y `.gitignore` | Generado |
| `.pytest_cache/` | `.gitignore` | Generado |
| `__init__.py` raíz | Revisar; probablemente sobra | Ruido |
| `skills-lock.json` / `.agents` / `.claude` | Decidir si se publican | Tooling interno |
| `max_total_pcm_kb=96` | Reemplazar por BRR | Presupuesto incorrecto |

No borrar `templates/bgm.it` hasta que el writer nuevo tenga tests verdes y
`smconv` acepte la salida. Sirve como referencia de header válido.

---

## 7. Pipeline objetivo

```
MIDI ──┐
       ├─ parse (canales, tempo map, CC, bank)
SF2  ──┘
       ↓
  normalizar (resample, loops, presupuesto)
       ↓
  mapear programa/banco → sample
       ↓
  cuantizar ticks → filas/patterns
       ↓
  it_writer (2 pasadas) → cancion.it
       ↓
  validar: openmpt123 --info + parser propio + smconv
       ↓
  soundbank.bnk + soundbank.h → VS-SNES
```

Ruta alternativa para emulador/FXPAK:

```
MIDI + SF2 → fluidsynth → bgm.wav (44.1 kHz) → bgm.pcm (MSU-1) → ROM MSU-1
```

Esta ruta no pasa por IT ni por SPC; es la forma más directa de "MIDI a audio".
Se puede ofrecer como `midi2it --render-msu1` sin tocar el writer.

---

## 8. Tests y CI

### 8.1 Tests unitarios

- `test_header_offsets`: escribir un IT mínimo y verificar que `ordnum`,
  `insnum`, `smpnum`, `patnum`, las tablas y los `IMPS`/`IMPI` apuntan a
  posiciones válidas.
- `test_sample_header`: los 80 bytes, `IMPS` en 0, flags, C5 en 0x3C, pointer
  en 0x48.
- `test_instrument_header`: 554 bytes, `IMPI` en 0, mapa en 0x40.
- `test_pattern_packing`: máscara con bit 7, campos en orden, terminador 0.
- `test_quantize`: un MIDI de 2 compases genera las filas esperadas.
- `test_multi_pattern`: una canción de 3 minutos genera >1 pattern y órdenes
  correctas.
- `test_note_off`: duración corta emite note cut/off.
- `test_budget`: un sample de 10 s falla el presupuesto; uno de 0.2 s pasa.
- `test_cli_maps_samples`: el CLI produce PCM >0 (hoy falla).

### 8.2 Tests de integración

- `openmpt123 --info`: duración, instrumentos, samples esperados.
- Parser propio: leer el IT generado y comparar notas contra el MIDI
  (pitch, fila, canal).
- `smconv`: exit code 0, **sin** "More than 8 channels", `Instrument data >0`,
  `Total ≤58 KB`.
- Render: `openmpt123 cancion.it --render /tmp/out`, luego `ffmpeg -af astats`
  para verificar que no es silencio y que dura lo esperado.
- Golden: hash del PCM de samples y del pattern 0 para detectar regresiones.

### 8.3 CI

- Agregar un SF2 de fixture pequeño y versionado (`tests/fixtures/tiny.sf2`,
  <100 KB) o generarlo en el test; no depender de los `.sf2` gitignored.
- Descargar PVSNESlib release y usar `smconv` en CI.
- Correr `pytest`, `openmpt123`, `smconv` y el render; fallar si algo no cumple.
- No usar `|| true` en el lint.

---

## 9. Roadmap

| Fase | Trabajo | Estimación | Entregable |
|---|---|---:|---|
| M0 | `it_writer.py` + tests de offsets/patterns | 2–3 días | IT mínimo válido en `openmpt123` |
| M1 | Parser MIDI v3 + cuantización + multi-pattern | 3–4 días | Canción completa con notas correctas |
| M2 | SF2 mapping (bank/zonas/loops) + presupuesto BRR | 2–3 días | Samples correctos y ≤48 KB |
| M3 | CLI/GUI parity + echo + SFX | 2 días | `cancion.it` + `sfx.it` listos para vs-snes |
| M4 | Integración vs-snes + CI + docs | 1–2 días | `make` de vs-snes con música generada |
| M5 | Ruta MSU-1 (`--render-msu1`) | 1–2 días | WAV/PCM para emulador/FXPAK |

Total: ~11–16 días de trabajo efectivo.

---

## 10. Integración con VS-SNES

### 10.1 Contrato de CLI

```bash
midi2it cancion.mid fuente.sf2 \
  -o mvp/res/bgm.it \
  --snes \
  --channels 7 \
  --rows-per-beat 4 \
  --max-brr-kb 48 \
  --echo edl=5,efb=48,evol=28,eon=1-6
```

Opcional:

```bash
midi2it cancion.mid fuente.sf2 --sfx sfx.it --sfx-bank 0
midi2it cancion.mid fuente.sf2 --render-msu1 bgm.wav
```

### 10.2 Makefile de VS-SNES

```make
AUDIOFILES := res/sfx.it res/bgm.it   # sfx PRIMERO
SMCONVFLAGS := -s -o $(SOUNDBANK) -V -b 5 -f
```

- `soundbank.h` debe exportar `MOD_SFX` y `MOD_BGM`.
- `spcLoad(MOD_SFX); spcLoadEffect(i); spcLoad(MOD_BGM); spcPlay(0);`
- `spcProcess()` en cada frame.
- Canal 7 reservado para SFX.

### 10.3 Criterios de aceptación

- `smconv` acepta `bgm.it` y `sfx.it` sin errores de canal.
- `Total ≤58 KB`, `Instrument data >0`, `Samples` con datos reales.
- La ROM de VS-SNES compila y la música suena en Mesen2/mednafen.
- El loop no tiene clic y el volumen se puede fade/duck.
- Un CI de vs-snes regenera la música y falla si `smconv` se queja.

---

## 11. Alternativas y decisiones

### 11.1 MSU-1 directo

Si el objetivo es solo emulador/FXPAK, `fluidsynth` renderiza MIDI+SF2 a WAV y
MSU-1 lo reproduce a 44.1 kHz estéreo. No hay que pelear con 8 canales ni con
BRR. Es la ruta más rápida para "audio directo"; la desventaja es que no corre
en cartucho real y los `.pcm` pesan MB.

### 11.2 OpenMPT manual

OpenMPT puede importar MIDI y usar un SF2 como MIDI Library, y exportar `.it`.
Es una buena validación de referencia, pero no es automatizable ni tiene
presupuesto SNES. Sirve para comparar el `.it` de `midi2it` contra uno hecho a
mano.

### 11.3 FamiStudio / SuperFamistudio

FamiStudio (NES) importa MIDI, pero no es SNES. No usar para este pipeline.
SuperFamistudio es un tracker SNES distinto; si se evalúa, verificar primero si
importa MIDI y si exporta un `.it` compatible con `smconv`; no asumirlo.

### 11.4 Decisión de arquitectura

- **Writer propio** en Python, sin dependencias binarias, testeable.
- **No** seguir parcheando `templates/bgm.it`.
- **No** usar `smconv` como validador único; validar el IT antes.
- **Sí** ofrecer la ruta MSU-1 como extra, no como reemplazo del SPC.

---

## 12. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El writer nuevo no reproduce el "sonido" del template | Pérdida de calidad percibida | Comparar A/B con openmpt123 y ajustar instrumentos/volúmenes |
| SF2 con muchas zonas/velocity layers | Mapeo incompleto | Empezar con 1 sample por programa; agregar zonas después |
| Presupuesto BRR | Samples no caben | Limitar loops, resamplear, reducir instrumentos |
| smconv tolerante | Errores silenciosos | Validar canales/instrument data/Total en tests |
| Canciones de 2 min | Muchos patterns/órdenes | 64 filas × N patterns; probar 64 patterns |
| MIDI tipo 0 | Canales colapsados | Parsear por canal, no por track |
| Drums | Sin percusión | Banco 128 + canal 10; mapeo dedicado |
| Loop | Clic audible | Alinear a 16 frames; validar con render |

---

## 13. Referencias

- ITTECH / formato IT: <https://github.com/JETSAMIC/SwiftIT/blob/main/Reference/IT-Format.md>
- OpenMPT: <https://openmpt.org/>
- SNESMOD: <https://github.com/mukunda-/snesmod>
- `smconv` (PVSNESlib): <https://github.com/alekmaul/pvsneslib/tree/master/tools/smconv>
- PVSNESlib — Sounds and Musics: <https://github.com/alekmaul/pvsneslib/wiki/Sounds-and-Musics>
- MSU-1 specs: <https://helmet.kafuka.org/msu1.htm>
- VS-SNES: <https://github.com/fenrircl/vs-snes>
