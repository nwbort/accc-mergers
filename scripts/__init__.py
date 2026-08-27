"""Data-pipeline package for the ACCC merger tracker.

Modules here are run as package entry points from the repository root, e.g.::

    python -m scripts.extract_mergers
    python -m scripts.generate.generate_static_data

Running them by file path (``python scripts/extract_mergers.py``) does not
work: the sub-packages import each other absolutely (``from scripts.slug
import slugify``), which needs the repository root on ``sys.path``. ``-m``
puts it there; a path invocation puts the script's own directory there
instead.

Layout:

* top level — ``extract_mergers`` plus the shared helpers (``slug``,
  ``date_utils``, ``normalization``, ``cutoff``, ``merger_filters``) and the
  standalone maintenance scripts.
* ``scrape/``   — fetching from the ACCC register and the Tribunal site.
* ``parse/``    — pulling structure out of the downloaded PDFs.
* ``detect/``   — cross-merger analysis (duplicates, related mergers/parties).
* ``generate/`` — everything that writes the site's published outputs,
  including the ``static_data`` package.
* ``constants/``, ``tools/``, ``tests/``.
"""
