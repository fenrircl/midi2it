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
import os, sys, subprocess, threading

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
        self.title("midi2it — MIDI + SF2 → IT para SNES (DAW)")
        self.geometry("1500x800")
        self.minsize(1100, 700)
        self.configure(bg='#1a1a2e')

        # Estado global
        self.midi_data = None
        self.midi_path = None
        self.sf2_samples = {}      # sf2_path -> dict de samples
        self.current_it_path = None

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')

        # Layout 3 columnas: TrackPanel (izq) | Center (piano+preview) | SF2Browser (der)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _build_layout(self):
        # ── IZQUIERDA: TrackPanel ──
        self.track_panel = TrackPanel(
            self,
            on_update=lambda: self._on_update(),
            on_play_track=self._play_track,
            on_remove_track=self._remove_track,
            width=260
        )
        self.track_panel.pack_propagate(False)
        self.track_panel.pack(side=tk.LEFT, fill=tk.Y)

        # ── CENTRO: PianoRoll + Preview ──
        center = tk.Frame(self, bg='#1a1a2e')
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Toolbar piano roll
        toolbar = tk.Frame(center, bg='#16213e', height=36)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(toolbar, text="Piano Roll", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=5)
        self.info_label = tk.Label(toolbar, text="Carga un MIDI para comenzar",
                                    fg='#666', bg='#16213e', font=('Helvetica', 8))
        self.info_label.pack(side=tk.LEFT, padx=20)
        ttk.Button(toolbar, text="🔍−", width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 0.7)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="🔍+", width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 1.4)).pack(side=tk.RIGHT, padx=2)

        # Piano roll
        self.piano_roll = PianoRoll(center)
        self.piano_roll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ── DERECHA: SF2Browser ──
        self.sf2_browser = SF2Browser(
            self,
            on_instrument_pick=self._on_instrument_pick,
            on_sf2_load=self._on_sf2_load,
            width=300
        )
        self.sf2_browser.pack_propagate(False)
        self.sf2_browser.pack(side=tk.RIGHT, fill=tk.Y)

        # ── ABAJO: Preview ── (sobre center, docked bottom)
        # Re-empacamos: primero preview abajo, luego piano roll arriba
        # Mejor: usar grid o un packing ordenado
        # En realidad ya empaque piano roll; añado preview docked abajo:
        # (lo creamos aparte y lo ponemos con side=BOTTOM dentro de center)
        # Para simplificar, lo pongo como ventana aparte (no, queda feo)
        # Workaround: empaque de nuevo
        # Destruir packing actual y re-empaquetar:
        # (esto es mas facil: recrear center con pack invertido)

        # Mejor: redibujar correctamente
        center.destroy()
        center = tk.Frame(self, bg='#1a1a2e')
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Preview abajo
        self.preview = PreviewPanel(
            center,
            on_export=self._do_export_it,
            on_play_mix=self._play_mix,
            on_play_track=self._play_single_track,
            on_export_wav=self._do_export_wav,
            on_import_midi=self._load_midi,
            on_import_sf2=self._load_sf2_via_dialog,
        )
        self.preview.pack(side=tk.BOTTOM, fill=tk.X)
        # Piano roll arriba
        center2 = tk.Frame(center, bg='#1a1a2e')
        center2.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(center2, bg='#16213e', height=36)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(toolbar, text="Piano Roll", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=5)
        self.info_label = tk.Label(toolbar, text="Carga un MIDI para comenzar",
                                    fg='#666', bg='#16213e', font=('Helvetica', 8))
        self.info_label.pack(side=tk.LEFT, padx=20)
        ttk.Button(toolbar, text="🔍−", width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 0.7)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="🔍+", width=3,
                   command=lambda: self.piano_roll.set_zoom(self.piano_roll.zoom * 1.4)).pack(side=tk.RIGHT, padx=2)
        self.piano_roll = PianoRoll(center2)
        self.piano_roll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Check deps al inicio
        self.after(500, self._check_deps_on_start)

    # ─── Acciones: cargar MIDI/SF2 ───

    def _load_midi(self):
        path = filedialog.askopenfilename(
            title="Cargar archivo MIDI",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        if not path:
            return
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
            self.preview.set_status(f"✅ MIDI cargado: {name}")
            self.title(f"midi2it — {name}")
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

    def _reload_tracks(self):
        """Reconstruye las pistas del track panel. Usa el primer SF2 si hay."""
        sf2_path = None
        sf2_name = None
        samples = None
        if self.sf2_samples:
            sf2_path = list(self.sf2_samples.keys())[0]
            samples = self.sf2_samples[sf2_path]
            sf2_name = os.path.basename(sf2_path).replace('.sf2', '').replace('.SF2', '')

        if self.midi_data:
            self.track_panel.load_tracks(self.midi_data, samples, sf2_name, sf2_path)

    def _on_instrument_pick(self, sf2_path, sample_index, program, label):
        """Asigna el instrumento del browser a la primera pista seleccionada."""
        if not self.track_panel.track_widgets:
            self.preview.set_status("❌ No hay pistas. Carga un MIDI primero.")
            return
        # Encontrar el item_id en el catalog del track_panel
        sf2_name = os.path.basename(sf2_path).replace('.sf2', '').replace('.SF2', '')
        # Buscar el sample en el sf2_samples
        if sf2_path not in self.sf2_samples:
            self.sf2_samples[sf2_path] = sf2_parser.parse(sf2_path, max_samples=128)
        samples = self.sf2_samples[sf2_path]
        sample_name = samples.get(sample_index, {}).get('name', f'smp{sample_index}')

        item_id = self.track_panel.register_instrument(
            sf2_path, sf2_name, sample_index, program, sample_name
        )
        # Asignar a la primera pista (o la que este marcada como 'selected' - simplificado)
        track = self.track_panel.track_widgets[0]
        # Buscar label en el catalog
        for v in self.track_panel.catalog.values():
            if v['sample_index'] == sample_index and v['sf2_path'] == sf2_path:
                track.instr_var.set(v['label'])
                break

        self.preview.set_status(f"✅ Asignado: {label}")

    def _on_update(self):
        if self.midi_data:
            self.preview.set_status("🔄 Configuración actualizada")

    def _remove_track(self, idx):
        pass  # ya manejado en track_panel

    # ─── Reproduccion ───

    def _play_mix(self):
        """Preview mezclado: render MIDI completo a WAV y reproduce."""
        if not self.midi_path:
            self.preview.set_status("❌ Sin MIDI")
            return

        # SF2: usar el primero cargado
        if not self.sf2_samples:
            self.preview.set_status("❌ Carga un SF2 primero")
            return
        sf2_path = list(self.sf2_samples.keys())[0]

        self.preview.set_status("🔊 Renderizando mezcla...")
        self.preview.update_progress(0, 100)

        def worker():
            wav = wav_renderer.render_full_mix(self.midi_path, sf2_path)
            if not wav:
                self.preview.set_status("❌ fluidsynth fallo (revisa Herramientas → Dependencias)")
                return
            p = wav_renderer.play_wav(wav, on_end=lambda: self.preview.cleanup_proc(p))
            if p:
                self.preview.register_proc(p)
                self.preview.set_status("🔊 Reproduciendo mezcla...")
            else:
                self.preview.set_status(f"✅ WAV: {wav}")

        threading.Thread(target=worker, daemon=True).start()

    def _play_track(self, track_index):
        """Preview de una pista individual (boton ▶ por canal)."""
        if not self.midi_path:
            self.preview.set_status("❌ Sin MIDI")
            return
        if not self.sf2_samples:
            self.preview.set_status("❌ Carga un SF2 primero")
            return
        sf2_path = list(self.sf2_samples.keys())[0]

        self.preview.set_status(f"🔊 Renderizando pista {track_index}...")
        def worker():
            wav = wav_renderer.render_single_track(self.midi_path, sf2_path, track_index)
            if not wav:
                self.preview.set_status("❌ Error al renderizar pista")
                return
            p = wav_renderer.play_wav(wav, on_end=lambda: self.preview.cleanup_proc(p))
            if p:
                self.preview.register_proc(p)
                self.preview.set_status(f"🔊 Pista {track_index} reproduciendo...")
        threading.Thread(target=worker, daemon=True).start()

    def _play_single_track(self, midi_path, sf2_path):
        # No usado por ahora (legacy callback)
        pass

    # ─── Export ───

    def _do_export_it(self, path, with_bnk=True):
        if not self.midi_data:
            messagebox.showwarning("Sin datos", "Carga un MIDI primero.")
            return

        track_cfg_full = self.track_panel.get_config()
        track_config = track_cfg_full['tracks']
        tempo = track_cfg_full['tempo']

        # Combinar samples de todos los SF2 cargados
        all_samples = {}
        for sf2_path, samples in self.sf2_samples.items():
            # offset para evitar colisiones de indices
            offset = max(all_samples.keys()) + 1 if all_samples else 0
            for k, v in samples.items():
                all_samples[k + offset] = v
        # Reescribir sample_index en track_config para que apunten al all_samples
        for tc in track_config:
            if tc.get('sample_index') is not None:
                # buscar el sample en cualquier SF2
                for sf2_path, samples in self.sf2_samples.items():
                    if tc['sample_index'] in samples:
                        offset = sum(len(s) for s in list(self.sf2_samples.values())[:list(self.sf2_samples.keys()).index(sf2_path)])
                        tc['sample_index'] = tc['sample_index'] + offset
                        break

        it_builder.build(
            midi_data=self.midi_data,
            samples_data=all_samples,
            output_path=path,
            track_config=track_config,
            tempo_override=tempo,
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
        sf2_path = list(self.sf2_samples.keys())[0]

        self.preview.set_status("⚙️ Renderizando WAV...")
        self.update()
        wav = wav_renderer.render_full_mix(self.midi_path, sf2_path, output_wav=path)
        if not wav:
            raise RuntimeError("Fluidsynth no pudo renderizar el MIDI")
        self.preview.set_status(f"✅ WAV: {os.path.basename(path)}")

    def _check_deps_on_start(self):
        try:
            from core import deps
            status = deps.check()
        except Exception:
            return
        missing = [t for t, i in status.items() if not i['ok']]
        if not missing:
            return
        names = ", ".join(missing)
        if messagebox.askyesno(
                "Dependencias faltantes",
                f"Faltan herramientas opcionales: {names}.\n\n"
                "Sin ellas el preview o la exportación a SNES pueden no funcionar.\n\n"
                "Puedes instalarlas desde el gestor (botón 📁 SF2 → revisa el log)."):
            pass

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
