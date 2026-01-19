# Data Directory

This directory contains all data files for the ACCC Mergers Tracker, organized by processing stage.

## Structure

### raw/
Raw data scraped from the ACCC website:
- `acquisitions-register.html` - Main acquisitions register page
- `*.html` - Individual merger page HTML files
- `MN-*/` - Subdirectories containing merger documents (PDFs, DOCX files)

### processed/
Processed/intermediate data files:
- `mergers.json` - Master merger data extracted from HTML
- `questionnaire_data.json` - Questionnaire metadata
- `commentary.json` - Commentary data

## Data Pipeline Flow

```
raw/ → processed/ → ../merger-tracker/frontend/public/data/
```

1. **Scraping**: ACCC website → `raw/`
2. **Extraction**: `raw/` → `processed/` (via Python scripts)
3. **Generation**: `processed/` → `frontend/public/data/` (production-ready JSON)
