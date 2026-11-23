"""Compatibility entry point for building IT files.

The old implementation modified ``templates/bgm.it`` in place. Export now
delegates to the standalone IT writer, which rebuilds all offset tables.
"""

from . import it_writer


def build(midi_data, samples_data, output_path, template_path=None, **kwargs):
    """Build an IT file; ``template_path`` is accepted for old callers only."""
    return it_writer.build(midi_data, samples_data, output_path, **kwargs)


def estimate_brr(midi_data, samples_data, track_config, **kwargs):
    """Estimate BRR use without writing an IT file."""
    return it_writer.estimate_brr(midi_data, samples_data, track_config, **kwargs)


def suggest_max_sample_sec(midi_data, samples_data, track_config, **kwargs):
    """Suggest the longest per-sample duration that fits the BRR limit."""
    return it_writer.suggest_max_sample_sec(
        midi_data, samples_data, track_config, **kwargs)


__all__ = ["build", "estimate_brr", "suggest_max_sample_sec"]
