#!/bin/bash
#
# This script scrapes the ACCC acquisitions register.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
BASE_URL="https://www.accc.gov.au"
REGISTER_URL="${BASE_URL}/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1"
MAIN_PAGE_FILE="acquisitions-register.html"
SUBFOLDER="matters"
USER_AGENT="Mozilla/5.0 (compatible; git-scraper-bot/1.0;)" # Be a good citizen

# --- Functions ---

# Function to clean dynamic content from HTML files
clean_html() {
  echo "Cleaning dynamic content from all downloaded HTML files..."
  
  # Find all .html files in the current directory and the subfolder
  find . -name "*.html" | while IFS= read -r file; do
    echo "  - Cleaning $file"
    
    # Use sed to perform in-place replacements.
    # The -E flag enables extended regular expressions.
    # Each '-e' adds another expression to the command.
    sed -i -E \
      -e 's/js-view-dom-id-[a-f0-9]{64}/js-view-dom-id-STATIC/g' \
      -e 's/("views_dom_id:)[a-f0-9]{64}/\1STATIC"/g' \
      -e 's/(id="edit-submit-accc-search-site--)[^"]+"/\1STATIC"/g' \
      -e 's/(js\/js_)[^.]+\.js/\1STATIC.js/g' \
      "$file"
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

# 4. Loop through each link, download the page, and save it
echo "$relative_links" | while IFS= read -r link; do
  full_url="${BASE_URL}${link}"
  
  echo "  - Fetching: $full_url"
  
  temp_html=$(mktemp)
  curl -s -L -A "$USER_AGENT" "$full_url" -o "$temp_html"
  
  # Extract matter number
  matter_number=$(cat "$temp_html" | pup '.field--name-dynamic-token-fieldnode-acccgov-merger-id p text{}' | tr -d '[:space:]')
  
  if [ -n "$matter_number" ]; then
    filename="${SUBFOLDER}/${matter_number}.html"
    mv "$temp_html" "$filename"
  else
    fallback_name=$(basename "$link")
    filename="${SUBFOLDER}/${fallback_name}.html"
    mv "$temp_html" "$filename"
  fi
  
  # Politeness delay to avoid overwhelming the server
  sleep 1
done

# 5. Clean the downloaded files before committing
clean_html

echo "Scraping process completed successfully."
