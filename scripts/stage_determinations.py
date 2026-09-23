"""Which phase each of a matter's determinations belongs to.

The register carries a single headline determination per matter
(``accc_determination`` + ``determination_publication_date``) beside its
current ``stage``, and the pipeline used to read the phase of a determination
straight off that stage. That holds for Phase 1 and Phase 2, but not for the
public benefit phase: a public benefit application follows a Phase 2
determination, so when the stage moves to "Public benefit phase" the headline
either still shows the Phase 2 outcome or is blanked until the public benefit
determination lands. Either way, reading the phase off the current stage loses
the Phase 2 determination or files it under the wrong phase.

So the determination each phase reached is recorded as it is seen, keyed by
phase (``merger_status.PHASES``), and carried forward from one scrape to the
next in ``stage_determinations``::

    {"Phase 2": {"determination": "Not approved",
                 "date": "2026-09-22T12:00:00Z",
                 "stage": "Phase 2 - detailed assessment"}}

A headline determination is attributed to the current stage's phase only if it
is *newer* than every determination already recorded for another phase — a
headline dated on or before the Phase 2 determination, shown under the public
benefit stage, is the Phase 2 determination still on the page, not a new one.

The record is only persisted when it says something the headline doesn't (a
phase other than the current one), so the ordinary matter carries no extra
field. The very first public benefit scrape still has what it needs: the
previous snapshot, taken while the matter was in Phase 2, is folded in too.
"""

from scripts.constants import merger_status

FIELD = 'stage_determinations'


def _day(value: str | None) -> str:
    return (value or '')[:10]


def _headline_entry(merger: dict) -> tuple[str | None, dict | None]:
    """``(phase, entry)`` for the matter's headline determination, if it has one."""
    det = merger.get('accc_determination')
    date = merger.get('determination_publication_date')
    stage = merger.get('stage')
    phase = merger_status.stage_phase(stage)
    if not (det and date and phase) or phase == merger_status.WAIVER:
        return None, None
    return phase, {'determination': det, 'date': date, 'stage': stage}


def _carried_over_from(records: dict, phase: str, entry: dict) -> str | None:
    """The other phase whose determination ``entry`` is still showing, if any."""
    for other, recorded in records.items():
        if other != phase and _day(recorded.get('date')) >= _day(entry['date']):
            return other
    return None


def _fold_in(records: dict, merger: dict | None) -> None:
    if not merger:
        return
    for phase, recorded in (merger.get(FIELD) or {}).items():
        if isinstance(recorded, dict) and recorded.get('determination'):
            records[phase] = dict(recorded)
    phase, entry = _headline_entry(merger)
    if phase and not _carried_over_from(records, phase, entry):
        records[phase] = entry


def resolve(merger: dict, previous: dict | None = None) -> dict:
    """Every phase's determination for ``merger``, keyed by phase.

    ``previous`` is the matter's last stored snapshot, when there is one; its
    record and headline are folded in first so the current page can only add
    to what was already known.
    """
    records: dict = {}
    _fold_in(records, previous)
    _fold_in(records, merger)
    return records


def headline_phase(merger: dict, records: dict) -> str | None:
    """The phase the headline determination actually belongs to.

    The current stage's phase, unless the headline is a determination already
    recorded for an earlier phase (the Phase 2 outcome still showing once the
    stage has moved on to the public benefit phase).
    """
    phase, entry = _headline_entry(merger)
    if not phase:
        return None
    return _carried_over_from(records, phase, entry) or phase


def to_persist(merger: dict, records: dict) -> dict | None:
    """The record worth storing on ``merger``, or None when the headline says it all."""
    current = merger_status.stage_phase(merger.get('stage'))
    if any(phase != current for phase in records):
        return records
    return None
