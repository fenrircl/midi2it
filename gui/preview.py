"""Transport and export controls for the main window."""

import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class PreviewPanel(tk.Frame):
    """Playback and export bar."""

    def __init__(self, parent, on_export=None, on_play_mix=None,
                 on_play_track=None, on_export_wav=None, on_stop=None,
                 on_estimate_brr=None, on_optimize_brr=None, **kwargs):
        super().__init__(parent, bg='#111827', **kwargs)
        self.on_export = on_export
        self.on_play_mix = on_play_mix
        self.on_play_track = on_play_track
        self.on_export_wav = on_export_wav
        self.on_stop = on_stop
        self.on_estimate_brr = on_estimate_brr
        self.on_optimize_brr = on_optimize_brr
        self._procs = []

        transport = tk.Frame(self, bg='#182235', padx=12, pady=10)
        transport.pack(fill=tk.X, pady=(0, 1))
        self.play_btn = ttk.Button(
            transport, text='▶  Reproducir', command=self._play,
            style='Accent.TButton', state=tk.DISABLED)
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(transport, text='■  Detener', command=self._stop,
                   style='Quiet.TButton').pack(side=tk.LEFT)
        self.status_label = tk.Label(transport, text='Carga un MIDI y un SoundFont',
                                     fg='#94a3b8', bg='#182235',
                                     font=('Segoe UI', 8), anchor='e')
        self.status_label.pack(side=tk.RIGHT, padx=4)

        footer = tk.Frame(self, bg='#111827', padx=12, pady=9)
        footer.pack(fill=tk.X)
        tk.Label(footer, text='EXPORTAR', fg='#64748b', bg='#111827',
                 font=('Segoe UI', 8, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(footer, text='Exportar IT', command=self._export_it,
                   style='Quiet.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(footer, text='Exportar WAV', command=self._export_wav,
                   style='Quiet.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text='Estimar BRR', command=self._estimate_brr,
                   style='Quiet.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text='Optimizar', command=self._optimize_brr,
                   style='Quiet.TButton').pack(side=tk.LEFT, padx=5)
        self.bnk_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(footer, text='.bnk', variable=self.bnk_var,
                        style='TCheckbutton').pack(side=tk.LEFT, padx=10)
    def _play(self):
        if self.on_play_mix:
            self.on_play_mix()

    def _estimate_brr(self):
        if self.on_estimate_brr:
            self.on_estimate_brr()

    def _optimize_brr(self):
        if self.on_optimize_brr:
            self.on_optimize_brr()

    def _stop(self):
        self.stop_audio()
        if self.on_stop:
            self.on_stop()
        else:
            self.set_status('Reproducción detenida')

    def stop_audio(self):
        for process in self._procs[:]:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except Exception:
                pass
        self._procs.clear()

    def register_proc(self, process):
        self._procs.append(process)

    def cleanup_proc(self, process):
        if process in self._procs:
            self._procs.remove(process)

    def _export_it(self):
        if not self.on_export:
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.it',
            filetypes=[('Impulse Tracker', '*.it'), ('Todos los archivos', '*.*')],
            title='Exportar música para SNES')
        if not path:
            return
        self.set_status('Generando archivo IT…')
        try:
            self.on_export(path, with_bnk=self.bnk_var.get())
            self.set_status(f'Exportado: {os.path.basename(path)}')
        except Exception as exc:
            self.set_status(f'Error: {exc}')
            messagebox.showerror('Error de exportación', str(exc))

    def _export_wav(self):
        if not self.on_export_wav:
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.wav',
            filetypes=[('WAV', '*.wav'), ('Todos los archivos', '*.*')],
            title='Exportar mezcla a WAV')
        if not path:
            return
        self.set_status('Renderizando WAV…')
        try:
            self.on_export_wav(path)
            self.set_status(f'WAV exportado: {os.path.basename(path)}')
        except Exception as exc:
            self.set_status(f'Error: {exc}')
            messagebox.showerror('Error al exportar WAV', str(exc))

    def set_status(self, text):
        self.status_label.config(text=text)

    def update_progress(self, current, total):
        # Conservado para compatibilidad; render y reproducción no exponen progreso temporal.
        return None
