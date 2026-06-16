"""
midi2it_gui.py — Interfaz gráfica principal (tkinter).
Mini DAW para cargar MIDI+SF2, editar pistas, visualizar notas y exportar a IT.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, sys

sys.path.insert(0, os.path.dirname(__file__))

from core import midi_parser, sf2_parser, it_builder
from gui.piano_roll import PianoRoll
from gui.track_panel import TrackPanel
from gui.preview import PreviewPanel


class MIDI2ITApp(tk.Tk):
    """Ventana principal de la aplicación."""

    def __init__(self):
        super().__init__()
        self.title("midi2it — MIDI + SF2 → IT para SNES")
        self.geometry("1280x720")
        self.minsize(900, 600)
        self.configure(bg='#1a1a2e')

        # Datos del proyecto
        self.midi_data = None
        self.sf2_samples = None
        self.midi_path = None
        self.sf2_path = None
        self.current_it_path = None

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TScale', background='#0f3460', troughcolor='#1a1a3e')

        self._build_menu()
        self._build_layout()

        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ─── MENU ────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self, bg='#16213e', fg='white')
        self.config(menu=menubar)

        filemenu = tk.Menu(menubar, tearoff=0, bg='#16213e', fg='white')
        menubar.add_cascade(label="Archivo", menu=filemenu)
        filemenu.add_command(label="Cargar MIDI...", command=self._load_midi, accelerator="Ctrl+M")
        filemenu.add_command(label="Cargar SF2...", command=self._load_sf2, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exportar IT...", command=self._do_export, accelerator="Ctrl+E")
        filemenu.add_separator()
        filemenu.add_command(label="Salir", command=self._quit)

        helpmenu = tk.Menu(menubar, tearoff=0, bg='#16213e', fg='white')
        menubar.add_cascade(label="Ayuda", menu=helpmenu)
        helpmenu.add_command(label="Acerca de", command=self._about)

        # Atajos de teclado
        self.bind_all('<Control-m>', lambda e: self._load_midi())
        self.bind_all('<Control-s>', lambda e: self._load_sf2())
        self.bind_all('<Control-e>', lambda e: self._do_export())

    # ─── LAYOUT ──────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Panel izquierdo: pistas
        self.track_panel = TrackPanel(self, on_update=self._on_tracks_update)
        self.track_panel.pack(side=tk.LEFT, fill=tk.Y, width=220)

        # Panel central: piano roll
        center = tk.Frame(self, bg='#1a1a2e')
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

        self.piano_roll = PianoRoll(center)
        self.piano_roll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Panel inferior: preview y exportación
        self.preview = PreviewPanel(self, on_export=self._do_export, on_play=self._play_preview)
        self.preview.pack(side=tk.BOTTOM, fill=tk.X)

    # ─── ACCIONES ────────────────────────────────────────────────────────────

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
            self.track_panel.load_tracks(self.midi_data, self.sf2_samples)

            name = os.path.basename(path)
            num_tracks = len(self.midi_data['tracks'])
            tempo = self.midi_data['tempo']
            self.info_label.config(
                text=f"{name} — {num_tracks} pistas, {tempo:.0f} BPM, "
                     f"{self.midi_data['duration_seconds']:.1f}s"
            )
            self.preview.set_status(f"✅ MIDI cargado: {name}")
            self.title(f"midi2it — {name}")
        except Exception as e:
            messagebox.showerror("Error al cargar MIDI", str(e))

    def _load_sf2(self):
        path = filedialog.askopenfilename(
            title="Cargar SoundFont",
            filetypes=[("SoundFont", "*.sf2"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.sf2_samples = sf2_parser.parse(path)
            self.sf2_path = path
            self.track_panel.load_tracks(self.midi_data, self.sf2_samples)
            self.preview.set_status(f"✅ SF2 cargado: {os.path.basename(path)} ({len(self.sf2_samples)} samples)")
        except Exception as e:
            messagebox.showerror("Error al cargar SF2", str(e))

    def _on_tracks_update(self):
        """Se llama cuando se modifican controles de pista."""
        if self.midi_data:
            self.preview.set_status("🔄 Actualizado")

    def _do_export(self, path=None):
        if not self.midi_data:
            messagebox.showwarning("Sin datos", "Carga un archivo MIDI primero.")
            return

        if not path:
            # Default: exportar .it en el directorio actual
            default_name = (os.path.splitext(os.path.basename(self.midi_path or 'output'))[0] 
                           if self.midi_path else 'output')
            path = filedialog.asksaveasfilename(
                defaultextension=".it",
                initialfile=f"{default_name}.it",
                filetypes=[("IT files", "*.it"), ("All files", "*.*")],
                title="Exportar como IT para SNES"
            )
            if not path:
                return

        try:
            track_cfg = self.track_panel.get_config()
            self.preview.set_status("⚙️ Generando IT...")
            self.update()

            it_builder.build(
                midi_data=self.midi_data,
                samples_data=self.sf2_samples or {},
                output_path=path,
                tempo_override=track_cfg.get('tempo'),
                track_config=track_cfg.get('tracks'),
            )
            self.current_it_path = path

            # ¿Exportar también .bnk?
            if self.preview.bnk_var.get():
                self.preview.set_status("⚙️ Ejecutando smconv...")
                self.update()
                
                from core.smconv_runner import convert_to_soundbank, find_smconv
                smconv_path = find_smconv()
                if smconv_path:
                    result = convert_to_soundbank(path)
                    if result and 'error' not in result:
                        bnk = result.get('bnk', '')
                        asm_file = result.get('asm', '')
                        h_file = result.get('h', '')
                        self.preview.set_status(
                            f"✅ IT + .bnk exportados: {os.path.basename(path)}"
                        )
                        msg = (
                            f"IT guardado en:\n{path}\n\n"
                            f"Soundbank generado:\n"
                            f"  {os.path.basename(bnk) if bnk else 'N/A'}\n"
                            f"  {os.path.basename(asm_file) if asm_file else 'N/A'}\n"
                            f"  {os.path.basename(h_file) if h_file else 'N/A'}\n\n"
                            f"Para integrar en tu proyecto:\n"
                            f"  1. Copia los archivos a mvp/res/\n"
                            f"  2. En Makefile: AUDIOFILES := res/{os.path.splitext(os.path.basename(path))[0]}.it\n"
                            f"  3. make clean && make"
                        )
                    elif result and 'error' in result:
                        msg = f"IT exportado en:\n{path}\n\n⚠️ smconv: {result['error']}"
                    else:
                        msg = f"IT exportado en:\n{path}\n\n⚠️ smconv no encontrado. Solo se exportó .it"
                else:
                    msg = (
                        f"IT exportado en:\n{path}\n\n"
                        f"⚠️ smconv no encontrado. Para generar .bnk:\n"
                        f"  export PVSNESLIB_HOME=~/snesdev/pvsneslib\n"
                        f"  smconv -s -o soundbank -b 5 \"{path}\""
                    )
            else:
                msg = f"IT exportado en:\n{path}"

            messagebox.showinfo("Exportación completada", msg)

        except Exception as e:
            self.preview.set_status(f"❌ Error: {e}")
            messagebox.showerror("Error de exportación", str(e))

    def _play_preview(self):
        """Reproduce preview usando FluidSynth (si está disponible)."""
        self.preview.set_status("🔊 Reproduciendo... (render MIDI)")
        self.preview.update_progress(0, 100)

        if not self.midi_path:
            self.preview.set_status("❌ Sin MIDI cargado")
            return

        try:
            import subprocess, tempfile
            tmp_wav = tempfile.mktemp(suffix='.wav')
            sf2 = self.sf2_path or '/usr/share/sounds/sf2/FluidR3_GM.sf2'

            if os.path.exists('/usr/bin/fluidsynth'):
                subprocess.run(
                    ['fluidsynth', '-F', tmp_wav, '-i', sf2, self.midi_path],
                    capture_output=True, timeout=30
                )
                if os.path.exists('/usr/bin/ffplay'):
                    subprocess.Popen(['ffplay', '-nodisp', '-autoexit', tmp_wav],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.preview.set_status("🔊 Reproduciendo...")
                else:
                    self.preview.set_status(f"✅ Renderizado: {tmp_wav}")
            else:
                self.preview.set_status("❌ FluidSynth no instalado")
        except Exception as e:
            self.preview.set_status(f"❌ Error: {e}")

    def _about(self):
        messagebox.showinfo("Acerca de midi2it",
            "midi2it v0.1.0\n\n"
            "Conversor MIDI + SoundFont → IT para SNES.\n"
            "Usa PVSNESlib (smconv) para generar soundbanks\n"
            "compatibles con SNES real.\n\n"
            "Creado para el proyecto vs-snes (fenrircl).\n"
            "https://github.com/fenrircl/midi2it")

    def _quit(self):
        self.destroy()


def main():
    app = MIDI2ITApp()
    app.mainloop()


if __name__ == '__main__':
    main()
