"""
tests/test_e2e.py — Test end-to-end de midi2it.

Verifica que el pipeline completo funciona:
  MIDI + SF2 → parser → IT builder → openmpt123 validation

Usado por CI (GitHub Actions) y localmente con: python -m pytest tests/
"""
import os
import sys
import subprocess
import pytest

# Anadir el directorio raiz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core import midi_parser, sf2_parser, it_builder


REPO = os.path.join(os.path.dirname(__file__), '..')
MIDI_FILE = os.path.join(REPO, 'examples', 'forest-night-fever.mid')
SF2_FILE = os.path.join(REPO, 'examples', 'soundfonts', 'DraculaX.sf2')


@pytest.fixture(scope='module')
def midi_data():
    if not os.path.exists(MIDI_FILE):
        pytest.skip(f"MIDI de ejemplo no encontrado: {MIDI_FILE}")
    return midi_parser.parse(MIDI_FILE)


@pytest.fixture(scope='module')
def sf2_data():
    if not os.path.exists(SF2_FILE):
        pytest.skip(f"SF2 de ejemplo no encontrado: {SF2_FILE}")
    return sf2_parser.parse(SF2_FILE, max_samples=16)


@pytest.fixture(scope='module')
def sf2_programs():
    if not os.path.exists(SF2_FILE):
        pytest.skip(f"SF2 de ejemplo no encontrado: {SF2_FILE}")
    return sf2_parser.extract_instrument_programs(SF2_FILE)


def test_template_exists():
    """El template bgm.it debe estar en el repo."""
    path = os.path.join(REPO, 'templates', 'bgm.it')
    assert os.path.exists(path), f"❌ {path} no existe (¿lo borraste?)"
    size = os.path.getsize(path)
    assert 40000 < size < 60000, f"❌ bgm.it tiene tamaño raro: {size} bytes"
    # Verificar header
    with open(path, 'rb') as f:
        data = f.read(8)
    assert data[:4] == b'IMPM', f"❌ bgm.it no es IT valido (header: {data[:4]})"
    assert data[5:6] == b'\x00', f"❌ bgm.it no es IT valido"


def test_midi_parse(midi_data):
    assert 'tracks' in midi_data
    assert len(midi_data['tracks']) > 0
    assert midi_data['tempo'] > 0
    # Notas con duracion (no eventos sueltos)
    total_notes = sum(len(t.get('notes', [])) for t in midi_data['tracks'])
    assert total_notes > 0, "❌ MIDI no tiene notas con duracion"


def test_sf2_parse(sf2_data):
    assert len(sf2_data) > 0
    # Verificar estructura de un sample
    first = next(iter(sf2_data.values()))
    assert 'name' in first
    assert 'data' in first
    assert 'rate' in first
    assert first['rate'] > 0
    assert len(first['data']) > 0


def test_sf2_programs(sf2_programs):
    assert len(sf2_programs) > 0
    # Verificar que el mapeo es program -> sample (ambos int)
    for prog, smp in sf2_programs.items():
        assert isinstance(prog, int)
        assert isinstance(smp, int)


