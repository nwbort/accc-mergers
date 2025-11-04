#!/bin/bash
#
# This script scrapes the ACCC acquisitions register.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Export variables so they are available to subshells spawned by xargs.
export BASE_URL="https://www.accc.gov.au"
export REGISTER_URL="${BASE_URL}/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&items_per_page=20"
export MAIN_PAGE_FILE="acquisitions-register.html"
export SUBFOLDER="matters"
export USER_AGENT="Mozilla/5.0 (compatible; git-scraper-bot/1.0;)" # Be a good citizen

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
  
  # Find all .html files in the current directory and the subfolder
  find . -name "*.html" | while IFS= read -r file; do
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
      "$file"

    # Use a second sed pass for complex multi-line replacements.
    sed -i -E -e ':a;N;$!ba;s#(<a[^>]*class="[^"]*megamenu-page-link-level-3[^"]*"[^>]*href=")[^"]*("[^>]*>[[:space:]]*<span>)[^<]*(</span>)#\1STATIC_HREF\2STATIC_TEXT\3#g' "$file"
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

# 4. Fetch the individual matter pages in parallel
echo "Fetching individual matter pages in parallel..."
echo "$relative_links" | xargs -P 8 -I {} bash -c 'fetch_matter_page "$@"' _ {}

# 5. Clean the downloaded files before committing
clean_html

echo "Scraping process completed successfully."
