# Graph Report - midi2it  (2026-11-23)

## Corpus Check
- Corpus is ~17,881 words - fits in a single context window. You may not need a graph.

## Summary
- 328 nodes · 565 edges · 15 communities (12 shown, 3 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- IT Building & SoundFont Parsing
- Dependency Installation
- IT Conversion Pipeline
- WAV Rendering & Dialogs
- Track Panel & Instrument Catalog
- Piano Roll Rendering
- Main Application Controller
- MIDI Parsing & Note Editing
- Dependency Install Dialog
- Preview & Playback Panel
- SoundFont Browser
- Testing Patterns Skills
- Core Package Init
- GUI Package Init
- Package Root

## God Nodes (most connected - your core abstractions)
1. `TrackPanel` - 25 edges
2. `MIDI2ITApp` - 24 edges
3. `PianoRoll` - 22 edges
4. `PreviewPanel` - 21 edges
5. `build()` - 20 edges
6. `SF2Browser` - 20 edges
7. `DepsDialog` - 17 edges
8. `parse()` - 13 edges
9. `portable_install()` - 11 edges
10. `TrackChannel` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Sandboxed Python execution with 100+ pre-installed libraries` --semantically_similar_to--> `Portable dependency manager (~/.midi2it/tools, no PATH/system install, no restart)`  [INFERRED] [semantically similar]
  .agents/skills/python-executor/SKILL.md → README.md
- `Impulse Tracker (.it) module format` --conceptually_related_to--> `build()`  [INFERRED]
  README.md → core/it_builder.py
- `smconv / PVSNESlib soundbank toolchain` --conceptually_related_to--> `convert_to_soundbank()`  [INFERRED]
  README.md → core/smconv_runner.py
- `MIDI2ITApp` --conceptually_related_to--> `GUI mini-DAW concept (piano roll, per-track instrument/volume/transpose/solo/mute, FluidSynth preview)`  [INFERRED]
  midi2it_gui.py → README.md
- `Portable dependency manager (~/.midi2it/tools, no PATH/system install, no restart)` --references--> `_check_deps_on_start()`  [INFERRED]
  README.md → midi2it_gui.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **MIDI+SF2 → IT conversion flow** — midi2it_main, core_midi_parser_parse, core_sf2_parser_parse, core_it_builder_build, readme_conversion_pipeline [EXTRACTED 1.00]
- **GUI mini-DAW widget composition** — midi2it_gui_midi2itapp, gui_piano_roll_pianoroll, gui_track_panel_trackpanel, gui_preview_previewpanel, gui_sf2_browser_sf2browser [EXTRACTED 1.00]
- **Windows release packaging and antivirus false-positive mitigation** — github_workflows_release_workflow, readme_pyinstaller_packaging, readme_antivirus_false_positive [INFERRED 0.95]
- **MIDI+SF2 → IT → soundbank export pipeline** — core_midi_parser_parse, core_sf2_parser_parse, core_it_builder_build, core_smconv_runner_convert_to_soundbank, tests_test_e2e_test_it_builder [EXTRACTED 1.00]
- **FluidSynth/ffplay audio preview stack** — core_wav_renderer_render_full_mix, core_wav_renderer_render_single_track, core_wav_renderer_play_wav, gui_preview_previewpanel, core_deps_check [INFERRED 0.85]
- **Dependency detection and portable install flow** — core_deps_check, core_deps_install_plan, core_deps_portable_install, gui_deps_dialog_depsdialog, core_smconv_runner_find_smconv [INFERRED 0.85]

## Communities (15 total, 3 thin omitted)

### Community 0 - "IT Building & SoundFont Parsing"
Cohesion: 0.07
Nodes (35): argparse, Claude Code local permission allowlist, _bundle_template(), find_template(), _make_instrument_header(), core/it_builder.py — Construye archivos .it compatibles con smconv de…, Genera un IT instrument header (482 bytes) que referencia 1 sample., extract_instrument_programs() (+27 more)

### Community 1 - "Dependency Installation"
Cohesion: 0.08
Nodes (38): check(), _download(), _exe(), executable(), _extract(), _find_exe(), has_portable(), install_plan() (+30 more)

### Community 2 - "IT Conversion Pipeline"
Cohesion: 0.08
Nodes (37): build(), _filter_tracks(), _make_sample_header(), Genera el archivo .it. Args: midi_data: dict del midi_parser (tracks, tempo,…, Aplica mute/solo y limita a 8 pistas (limite SPC700)., Genera un sample header IT (80 bytes). Args: sidx: indice del sample (0-99)…, parse(), Extrae hasta `max_samples` samples utilizables del SF2. Returns: dict[int,… (+29 more)

### Community 3 - "WAV Rendering & Dialogs"
Cohesion: 0.10
Nodes (24): core, play_wav(), core/wav_renderer.py — Renderiza MIDI a WAV usando FluidSynth. Soporta render…, Reproduce un WAV con ffplay. Devuelve el proceso. Args: wav_path: ruta al WAV…, Renderiza UNA pista del MIDI a WAV (mutea el resto). Args: midi_path: ruta al…, Renderiza el MIDI completo a WAV con todos los canales mezclados. Returns: ruta…, render_full_mix(), render_single_track() (+16 more)

### Community 4 - "Track Panel & Instrument Catalog"
Cohesion: 0.11
Nodes (9): Auto-genera pistas segun el MIDI y los instrumentos disponibles en el SF2., Agrega una pista vacia para que el usuario la configure., Retorna configuracion actual de pistas para it_builder.build()., Panel lateral con lista de pistas y controles., Control individual para una pista MIDI., Actualiza las opciones del combobox., Registra un instrumento en el catalogo global. Devuelve item_id., TrackChannel (+1 more)

### Community 5 - "Piano Roll Rendering"
Cohesion: 0.11
Nodes (14): PianoRoll._draw_grid, PianoRoll, Dibuja las notas MIDI como rectángulos., Carga datos MIDI para visualización., Maneja click para seleccionar/agregar notas., Maneja arrastre para mover notas., Canvas-based piano roll para edición de notas MIDI., Zoom con scroll del mouse. (+6 more)

### Community 6 - "Main Application Controller"
Cohesion: 0.10
Nodes (8): MIDI2ITApp, worker(), Wrapper para que el preview pueda pedir un SF2., Callback cuando el browser carga un SF2., Reconstruye las pistas del track panel. Usa el primer SF2 si hay., Asigna el instrumento del browser a la primera pista seleccionada., Preview mezclado: render MIDI completo a WAV y reproduce., Preview de una pista individual (boton ▶ por canal).

### Community 7 - "MIDI Parsing & Note Editing"
Cohesion: 0.11
Nodes (21): add_note(), _extract_notes(), move_note(), parse(), core/midi_parser.py — Parsea archivos MIDI extrayendo pistas, notas, programas…, Analiza un archivo MIDI y devuelve estructura con pistas y notas., Resumen de una pista: rango de notas, cantidad, programa., Añade una nota a la pista. La inserta en orden y agrega eventos… (+13 more)

### Community 8 - "Dependency Install Dialog"
Cohesion: 0.19
Nodes (8): classify_result(), Clasifica el resultado de una instalación. Returns: 'ok' | 'already' | 'fail' -…, Ejecuta un comando de instalación, transmitiendo salida línea a línea. Returns:…, run_install(), DepsDialog, worker(), Avisa que hace falta reiniciar para detectar la herramienta (PATH/pip)., Ventana modal para revisar e instalar dependencias.

### Community 9 - "Preview & Playback Panel"
Cohesion: 0.12
Nodes (6): PreviewPanel, Preview de UNA pista (usa el callback de la app para extraerla)., Panel inferior con controles de reproduccion, export y WAV., Mata todos los procesos activos y limpia temporales., Registra un subprocess para poder matarlo en stop., Quita un proceso de la lista (cuando termina naturalmente).

### Community 10 - "SoundFont Browser"
Cohesion: 0.21
Nodes (5): Panel derecho con lista de SF2 cargados e instrumentos disponibles., Retorna el SF2 actualmente seleccionado., Retorna (sf2_path, sample_index, program, name) del instrumento seleccionado., Carga un SF2 y actualiza las listas., SF2Browser

### Community 11 - "Testing Patterns Skills"
Cohesion: 0.25
Nodes (11): Python Code Executor skill (infsh/python-executor via belt CLI), Testing patterns advanced reference (Patterns 6-10, DB, CI/CD), Testing patterns detailed reference (Patterns 1-5), Python Testing Patterns skill, AAA test structure (Arrange-Act-Assert), Test isolation (independent tests, no shared state), Sandboxed Python execution with 100+ pre-installed libraries, pytest fixtures for setup/teardown and shared state (+3 more)

## Ambiguous Edges - Review These
- `SNES/SPC700 hardware constraints (8 channels, 16-bit PCM, ~64KB sample RAM, 64-row patterns)` → `GUI mini-DAW concept (piano roll, per-track instrument/volume/transpose/solo/mute, FluidSynth preview)`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **4 isolated node(s):** `AAA test structure (Arrange-Act-Assert)`, `Mocking with unittest.mock (patch, side_effect)`, `PianoRoll._draw_grid`, `Claude Code local permission allowlist`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 135 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `SNES/SPC700 hardware constraints (8 channels, 16-bit PCM, ~64KB sample RAM, 64-row patterns)` and `GUI mini-DAW concept (piano roll, per-track instrument/volume/transpose/solo/mute, FluidSynth preview)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `TrackPanel` connect `Track Panel & Instrument Catalog` to `IT Conversion Pipeline`, `WAV Rendering & Dialogs`, `Piano Roll Rendering`, `Main Application Controller`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Why does `MIDI2ITApp` connect `Main Application Controller` to `IT Building & SoundFont Parsing`, `IT Conversion Pipeline`, `WAV Rendering & Dialogs`, `Track Panel & Instrument Catalog`, `Piano Roll Rendering`, `Preview & Playback Panel`, `SoundFont Browser`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Why does `PianoRoll` connect `Piano Roll Rendering` to `WAV Rendering & Dialogs`, `Track Panel & Instrument Catalog`, `Main Application Controller`, `MIDI Parsing & Note Editing`?**
  _High betweenness centrality (0.149) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `TrackPanel` (e.g. with `build()` and `PianoRoll`) actually correct?**
  _`TrackPanel` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `MIDI2ITApp` (e.g. with `PianoRoll` and `PreviewPanel`) actually correct?**
  _`MIDI2ITApp` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `PianoRoll` (e.g. with `TrackPanel` and `MIDI2ITApp`) actually correct?**
  _`PianoRoll` has 2 INFERRED edges - model-reasoned connections that need verification._