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
        super().__init__(parent, bg='#111827', **kwargs)
        self.on_update = on_update
        self.on_play_track = on_play_track
        self.on_remove_track = on_remove_track
        self.track_widgets = []
        self.selected_track_index = None

        # Estado: catalog global de instrumentos disponibles
        # catalog: {item_id: {label, sf2_path, sf2_name, sample_index, program, name}}
        self.catalog = {}
        self._next_item_id = 1

        tk.Label(self, text="PISTAS", fg='#cbd5e1', bg='#111827',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=10, pady=(12, 7))

        # Toolbar pista
        toolbar = tk.Frame(self, bg='#111827')
        toolbar.pack(fill=tk.X, padx=8)
        ttk.Button(toolbar, text='+ Pista', command=self._add_empty_track,
                   style='Quiet.TButton').pack(side=tk.LEFT)
        ttk.Button(toolbar, text='Quitar', command=self._remove_last_track,
                   style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Scrollable container: keep all MIDI tracks reachable in shorter windows.
        track_area = tk.Frame(self, bg='#111827')
        track_area.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.track_canvas = tk.Canvas(track_area, bg='#111827', highlightthickness=0,
                                      borderwidth=0)
        track_scroll = ttk.Scrollbar(track_area, orient=tk.VERTICAL,
                                     command=self.track_canvas.yview)
        self.track_canvas.configure(yscrollcommand=track_scroll.set)
        track_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.track_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.track_frame = tk.Frame(self.track_canvas, bg='#111827')
        self._track_window = self.track_canvas.create_window(
            (0, 0), window=self.track_frame, anchor='nw')
        self.track_frame.bind('<Configure>', self._update_track_scroll)
        self.track_canvas.bind('<Configure>', self._resize_track_frame)
        self.track_canvas.bind_all('<MouseWheel>', self._scroll_tracks, add='+')

        # Controles globales
        global_frame = tk.Frame(self, bg='#182235', pady=8)
        global_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=6, pady=6)

        tk.Label(global_frame, text="TEMPO", fg='#94a3b8', bg='#182235',
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=10)
        self.tempo_var = tk.IntVar(value=120)
        self.tempo_slider = ttk.Scale(global_frame, from_=30, to=240,
                                       variable=self.tempo_var, orient=tk.HORIZONTAL,
                                       length=150)
        self.tempo_slider.pack(pady=2)
        self.tempo_label = tk.Label(global_frame, text="120 BPM",
                                     fg='#c4b5fd', bg='#182235', font=('Segoe UI', 10, 'bold'))
        self.tempo_label.pack()
        self.tempo_var.trace('w', lambda *a: self.tempo_label.config(
            text=f"{self.tempo_var.get()} BPM"))

    def _update_track_scroll(self, _event=None):
        self.track_canvas.configure(scrollregion=self.track_canvas.bbox('all'))

    def _resize_track_frame(self, event):
        self.track_canvas.itemconfigure(self._track_window, width=event.width)

    def _scroll_tracks(self, event):
        widget = event.widget
        within_tracks = False
        while widget is not None:
            if widget in (self.track_canvas, self.track_frame):
                within_tracks = True
                break
            widget = getattr(widget, 'master', None)
        if within_tracks and self.track_canvas.winfo_height() > 1:
            self.track_canvas.yview_scroll(int(-event.delta / 120), 'units')

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
        if midi_data:
            self.tempo_var.set(max(30, min(240, round(midi_data.get('tempo', 120)))))
        for w in self.track_widgets:
            w.destroy()
        self.track_widgets.clear()

        for i, trk in enumerate(tracks[:8]):  # max 8
            frame = TrackChannel(
                self.track_frame, i, trk,
                color=TRACK_COLORS[i % len(TRACK_COLORS)],
                catalog=self.catalog,
                on_change=lambda: self._notify_update(),
            )
            self._wire_track(frame)
            frame.pack(fill=tk.X, pady=2)
            self.track_widgets.append(frame)
        if self.track_widgets:
            self.select_track(min(self.selected_track_index or 0, len(self.track_widgets) - 1))

    def _add_empty_track(self):
        """Agrega una pista vacia para que el usuario la configure."""
        idx = len(self.track_widgets)
        fake_track = {'name': f'Custom {idx+1}', 'index': idx, 'events': []}
        frame = TrackChannel(
            self.track_frame, idx, fake_track,
            color=TRACK_COLORS[idx % len(TRACK_COLORS)],
            catalog=self.catalog,
            on_change=lambda: self._notify_update(),
        )
        self._wire_track(frame)
        frame.pack(fill=tk.X, pady=2)
        self.track_widgets.append(frame)
        self.select_track(idx)
        self._notify_update()

    def _remove_last_track(self):
        if self.track_widgets:
            w = self.track_widgets[-1]
            w.destroy()
            self.track_widgets.pop()
            self.selected_track_index = min(self.selected_track_index or 0,
                                             len(self.track_widgets) - 1) if self.track_widgets else None
            if self.selected_track_index is not None:
                self.select_track(self.selected_track_index)
            self._notify_update()

    def _remove_track_widget(self, widget):
        if widget in self.track_widgets:
            widget.destroy()
            self.track_widgets.remove(widget)
            self._repair_selection()
            self._notify_update()

    def _wire_track(self, widget):
        widget.on_play = lambda w=widget: self._play_widget(w)
        widget.on_remove = lambda w=widget: self._remove_track_widget(w)
        widget.on_select = lambda w=widget: self.select_track(self.track_widgets.index(w)) \
            if w in self.track_widgets else None

    def _play_widget(self, widget):
        if widget in self.track_widgets:
            self._play_track(self.track_widgets.index(widget))

    def _remove_track(self, idx):
        if 0 <= idx < len(self.track_widgets):
            w = self.track_widgets[idx]
            w.destroy()
            self.track_widgets.pop(idx)
            self._repair_selection()
            self._notify_update()

    def _repair_selection(self):
        if not self.track_widgets:
            self.selected_track_index = None
        else:
            self.select_track(min(self.selected_track_index or 0, len(self.track_widgets) - 1))

    def select_track(self, index):
        if not 0 <= index < len(self.track_widgets):
            return
        self.selected_track_index = index
        for i, widget in enumerate(self.track_widgets):
            widget.set_selected(i == index)

    def get_selected_track(self):
        if self.selected_track_index is None:
            return None
        if self.selected_track_index >= len(self.track_widgets):
            return None
        return self.track_widgets[self.selected_track_index]

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
                 catalog=None, on_change=None, on_play=None, on_remove=None,
                 on_select=None):
        super().__init__(parent, bg='#182235', bd=1, relief=tk.FLAT,
                         highlightthickness=1, highlightbackground='#263449')
        self.index = index
        self.midi_track = track_data.get('index', index)
        self.name = track_data.get('name', f'Track {index}')
        self.catalog = catalog or {}
        self.on_change = on_change
        self.on_play = on_play
        self.on_remove = on_remove
        self.on_select = on_select

        # Header con color y nombre
        header = tk.Frame(self, bg='#202d42', height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        ch_label = tk.Label(header, text=f"{index + 1:02d}", fg='#c4b5fd',
                             bg='#202d42', font=('Segoe UI', 9, 'bold'))
        ch_label.pack(side=tk.LEFT, padx=(8, 5))

        name = self.name[:18]
        name_label = tk.Label(header, text=name, fg='#f8fafc', bg='#202d42',
                              font=('Segoe UI', 9))
        name_label.pack(side=tk.LEFT, padx=4)

        # Botones play y eliminar en el header
        if on_play:
            ttk.Button(header, text='▶', command=self._play,
                       style='Quiet.TButton').pack(side=tk.RIGHT, padx=4)
        if on_remove:
            ttk.Button(header, text='×', command=self._remove,
                       style='Danger.TButton').pack(side=tk.RIGHT, padx=3)

        # Cuerpo
        body = tk.Frame(self, bg='#182235', padx=8, pady=5)
        body.pack(fill=tk.X)

        # Instrumento (combobox)
        inst_frame = tk.Frame(body, bg='#182235')
        inst_frame.pack(fill=tk.X, pady=1)
        tk.Label(inst_frame, text="Instrumento", fg='#94a3b8', bg='#182235',
                 font=('Segoe UI', 8)).pack(side=tk.LEFT)

        self.instr_var = tk.StringVar()
        self.instr_combo = ttk.Combobox(inst_frame, textvariable=self.instr_var,
                                         values=list(self.catalog.values()),
                                         width=30, state='readonly',
                                         font=('Segoe UI', 8))
        self.instr_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        # Seleccionar primer instrumento si hay
        if self.catalog:
            midi_program = track_data.get('program')
            preferred = next((v for v in self.catalog.values()
                              if v.get('program') == midi_program), None)
            first = preferred or next(iter(self.catalog.values()))
            self.instr_var.set(first['label'])
        self.instr_combo.bind('<<ComboboxSelected>>', lambda e: self._notify())

        # Volumen
        vol_frame = tk.Frame(body, bg='#182235')
        vol_frame.pack(fill=tk.X, pady=1)
        tk.Label(vol_frame, text="Volumen", fg='#94a3b8', bg='#182235',
                 font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.vol_var = tk.IntVar(value=100)
        ttk.Scale(vol_frame, from_=0, to=200, variable=self.vol_var,
                   orient=tk.HORIZONTAL, length=80,
                   command=lambda v: self._notify()).pack(side=tk.LEFT, padx=2)
        self.vol_label = tk.Label(vol_frame, text="100", fg='#c4b5fd',
                                   bg='#182235', font=('Segoe UI', 8), width=3)
        self.vol_label.pack(side=tk.LEFT)
        self.vol_var.trace('w', lambda *a: self.vol_label.config(text=str(self.vol_var.get())))

        # Transposicion
        transp_frame = tk.Frame(body, bg='#182235')
        transp_frame.pack(fill=tk.X, pady=1)
        tk.Label(transp_frame, text="Transposición", fg='#94a3b8', bg='#182235',
                 font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.transp_var = tk.IntVar(value=0)
        ttk.Spinbox(transp_frame, from_=-24, to=24, textvariable=self.transp_var,
                    width=5, command=self._notify).pack(side=tk.LEFT, padx=5)

        # Solo/Mute
        solo_frame = tk.Frame(body, bg='#182235')
        solo_frame.pack(fill=tk.X, pady=2)
        self.solo_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(solo_frame, text="Solo", variable=self.solo_var,
                        command=self._notify).pack(side=tk.LEFT, padx=2)
        self.mute_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(solo_frame, text="Mute", variable=self.mute_var,
                        command=self._notify).pack(side=tk.LEFT, padx=6)
        self._bind_selection(self)

    def _bind_selection(self, widget):
        widget.bind('<Button-1>', self._select_from_click, add='+')
        for child in widget.winfo_children():
            self._bind_selection(child)

    def _select_from_click(self, _event=None):
        if self.on_select:
            self.on_select()

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
        sf2_path = None
        for v in self.catalog.values():
            if v['label'] == label:
                sample_index = v['sample_index']
                program = v['program']
                sf2_path = v['sf2_path']
                break

        return {
            'instrument': label,  # human-readable
            'sample_index': sample_index,  # numeric
            'sf2_path': sf2_path,
            'program': program,
            'volume': self.vol_var.get(),
            'transpose': self.transp_var.get(),
            'solo': self.solo_var.get(),
            'mute': self.mute_var.get(),
        }

    def _play(self):
        if self.on_play:
            self.on_play()

    def set_selected(self, selected):
        self.configure(highlightbackground='#8b5cf6' if selected else '#263449',
                       highlightcolor='#8b5cf6' if selected else '#263449')

    def _remove(self):
        if self.on_remove:
            self.on_remove()

    def _notify(self):
        if self.on_change:
            self.on_change()
