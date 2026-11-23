"""
midi2it_gui.py — Ventana principal. Mini DAW:
- Cargar MIDI (multi-canal)
- Cargar VARIOS SF2 desde el sidebar
- Asignar instrumentos a pistas (mezclando de cualquier SF2)
- Editar volumen/transpose/solo/mute por pista
- Preview mezclado + preview por pista
- Exportar IT (.bnk) y WAV
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, sys, subprocess, threading, queue

BG = '#0b1020'
PANEL = '#111827'
SURFACE = '#182235'
ACCENT = '#8b5cf6'
TEXT = '#f8fafc'
MUTED = '#94a3b8'

sys.path.insert(0, os.path.dirname(__file__))

from core import midi_parser, sf2_parser, it_builder, smconv_runner, wav_renderer
from gui.piano_roll import PianoRoll
from gui.track_panel import TrackPanel
from gui.preview import PreviewPanel
from gui.sf2_browser import SF2Browser


class MIDI2ITApp(tk.Tk):
    """Ventana principal."""

    def __init__(self):
        super().__init__()
        self.title("midi2it")
        self.geometry("1480x860")
        self.minsize(1180, 720)
        self.configure(bg=BG)

        # Estado global
        self.midi_data = None
        self.midi_path = None
        self.sf2_samples = {}      # sf2_path -> dict de samples
        self.current_it_path = None
        self._ui_queue = queue.Queue()
        self._deps_window = None
        self._playback_request = None
        self._play_generation = 0
        self._preview_refresh_after = None
        self._preview_wav_path = None
        self.max_sample_sec = 3.0
        self.max_brr_kb = 48.0

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=TEXT, font=('Segoe UI', 9))
        style.configure('TButton', font=('Segoe UI', 9), padding=(11, 7),
                        background='#202b3d', foreground=TEXT, borderwidth=0, focusthickness=0)
        style.map('TButton', background=[('active', '#334155'), ('disabled', '#1b2638')],
                  foreground=[('disabled', '#64748b')])
        style.configure('Accent.TButton', background=ACCENT, foreground='white',
                        font=('Segoe UI', 9, 'bold'))
        style.map('Accent.TButton', background=[('active', '#7c3aed')])
        style.configure('Quiet.TButton', background='#202b3d', foreground='#cbd5e1')
        style.configure('Danger.TButton', background='#3b2631', foreground='#fda4af')
        style.configure('TEntry', fieldbackground='#0f1726', foreground=TEXT,
                        insertcolor=TEXT, bordercolor='#334155', padding=6)
        style.configure('TCombobox', fieldbackground='#0f1726', foreground=TEXT,
                        background='#202b3d', arrowcolor='#cbd5e1', padding=5)
        style.configure('TCheckbutton', background='#182235', foreground='#cbd5e1')
        style.map('TCheckbutton', background=[('active', '#182235')])
        style.configure('TScrollbar', background='#202b3d', troughcolor='#0f1726',
                        bordercolor='#0f1726', arrowsize=12)
        style.configure('Horizontal.TScale', background='#182235', troughcolor='#334155')
        style.configure('TSpinbox', fieldbackground='#0f1726', foreground=TEXT,
                        background='#202b3d', arrowcolor='#cbd5e1', padding=4)

        # Layout 3 columnas: TrackPanel (izq) | Center (piano+preview) | SF2Browser (der)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _build_layout(self):
        self._build_menu()
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(shell, bg=PANEL, height=76)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        brand = tk.Frame(header, bg=PANEL)
        brand.pack(side=tk.LEFT, padx=20)
        tk.Label(brand, text='MIDI2IT', fg=TEXT, bg=PANEL,
                 font=('Segoe UI', 17, 'bold')).pack(anchor='w', pady=(12, 0))
        tk.Label(brand, text='Convierte, escucha y prepara música para SNES',
                 fg=MUTED, bg=PANEL, font=('Segoe UI', 9)).pack(anchor='w')

        actions = tk.Frame(header, bg=PANEL)
        actions.pack(side=tk.RIGHT, padx=18)
        ttk.Button(actions, text='1  Abrir MIDI', style='Accent.TButton',
                   command=self._load_midi).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text='2  Cargar SF2',
                   command=self._load_sf2_via_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text='Herramientas',
                   command=self._open_dependencies).pack(side=tk.LEFT, padx=4)

        workflow = tk.Frame(shell, bg='#101a2b', height=34)
        workflow.pack(fill=tk.X)
        workflow.pack_propagate(False)
        self.workflow_label = tk.Label(
            workflow, text='Flujo: abre un MIDI, carga un SoundFont y pulsa Reproducir',
            fg='#cbd5e1', bg='#101a2b', font=('Segoe UI', 9))
        self.workflow_label.pack(side=tk.LEFT, padx=20, pady=7)
        self.dependencies_status = tk.Label(workflow, text='Audio: comprobando…',
                                            fg=MUTED, bg='#101a2b', font=('Segoe UI', 8))
        self.dependencies_status.pack(side=tk.RIGHT, padx=18)

        content = tk.Frame(shell, bg=BG)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.track_panel = TrackPanel(
            content, on_update=self._on_update, on_play_track=self._play_track,
            on_remove_track=self._remove_track, on_tempo_change=self._on_update,
            width=270)
        self.track_panel.pack_propagate(False)
        self.track_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.sf2_browser = SF2Browser(
            content, on_instrument_pick=self._on_instrument_pick,
            on_sf2_load=self._on_sf2_load, on_sf2_remove=self._on_sf2_remove,
            width=290)
        self.sf2_browser.pack_propagate(False)
        self.sf2_browser.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        center = tk.Frame(content, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview = PreviewPanel(
            center, on_export=self._do_export_it, on_play_mix=self._play_mix,
            on_play_track=self._play_single_track, on_export_wav=self._do_export_wav,
            on_stop=self._stop_preview, on_estimate_brr=self._estimate_it_brr,
            on_optimize_brr=self._optimize_it_brr)
        self.preview.pack(side=tk.BOTTOM, fill=tk.X)

        editor = tk.Frame(center, bg=PANEL, highlightthickness=1,
                          highlightbackground='#263449')
        editor.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 8))
        toolbar = tk.Frame(editor, bg=SURFACE, height=46)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(toolbar, text='Piano roll', fg=TEXT, bg=SURFACE,
                 font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=(14, 8))
        self.info_label = tk.Label(toolbar, text='Sin MIDI cargado', fg=MUTED,
                                   bg=SURFACE, font=('Segoe UI', 9))
        self.info_label.pack(side=tk.LEFT, padx=8)
        ttk.Button(toolbar, text='−', width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 0.8)
                   ).pack(side=tk.RIGHT, padx=(2, 10))
        ttk.Button(toolbar, text='+', width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 1.25)
                   ).pack(side=tk.RIGHT, padx=2)
        roll_area = tk.Frame(editor, bg=BG)
        roll_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.piano_roll = PianoRoll(roll_area)
        vertical = ttk.Scrollbar(roll_area, orient=tk.VERTICAL, command=self.piano_roll.yview)
        horizontal = ttk.Scrollbar(roll_area, orient=tk.HORIZONTAL, command=self.piano_roll.xview)
        self.piano_roll.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.piano_roll.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        roll_area.rowconfigure(0, weight=1)
        roll_area.columnconfigure(0, weight=1)

        self._refresh_dependency_status()
        self._refresh_dependency_status()
        self.after(50, self._drain_ui_queue)
        self.after(500, self._check_deps_on_start)

    def _build_menu(self):
        menu = tk.Menu(self, tearoff=False)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label='Abrir MIDI…', command=self._load_midi)
        file_menu.add_command(label='Cargar SoundFont…', command=self._load_sf2_via_dialog)
        file_menu.add_separator()
        # El menú se crea antes que PreviewPanel durante el layout; resolver
        # el callback al hacer clic evita acceder a self.preview demasiado pronto.
        file_menu.add_command(label='Exportar IT…', command=lambda: self.preview._export_it())
        file_menu.add_command(label='Exportar WAV…', command=lambda: self.preview._export_wav())
        file_menu.add_separator()
        file_menu.add_command(label='Salir', command=self._quit)
        menu.add_cascade(label='Archivo', menu=file_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(label='Dependencias y herramientas…', command=self._open_dependencies)
        menu.add_cascade(label='Herramientas', menu=tools_menu)
        self.config(menu=menu)

    def _drain_ui_queue(self):
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                callback(*args)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._drain_ui_queue)

    def _open_dependencies(self):
        if self._deps_window is not None and self._deps_window.winfo_exists():
            self._deps_window.lift()
            self._deps_window.focus_force()
            return
        from gui.deps_dialog import DepsDialog
        self._deps_window = DepsDialog(self)

    def _refresh_dependency_status(self):
        from core import deps
        missing = [tool for tool in ('fluidsynth', 'ffplay') if not deps.executable(tool)]
        if missing:
            self.dependencies_status.config(text='Audio: instala FluidSynth + FFmpeg', fg='#fbbf24')
        else:
            self.dependencies_status.config(text='Audio listo', fg='#4ade80')
        ready = bool(self.midi_path and self.sf2_samples)
        self.preview.play_btn.config(state=tk.NORMAL if ready else tk.DISABLED)
        if self.midi_path and self.sf2_samples:
            if missing:
                self.workflow_label.config(
                    text='MIDI + SoundFont cargados · abre Herramientas para instalar el audio')
            else:
                self.workflow_label.config(text='Listo para escuchar')
        elif self.midi_path:
            self.workflow_label.config(text='Paso 2: carga un SoundFont para escuchar el MIDI')
        elif self.sf2_samples:
            self.workflow_label.config(text='Paso 1: abre un MIDI para escuchar con este SoundFont')
        else:
            self.workflow_label.config(text='Flujo: abre un MIDI, carga un SoundFont y pulsa Reproducir')

    # ─── Acciones: cargar MIDI/SF2 ───

    def _load_midi(self):
        path = filedialog.askopenfilename(
            title="Cargar archivo MIDI",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        if not path:
            return
        self._stop_preview()
        try:
            self.midi_data = midi_parser.parse(path)
            self.midi_path = path
            self.piano_roll.load_midi(self.midi_data)
            # Generar pistas en track_panel (sin SF2 por ahora)
            self._reload_tracks()

            name = os.path.basename(path)
            num_tracks = len(self.midi_data['tracks'])
            tempo = self.midi_data['tempo']
            self.info_label.config(
                text=f"🎵 {name} — {num_tracks} pistas, {tempo:.0f} BPM, "
                     f"{self.midi_data['duration_seconds']:.1f}s"
            )
            self.preview.set_status(f"MIDI cargado: {name}")
            self.title(f"midi2it — {name}")
            self._refresh_dependency_status()
        except Exception as e:
            messagebox.showerror("Error al cargar MIDI", str(e))

    def _load_sf2_via_dialog(self):
        """Wrapper para que el preview pueda pedir un SF2."""
        # Delegar al browser directamente
        self.sf2_browser._load_sf2()

    def _on_sf2_load(self, sf2_path, sf2_name, samples, programs, program_list):
        """Callback cuando el browser carga un SF2."""
        self.sf2_samples[sf2_path] = samples
        # Refrescar tracks para incluir los instrumentos del nuevo SF2
        self._reload_tracks()
        self.preview.set_status(f"SoundFont cargado: {sf2_name}")
        self._refresh_dependency_status()

    def _on_sf2_remove(self, sf2_path):
        self.sf2_samples.pop(sf2_path, None)
        self._reload_tracks()
        self._refresh_dependency_status()
        self.preview.set_status('SoundFont quitado')

    def _reload_tracks(self):
        """Reconstruye pistas y el catálogo con los programas de todos los SF2."""
        self.track_panel.clear_catalog()
        for sf2_path, info in self.sf2_browser.loaded_sf2s.items():
            sf2_name = info['name']
            for program, label in info.get('program_list', []):
                sample_index = info.get('programs', {}).get(program)
                if sample_index not in info.get('samples', {}):
                    continue
                self.track_panel.register_instrument(
                    sf2_path, sf2_name, sample_index, program, label)
        if self.midi_data:
            self.track_panel.load_tracks(self.midi_data)

    def _on_instrument_pick(self, sf2_path, sample_index, program, label):
        """Asigna el programa del browser a la pista seleccionada."""
        track = self.track_panel.get_selected_track()
        if track is None:
            self.preview.set_status("Selecciona una pista antes de asignar un instrumento")
            return
        # Encontrar el item_id en el catalog del track_panel
        sf2_name = os.path.basename(sf2_path).replace('.sf2', '').replace('.SF2', '')
        # Buscar el sample en el sf2_samples
        if sf2_path not in self.sf2_samples:
            self.sf2_samples[sf2_path] = sf2_parser.parse(sf2_path, max_samples=128)
        samples = self.sf2_samples[sf2_path]
        sample_name = samples.get(sample_index, {}).get('name', f'smp{sample_index}')

        self.track_panel.register_instrument(
            sf2_path, sf2_name, sample_index, program, sample_name
        )
        # Asignar a la pista seleccionada.
        for v in self.track_panel.catalog.values():
            if (v['sample_index'] == sample_index and v['sf2_path'] == sf2_path
                    and v['program'] == program):
                track.instr_var.set(v['label'])
                track._notify()
                break

        self.preview.set_status(f"✅ Asignado: {label}")

    def _on_update(self):
        if self.midi_data:
            if self._playback_request is not None:
                if self._preview_refresh_after is not None:
                    self.after_cancel(self._preview_refresh_after)
                self._preview_refresh_after = self.after(300, self._restart_preview)
            elif self.preview:
                self.preview.set_status("Configuración actualizada")

    def _remove_track(self, idx):
        pass  # ya manejado en track_panel

    # ─── Reproduccion ───

    def _play_mix(self):
        """Render the current GUI track settings and play the mix."""
        if not self.midi_path:
            self.preview.set_status("❌ Sin MIDI")
            return

        sf2_path = self._active_sf2_path()
        if not sf2_path:
            self.preview.set_status("❌ Carga un SF2 primero")
            return
        if not self._ensure_preview_tools():
            return

        self._playback_request = {'kind': 'mix'}
        self._start_preview_render()

    def _play_track(self, track_index):
        """Preview de una pista individual (boton ▶ por canal)."""
        if not self.midi_path:
            self.preview.set_status("❌ Sin MIDI")
            return
        if not self.sf2_samples:
            self.preview.set_status("❌ Carga un SF2 primero")
            return
        sf2_path = self._active_sf2_path()
        if not sf2_path:
            self.preview.set_status("Carga un SoundFont primero")
            return
        if not self._ensure_preview_tools():
            return

        self._playback_request = {'kind': 'track', 'index': track_index}
        self._start_preview_render()

    def _start_preview_render(self):
        request = dict(self._playback_request or {})
        if not request or not self.midi_path:
            return
        if self._preview_refresh_after is not None:
            self.after_cancel(self._preview_refresh_after)
            self._preview_refresh_after = None
        self.preview.stop_audio()
        self._remove_preview_wav()
        self._play_generation += 1
        generation = self._play_generation
        midi_path = self.midi_path
        tempo_bpm = self.track_panel.tempo_var.get()
        track_config = self.track_panel.get_config()['tracks']
        sf2_path = self._active_sf2_path()
        if request['kind'] == 'track':
            index = request['index']
            if index >= len(self.track_panel.track_widgets):
                self._stop_preview()
                return
            midi_track = self.track_panel.track_widgets[index].midi_track
            config = next((item for item in track_config
                           if item.get('midi_track') == midi_track), {})
            sf2_path = config.get('sf2_path') or sf2_path
            label = f'Pista {index + 1}'
            status = f'Reproduciendo pista {index + 1}…'
        else:
            midi_track = None
            label = 'Mezcla'
            status = 'Preparando reproducción…'
        if not sf2_path:
            self.preview.set_status('Carga un SoundFont primero')
            return
        self.preview.set_status(status)

        def worker():
            if midi_track is None:
                wav = wav_renderer.render_configured_mix(
                    midi_path, sf2_path, tempo_bpm=tempo_bpm,
                    track_config=track_config)
            else:
                wav = wav_renderer.render_single_track(
                    midi_path, sf2_path, midi_track, tempo_bpm=tempo_bpm,
                    track_config=track_config)
            self._ui_queue.put((self._play_rendered_wav, (wav, label, generation)))

        threading.Thread(target=worker, daemon=True).start()

    def _restart_preview(self):
        self._preview_refresh_after = None
        if self._playback_request is not None:
            self._start_preview_render()

    def _stop_preview(self):
        if self._preview_refresh_after is not None:
            self.after_cancel(self._preview_refresh_after)
            self._preview_refresh_after = None
        self._play_generation += 1
        self._playback_request = None
        if hasattr(self, 'preview'):
            self.preview.stop_audio()
            self._remove_preview_wav()
            self.preview.set_status('Reproducción detenida')

    def _remove_preview_wav(self):
        path = self._preview_wav_path
        self._preview_wav_path = None
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _active_sf2_path(self):
        selected = self.sf2_browser.get_active_sf2()
        if selected:
            return selected[0]
        return next(iter(self.sf2_samples), None)

    def _ensure_preview_tools(self):
        from core import deps
        missing = [name for name in ('fluidsynth', 'ffplay') if not deps.executable(name)]
        if not missing:
            return True
        message = ('Para escuchar necesitas FluidSynth y FFmpeg (incluye ffplay). '
                   'Puedes descargarlos desde Herramientas → Dependencias.\n\n'
                   '¿Abrir el gestor ahora?')
        if messagebox.askyesno('Falta configurar el audio', message):
            self._open_dependencies()
        return False

    def _play_rendered_wav(self, wav_path, label, generation):
        if generation != self._play_generation:
            if wav_path:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
            return
        if not wav_path:
            self.preview.set_status('No se pudo renderizar. Revisa las dependencias de audio.')
            self._playback_request = None
            return
        try:
            process = wav_renderer.play_wav(wav_path)
        except OSError as exc:
            self.preview.set_status(f'No se pudo iniciar ffplay: {exc}')
            self._playback_request = None
            return
        if not process:
            self.preview.set_status('No se encontró ffplay. Abre Herramientas → Dependencias.')
            self._playback_request = None
            return
        self.preview.register_proc(process)
        self._preview_wav_path = wav_path
        self.preview.set_status(f'Reproduciendo {label.lower()}')
        self._poll_audio_process(process, label, generation, wav_path)

    def _poll_audio_process(self, process, label, generation, wav_path):
        if process.poll() is None:
            self.after(250, self._poll_audio_process, process, label, generation, wav_path)
        else:
            self.preview.cleanup_proc(process)
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            if self._preview_wav_path == wav_path:
                self._preview_wav_path = None
            if generation == self._play_generation:
                self._playback_request = None
                self.preview.set_status(f'Fin: {label.lower()}')

    def _play_single_track(self, midi_path, sf2_path):
        # No usado por ahora (legacy callback)
        pass

    # ─── Export ───

    def _collect_it_export_data(self):
        track_cfg_full = self.track_panel.get_config()
        track_config = track_cfg_full['tracks']
        all_samples = {}
        sample_offsets = {}
        for sf2_path, samples in self.sf2_samples.items():
            offset = max(all_samples.keys()) + 1 if all_samples else 0
            sample_offsets[sf2_path] = offset
            for sample_index, sample in samples.items():
                all_samples[sample_index + offset] = sample
        for track in track_config:
            sf2_path = track.get('sf2_path')
            sample_index = track.get('sample_index')
            if sample_index is not None and sf2_path in sample_offsets:
                track['sample_index'] = sample_index + sample_offsets[sf2_path]
        return all_samples, track_config, track_cfg_full['tempo']

    def _estimate_it_brr(self):
        if not self.midi_data:
            messagebox.showwarning('Sin MIDI', 'Carga un MIDI antes de estimar.')
            return
        try:
            samples, tracks, _tempo = self._collect_it_export_data()
            estimate = it_builder.estimate_brr(
                self.midi_data, samples, tracks,
                max_sample_sec=self.max_sample_sec,
                max_brr_kb=self.max_brr_kb)
        except Exception as exc:
            messagebox.showerror('No se pudo estimar', str(exc))
            return
        state = 'Dentro del presupuesto' if estimate['fits'] else 'Excede el presupuesto'
        message = (
            f"{state}\n\n"
            f"BRR estimado: {estimate['brr_kb']:.1f} / {self.max_brr_kb:.0f} KB\n"
            f"Pistas activas: {estimate['active_tracks']}\n"
            f"Samples únicos: {estimate['unique_samples']}\n"
            f"Duración máxima por sample: {self.max_sample_sec:.2f} s"
        )
        if not estimate['fits']:
            message += '\n\nPulsa Optimizar para ajustar la duración automáticamente.'
        messagebox.showinfo('Tamaño de samples BRR', message)

    def _optimize_it_brr(self):
        if not self.midi_data:
            messagebox.showwarning('Sin MIDI', 'Carga un MIDI antes de optimizar.')
            return
        try:
            samples, tracks, _tempo = self._collect_it_export_data()
            duration = it_builder.suggest_max_sample_sec(
                self.midi_data, samples, tracks,
                max_sample_sec=self.max_sample_sec,
                max_brr_kb=self.max_brr_kb)
            if duration is None:
                messagebox.showerror(
                    'No cabe en el presupuesto',
                    'Incluso reduciendo los samples al mínimo, el BRR supera '
                    '48 KB. Silencia pistas o elige instrumentos con samples más cortos.')
                return
            self.max_sample_sec = duration
            estimate = it_builder.estimate_brr(
                self.midi_data, samples, tracks,
                max_sample_sec=duration, max_brr_kb=self.max_brr_kb)
        except Exception as exc:
            messagebox.showerror('No se pudo optimizar', str(exc))
            return

        self.preview.set_status(f"BRR: {estimate['brr_kb']:.1f}/{self.max_brr_kb:.0f} KB")
        messagebox.showinfo(
            'Optimización lista',
            f"Tamaño estimado: {estimate['brr_kb']:.1f} / {self.max_brr_kb:.0f} KB BRR\n"
            f"Duración máxima por sample: {duration:.2f} s\n\n"
            'Se aplicará a las próximas exportaciones IT de esta sesión. '
            'Acortar samples puede cambiar colas y sostenidos; los SF2 originales '
            'no se modifican.')

    def _do_export_it(self, path, with_bnk=True):
        if not self.midi_data:
            messagebox.showwarning("Sin datos", "Carga un MIDI primero.")
            return

        self._stop_preview()

        all_samples, track_config, tempo = self._collect_it_export_data()

        it_builder.build(
            midi_data=self.midi_data,
            samples_data=all_samples,
            output_path=path,
            track_config=track_config,
            tempo_override=tempo,
            max_sample_sec=self.max_sample_sec,
            max_brr_kb=self.max_brr_kb,
        )
        self.current_it_path = path

        msg = f"IT guardado en:\n{path}"

        if with_bnk:
            self.preview.set_status("⚙️ Ejecutando smconv...")
            self.update()
            smconv_path = smconv_runner.find_smconv()
            if smconv_path:
                result = smconv_runner.convert_to_soundbank(path)
                if result and 'error' not in result:
                    bnk = result.get('bnk', '')
                    asm_file = result.get('asm', '')
                    h_file = result.get('h', '')
                    msg += (
                        f"\n\nSoundbank generado:\n"
                        f"  {os.path.basename(bnk) if bnk else 'N/A'}\n"
                        f"  {os.path.basename(asm_file) if asm_file else 'N/A'}\n"
                        f"  {os.path.basename(h_file) if h_file else 'N/A'}\n\n"
                        f"Para integrar en tu proyecto PVSNESlib:\n"
                        f"  cp {bnk} mvp/res/\n"
                        f"  cd mvp && make clean && make"
                    )
                elif result and 'error' in result:
                    msg += f"\n\n⚠️ smconv: {result['error'][:200]}"
                else:
                    msg += "\n\n⚠️ smconv no produjo output"
            else:
                msg += "\n\n⚠️ smconv no encontrado"

        messagebox.showinfo("Exportación completada", msg)

    def _do_export_wav(self, path):
        if not self.midi_path:
            messagebox.showwarning("Sin datos", "Carga un MIDI primero.")
            return
        if not self.sf2_samples:
            messagebox.showwarning("Sin SF2", "Carga un SF2 primero.")
            return
        sf2_path = self._active_sf2_path()
        if not sf2_path:
            messagebox.showwarning('Sin SoundFont', 'Carga un SoundFont primero.')
            return

        self._stop_preview()
        self.preview.set_status("⚙️ Renderizando WAV...")
        self.update()
        wav = wav_renderer.render_configured_mix(
            self.midi_path, sf2_path, output_wav=path,
            tempo_bpm=self.track_panel.tempo_var.get(),
            track_config=self.track_panel.get_config()['tracks'])
        if not wav:
            raise RuntimeError("Fluidsynth no pudo renderizar el MIDI")
        self.preview.set_status(f"✅ WAV: {os.path.basename(path)}")

    def _check_deps_on_start(self):
        try:
            from core import deps
            status = deps.check()
        except Exception:
            return
        self._refresh_dependency_status()
        missing_audio = [name for name in ('fluidsynth', 'ffplay') if not deps.executable(name)]
        missing_mido = not status['mido']['ok']
        if not missing_audio and not missing_mido:
            return
        if missing_mido:
            prompt = "Falta mido para abrir archivos MIDI."
        else:
            prompt = "Para escuchar MIDI + SF2 instala FluidSynth y FFmpeg (ffplay)."
        if messagebox.askyesno(
                "Configurar midi2it",
                prompt + "\n\n¿Abrir el gestor de herramientas?"):
            self._open_dependencies()

    def _quit(self):
        # Stop procesos activos
        if hasattr(self, 'preview'):
            self.preview._stop()
        self.destroy()


def main():
    app = MIDI2ITApp()
    app.mainloop()


if __name__ == '__main__':
    main()
