"""
core/wav_renderer.py — Renderiza MIDI a WAV usando FluidSynth.
Soporta render del MIDI completo (mezclado) o de 1 pista individual.
"""
import os, subprocess, tempfile


def _hidden_process_options():
    """Hide console windows for native audio tools on Windows."""
    if os.name != 'nt':
        return {}
    options = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    options['startupinfo'] = startupinfo
    return options


def _prepare_preview_midi(midi_path, tempo_bpm=None, track_config=None,
                          only_track=None):
    """Create a temporary MIDI with the current GUI track and tempo settings."""
    import mido

    midi = mido.MidiFile(midi_path)
    configs = {item.get('midi_track'): item for item in (track_config or [])}
    has_solo = any(item.get('solo') for item in configs.values())
    initial_tempo = 500000
    for track in midi.tracks:
        tempo_event = next((msg for msg in track if msg.type == 'set_tempo'), None)
        if tempo_event:
            initial_tempo = tempo_event.tempo
            break
    source_bpm = 60000000 / initial_tempo
    tempo_ratio = source_bpm / float(tempo_bpm) if tempo_bpm else 1.0

    output = mido.MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    for midi_index, track in enumerate(midi.tracks):
        cfg = configs.get(midi_index, {})
        keep_track = (only_track is None or midi_index == only_track)
        muted = cfg.get('mute', False) or (has_solo and not cfg.get('solo', False))
        if not keep_track or muted:
            continue

        channel = next((msg.channel for msg in track if hasattr(msg, 'channel')), 0)
        program = cfg.get('program')
        events = []
        if program is not None:
            events.append(mido.Message('program_change', channel=channel,
                                       program=max(0, min(127, int(program))), time=0))
        for msg in track:
            if program is not None and msg.type == 'program_change':
                continue
            if msg.type == 'set_tempo' and tempo_bpm:
                events.append(msg.copy(tempo=max(1, int(msg.tempo * tempo_ratio))))
                continue
            if hasattr(msg, 'channel') and msg.type in ('note_on', 'note_off'):
                transpose = int(cfg.get('transpose', 0) or 0)
                velocity = msg.velocity
                if msg.type == 'note_on' and velocity > 0:
                    velocity = max(1, min(127, round(velocity *
                                      float(cfg.get('volume', 100) or 0) / 100)))
                msg = msg.copy(note=max(0, min(127, msg.note + transpose)),
                               velocity=velocity)
            events.append(msg.copy())
        if tempo_bpm and not any(msg.type == 'set_tempo' for msg in events):
            events.insert(0, mido.MetaMessage(
                'set_tempo', tempo=max(1, int(60000000 / float(tempo_bpm))), time=0))
        output_track = mido.MidiTrack()
        output_track.extend(events)
        output.tracks.append(output_track)

    fd, temp_path = tempfile.mkstemp(suffix='.mid')
    os.close(fd)
    output.save(temp_path)
    return temp_path


def _tool_and_env(name):
    """Resolve system or downloaded portable tools and expose adjacent DLLs."""
    from core import deps

    executable = deps.executable(name)
    if not executable:
        return None, None
    env = os.environ.copy()
    tool_dir = os.path.dirname(executable)
    env['PATH'] = tool_dir + os.pathsep + env.get('PATH', '')
    return executable, env


def render_full_mix(midi_path, sf2_path, output_wav=None, sample_rate=44100,
                    tempo_bpm=None, track_config=None):
    """Renderiza el MIDI completo a WAV con todos los canales mezclados.

    Returns:
        ruta al WAV generado, o None si falla
    """
    if not output_wav:
        fd, output_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

    fluidsynth, env = _tool_and_env('fluidsynth')
    if not fluidsynth:
        return None
    preview_midi = None
    render_midi = midi_path
    if tempo_bpm is not None or track_config is not None:
        try:
            preview_midi = _prepare_preview_midi(
                midi_path, tempo_bpm=tempo_bpm, track_config=track_config)
            render_midi = preview_midi
        except Exception:
            return None
    try:
        result = subprocess.run(
            [fluidsynth, '-F', output_wav, '-r', str(sample_rate),
             '-i', sf2_path, render_midi],
            capture_output=True, text=True, timeout=120, env=env,
            **_hidden_process_options()
        )
        if result.returncode != 0:
            return None
        if not os.path.exists(output_wav) or os.path.getsize(output_wav) < 100:
            return None
        return output_wav
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        if preview_midi:
            try:
                os.unlink(preview_midi)
            except OSError:
                pass


