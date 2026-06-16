"""
core/midi_parser.py — Parsea archivos MIDI extrayendo pistas, notas, programas y tempo.
"""
import mido

def parse(midi_path):
    """Analiza un archivo MIDI y devuelve estructura con pistas y eventos."""
    midi = mido.MidiFile(midi_path)
    
    tracks = []
    for i, track in enumerate(midi.tracks):
        events = []
        abs_ticks = 0
        for msg in track:
            abs_ticks += msg.time
            events.append({
                'type': msg.type,
                'note': getattr(msg, 'note', None),
                'velocity': getattr(msg, 'velocity', None),
                'program': getattr(msg, 'program', None),
                'channel': getattr(msg, 'channel', None),
                'value': getattr(msg, 'value', None),
                'control': getattr(msg, 'control', None),
                'ticks': msg.time,
                'abs_ticks': abs_ticks,
            })
        if any(e['type'] == 'note_on' for e in events):
            tracks.append({
                'index': i,
                'name': track.name or f"Track {i}",
                'events': events,
            })
    
    # Obtener tempo
    tempo = 120.0
    for t in midi.tracks:
        for msg in t:
            if msg.type == 'set_tempo':
                tempo = 60000000.0 / msg.tempo
    
    return {
        'filename': midi_path,
        'ticks_per_beat': midi.ticks_per_beat,
        'tempo': tempo,
        'duration_seconds': midi.length,
        'tracks': tracks,
        'raw': midi,
    }


def track_summary(track_data):
    """Resumen de una pista: rango de notas, cantidad de eventos, programa usado."""
    notes = []
    programs = set()
    for e in track_data['events']:
        if e['type'] == 'note_on' and e['velocity'] > 0:
            notes.append(e['note'])
        if e['type'] == 'program_change':
            programs.add(e['program'])
    
    if not notes:
        return {'notes': 0, 'range': None, 'programs': list(programs)}
    
    return {
        'notes': len(notes),
        'range': (min(notes), max(notes)),
        'programs': list(programs) if programs else [0],
    }
