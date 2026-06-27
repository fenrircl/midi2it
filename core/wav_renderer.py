"""
core/wav_renderer.py — Renderiza MIDI a WAV usando FluidSynth.
Soporta render del MIDI completo (mezclado) o de 1 pista individual.
"""
import os, subprocess, tempfile


def render_full_mix(midi_path, sf2_path, output_wav=None, sample_rate=44100):
    """Renderiza el MIDI completo a WAV con todos los canales mezclados.

    Returns:
        ruta al WAV generado, o None si falla
    """
    if not output_wav:
        fd, output_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

    try:
        result = subprocess.run(
            ['fluidsynth', '-F', output_wav, '-r', str(sample_rate),
             '-i', sf2_path, midi_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return None
        if not os.path.exists(output_wav) or os.path.getsize(output_wav) < 100:
            return None
        return output_wav
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def render_single_track(midi_path, sf2_path, track_index, output_wav=None,
                        sample_rate=44100):
    """Renderiza UNA pista del MIDI a WAV (mutea el resto).

    Args:
        midi_path: ruta al MIDI
        sf2_path: ruta al SoundFont
        track_index: indice de la pista a reproducir (0-based)
        output_wav: ruta destino (opcional)
        sample_rate: Hz

    Returns:
        ruta al WAV, o None
    """
    import mido

    if not output_wav:
        fd, output_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

    # 1) Crear MIDI temporal solo con la pista solicitada
    try:
        src = mido.MidiFile(midi_path)
    except Exception:
        return None

    out = mido.MidiFile(type=0)  # type 0 = single track
    # Concatenar todas las pistas pero solo dejar audio de la pista track_index
    # en el canal 0, el resto en canal 1 (muteable con fluidsynth)

    # Estrategia simple: copiar todos los eventos a la pista 0
    # Cambiar canales: la pista target -> canal 0, resto -> canal 1
    # Luego usar fluidsynth -c 0 -L 1 (solo canal 0 audible)

    merged = mido.MidiTrack()
    target_track = None
    if track_index < len(src.tracks):
        target_track = src.tracks[track_index]

    if target_track:
        for msg in target_track:
            if hasattr(msg, 'channel') and msg.type in ('note_on', 'note_off',
                                                        'program_change',
                                                        'control_change',
                                                        'pitchwheel',
                                                        'polytouch', 'aftertouch'):
                # Re-mapear a canal 0
                merged.append(msg.copy(channel=0))
            else:
                merged.append(msg.copy())
    # Agregar meta de tempo del primer track que tenga set_tempo
    for t in src.tracks:
        for m in t:
            if m.type == 'set_tempo':
                merged.append(m.copy())
                break
        else:
            continue
        break

    out.tracks.append(merged)

    # 2) Guardar MIDI temporal
    fd, tmp_midi = tempfile.mkstemp(suffix='.mid')
    os.close(fd)
    out.save(tmp_midi)

    # 3) Renderizar con fluidsynth restringido a canal 0
    try:
        # -c 0: solo canal 0 audible. -L 0: solo enviar a canal 0 (silencia resto)
        # El truco: si nuestra pista esta en canal 0, -c 0 la deja audible
        result = subprocess.run(
            ['fluidsynth', '-F', output_wav, '-r', str(sample_rate),
             '-c', '0', '-L', '0', sf2_path, tmp_midi],
            capture_output=True, text=True, timeout=120
        )
        # Limpiar midi temp
        try:
            os.unlink(tmp_midi)
        except Exception:
            pass
        if result.returncode != 0:
            return None
        if not os.path.exists(output_wav) or os.path.getsize(output_wav) < 100:
            return None
        return output_wav
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            os.unlink(tmp_midi)
        except Exception:
            pass
        return None


def play_wav(wav_path, on_end=None):
    """Reproduce un WAV con ffplay. Devuelve el proceso.

    Args:
        wav_path: ruta al WAV
        on_end: callback cuando termina

    Returns:
        subprocess.Popen
    """
    import shutil
    ffplay = shutil.which('ffplay')
    if not ffplay:
        return None

    p = subprocess.Popen(
        [ffplay, '-nodisp', '-autoexit', '-loglevel', 'quiet', wav_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    if on_end:
        def waiter():
            p.wait()
            try:
                on_end()
            except Exception:
                pass
        import threading
        threading.Thread(target=waiter, daemon=True).start()

    return p
