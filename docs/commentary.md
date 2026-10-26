# Adding Commentary to Mergers

This repository supports adding your own commentary and analysis to merger filings. Commentary is stored separately from the scraped ACCC data and is merged during the static data generation process.

## How It Works

1. **Edit `data/processed/commentary.json`** - Add your commentary for any merger using its merger ID
2. **Run `generate_static_data.py`** - The script automatically merges your commentary into the output
3. **Deploy** - Commentary appears on the merger detail page with a distinctive blue callout

## File Structure

Commentary is stored in `data/processed/commentary.json`. Each merger holds a `comments` array, so a matter can collect several comments over time:

```json
{
  "MN-01016": {
    "comments": [
      {
        "commentary": "Your analysis or commentary text here.",
        "tags": ["notable", "beverage", "approved"],
        "date": "2026-01-17",
        "author": "Your Name"
      },
      {
        "commentary": "A follow-up comment added later.",
        "tags": ["update"],
        "date": "2026-02-01"
      }
    ]
  }
}
```

## Fields

All fields inside each comment are optional:

- **`commentary`** (string): Your analysis or commentary text. Supports full **markdown formatting** including:
  - Bold (`**bold**`) and italic (`*italic*`)
  - Lists (bulleted and numbered)
  - Links (`[text](url)`)
  - Headings, code blocks, and more
- **`tags`** (array): Custom tags for categorization (e.g., "notable", "complex", "approved")
- **`date`** (string): ISO date of the comment (YYYY-MM-DD). Comments are shown newest first by this date
- **`author`** (string): Author name (optional)

## Finding Merger IDs

Merger IDs follow these formats:
- **Notifications**: `MN-XXXXX` (e.g., `MN-01016`)
- **Waivers**: `WA-XXXXX` (e.g., `WA-00001`)

You can find merger IDs:
- In the URL: `mergers.fyi/mergers/MN-01016`
- On the merger detail page
- In `data/processed/mergers.json`

## Example Commentary

```json
{
  "MN-01016": {
    "comments": [{
      "commentary": "This acquisition represents Asahi's continued expansion in Australian beverage manufacturing infrastructure.\n\n**Key points:**\n- Phase 1 determination approved\n- No significant competition concerns identified\n- Part of broader consolidation in beverage manufacturing\n\nSee [ACCC's market definition guidance](https://www.accc.gov.au/) for context.",
      "tags": ["beverage", "real-estate", "approved"],
      "date": "2026-01-17"
    }]
  }
}
```

The commentary will render with proper markdown formatting on the site.

## Updating the Site

After editing `data/processed/commentary.json`:

```bash
# Regenerate static data files
python3 -m scripts.generate.generate_static_data

# Commit your changes
git add data/processed/commentary.json frontend/public/data/
git commit -m "Add commentary for MN-01016"
git push
```

Cloudflare Pages deploys the push automatically. Skipping the regenerate step also works: every push to `main` runs `pipeline.yml`, which regenerates the static files and commits them.

## Display

Commentary appears on the merger detail page as a blue callout box with, for each comment:
- A speech bubble icon
- Your commentary text
- Tags (if provided)
- Date (if provided)
- Author name (if provided)

## Notes

- Commentary is version-controlled in git, so you have full history
- The `_README` and `_example` keys in `commentary.json` are ignored (any key starting with `_`)
- Commentary won't be overwritten by the scraper - it's completely separate
- You can add commentary to any merger, past or present
