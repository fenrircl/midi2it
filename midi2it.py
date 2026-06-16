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

    args = parser.parse_args()

    # GUI mode
    if args.gui or (not args.midi and not args.sf2):
        try:
            from midi2it_gui import main as gui_main
            gui_main()
        except ImportError:
            print("Error: No se pudo cargar la GUI. ¿Falta tkinter?")
            print("Instálalo con: sudo apt install python3-tk")
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

    # 3. Build IT
    print(f"\n🔧 Generando IT...")
    it_builder.build(
        midi_data=midi,
        samples_data=samples,
        output_path=args.output,
        tempo_override=args.tempo or None,
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
