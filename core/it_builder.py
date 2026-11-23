"""Compatibility entry point for building IT files.

The old implementation modified ``templates/bgm.it`` in place. Export now
delegates to the standalone IT writer, which rebuilds all offset tables.
"""

from . import it_writer


def build(midi_data, samples_data, output_path, template_path=None, **kwargs):
    """Build an IT file; ``template_path`` is accepted for old callers only."""
    return it_writer.build(midi_data, samples_data, output_path, **kwargs)

__all__ = ["build"]
