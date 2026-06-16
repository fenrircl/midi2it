"""
gui/piano_roll.py — Widget de piano roll para visualizar y editar notas MIDI.
"""
import tkinter as tk
from tkinter import ttk

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
KEYS_OCTAVE = [0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1]  # 1 = black key
NOTE_COLORS = ['#e8e8e8', '#2a2a2a']  # white bg, black bg

TRACK_COLORS = [
    '#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff',
    '#ff8fab', '#845ef7', '#20c997', '#ff922b',
]


class PianoRoll(tk.Canvas):
    """Canvas-based piano roll para edición de notas MIDI."""
    
    def __init__(self, parent, midi_data=None, **kwargs):
        super().__init__(parent, bg='#1a1a2e', highlightthickness=0, **kwargs)
        self.midi_data = midi_data
        self.track_data = []
        
        # Configuración visual
        self.key_width = 50
        self.row_height = 16
        self.beat_width = 80
        
        self.visible_octaves = range(2, 7)  # C2 a B6
        self.offset_beat = 0
        self.max_beats = 64
        
        self.selected_notes = set()
        self.dragging = None
        self.zoom = 1.0
        
        # Bindings
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<MouseWheel>', self.on_scroll)
        
        self._draw_grid()
    
    def _note_to_y(self, note):
        """Convierte número MIDI a coordenada Y en el canvas."""
        min_note = self.visible_octaves[0] * 12
        max_note = (self.visible_octaves[-1] + 1) * 12
        total_keys = max_note - min_note
        y_per_key = self.row_height
        return (max_note - note - 1) * y_per_key + y_per_key // 2
    
    def _y_to_note(self, y):
        """Convierte coordenada Y a número MIDI."""
        min_note = self.visible_octaves[0] * 12
        max_note = (self.visible_octaves[-1] + 1) * 12
        note = max_note - 1 - int(y // self.row_height)
        return max(min_note, min(note, max_note))
    
    def _beat_to_x(self, beat):
        """Convierte beat a coordenada X."""
        return self.key_width + beat * self.beat_width * self.zoom
    
    def _x_to_beat(self, x):
        """Convierte coordenada X a beat."""
        return int((x - self.key_width) / (self.beat_width * self.zoom))
    
    def _draw_grid(self):
        """Dibuja la grilla del piano roll."""
        self.delete('all')
        
        min_note = self.visible_octaves[0] * 12
        max_note = (self.visible_octaves[-1] + 1) * 12
        num_keys = max_note - min_note
        
        w = self.key_width + self.max_beats * self.beat_width * self.zoom + 20
        h = num_keys * self.row_height + 20
        self.config(scrollregion=(0, 0, w, h))
        
        # Dibujar filas (piano keys)
        for i in range(num_keys):
            note = max_note - 1 - i
            y = i * self.row_height
            octave = (note // 12) - 1
            note_name = NOTE_NAMES[note % 12]
            is_black = KEYS_OCTAVE[note % 12]
            
            bg_color = '#2a2a3e' if is_black else '#1a1a2e'
            self.create_rectangle(0, y, self.key_width, y + self.row_height,
                                  fill=bg_color, outline='#3a3a5e', width=1)
            
            # Label de nota
            if not is_black:
                self.create_text(5, y + self.row_height // 2,
                                 text=f"{note_name}{octave}",
                                 anchor='w', fill='#8888aa', font=('Helvetica', 7))
            
            # Grid vertical (beats)
            for beat in range(0, self.max_beats + 1, 1):
                x = self._beat_to_x(beat)
                is_bar = beat % 4 == 0
                color = '#3a3a5e' if is_bar else '#2a2a4e'
                self.create_line(x, y, x, y + self.row_height, fill=color, width=1 if is_bar else 1)
            
            # Separator line
            self.create_line(self.key_width, y, w, y, fill='#2a2a4e', width=1)
        
        # Beat numbers
        for beat in range(0, self.max_beats + 1, 4):
            x = self._beat_to_x(beat)
            self.create_text(x, h - 12, text=f"{beat//4+1}", fill='#8888aa', font=('Helvetica', 8))
        
        # Dibujar notas
        if self.midi_data:
            self._draw_notes()
    
    def _draw_notes(self):
        """Dibuja las notas MIDI como rectángulos."""
        min_note = self.visible_octaves[0] * 12
        max_note = (self.visible_octaves[-1] + 1) * 12
        
        for ti, trk_data in enumerate(self.track_data):
            if not trk_data.get('visible', True):
                continue
            
            color = TRACK_COLORS[ti % len(TRACK_COLORS)]
            events = trk_data.get('events', [])
            
            # Map note_on events to create note rects
            note_starts = {}
            for event in events:
                if event['type'] == 'note_on' and event.get('velocity', 0) > 0:
                    note = event['note']
                    if min_note <= note <= max_note:
                        abs_beat = event['abs_ticks'] / self.midi_data['ticks_per_beat']
                        note_starts[note] = abs_beat
                elif event['type'] == 'note_off' or (event['type'] == 'note_on' and event.get('velocity', 0) == 0):
                    note = event.get('note', 0)
                    if note in note_starts:
                        start_beat = note_starts.pop(note)
                        abs_beat = event['abs_ticks'] / self.midi_data['ticks_per_beat']
                        duration = abs_beat - start_beat
                        
                        x1 = self._beat_to_x(start_beat)
                        x2 = self._beat_to_x(abs_beat)
                        y = self._note_to_y(note)
                        
                        self.create_rectangle(
                            x1, y - self.row_height // 2 + 2,
                            max(x1 + 4, x2), y + self.row_height // 2 - 2,
                            fill=color, outline='white', width=1,
                            tags=('note', f'track{ti}')
                        )
    
    def load_midi(self, midi_data):
        """Carga datos MIDI para visualización."""
        self.midi_data = midi_data
        self.track_data = midi_data.get('tracks', [])
        self._draw_grid()
    
    def on_click(self, event):
        """Maneja click para seleccionar/agregar notas."""
        beat = self._x_to_beat(event.x)
        note = self._y_to_note(event.y)
        if 0 <= beat < self.max_beats:
            self.dragging = {'note': note, 'beat': beat}
    
    def on_drag(self, event):
        """Maneja arrastre para mover notas."""
        if self.dragging:
            beat = self._x_to_beat(event.x)
            note = self._y_to_note(event.y)
            self.dragging['note'] = note
            self.dragging['beat'] = beat
    
    def on_release(self, event):
        """Finaliza edición."""
        self.dragging = None
    
    def on_scroll(self, event):
        """Zoom con scroll del mouse."""
        self.zoom *= 1.1 if event.delta > 0 else 0.9
        self.zoom = max(0.3, min(self.zoom, 4.0))
        self._draw_grid()
    
    def set_zoom(self, zoom_level):
        self.zoom = zoom_level
        self._draw_grid()
