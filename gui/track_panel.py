"""
gui/track_panel.py — Panel de control de pistas con selector de instrumento,
volumen, transposición, solo/mute.
"""
import tkinter as tk
from tkinter import ttk

TRACK_COLORS = [
    '#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff',
    '#ff8fab', '#845ef7', '#20c997', '#ff922b',
]


class TrackPanel(tk.Frame):
    """Panel lateral con lista de pistas y controles."""

    def __init__(self, parent, on_update=None, **kwargs):
        super().__init__(parent, bg='#16213e', **kwargs)
        self.on_update = on_update
        self.track_widgets = []
        
        tk.Label(self, text="PISTAS", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(pady=(10, 5))
        
        self.track_frame = tk.Frame(self, bg='#16213e')
        self.track_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Controles globales
        global_frame = tk.Frame(self, bg='#0f3460', pady=8)
        global_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        
        tk.Label(global_frame, text="Tempo", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 8)).pack()
        self.tempo_var = tk.IntVar(value=120)
        self.tempo_slider = ttk.Scale(global_frame, from_=30, to=240,
                                       variable=self.tempo_var, orient=tk.HORIZONTAL,
                                       length=150)
        self.tempo_slider.pack(pady=2)
        self.tempo_label = tk.Label(global_frame, text="120 BPM",
                                     fg='#4d96ff', bg='#0f3460', font=('Helvetica', 10, 'bold'))
        self.tempo_label.pack()
        self.tempo_var.trace('w', lambda *a: self.tempo_label.config(
            text=f"{self.tempo_var.get()} BPM"))
    
    def load_tracks(self, midi_data, sf2_instruments=None):
        """Carga las pistas del MIDI y crea controles."""
        for w in self.track_widgets:
            w.destroy()
        self.track_widgets.clear()
        
        tracks = midi_data.get('tracks', [])
        
        if not tracks:
            tk.Label(self.track_frame, text="(sin pistas)", fg='#666',
                     bg='#16213e', font=('Helvetica', 8)).pack()
            return
        
        for i, trk in enumerate(tracks[:8]):  # máx 8 canales
            frame = TrackChannel(self.track_frame, i, trk,
                                  color=TRACK_COLORS[i % len(TRACK_COLORS)],
                                  sf2_instruments=sf2_instruments,
                                  on_change=lambda: self._notify_update())
            frame.pack(fill=tk.X, pady=2)
            self.track_widgets.append(frame)
    
    def get_config(self):
        """Retorna configuración actual de pistas."""
        config = []
        for w in self.track_widgets:
            config.append(w.get_config())
        return {
            'tracks': config,
            'tempo': self.tempo_var.get(),
        }
    
    def _notify_update(self):
        if self.on_update:
            self.on_update()


class TrackChannel(tk.Frame):
    """Control individual para una pista MIDI."""

    def __init__(self, parent, index, track_data, color='#4d96ff',
                 sf2_instruments=None, on_change=None):
        super().__init__(parent, bg='#0f3460', bd=1, relief=tk.RIDGE)
        self.index = index
        self.on_change = on_change
        
        # Header con color y nombre
        header = tk.Frame(self, bg=color, height=24)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        ch_label = tk.Label(header, text=f"CH {index}", fg='white',
                             bg=color, font=('Helvetica', 8, 'bold'))
        ch_label.pack(side=tk.LEFT, padx=4)
        
        name = track_data.get('name', f'Track {index}')
        tk.Label(header, text=name[:20], fg='white', bg=color,
                 font=('Helvetica', 7)).pack(side=tk.LEFT, padx=4)
        
        # Cuerpo del control
        body = tk.Frame(self, bg='#0f3460', padx=4, pady=2)
        body.pack(fill=tk.X)
        
        # Instrumento
        inst_frame = tk.Frame(body, bg='#0f3460')
        inst_frame.pack(fill=tk.X, pady=1)
        tk.Label(inst_frame, text="Inst:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        
        self.instr_var = tk.StringVar(value="Default")
        instr_combo = ttk.Combobox(inst_frame, textvariable=self.instr_var,
                                    values=["Default"], width=16, state='readonly')
        instr_combo.pack(side=tk.LEFT, padx=2)
        
        if sf2_instruments:
            names = [f"{k}: {v['name'][:12]}" for k, v in sf2_instruments.items()]
            instr_combo['values'] = names
            if names:
                self.instr_var.set(names[0])
        
        # Volumen
        vol_frame = tk.Frame(body, bg='#0f3460')
        vol_frame.pack(fill=tk.X, pady=1)
        tk.Label(vol_frame, text="Vol:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        self.vol_var = tk.IntVar(value=100)
        ttk.Scale(vol_frame, from_=0, to=200, variable=self.vol_var,
                   orient=tk.HORIZONTAL, length=80).pack(side=tk.LEFT, padx=2)
        tk.Label(vol_frame, textvariable=self.vol_var, fg='#4d96ff',
                 bg='#0f3460', font=('Helvetica', 7)).pack(side=tk.LEFT)
        
        # Transposición
        transp_frame = tk.Frame(body, bg='#0f3460')
        transp_frame.pack(fill=tk.X, pady=1)
        tk.Label(transp_frame, text="Trans:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        self.transp_var = tk.IntVar(value=0)
        tk.Spinbox(transp_frame, from_=-24, to=24, textvariable=self.transp_var,
                    width=4, font=('Helvetica', 7)).pack(side=tk.LEFT, padx=2)
        
        # Solo/Mute
        solo_frame = tk.Frame(body, bg='#0f3460')
        solo_frame.pack(fill=tk.X, pady=2)
        self.solo_var = tk.BooleanVar(value=False)
        tk.Checkbutton(solo_frame, text="Solo", variable=self.solo_var,
                        fg='#ffd93d', bg='#0f3460', selectcolor='#16213e',
                        font=('Helvetica', 7)).pack(side=tk.LEFT, padx=2)
        self.mute_var = tk.BooleanVar(value=False)
        tk.Checkbutton(solo_frame, text="Mute", variable=self.mute_var,
                        fg='#ff6b6b', bg='#0f3460', selectcolor='#16213e',
                        font=('Helvetica', 7)).pack(side=tk.LEFT, padx=2)
    
    def get_config(self):
        return {
            'instrument': self.instr_var.get(),
            'volume': self.vol_var.get(),
            'transpose': self.transp_var.get(),
            'solo': self.solo_var.get(),
            'mute': self.mute_var.get(),
        }
