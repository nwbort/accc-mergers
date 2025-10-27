# ACCC mergers register scraper

This repository contains a set of scripts to automatically scrape, parse, and store data from the Australian Competition and Consume Commission's (ACCC) public mergers register.

## Data

The primary data outputs of this project are:

*   **`mergers.json`**: a json array where each object represents a single merger. The structure of a merger object includes:
    * `merger_name`: the name of the merger;
    * `status`: the current assessment status (e.g., "assessment completed", "under assessment");
    * `merger_id`: the unique identifier for the merger;
    * `effective_notification_datetime`: the effective notification date;
    * `acquirers` & `targets`: a list of the companies involved;
    * `anszic_codes`: relevant anzsic industry codes;
    * `merger_description`: a summary of the merger; and
    * `attachments`: a list of associated documents with their titles, dates, and urls.

*   **`matters/`**: this directory stores the raw html file for each merger, named by its id (e.g., [`matters/MN-01016.html`](/matters/MN-01016.html)). It also contains subdirectories for each merger that holds its downloaded attachments.