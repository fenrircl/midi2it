#!/usr/bin/env python3
"""
midi2it — MIDI + SoundFont → IT para SNES
CLI: Convierte MIDI+SF2 a .it compatible con smconv de PVSNESlib.

Uso:
    python3 midi2it.py entrada.mid entrada.sf2 -o salida.it
    python3 midi2it.py entrada.mid -g   # abre GUI
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))

from core import midi_parser, sf2_parser, it_builder


def main():
    parser = argparse.ArgumentParser(
        description='midi2it — MIDI + SoundFont → IT para SNES',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s cancion.mid DraculaX.sf2 -o cancion.it
  %(prog)s cancion.mid -g                          # abrir GUI
  %(prog)s cancion.mid DraculaX.sf2 -o cancion.it --tempo 140
        """)
    parser.add_argument('midi', nargs='?', help='Archivo MIDI de entrada')
    parser.add_argument('sf2', nargs='?', help='Archivo SoundFont (.sf2)')
    parser.add_argument('-o', '--output', default='output.it', help='Archivo IT de salida')
    parser.add_argument('--tempo', type=float, default=0, help='Tempo forzado (BPM)')
    parser.add_argument('-g', '--gui', action='store_true', help='Abrir interfaz gráfica')
    parser.add_argument('-v', '--verbose', action='store_true', help='Mostrar información detallada')
    parser.add_argument('--snes', action='store_true', help='Limitar samples para SNES y validar presupuesto BRR')
    parser.add_argument('--max-sample-sec', type=float, default=3.0, help='Duración máxima por sample en segundos (default: 3.0)')
    parser.add_argument('--max-pcm-kb', type=float, default=None,
                        help='Límite PCM opcional en KB (modo --snes: default 96)')
    parser.add_argument('--max-brr-kb', type=float, default=48, help='Presupuesto BRR estimado en KB (default: 48)')
    parser.add_argument('--rows-per-beat', type=int, default=4, help='Resolución del patrón (filas por beat, default: 4)')

    args = parser.parse_args()

    # GUI mode
    if args.gui or (not args.midi and not args.sf2):
        try:
            from midi2it_gui import main as gui_main
            gui_main()
        except ImportError:
            print("Error: No se pudo cargar la GUI. ¿Falta tkinter?")
            if os.name == 'nt':
                print("En Windows: reinstala Python desde python.org con la opción 'tcl/tk and IDLE' marcada.")
            else:
                print("En Linux: sudo apt install python3-tk")
                print("En macOS: brew install python-tk")
        return

    if not args.midi or not args.sf2:
        parser.print_help()
        return

    # CLI mode
    print("🎵 midi2it — MIDI + SF2 → IT para SNES")
    print("=" * 45)

    # 1. Parse MIDI
    print(f"\n📥 MIDI: {args.midi}")
    midi = midi_parser.parse(args.midi)
    print(f"   Tempo: {midi['tempo']:.1f} BPM")
    print(f"   Duración: {midi['duration_seconds']:.1f}s")
    print(f"   Pistas: {len(midi['tracks'])}")

    # 2. Parse SF2
    print(f"\n📦 SF2: {args.sf2}")
    samples = sf2_parser.parse(args.sf2)
    print(f"   Samples extraídos: {len(samples)}")

    # El CLI también debe asignar un sample real a cada pista MIDI.
    program_samples = sf2_parser.extract_instrument_programs(args.sf2)
    track_config = []
    available_ids = set(samples)
    for i, track in enumerate(midi['tracks']):
        program = track.get('program', 0)
        sample_index = program_samples.get(program)
        if sample_index not in available_ids:
            sample_index = next(iter(samples), None)
            if sample_index is not None:
                print(f"   Aviso: programa {program} sin sample disponible; se usará {samples[sample_index]['name']}")
        track_config.append({
            'midi_track': track.get('index', i),
            'program': program,
            'sample_index': sample_index,
            'volume': 100,
            'transpose': 0,
            'solo': False,
            'mute': False,
            'name': track.get('name', f'Track {i}'),
        })

    # 3. Build IT
    print(f"\n🔧 Generando IT...")
    snes_kwargs = {
        'max_sample_sec': args.max_sample_sec,
        'max_brr_kb': args.max_brr_kb,
    }
    if args.snes:
        snes_kwargs['max_total_pcm_kb'] = args.max_pcm_kb if args.max_pcm_kb is not None else 96
        print(f"   🎮 Modo SNES: max {args.max_sample_sec}s por sample, "
              f"presupuesto {args.max_brr_kb}KB BRR estimado")
    elif args.max_pcm_kb is not None:
        snes_kwargs['max_total_pcm_kb'] = args.max_pcm_kb
    it_builder.build(
        midi_data=midi,
        samples_data=samples,
        output_path=args.output,
        track_config=track_config,
        tempo_override=args.tempo or None,
        rows_per_beat=args.rows_per_beat,
        **snes_kwargs,
    )

    size_kb = os.path.getsize(args.output) / 1024
    print(f"✅ IT creado: {args.output} ({size_kb:.1f} KB)")

    # 4. Validate
    try:
        import subprocess
        r = subprocess.run(['openmpt123', '--info', args.output],
                          capture_output=True, text=True, timeout=10)
        for line in r.stdout.split('\n'):
            if any(x in line for x in ['Instruments:', 'Samples:', 'Tracker:']):
                print(f"   {line.strip()}")
    except:
        pass

    print(f"\n📋 Para usar en tu proyecto:")
    print(f"   cp \"{args.output}\" mvp/res/forest_loop.it")
    print(f"   cd mvp && make")


if __name__ == '__main__':
    main()
