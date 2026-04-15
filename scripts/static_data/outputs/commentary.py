"""Commentary index — ``commentary.json``."""


def generate(mergers: list, commentary: dict) -> dict:
    """Return the commentary.json payload for mergers with user commentary."""
    items = []

    for m in mergers:
        merger_id = m.get('merger_id', '')
        if merger_id in commentary:
            comm = commentary[merger_id]

            # Find determination event URL
            determination_url = None
            det_date = m.get('determination_publication_date')
            if det_date:
                for event in m.get('events', []):
                    if (event.get('date') == det_date and
                            'determination' in event.get('title', '').lower()):
                        determination_url = event.get('url_gh') or event.get('url')
                        break

            items.append({
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
            })

    # Sort by most recent comment date descending
    def get_latest_comment_date(item):
        dates = [c.get('date', '') for c in item.get('comments', []) if c.get('date')]
        return max(dates) if dates else ''

    items.sort(key=get_latest_comment_date, reverse=True)

    return {
        "items": items,
        "count": len(items),
    }
