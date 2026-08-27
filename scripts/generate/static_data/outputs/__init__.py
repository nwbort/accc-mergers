"""Output generators — one module per generated JSON artefact.

Each module exposes a ``generate(mergers, output_dir, ...)`` function that writes
one or more JSON files into ``output_dir`` (or returns a dict for the orchestrator
to write, for the small single-file outputs).
"""
