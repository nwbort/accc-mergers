"""Waiver → notification refile tracker — ``refiled-notifications.json``.

Surfaces every merger originally filed as a waiver application, declined,
and later re-filed as a formal notification — the ``waiver_refiled`` pairs
recorded in ``related_mergers.json``. Companion view to the Phase 2 tracker
(``phase2.py``). Relies on ``link_related_mergers`` having already attached
``related_merger`` to each merger (see :func:`static_data.enrichment`).
"""


def _entry(waiver: dict, notification: dict) -> dict:
    return {
        'waiver_id': waiver.get('merger_id'),
        'waiver_name': waiver.get('merger_name'),
        'waiver_filed_date': waiver.get('effective_notification_datetime'),
        'waiver_declined_date': waiver.get('determination_publication_date'),
        'notification_id': notification.get('merger_id'),
        'notification_name': notification.get('merger_name'),
        'notification_filed_date': notification.get('effective_notification_datetime'),
        'notification_status': notification.get('status'),
        'notification_determination': notification.get('accc_determination'),
        'notification_determination_date': notification.get('determination_publication_date'),
    }


def generate(mergers: list) -> dict:
    """Return the refiled-notifications.json payload.

    ``current`` holds pairs whose notification hasn't been determined yet;
    ``completed`` holds pairs where the notification has a determination.
    """
    by_id = {m.get('merger_id'): m for m in mergers if m.get('merger_id')}

    current = []
    completed = []
    for merger in mergers:
        related = merger.get('related_merger')
        if not related or related.get('relationship') != 'refiled_as':
            continue
        notification = by_id.get(related.get('merger_id'))
        if not notification:
            continue
        entry = _entry(merger, notification)
        if entry['notification_determination'] and entry['notification_determination_date']:
            completed.append(entry)
        else:
            current.append(entry)

    # Current: most recently filed notification first (freshest matter on top).
    current.sort(key=lambda e: e['notification_filed_date'] or '', reverse=True)
    # Completed: most recently determined first.
    completed.sort(key=lambda e: e['notification_determination_date'] or '', reverse=True)

    return {
        'current': current,
        'completed': completed,
        'count': {'current': len(current), 'completed': len(completed)},
    }