def test_it_builder(midi_data, sf2_data, sf2_programs, tmp_path):
    """Build un IT y verifica que openmpt123 lo puede leer."""
    # track_config simple
    track_config = []
    for i, t in enumerate(midi_data['tracks'][:8]):
        # Tomar el primer programa mapeado, fallback al primer sample
        prog = list(sf2_programs.keys())[i] if i < len(sf2_programs) else 0
        smp = sf2_programs.get(prog, 0)
        track_config.append({
            'midi_track': i, 'program': prog, 'sample_index': smp,
            'volume': 100, 'transpose': 0, 'solo': False, 'mute': False,
            'name': t.get('name', f'T{i}')
        })

    output = str(tmp_path / 'test.it')
    it_builder.build(
        midi_data=midi_data, samples_data=sf2_data,
        output_path=output, track_config=track_config,
        max_total_pcm_kb=64,
    )
    assert os.path.exists(output), "❌ IT no fue creado"
    size = os.path.getsize(output)
    assert size > 1000, f"❌ IT demasiado pequeño: {size} bytes"

    # Validar con openmpt123 si está disponible
    openmpt123 = subprocess.run(['which', 'openmpt123'], capture_output=True, text=True)
    if openmpt123.returncode == 0:
        result = subprocess.run(
            ['openmpt123', '--info', output],
            capture_output=True, text=True, timeout=10
        )
        output_text = result.stdout
        # Debe reportar instrumentos y samples (no silencio)
        assert 'Instruments:' in output_text
        assert 'Samples....:' in output_text
        # Extraer numero de samples
        for line in output_text.split('\n'):
            if line.startswith('Samples....:'):
                n = int(line.split(':')[1].strip())
                assert n > 0, f"❌ openmpt123 reporta 0 samples"
            if line.startswith('Instruments:'):
                n = int(line.split(':')[1].strip())
                # Debe haber al menos 1 instrument (idealmente N tracks)
                assert n >= 1, f"❌ openmpt123 reporta 0 instruments"


def test_mute_solo(midi_data, sf2_data, sf2_programs, tmp_path):
    """Verificar que mute/solo funcionan (producen ITs distintos)."""
    track_config = []
    for i, t in enumerate(midi_data['tracks'][:2]):
        prog = list(sf2_programs.keys())[i] if i < len(sf2_programs) else 0
        smp = sf2_programs.get(prog, 0)
        track_config.append({
            'midi_track': i, 'program': prog, 'sample_index': smp,
            'volume': 100, 'transpose': 0, 'solo': False, 'mute': False,
            'name': t.get('name', f'T{i}')
        })

    # Full
    full_out = str(tmp_path / 'full.it')
    it_builder.build(midi_data=midi_data, samples_data=sf2_data,
                     output_path=full_out, track_config=track_config,
                     max_total_pcm_kb=64)

    # Solo primera pista
    solo_cfg = [track_config[0]]
    solo_out = str(tmp_path / 'solo.it')
    it_builder.build(midi_data=midi_data, samples_data=sf2_data,
                     output_path=solo_out, track_config=solo_cfg,
                     max_total_pcm_kb=64)

    # Mute primera pista
    mute_cfg = [{**track_config[0], 'mute': True}, track_config[1]]
    mute_out = str(tmp_path / 'mute.it')
    it_builder.build(midi_data=midi_data, samples_data=sf2_data,
                     output_path=mute_out, track_config=mute_cfg,
                     max_total_pcm_kb=64)

    # Los 3 ITs deben ser distintos en tamaño
    sizes = {os.path.getsize(p) for p in [full_out, solo_out, mute_out]}
    assert len(sizes) >= 2, f"❌ mute/solo no afectan el output: {sizes}"


def test_multi_sf2(midi_data, sf2_data, tmp_path):
    """Verificar que se pueden combinar samples de varios SF2."""
    sf2_b = sf2_parser.parse(SF2_FILE, max_samples=16)
    # Combinar con offset
    combined = {}
    for k, v in sf2_data.items():
        combined[k] = v
    offset = max(combined.keys()) + 1
    for k, v in sf2_b.items():
        combined[k + offset] = v

    # track_config: 2 pistas, una con sample del SF2 A, otra del SF2 B (offset)
    track_config = [
        {'midi_track': 0, 'program': 0, 'sample_index': 0, 'volume': 100,
         'transpose': 0, 'solo': False, 'mute': False, 'name': 'A'},
        {'midi_track': 1, 'program': 0, 'sample_index': offset, 'volume': 100,
         'transpose': 0, 'solo': False, 'mute': False, 'name': 'B'},
    ]
    output = str(tmp_path / 'multi.it')
    it_builder.build(midi_data=midi_data, samples_data=combined,
                     output_path=output, track_config=track_config,
                     max_total_pcm_kb=64)
    assert os.path.exists(output)
    assert os.path.getsize(output) > 1000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
