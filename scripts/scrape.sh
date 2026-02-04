#!/bin/bash
#
# This script scrapes the ACCC acquisitions register.
#
# Usage:
#   ./scrape.sh [--all]
#
# Options:
#   --all    Scrape all mergers, ignoring cutoff dates (by default, mergers
#            are skipped 3 weeks after an approved notification or waiver decision)

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Parse Arguments ---
SCRAPE_ALL=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      SCRAPE_ALL=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--all]"
      exit 1
      ;;
  esac
done

# --- Configuration ---
# Export variables so they are available to subshells spawned by xargs.
export BASE_URL="https://www.accc.gov.au"
export REGISTER_URL="${BASE_URL}/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&items_per_page=50"
export MAIN_PAGE_FILE="data/raw/acquisitions-register.html"
export SUBFOLDER="data/raw/matters"
export USER_AGENT="Mozilla/5.0 (compatible; git-scraper-bot/1.0;)" # Be a good citizen
export MERGERS_JSON="data/processed/mergers.json"
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Functions ---

# Function to fetch and process a single matter page.
# It's designed to be called by xargs for parallel execution.
fetch_matter_page() {
  local link="$1"
  local full_url="${BASE_URL}${link}"
  
  echo "  - Fetching: $full_url"
  
  local temp_html
  temp_html=$(mktemp)
  # Ensure temp file is cleaned up when the function returns
  trap 'rm -f "$temp_html"' RETURN

  # Download the page. The --fail flag ensures curl exits with an error on HTTP failures (like 404).
  if ! curl -s -L -A "$USER_AGENT" --fail "$full_url" -o "$temp_html"; then
      echo "  - FAILED to fetch: $full_url"
      # Returning a non-zero status will cause xargs to stop
      return 1
  fi
  
  # Extract matter number
  local matter_number
  matter_number=$(cat "$temp_html" | pup '.field--name-dynamic-token-fieldnode-acccgov-merger-id p text{}' | tr -d '[:space:]')
  
  local filename
  if [ -n "$matter_number" ]; then
    filename="${SUBFOLDER}/${matter_number}.html"
    mv "$temp_html" "$filename"
  else
    # Fallback in case matter number isn't found
    local fallback_name
    fallback_name=$(basename "$link")
    filename="${SUBFOLDER}/${fallback_name}.html"
    mv "$temp_html" "$filename"
    echo "    Warning: Could not find matter number for $full_url. Used fallback name: $fallback_name"
  fi
}
# Export the function so it's available to subshells spawned by xargs
export -f fetch_matter_page

# Function to clean dynamic content from HTML files
clean_html() {
  echo "Cleaning dynamic content from all downloaded HTML files..."
  
  # Find .html files in the root, data/raw, and the matters subfolder
  { find . -maxdepth 1 -name "*.html"; find "data/raw" -maxdepth 1 -name "*.html" 2>/dev/null; find "./$SUBFOLDER" -maxdepth 1 -name "*.html" 2>/dev/null; } | while IFS= read -r file; do
    echo "  - Cleaning $file"
    
    # Use sed to perform in-place replacements for simple line-based patterns.
    # The -E flag enables extended regular expressions.
    # Each '-e' adds another expression to the command.
    sed -i -E \
      -e 's/js-view-dom-id-[a-f0-9]{64}/js-view-dom-id-STATIC/g' \
      -e 's/(id="edit-submit-accc-search-site--)[^"]+"/\1STATIC"/g' \
      -e 's/(css\/css_)[^.]+\.css/\1STATIC.css/g' \
      -e 's/(js\/js_)[^.]+\.js/\1STATIC.js/g' \
      -e 's/("libraries":")[^"]+"/\1STATIC_LIBRARIES"/g' \
      -e 's/("permissionsHash":")[^"]+"/\1STATIC_HASH"/g' \
      -e 's/("view_dom_id":")[a-f0-9]{64}/\1STATIC"/g' \
      -e 's/(views_dom_id:)[a-f0-9]{64}/\1STATIC/g' \
      -e 's/include=[^"&>]+/include=STATIC/g' \
      -e 's/href="https:\/\/app\.readspeaker\.com\/[^"]+"/href="STATIC_READSPEAKER_URL"/g' \
      -e 's/(icons\.svg\?t)[^#]+#/\1STATIC#/g' \
      -e 's/(\?t)[^">]+/\1STATIC/g' \
      -e 's/("css_js_query_string":")[^"]+"/\1STATIC"/g' \
      "$file"

    # Use a second sed pass for complex multi-line replacements.
    sed -i -E -e ':a;N;$!ba;s#(<a[^>]*class="[^"]*megamenu-page-link-level-3[^"]*"[^>]*href=")[^"]*("[^>]*>[[:space:]]*<span>)[^<]*(</span>)#\1STATIC_HREF\2STATIC_TEXT\3#g' "$file"

    # Squeeze multiple consecutive blank lines into a single blank line.
    # This prevents unnecessary diffs when the server adds/removes blank lines.
    temp_file=$(mktemp)
    cat -s "$file" > "$temp_file" && mv "$temp_file" "$file"
  done

  echo "Cleaning complete."
}


# --- Main Script ---

# 1. Download the main acquisitions list page
echo "Downloading main register page from $REGISTER_URL..."
curl -s -L -A "$USER_AGENT" "$REGISTER_URL" -o "$MAIN_PAGE_FILE"
echo "Saved main page to '$MAIN_PAGE_FILE'"

# 2. Create the subdirectory for individual acquisition pages
mkdir -p "$SUBFOLDER"

# 3. Extract relative links
echo "Extracting links from main page..."
relative_links=$(cat "$MAIN_PAGE_FILE" | pup '.accc-collapsed-card__header a attr{href}' | grep -v '#card-' | tr -d '\r')

if [ -z "$relative_links" ]; then
  echo "Warning: No acquisition links found on the main page. The website structure might have changed."
  exit 0
fi

# 4. Filter out links for mergers past cutoff (unless --all is specified)
if [ "$SCRAPE_ALL" = true ]; then
  echo "Scraping all mergers (--all flag specified)"
  links_to_fetch="$relative_links"
else
  # Get list of URL paths to skip from cutoff.py
  skip_paths_file=$(mktemp)
  trap 'rm -f "$skip_paths_file"' EXIT

  if [ -f "$MERGERS_JSON" ]; then
    python3 "$SCRIPT_DIR/cutoff.py" --paths "$MERGERS_JSON" > "$skip_paths_file" 2>/dev/null || true
  fi

  skip_count=$(wc -l < "$skip_paths_file" | tr -d ' ')
  if [ "$skip_count" -gt 0 ]; then
    echo "Skipping $skip_count merger(s) past cutoff date (use --all to scrape all)"

    # Filter out links that are in the skip list
    links_to_fetch=$(echo "$relative_links" | while IFS= read -r link; do
      if ! grep -qF "$link" "$skip_paths_file" 2>/dev/null; then
        echo "$link"
      fi
    done)
  else
    links_to_fetch="$relative_links"
  fi
fi

link_count=$(echo "$links_to_fetch" | grep -c . || true)
if [ "$link_count" -eq 0 ]; then
  echo "No mergers to fetch (all are past cutoff)."
  clean_html
  echo "Scraping process completed successfully."
  exit 0
fi

echo "Fetching $link_count merger page(s)..."

# 5. Fetch the individual matter pages in parallel
echo "$links_to_fetch" | xargs -P 8 -I {} bash -c 'fetch_matter_page "$@"' _ {}

# 6. Clean the downloaded files before committing
clean_html

echo "Scraping process completed successfully."
