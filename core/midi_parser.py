"""
core/midi_parser.py — Parsea archivos MIDI extrayendo pistas, notas, programas y tempo.

ARQUITECTURA v2 (para edicion tipo Guitar Pro):
  - tracks[i].notes: lista de {pitch, start_tick, duration_tick, velocity, channel}
    (notas con duracion ya computada, no eventos sueltos)
  - tracks[i].events: eventos crudos (note_on/off, program_change, etc) - para
    preservar al exportar de vuelta
  - tracks[i].name, .channel, .program
"""
# mido se importa de forma diferida (lazy) para que la GUI pueda arrancar
# y ofrecer instalarlo aunque aún no esté presente.

def parse(midi_path):
    """Analiza un archivo MIDI y devuelve estructura con pistas y notas."""
    try:
        import mido
    except ImportError:
        raise RuntimeError(
            "Falta la dependencia 'mido'. Instálala desde el menú "
            "Herramientas → Dependencias, o con: pip install mido")
    midi = mido.MidiFile(midi_path)

    # 1) Primer pase: extraer tempo global
    tempo = 120.0
    for t in midi.tracks:
        for msg in t:
            if msg.type == 'set_tempo':
                tempo = 60000000.0 / msg.tempo
                break
        else:
            continue
        break

    # 2) Segundo pase: parsear cada track
    tracks = []
    for ti, track in enumerate(midi.tracks):
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

        # 3) Convertir note_on/note_off sueltos en notas con duracion
        notes = _extract_notes(events)

        # Filtrar tracks sin notas y sin eventos
        if not notes and not any(e['type'] in ('program_change', 'control_change')
                                  for e in events):
            continue

        # 4) Detectar programa (program_change)
        program = None
        for e in events:
            if e['type'] == 'program_change':
                program = e['program']
                break

        # 5) Canal MIDI (0-15)
        channel = None
        for e in events:
            if e['channel'] is not None:
                channel = e['channel']
                break

        tracks.append({
            'index': ti,
            'name': track.name or f"Track {ti}",
            'channel': channel if channel is not None else 0,
            'program': program if program is not None else 0,
            'events': events,
            'notes': notes,
        })

    return {
        'filename': midi_path,
        'ticks_per_beat': midi.ticks_per_beat,
        'tempo': tempo,
        'duration_seconds': midi.length,
        'tracks': tracks,
        'raw': midi,
    }


def _extract_notes(events):
    """Convierte eventos note_on/note_off en notas con duracion.

    Soporta los 3 formatos MIDI:
    - note_on + note_off
    - note_on velocity=0 (equivale a note_off)
    - note_on sin note_off (dura hasta fin del track)

    Returns:
        list of {pitch, start_tick, duration_tick, velocity, channel}
    """
    notes = []
    active = {}  # (pitch, channel) -> {start_tick, velocity}

    for e in events:
        if e['type'] == 'note_on':
            ch = e.get('channel', 0)
            pitch = e['note']
            vel = e.get('velocity', 0) or 0
            key = (pitch, ch)
            if vel > 0:
                # Note on
                if key in active:
                    # Re-trigger: cerrar la anterior con duracion 0
                    prev = active.pop(key)
                    notes.append({
                        'pitch': pitch,
                        'start_tick': prev['start_tick'],
                        'duration_tick': max(1, e['abs_ticks'] - prev['start_tick']),
                        'velocity': prev['velocity'],
                        'channel': ch,
                    })
                active[key] = {
                    'start_tick': e['abs_ticks'],
                    'velocity': vel,
                }
            else:
                # velocity=0 = note_off (formato running status)
                if key in active:
                    prev = active.pop(key)
                    notes.append({
                        'pitch': pitch,
                        'start_tick': prev['start_tick'],
                        'duration_tick': max(1, e['abs_ticks'] - prev['start_tick']),
                        'velocity': prev['velocity'],
                        'channel': ch,
                    })
        elif e['type'] == 'note_off':
            ch = e.get('channel', 0)
            pitch = e['note']
            key = (pitch, ch)
            if key in active:
                prev = active.pop(key)
                notes.append({
                    'pitch': pitch,
                    'start_tick': prev['start_tick'],
                    'duration_tick': max(1, e['abs_ticks'] - prev['start_tick']),
                    'velocity': prev['velocity'],
                    'channel': ch,
                })

    # Notas que nunca se cerraron: duran hasta el final
    last_tick = max((e['abs_ticks'] for e in events), default=0)
    for (pitch, ch), prev in active.items():
        notes.append({
            'pitch': pitch,
            'start_tick': prev['start_tick'],
            'duration_tick': max(1, last_tick - prev['start_tick']),
            'velocity': prev['velocity'],
            'channel': ch,
        })

    # Ordenar por start_tick
    notes.sort(key=lambda n: (n['start_tick'], n['pitch']))
    return notes


