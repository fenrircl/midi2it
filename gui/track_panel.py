"""
gui/track_panel.py — Panel lateral con pistas. Cada pista tiene:
- Selector de instrumento (combobox poblado con samples de TODOS los SF2 cargados)
- Volumen, transposicion, solo, mute
- Boton Play (preview por canal)
- Indicador del SF2 de origen
"""
import tkinter as tk
from tkinter import ttk

TRACK_COLORS = [
    '#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff',
    '#ff8fab', '#845ef7', '#20c997', '#ff922b',
]


class TrackPanel(tk.Frame):
    """Panel lateral con lista de pistas y controles."""

    def __init__(self, parent, on_update=None, on_play_track=None, on_remove_track=None, **kwargs):
        super().__init__(parent, bg='#16213e', **kwargs)
        self.on_update = on_update
        self.on_play_track = on_play_track
        self.on_remove_track = on_remove_track
        self.track_widgets = []

        # Estado: catalog global de instrumentos disponibles
        # catalog: {item_id: {label, sf2_path, sf2_name, sample_index, program, name}}
        self.catalog = {}
        self._next_item_id = 1

        tk.Label(self, text="PISTAS", fg='#8888aa', bg='#16213e',
                 font=('Helvetica', 10, 'bold')).pack(pady=(10, 5))

        # Toolbar pista
        toolbar = tk.Frame(self, bg='#16213e')
        toolbar.pack(fill=tk.X, padx=5)
        tk.Button(toolbar, text="+ Pista", command=self._add_empty_track,
                  bg='#0f3460', fg='white', bd=0, padx=8, font=('Helvetica', 8)).pack(side=tk.LEFT)
        tk.Button(toolbar, text="- Quitar", command=self._remove_last_track,
                  bg='#0f3460', fg='#ff6b6b', bd=0, padx=8, font=('Helvetica', 8)).pack(side=tk.LEFT, padx=4)

        # Scrollable container
        self.track_frame = tk.Frame(self, bg='#16213e')
        self.track_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

    # ─── Catalogo de instrumentos (de SF2 cargados) ───

    def register_instrument(self, sf2_path, sf2_name, sample_index, program, sample_name):
        """Registra un instrumento en el catalogo global. Devuelve item_id."""
        item_id = f"item_{self._next_item_id}"
        self._next_item_id += 1
        label = f"[{sf2_name[:10]}] prog={program} #{sample_index} {sample_name[:20]}"
        self.catalog[item_id] = {
            'label': label,
            'sf2_path': sf2_path,
            'sf2_name': sf2_name,
            'sample_index': sample_index,
            'program': program,
            'name': sample_name,
        }
        # Actualizar combobox de todas las pistas
        self._refresh_all_comboboxes()
        return item_id

    def clear_catalog(self):
        self.catalog.clear()
        self._refresh_all_comboboxes()

    def _catalog_labels(self):
        return [v['label'] for v in self.catalog.values()]

    def _catalog_lookup_by_label(self, label):
        for v in self.catalog.values():
            if v['label'] == label:
                return v
        return None

    def _refresh_all_comboboxes(self):
        labels = self._catalog_labels()
        for w in self.track_widgets:
            w.refresh_instrument_list(labels)

    # ─── Gestion de pistas ───

    def load_tracks(self, midi_data, sf2_samples=None, sf2_name=None, sf2_path=None):
        """Auto-genera pistas segun el MIDI y los instrumentos disponibles en el SF2."""
        # Si hay SF2 y samples, registrar todos
        if sf2_samples and sf2_name:
            for sid, s in sf2_samples.items():
                # usar indice del SF2 como 'programa proxy' si no hay extractor
                self.register_instrument(
                    sf2_path or '', sf2_name, sid,
                    sid, s.get('name', f'smp{sid}')
                )

        # Crear 1 pista por track del MIDI
        tracks = midi_data.get('tracks', []) if midi_data else []
        for w in self.track_widgets:
            w.destroy()
        self.track_widgets.clear()

        # Asignar primer instrumento del catalogo como default
        default_item = None
        if self.catalog:
            default_item = list(self.catalog.values())[0]

        for i, trk in enumerate(tracks[:8]):  # max 8
            midi_track = trk.get('index', i)
            frame = TrackChannel(
                self.track_frame, i, trk,
                color=TRACK_COLORS[i % len(TRACK_COLORS)],
                catalog=self.catalog,
                on_change=lambda: self._notify_update(),
                on_play=lambda idx=i: self._play_track(idx),
                on_remove=lambda idx=i: self._remove_track(idx),
            )
            frame.pack(fill=tk.X, pady=2)
            self.track_widgets.append(frame)

    def _add_empty_track(self):
        """Agrega una pista vacia para que el usuario la configure."""
        idx = len(self.track_widgets)
        fake_track = {'name': f'Custom {idx+1}', 'index': idx, 'events': []}
        frame = TrackChannel(
            self.track_frame, idx, fake_track,
            color=TRACK_COLORS[idx % len(TRACK_COLORS)],
            catalog=self.catalog,
            on_change=lambda: self._notify_update(),
            on_play=lambda: self._play_track(idx),
            on_remove=lambda: self._remove_track_widget(frame),
        )
        frame.pack(fill=tk.X, pady=2)
        self.track_widgets.append(frame)
        self._notify_update()

    def _remove_last_track(self):
        if self.track_widgets:
            w = self.track_widgets[-1]
            w.destroy()
            self.track_widgets.pop()
            self._notify_update()

    def _remove_track_widget(self, widget):
        if widget in self.track_widgets:
            widget.destroy()
            self.track_widgets.remove(widget)
            self._notify_update()

    def _remove_track(self, idx):
        if 0 <= idx < len(self.track_widgets):
            w = self.track_widgets[idx]
            w.destroy()
            self.track_widgets.pop(idx)
            self._notify_update()

    def get_config(self):
        """Retorna configuracion actual de pistas para it_builder.build()."""
        config = []
        for i, w in enumerate(self.track_widgets):
            cfg = w.get_config()
            cfg['midi_track'] = getattr(w, 'midi_track', i)
            cfg['name'] = getattr(w, 'name', f'Track{i}')
            config.append(cfg)
        return {
            'tracks': config,
            'tempo': self.tempo_var.get(),
        }

    def _play_track(self, idx):
        if self.on_play_track:
            self.on_play_track(idx)

    def _notify_update(self):
        if self.on_update:
            self.on_update()


