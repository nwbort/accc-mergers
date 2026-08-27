"""Commentary index — ``commentary.json``."""


def _appeal_summary(m: dict) -> dict | None:
    """Slim appeal fields needed to render the status badge's appeal suffix.

    Mirrors ``outputs/list.py``'s ``_appeal_summary`` — only the lifecycle
    status and the concluded result are carried, not the full documents list.
    Returns ``None`` when the merger has no tribunal appeal.
    """
    appeal = m.get('appeal')
    if not appeal:
        return None
    return {
        'status': appeal.get('status'),
        'outcome': appeal.get('outcome'),
        'effective_determination': appeal.get('effective_determination'),
    }


def generate(mergers: list, commentary: dict) -> dict:
    """Return the commentary.json payload for mergers with user commentary."""
    items = []

    for m in mergers:
        merger_id = m.get('merger_id', '')
        if merger_id in commentary:
            comm = commentary[merger_id]

            # Find determination event URL
            determination_url = None
            for event in m.get('events', []):
                if event.get('is_determination_event'):
                    determination_url = event.get('url_gh') or event.get('url')
                    break

            item = {
                "merger_id": merger_id,
                "merger_name": m.get('merger_name'),
                "status": m.get('status'),
                "accc_determination": m.get('accc_determination'),
                "is_waiver": m.get('is_waiver', False),
                "effective_notification_datetime": m.get('effective_notification_datetime'),
                "determination_publication_date": m.get('determination_publication_date'),
                "determination_url": determination_url,
                "stage": m.get('stage'),
                "acquirers": m.get('acquirers', []),
                "targets": m.get('targets', []),
                "anzsic_codes": m.get('anzsic_codes', []),
                "comments": comm.get('comments', []),
            }
            if m.get('under_appeal'):
                item["under_appeal"] = True
                appeal = _appeal_summary(m)
                if appeal:
                    item["appeal"] = appeal
            items.append(item)

    # Sort by most recent comment date descending
    def get_latest_comment_date(item):
        dates = [c.get('date', '') for c in item.get('comments', []) if c.get('date')]
        return max(dates) if dates else ''

    items.sort(key=get_latest_comment_date, reverse=True)

    return {
        "items": items,
        "count": len(items),
    }
