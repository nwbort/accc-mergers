"""Static data generation package.

Splits what used to live in ``scripts/generate_static_data.py`` into focused
modules:

- :mod:`static_data.business_days` — business day / calendar day arithmetic.
- :mod:`static_data.loaders` — load commentary, questionnaire, related merger data.
- :mod:`static_data.filters` — waiver / suspended merger filters.
- :mod:`static_data.enrichment` — ``enrich_merger`` and phase helpers.
- :mod:`static_data.outputs` — one submodule per generated JSON artefact.

The orchestrator (``scripts/generate_static_data.py``) stitches these together
and remains the CLI entry point used by GitHub Actions workflows.
"""
