"""
gui/preview.py — Panel de previsualización y exportación.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess, os, threading


class PreviewPanel(tk.Frame):
    """Panel inferior con controles de reproducción y exportación."""

    def __init__(self, parent, on_export=None, on_play=None, **kwargs):
        super().__init__(parent, bg='#0f3460', **kwargs)
        self.on_export = on_export
        self.on_play = on_play
        
        # Barra de control
        controls = tk.Frame(self, bg='#0f3460')
        controls.pack(fill=tk.X, pady=4, padx=10)
        
        # Botones de reproducción
        self.play_btn = tk.Button(controls, text="▶ Play", command=self._play,
                                   bg='#6bcb77', fg='white', bd=0, padx=10)
        self.play_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_btn = tk.Button(controls, text="■ Stop", command=self._stop,
                                   bg='#ff6b6b', fg='white', bd=0, padx=10)
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        
        # Barra de progreso
        tk.Label(controls, text="Progreso:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 8)).pack(side=tk.LEFT, padx=(20, 5))
        self.progress = ttk.Progressbar(controls, length=200, mode='determinate')
        self.progress.pack(side=tk.LEFT, padx=5)
        
        self.pos_label = tk.Label(controls, text="0:00 / 0:00", fg='#aaa',
                                   bg='#0f3460', font=('Helvetica', 8))
        self.pos_label.pack(side=tk.LEFT, padx=5)
        
        # Separador
        sep = tk.Frame(self, height=1, bg='#1a1a3e')
        sep.pack(fill=tk.X)
        
        # Barra de exportación
        export_frame = tk.Frame(self, bg='#0f3460')
        export_frame.pack(fill=tk.X, pady=4, padx=10)
        
        self.export_btn = tk.Button(export_frame, text="🎵 Exportar IT", command=self._export,
                                     bg='#4d96ff', fg='white', bd=0, padx=15,
                                     font=('Helvetica', 10, 'bold'))
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        self.status_label = tk.Label(export_frame, text="Listo", fg='#8888aa',
                                      bg='#0f3460', font=('Helvetica', 8))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Opciones de exportación
        opt_frame = tk.Frame(self, bg='#0f3460')
        opt_frame.pack(fill=tk.X, padx=10, pady=(0, 4))
        
        # Checkbox para exportar .bnk también
        self.bnk_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="Exportar también .bnk (si smconv disponible)",
                       variable=self.bnk_var, fg='#aaa', bg='#0f3460',
                       selectcolor='#16213e', font=('Helvetica', 7)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(opt_frame, text="Formato:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="it")
        ttk.Combobox(opt_frame, textvariable=self.format_var,
                      values=["it"], width=5, state='readonly',
                      font=('Helvetica', 7)).pack(side=tk.LEFT, padx=2)
        
        tk.Label(opt_frame, text="Calidad:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT, padx=(10, 2))
        self.quality_var = tk.StringVar(value="Alta")
        ttk.Combobox(opt_frame, textvariable=self.quality_var,
                      values=["Alta (32kHz)", "Media (16kHz)", "Baja (8kHz)"],
                      width=14, state='readonly', font=('Helvetica', 7)).pack(side=tk.LEFT)
    
    def _play(self):
        if self.on_play:
            threading.Thread(target=self.on_play, daemon=True).start()
    
    def _stop(self):
        self.status_label.config(text="Detenido")
    
    def _export(self):
        if self.on_export:
            path = filedialog.asksaveasfilename(
                defaultextension=".it",
                filetypes=[("IT files", "*.it"), ("All files", "*.*")],
                title="Exportar como IT"
            )
            if path:
                self.status_label.config(text="Exportando...")
                self.update()
                try:
                    self.on_export(path)
                    self.status_label.config(text=f"✅ Exportado: {os.path.basename(path)}")
                except Exception as e:
                    self.status_label.config(text=f"❌ Error: {e}")
                    messagebox.showerror("Error", str(e))
    
    def set_status(self, text):
        self.status_label.config(text=text)
    
    def update_progress(self, current, total):
        self.progress['value'] = int(current / total * 100) if total else 0
        self.pos_label.config(text=f"{int(current//60)}:{int(current%60):02d} / "
                                    f"{int(total//60)}:{int(total%60):02d}")