class TrackChannel(tk.Frame):
    """Control individual para una pista MIDI."""

    def __init__(self, parent, index, track_data, color='#4d96ff',
                 catalog=None, on_change=None, on_play=None, on_remove=None):
        super().__init__(parent, bg='#0f3460', bd=1, relief=tk.RIDGE)
        self.index = index
        self.midi_track = track_data.get('index', index)
        self.name = track_data.get('name', f'Track {index}')
        self.catalog = catalog or {}
        self.on_change = on_change
        self.on_play = on_play
        self.on_remove = on_remove

        # Header con color y nombre
        header = tk.Frame(self, bg=color, height=26)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        ch_label = tk.Label(header, text=f"CH {index}", fg='white',
                             bg=color, font=('Helvetica', 9, 'bold'))
        ch_label.pack(side=tk.LEFT, padx=4)

        name = self.name[:18]
        tk.Label(header, text=name, fg='white', bg=color,
                 font=('Helvetica', 8)).pack(side=tk.LEFT, padx=4)

        # Botones play y eliminar en el header
        if on_play:
            tk.Button(header, text="▶", command=self._play, bg=color, fg='white',
                      bd=0, font=('Helvetica', 9, 'bold'),
                      activebackground='#0f3460').pack(side=tk.RIGHT, padx=2)
        if on_remove:
            tk.Button(header, text="✕", command=self._remove, bg=color, fg='white',
                      bd=0, font=('Helvetica', 9, 'bold'),
                      activebackground='#0f3460').pack(side=tk.RIGHT, padx=2)

        # Cuerpo
        body = tk.Frame(self, bg='#0f3460', padx=4, pady=2)
        body.pack(fill=tk.X)

        # Instrumento (combobox)
        inst_frame = tk.Frame(body, bg='#0f3460')
        inst_frame.pack(fill=tk.X, pady=1)
        tk.Label(inst_frame, text="Inst:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)

        self.instr_var = tk.StringVar()
        self.instr_combo = ttk.Combobox(inst_frame, textvariable=self.instr_var,
                                         values=list(self.catalog.values()),
                                         width=30, state='readonly',
                                         font=('Helvetica', 7))
        self.instr_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        # Seleccionar primer instrumento si hay
        if self.catalog:
            first = list(self.catalog.values())[0]
            self.instr_var.set(first['label'])
        self.instr_combo.bind('<<ComboboxSelected>>', lambda e: self._notify())

        # Volumen
        vol_frame = tk.Frame(body, bg='#0f3460')
        vol_frame.pack(fill=tk.X, pady=1)
        tk.Label(vol_frame, text="Vol:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        self.vol_var = tk.IntVar(value=100)
        ttk.Scale(vol_frame, from_=0, to=200, variable=self.vol_var,
                   orient=tk.HORIZONTAL, length=80,
                   command=lambda v: self._notify()).pack(side=tk.LEFT, padx=2)
        self.vol_label = tk.Label(vol_frame, text="100", fg='#4d96ff',
                                   bg='#0f3460', font=('Helvetica', 7), width=3)
        self.vol_label.pack(side=tk.LEFT)
        self.vol_var.trace('w', lambda *a: self.vol_label.config(text=str(self.vol_var.get())))

        # Transposicion
        transp_frame = tk.Frame(body, bg='#0f3460')
        transp_frame.pack(fill=tk.X, pady=1)
        tk.Label(transp_frame, text="Trans:", fg='#aaa', bg='#0f3460',
                 font=('Helvetica', 7)).pack(side=tk.LEFT)
        self.transp_var = tk.IntVar(value=0)
        tk.Spinbox(transp_frame, from_=-24, to=24, textvariable=self.transp_var,
                    width=4, font=('Helvetica', 7),
                    command=self._notify).pack(side=tk.LEFT, padx=2)

        # Solo/Mute
        solo_frame = tk.Frame(body, bg='#0f3460')
        solo_frame.pack(fill=tk.X, pady=2)
        self.solo_var = tk.BooleanVar(value=False)
        tk.Checkbutton(solo_frame, text="Solo", variable=self.solo_var,
                        fg='#ffd93d', bg='#0f3460', selectcolor='#16213e',
                        font=('Helvetica', 7), command=self._notify).pack(side=tk.LEFT, padx=2)
        self.mute_var = tk.BooleanVar(value=False)
        tk.Checkbutton(solo_frame, text="Mute", variable=self.mute_var,
                        fg='#ff6b6b', bg='#0f3460', selectcolor='#16213e',
                        font=('Helvetica', 7), command=self._notify).pack(side=tk.LEFT, padx=2)

    def refresh_instrument_list(self, labels):
        """Actualiza las opciones del combobox."""
        current = self.instr_var.get()
        self.instr_combo['values'] = labels
        if current in labels:
            self.instr_var.set(current)
        elif labels:
            self.instr_var.set(labels[0])

    def get_config(self):
        # Buscar sample_index del instrumento seleccionado
        label = self.instr_var.get()
        sample_index = None
        program = None
        for v in self.catalog.values():
            if v['label'] == label:
                sample_index = v['sample_index']
                program = v['program']
                break

        return {
            'instrument': label,  # human-readable
            'sample_index': sample_index,  # numeric
            'program': program,
            'volume': self.vol_var.get(),
            'transpose': self.transp_var.get(),
            'solo': self.solo_var.get(),
            'mute': self.mute_var.get(),
        }

    def _play(self):
        if self.on_play:
            self.on_play()

    def _remove(self):
        if self.on_remove:
            self.on_remove()

    def _notify(self):
        if self.on_change:
            self.on_change()