def render_single_track(midi_path, sf2_path, track_index, output_wav=None,
                        sample_rate=44100, tempo_bpm=None, track_config=None):
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
    if not output_wav:
        fd, output_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

    fluidsynth, env = _tool_and_env('fluidsynth')
    if not fluidsynth:
        return None
    tmp_midi = None
    try:
        tmp_midi = _prepare_preview_midi(midi_path, tempo_bpm=tempo_bpm,
                                         track_config=track_config,
                                         only_track=track_index)
        import mido
        single = mido.MidiFile(tmp_midi)
        for track in single.tracks:
            for index, msg in enumerate(track):
                if hasattr(msg, 'channel'):
                    track[index] = msg.copy(channel=0)
        single.type = 0
        single.save(tmp_midi)
    except Exception:
        if tmp_midi:
            try:
                os.unlink(tmp_midi)
            except OSError:
                pass
        return None
    try:
        result = subprocess.run(
            [fluidsynth, '-F', output_wav, '-r', str(sample_rate),
             '-i', sf2_path, tmp_midi],
            capture_output=True, text=True, timeout=120, env=env,
            **_hidden_process_options()
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
        except OSError:
            pass
        return None


def render_configured_mix(midi_path, fallback_sf2, tempo_bpm, track_config,
                          output_wav=None, sample_rate=44100):
    """Render a GUI mix, honoring per-track instruments and SoundFonts."""
    soundfonts = {
        item.get('sf2_path') or fallback_sf2
        for item in (track_config or [])
        if not item.get('mute') and (item.get('sf2_path') or fallback_sf2)
    }
    soundfonts = {path for path in soundfonts if path}
    if len(soundfonts) <= 1:
        return render_full_mix(
            midi_path, next(iter(soundfonts), fallback_sf2), output_wav=output_wav,
            sample_rate=sample_rate, tempo_bpm=tempo_bpm,
            track_config=track_config)

    ffmpeg, env = _tool_and_env('ffmpeg')
    if not ffmpeg:
        return None
    if not output_wav:
        fd, output_wav = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

    configs = {item.get('midi_track'): item for item in (track_config or [])}
    has_solo = any(item.get('solo') for item in configs.values())
    rendered = []
    try:
        for midi_track, config in configs.items():
            if config.get('mute') or (has_solo and not config.get('solo')):
                continue
            sf2_path = config.get('sf2_path') or fallback_sf2
            if not sf2_path:
                continue
            fd, track_wav = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            rendered.append(track_wav)
            if not render_single_track(
                    midi_path, sf2_path, midi_track, output_wav=track_wav,
                    sample_rate=sample_rate, tempo_bpm=tempo_bpm,
                    track_config=track_config):
                return None
        if not rendered:
            return None
        args = [ffmpeg, '-y']
        for track_wav in rendered:
            args.extend(['-i', track_wav])
        inputs = ''.join(f'[{i}:a]' for i in range(len(rendered)))
        args.extend(['-filter_complex',
                     f'{inputs}amix=inputs={len(rendered)}:duration=longest:'
                     'dropout_transition=0:normalize=0',
                     '-c:a', 'pcm_s16le', output_wav])
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=180, env=env, **_hidden_process_options())
        if result.returncode != 0 or not os.path.exists(output_wav) \
                or os.path.getsize(output_wav) < 100:
            return None
        return output_wav
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        for track_wav in rendered:
            try:
                os.unlink(track_wav)
            except OSError:
                pass


def play_wav(wav_path, on_end=None):
    """Reproduce un WAV con ffplay. Devuelve el proceso.

    Args:
        wav_path: ruta al WAV
        on_end: callback cuando termina

    Returns:
        subprocess.Popen
    """
    ffplay, env = _tool_and_env('ffplay')
    if not ffplay:
        return None

    p = subprocess.Popen(
        [ffplay, '-nodisp', '-autoexit', '-loglevel', 'quiet', wav_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
        **_hidden_process_options()
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
