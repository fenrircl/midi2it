"""
gui/preview.py — Panel de preview, export, stop global.
Reproduce MIDI con FluidSynth, renderiza a WAV, ffplay con stop real.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess, os, threading, tempfile, time


class PreviewPanel(tk.Frame):
    """Panel inferior con controles de reproduccion, export y WAV."""

    def __init__(self, parent, on_export=None, on_play_mix=None,
                 on_play_track=None, on_export_wav=None, on_import_midi=None,
                 on_import_sf2=None, **kwargs):
        super().__init__(parent, bg='#0f3460', **kwargs)
        self.on_export = on_export
        self.on_play_mix = on_play_mix
        self.on_play_track = on_play_track
        self.on_export_wav = on_export_wav
        self.on_import_midi = on_import_midi
        self.on_import_sf2 = on_import_sf2

        # Procesos activos (para poder matarlos en stop)
        self._procs = []

        # Toolbar superior: import + play + stop
        top = tk.Frame(self, bg='#0f3460')
        top.pack(fill=tk.X, pady=4, padx=10)

        tk.Button(top, text="📁 MIDI", command=self._import_midi,
                  bg='#845ef7', fg='white', bd=0, padx=8,
                  font=('Helvetica', 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="📁 SF2", command=self._import_sf2,
                  bg='#845ef7', fg='white', bd=0, padx=8,
                  font=('Helvetica', 8)).pack(side=tk.LEFT, padx=2)

        tk.Frame(top, width=20, bg='#0f3460').pack(side=tk.LEFT)

        self.play_btn = tk.Button(top, text="▶ Play mezclado", command=self._play,
                                   bg='#6bcb77', fg='white', bd=0, padx=10,
                                   font=('Helvetica', 9, 'bold'))
        self.play_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = tk.Button(top, text="■ Stop", command=self._stop,
                                   bg='#ff6b6b', fg='white', bd=0, padx=10,
                                   font=('Helvetica', 9, 'bold'))
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        # Progreso
        tk.Label(top, text="Progreso:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 8)).pack(side=tk.LEFT, padx=(20, 5))
        self.progress = ttk.Progressbar(top, length=200, mode='determinate')
        self.progress.pack(side=tk.LEFT, padx=5)
        self.pos_label = tk.Label(top, text="0:00 / 0:00", fg='#aaa',
                                   bg='#0f3460', font=('Helvetica', 8))
        self.pos_label.pack(side=tk.LEFT, padx=5)

        # Separador
        sep = tk.Frame(self, height=1, bg='#1a1a3e')
        sep.pack(fill=tk.X)

        # Toolbar export
        bottom = tk.Frame(self, bg='#0f3460')
        bottom.pack(fill=tk.X, pady=4, padx=10)

        self.export_it_btn = tk.Button(bottom, text="🎵 Exportar IT (SNES)",
                                        command=self._export_it,
                                        bg='#4d96ff', fg='white', bd=0, padx=12,
                                        font=('Helvetica', 9, 'bold'))
        self.export_it_btn.pack(side=tk.LEFT, padx=2)

        self.export_wav_btn = tk.Button(bottom, text="💾 Exportar WAV",
                                         command=self._export_wav,
                                         bg='#20c997', fg='white', bd=0, padx=12,
                                         font=('Helvetica', 9, 'bold'))
        self.export_wav_btn.pack(side=tk.LEFT, padx=2)

        # Checkbox bnk
        self.bnk_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bottom, text="+ .bnk (smconv)",
                       variable=self.bnk_var, fg='#aaa', bg='#0f3460',
                       selectcolor='#16213e', font=('Helvetica', 8)).pack(side=tk.LEFT, padx=8)

        # Status
        self.status_label = tk.Label(bottom, text="Listo", fg='#8888aa',
                                      bg='#0f3460', font=('Helvetica', 8))
        self.status_label.pack(side=tk.LEFT, padx=10)

    # ─── Import ───

    def _import_midi(self):
        if self.on_import_midi:
            self.on_import_midi()

    def _import_sf2(self):
        if self.on_import_sf2:
            self.on_import_sf2()

    # ─── Play / Stop ───

    def _play(self):
        if self.on_play_mix:
            self.on_play_mix()

    def play_track(self, midi_path, sf2_path):
        """Preview de UNA pista (usa el callback de la app para extraerla)."""
        if self.on_play_track:
            self.on_play_track(midi_path, sf2_path)

    def _stop(self):
        """Mata todos los procesos activos y limpia temporales."""
        for p in self._procs:
            try:
                if hasattr(p, 'poll') and p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        p.kill()
            except Exception:
                pass
        self._procs.clear()
        self.set_status("⏹ Detenido")

    def is_playing(self):
        return len(self._procs) > 0

    def register_proc(self, p):
        """Registra un subprocess para poder matarlo en stop."""
        self._procs.append(p)

    def cleanup_proc(self, p):
        """Quita un proceso de la lista (cuando termina naturalmente)."""
        if p in self._procs:
            self._procs.remove(p)

    # ─── Export ───

    def _export_it(self):
        if self.on_export:
            path = filedialog.asksaveasfilename(
                defaultextension=".it",
                filetypes=[("IT files", "*.it"), ("All files", "*.*")],
                title="Exportar como IT para SNES"
            )
            if path:
                self.set_status("⚙️ Generando IT...")
                self.update()
                try:
                    self.on_export(path, with_bnk=self.bnk_var.get())
                    self.set_status(f"✅ Exportado: {os.path.basename(path)}")
                except Exception as e:
                    self.set_status(f"❌ Error: {e}")
                    messagebox.showerror("Error", str(e))

    def _export_wav(self):
        if self.on_export_wav:
            path = filedialog.asksaveasfilename(
                defaultextension=".wav",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
                title="Exportar como WAV"
            )
            if path:
                self.set_status("⚙️ Renderizando WAV...")
                self.update()
                try:
                    self.on_export_wav(path)
                    self.set_status(f"✅ WAV: {os.path.basename(path)}")
                except Exception as e:
                    self.set_status(f"❌ Error: {e}")
                    messagebox.showerror("Error", str(e))

    # ─── Status / Progress ───

    def set_status(self, text):
        self.status_label.config(text=text)

    def update_progress(self, current, total):
        self.progress['value'] = int(current / total * 100) if total else 0
        self.pos_label.config(text=f"{int(current//60)}:{int(current%60):02d} / "
                                    f"{int(total//60)}:{int(total%60):02d}")
