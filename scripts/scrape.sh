#!/bin/bash
#
# This script scrapes the ACCC acquisitions register.
#
# Usage:
#   ./scrape.sh [--all]
#   ./scrape.sh --clean-file <path>
#
# Options:
#   --all              Scrape all mergers, ignoring cutoff dates (by default,
#                      mergers are skipped 3 weeks after an approved notification
#                      or waiver decision)
#   --clean-file <path>  Apply HTML cleaning to a single file and exit. Used by
#                        the pipeline to re-clean files after a git rebase.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Parse Arguments ---
SCRAPE_ALL=false
CLEAN_FILE_PATH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      SCRAPE_ALL=true
      shift
      ;;
    --clean-file)
      if [[ -z "${2:-}" ]]; then
        echo "Error: --clean-file requires a file path argument"
        echo "Usage: $0 --clean-file <path>"
        exit 1
      fi
      CLEAN_FILE_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--all] | $0 --clean-file <path>"
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
export USER_AGENT="Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)"
export MERGERS_JSON="data/processed/mergers.json"
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PARALLEL_JOBS=24

# --- Functions ---

# Function to clean dynamic content from a single HTML file.
# Exported so it can be called from subshells spawned by xargs.
clean_file() {
  local file="$1"

  # Single-pass perl rewrite. Slurp mode (-0777) lets the multi-line patterns
  # (BOOMR script, dcterms/canonical reorder, megamenu) work alongside the
  # line-scoped ones. Negated classes include \n so line-scoped patterns can't
  # accidentally span lines under slurp mode.
  perl -i -0777 -pe '
    s/js-view-dom-id-[a-f0-9]{64}/js-view-dom-id-STATIC/g;
    s/(id="edit-submit-accc-search-site--)[^"\n]+"/${1}STATIC"/g;
    s/(data-drupal-selector="form-)[^"\n]+(" type="hidden" name="form_build_id")/${1}STATIC${2}/g;
    s/(name="form_build_id" value="form-)[^"\n]+"/${1}STATIC"/g;
    s/(css\/css_)[^.\n]+\.css/${1}STATIC.css/g;
    s/(js\/js_)[^.\n]+\.js/${1}STATIC.js/g;
    s/("libraries":")[^"\n]+"/${1}STATIC_LIBRARIES"/g;
    s/("permissionsHash":")[^"\n]+"/${1}STATIC_HASH"/g;
    s/("view_dom_id":")[a-f0-9]{64}/${1}STATIC"/g;
    s/(views_dom_id:)[a-f0-9]{64}/${1}STATIC/g;
    s/include=[^"&>\n]+/include=STATIC/g;
    s/href="https:\/\/app\.readspeaker\.com\/[^"\n]+"/href="STATIC_READSPEAKER_URL"/g;
    s/(icons\.svg\?t)[^#\n]+#/${1}STATIC#/g;
    s/(\?t)[^">\n]+/${1}STATIC/g;
    s/("css_js_query_string":")[^"\n]+"/${1}STATIC"/g;
    s/[ \t]*\n[ \t]*<script>!function\(e\)\{var n="https:\/\/s\.go-mpulse\.net\/boomerang\/".*?\(window\);<\/script><\/head>/\n  <\/head>/s;
    s{(<meta name="dcterms\.modified"[^\n]*/>\n)(<meta name="dcterms\.created"[^\n]*/>\n)}{$2$1}g;
    s{(<link rel="canonical"[^\n]*/>\n)(<link rel="shortlink"[^\n]*/>\n)}{$2$1}g;
    s#(<a[^>]*class="[^"]*megamenu-page-link-level-3[^"]*"[^>]*href=")[^"]*("[^>]*>[[:space:]]*<span>)[^<]*(</span>)#${1}STATIC_HREF${2}STATIC_TEXT${3}#g;
    s/\n{3,}/\n\n/g;
  ' "$file"
}
# Export the function so it's available to subshells spawned by xargs
export -f clean_file

# Function to clean dynamic content from all HTML files (used with --all)
clean_html() {
  local files_list
  files_list=$(mktemp)
  trap 'rm -f "$files_list"' RETURN
  {
    find . -maxdepth 1 -name "*.html"
    find "data/raw" -maxdepth 1 -name "*.html" 2>/dev/null
    find "./$SUBFOLDER" -maxdepth 1 -name "*.html" 2>/dev/null
  } > "$files_list"

  local file_count
  file_count=$(wc -l < "$files_list" | tr -d ' ')

  if [ "$file_count" -eq 0 ]; then
    echo "No HTML files to clean."
    return
  fi

  echo "Cleaning dynamic content from $file_count HTML file(s) in parallel..."
  xargs -P "$PARALLEL_JOBS" -I {} bash -c 'clean_file "$1"' _ {} < "$files_list"
  echo "Successfully cleaned $file_count HTML file(s)"
}

# Function to fetch and process a single matter page.
# It's designed to be called by xargs for parallel execution.
fetch_matter_page() {
  local link="$1"
  local full_url="${BASE_URL}${link}"

  local temp_html
  temp_html=$(mktemp)
  # Ensure temp file is cleaned up when the function returns
  trap 'rm -f "$temp_html"' RETURN

  # Download the page. The --fail flag ensures curl exits with an error on HTTP failures (like 404).
  if ! curl -s -L --compressed -A "$USER_AGENT" --fail "$full_url" -o "$temp_html"; then
      echo "FAILED: $full_url" >&2
      # Returning a non-zero status will cause xargs to stop
      return 1
  fi

  # Extract matter number
  local matter_number
  matter_number=$(pup '.field--name-dynamic-token-fieldnode-acccgov-merger-id p text{}' < "$temp_html" | tr -d '[:space:]')

  # Whitelist the matter number to a safe filename pattern to prevent path
  # traversal if the upstream site ever returns unexpected content. Expected
  # values look like "MN-12345" or "WA-12345".
  if [[ -n "$matter_number" && ! "$matter_number" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "    Warning: Rejected unsafe matter number '$matter_number' for $full_url" >&2
    matter_number=""
  fi

  local filename
  if [ -n "$matter_number" ]; then
    filename="${SUBFOLDER}/${matter_number}.html"
    mv "$temp_html" "$filename"
  else
    # Fallback in case matter number isn't found or was rejected. basename strips
    # any leading path, and we additionally scrub anything outside a safe set.
    local fallback_name
    fallback_name=$(basename "$link")
    fallback_name=$(echo "$fallback_name" | tr -cd 'A-Za-z0-9_.-')
    if [ -z "$fallback_name" ]; then
      echo "    Warning: Skipping $full_url (no safe filename)" >&2
      return 1
    fi
    filename="${SUBFOLDER}/${fallback_name}.html"
    mv "$temp_html" "$filename"
    echo "    Warning: Could not find matter number for $full_url. Used fallback name: $fallback_name"
  fi

  clean_file "$filename"

}
# Export the function so it's available to subshells spawned by xargs
export -f fetch_matter_page

# Function to fetch a single register page into PAGE_TEMP_DIR.
# Exported so it can be called from subshells spawned by xargs.
fetch_register_page() {
  local page="$1"
  curl -s -L --compressed -A "$USER_AGENT" "${REGISTER_URL}&page=${page}" -o "${PAGE_TEMP_DIR}/page_${page}.html"
}
export -f fetch_register_page

# If called with --clean-file, just clean the specified file and exit.
# This mode is used by the pipeline to re-clean files after a git rebase.
if [ -n "$CLEAN_FILE_PATH" ]; then
  clean_file "$CLEAN_FILE_PATH"
  exit 0
fi

# --- Main Script ---

# 1. Download the first page of the acquisitions register
echo "Downloading main register page from $REGISTER_URL..."

# Up to 2 attempts (1 retry) with 30-second per-attempt timeout. Curl handles
# the retry/backoff itself.
if curl -s -L --compressed -A "$USER_AGENT" \
     --max-time 30 --retry 1 --retry-delay 30 --retry-max-time 90 \
     "$REGISTER_URL" -o "$MAIN_PAGE_FILE"; then
  echo "Saved main page to '$MAIN_PAGE_FILE'"
  clean_file "$MAIN_PAGE_FILE"
else
  echo "Failed to download main page after retries"
  exit 1
fi

# 2. Create the subdirectory for individual acquisition pages
mkdir -p "$SUBFOLDER"

# 3. Handle pagination and extract relative links from all pages
echo "Extracting links from register pages..."

# Extract links from the first page
relative_links=$(pup '.accc-collapsed-card__header a attr{href}' < "$MAIN_PAGE_FILE" | grep -v '#card-' | tr -d '\r')

# Check if there are additional pages by looking for the "Go to last page" link.
# pup does not decode HTML entities in attributes, so we decode &amp; to & with sed.
last_page_href=$(pup 'a[title="Go to last page"] attr{href}' < "$MAIN_PAGE_FILE" | sed 's/&amp;/\&/g' | tr -d '\r')

if [ -n "$last_page_href" ]; then
  # Extract the page number from the href (e.g. "?init=1&items_per_page=20&page=2" -> "2")
  last_page=$(echo "$last_page_href" | grep -oP '[?&]page=\K[0-9]+' || true)

  if [ -n "$last_page" ] && [ "$last_page" -gt 0 ]; then
    echo "Register has $(( last_page + 1 )) pages. Fetching additional pages in parallel..."

    PAGE_TEMP_DIR=$(mktemp -d)
    export PAGE_TEMP_DIR

    seq 1 "$last_page" | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'fetch_register_page "$@"' _ {}

    for (( page=1; page<=last_page; page++ )); do
      page_file="${PAGE_TEMP_DIR}/page_${page}.html"
      if [ -f "$page_file" ]; then
        page_links=$(pup '.accc-collapsed-card__header a attr{href}' < "$page_file" | grep -v '#card-' | tr -d '\r')
        if [ -n "$page_links" ]; then
          relative_links=$(printf '%s\n%s' "$relative_links" "$page_links")
        fi
      fi
    done

    rm -rf "$PAGE_TEMP_DIR"
  fi
fi

if [ -z "$relative_links" ]; then
  echo "Warning: No acquisition links found on the register. The website structure might have changed."
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

    # Filter out links that exactly match a skip path. Single grep call vs.
    # spawning one per link.
    links_to_fetch=$(grep -vxFf "$skip_paths_file" <<< "$relative_links" || true)
  else
    links_to_fetch="$relative_links"
  fi
fi

link_count=$(echo "$links_to_fetch" | grep -c . || true)
if [ "$link_count" -eq 0 ]; then
  echo "No mergers to fetch (all are past cutoff)."
  echo "Scraping process completed successfully."
  exit 0
fi

echo "Fetching $link_count merger page(s)..."

# 5. Fetch the individual matter pages in parallel
# Capture any failures from stderr
failed_urls_file=$(mktemp)
trap 'rm -f "$failed_urls_file"' EXIT

if echo "$links_to_fetch" | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'fetch_matter_page "$@"' _ {} 2>"$failed_urls_file"; then
  # All succeeded
  echo "Successfully fetched $link_count merger page(s)"
else
  # Some failed - xargs returns non-zero if any command failed
  failed_count=$(grep -c "^FAILED:" "$failed_urls_file" 2>/dev/null || echo "0")
  success_count=$((link_count - failed_count))

  echo "Successfully fetched $success_count merger page(s)"

  if [ "$failed_count" -gt 0 ]; then
    echo "$failed_count merger page(s) unsuccessful:"
    grep "^FAILED:" "$failed_urls_file" | sed 's/^FAILED: /- /'
  fi
fi

# 6. When scraping all mergers, re-clean everything (files were also cleaned inline,
#    but a full pass ensures consistency for files downloaded in previous runs).
if [ "$SCRAPE_ALL" = true ]; then
  clean_html
fi

echo "Scraping process completed successfully."