def track_summary(track_data):
    """Resumen de una pista: rango de notas, cantidad, programa."""
    notes = track_data.get('notes', [])
    if not notes:
        # Fallback al parser viejo
        notes = []
        for e in track_data.get('events', []):
            if e['type'] == 'note_on' and e['velocity'] and e['velocity'] > 0:
                notes.append({'pitch': e['note']})
    pitches = [n['pitch'] for n in notes]
    return {
        'notes': len(notes),
        'range': (min(pitches), max(pitches)) if pitches else None,
        'program': track_data.get('program', 0),
    }


def add_note(track_data, pitch, start_tick, duration_tick, velocity=100, channel=None):
    """Añade una nota a la pista. La inserta en orden y agrega eventos note_on+note_off.

    Returns:
        la nota creada
    """
    ch = channel if channel is not None else track_data.get('channel', 0)
    note = {
        'pitch': pitch,
        'start_tick': start_tick,
        'duration_tick': duration_tick,
        'velocity': velocity,
        'channel': ch,
    }
    track_data.setdefault('notes', []).append(note)
    track_data['notes'].sort(key=lambda n: (n['start_tick'], n['pitch']))

    # Sincronizar events[] para que el export MIDI siga funcionando
    events = track_data.setdefault('events', [])
    # Eliminar eventos existentes de esa nota (en caso de overwrite)
    events[:] = [e for e in events
                  if not (e['type'] in ('note_on', 'note_off') and e.get('note') == pitch
                          and e.get('channel') == ch
                          and abs(e['abs_ticks'] - start_tick) < duration_tick)]
    # Agregar note_on
    events.append({
        'type': 'note_on', 'note': pitch, 'velocity': velocity,
        'channel': ch, 'ticks': 0, 'abs_ticks': start_tick,
    })
    # Agregar note_off
    events.append({
        'type': 'note_off', 'note': pitch, 'velocity': 0,
        'channel': ch, 'ticks': 0, 'abs_ticks': start_tick + duration_tick,
    })
    events.sort(key=lambda e: e['abs_ticks'])
    return note


def remove_note(track_data, pitch, start_tick, channel=None):
    """Elimina una nota de la pista (busca por pitch+start_tick+channel)."""
    ch = channel if channel is not None else track_data.get('channel', 0)
    notes = track_data.get('notes', [])
    track_data['notes'] = [
        n for n in notes
        if not (n['pitch'] == pitch and n['start_tick'] == start_tick and n['channel'] == ch)
    ]
    # Eliminar eventos correspondientes
    events = track_data.get('events', [])
    track_data['events'] = [
        e for e in events
        if not (e['type'] in ('note_on', 'note_off')
                and e.get('note') == pitch
                and e.get('channel') == ch
                and abs(e['abs_ticks'] - start_tick) < 10)
    ]


def move_note(track_data, pitch, start_tick, new_pitch=None, new_start_tick=None,
              channel=None):
    """Mueve una nota (cambia pitch y/o start_tick). Mantiene duracion y velocity."""
    ch = channel if channel is not None else track_data.get('channel', 0)
    for n in track_data.get('notes', []):
        if n['pitch'] == pitch and n['start_tick'] == start_tick and n['channel'] == ch:
            if new_pitch is not None:
                n['pitch'] = new_pitch
            if new_start_tick is not None:
                n['start_tick'] = max(0, new_start_tick)
            # Reordenar
            track_data['notes'].sort(key=lambda x: (x['start_tick'], x['pitch']))
            return n
    return None


def resize_note(track_data, pitch, start_tick, new_duration, channel=None):
    """Cambia la duracion de una nota."""
    ch = channel if channel is not None else track_data.get('channel', 0)
    for n in track_data.get('notes', []):
        if n['pitch'] == pitch and n['start_tick'] == start_tick and n['channel'] == ch:
            n['duration_tick'] = max(1, new_duration)
            return n
    return None
