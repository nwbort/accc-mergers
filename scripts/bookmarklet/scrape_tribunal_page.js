// Tribunal matter page snapshot bookmarklet.
//
// Runs in the browser, on an already-loaded tribunal matter page (after
// Cloudflare's JS challenge has been solved by the real browser), and
// downloads a JSON snapshot of the document table(s) on the page. That file
// is later fed to `scripts/ingest_tribunal_snapshot.py`, which folds it into
// `data/processed/tribunal_appeals.json` exactly like scrape_tribunal.py
// would — see scripts/bookmarklet/README.md for the end-to-end flow.
//
// This is a deliberate DOM port of the parsing logic in scrape_tribunal.py
// (contentRoot/headerFieldMap/bodyRows/parseDocumentRow/parseMatterPage
// mirror _content_root/_header_field_map/_body_rows/parse_document_row/
// parse_matter_page there, and the normalise* helpers mirror the
// like-named Python functions). If you change the parsing rules on the
// Python side, update this file to match, then run `build.py` to
// regenerate the installable bookmarklet + install.html.
(function () {
  'use strict';

  function collapse(text) {
    return (text || '').split(/\s+/).filter(Boolean).join(' ');
  }

  // Column header keyword -> document field. First match wins per column,
  // same order/semantics as _COLUMN_KEYWORDS in scrape_tribunal.py.
  var COLUMN_KEYWORDS = [
    ['date', 'date'],
    ['filed_by', 'filed'],
    ['filed_by', 'lodged'],
    ['filed_by', 'submitted'],
    ['filed_by', 'party'],
    ['filed_by', 'author'],
    ['confidentiality', 'confiden'],
    ['description', 'document'],
    ['description', 'description'],
    ['description', 'title'],
    ['description', 'name'],
  ];

  // Trailing "(PDF, 537.8 KB)"-style annotation stripped from descriptions,
  // matching _FILE_ANNOTATION_RE.
  var FILE_ANNOTATION_RE = /\s*\((?:PDF|DOCX?|XLSX?|PPTX?|RTF|ZIP|TXT|HTML?)\b[^)]*\)\s*$/i;

  var MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
  ];
  var MONTH_NUMBER = {};
  MONTHS.forEach(function (name, idx) {
    MONTH_NUMBER[name] = idx + 1;
    MONTH_NUMBER[name.slice(0, 3)] = idx + 1;
  });

  function pad2(n) {
    return String(n).length < 2 ? '0' + n : String(n);
  }

  // Mirrors normalise_date: tries each known format, else returns the text
  // unchanged (never throws on an unrecognised format).
  function normaliseDate(value) {
    if (!value) return null;
    var text = collapse(value);
    var m;
    if ((m = text.match(/^(\d{4})-(\d{2})-(\d{2})$/))) {
      return text;
    }
    if ((m = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/))) {
      return m[3] + '-' + pad2(m[2]) + '-' + pad2(m[1]);
    }
    if ((m = text.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/))) {
      return m[3] + '-' + pad2(m[2]) + '-' + pad2(m[1]);
    }
    if ((m = text.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/))) {
      var monthNum = MONTH_NUMBER[m[2].toLowerCase()];
      if (monthNum) {
        return m[3] + '-' + pad2(monthNum) + '-' + pad2(m[1]);
      }
    }
    return text || null;
  }

  function cleanDescription(value) {
    if (!value) return null;
    var text = collapse(value).replace(FILE_ANNOTATION_RE, '').trim();
    return text || null;
  }

  function normaliseConfidentiality(value) {
    if (!value) return null;
    var text = collapse(value).toLowerCase();
    if (text.indexOf('non') !== -1 && text.indexOf('confiden') !== -1) return 'Non-confidential';
    if (text.indexOf('confiden') !== -1) return 'Confidential';
    return collapse(value) || null;
  }

  // Mirrors _content_root: best-effort main-content container so header/
  // footer tables (nav, related links, etc.) aren't picked up.
  function contentRoot() {
    var selectors = ['main', '[role="main"]', '.region-content', '#content'];
    for (var i = 0; i < selectors.length; i++) {
      var node = document.querySelector(selectors[i]);
      if (node) return node;
    }
    return document;
  }

  // Mirrors _header_field_map.
  function headerFieldMap(table) {
    var headerCells = Array.prototype.slice.call(table.querySelectorAll('thead th'));
    if (headerCells.length === 0) {
      var firstRow = table.querySelector('tr');
      headerCells = firstRow ? Array.prototype.slice.call(firstRow.querySelectorAll('th,td')) : [];
    }
    var fieldMap = {};
    headerCells.forEach(function (cell, idx) {
      var header = collapse(cell.textContent).toLowerCase();
      for (var i = 0; i < COLUMN_KEYWORDS.length; i++) {
        var field = COLUMN_KEYWORDS[i][0];
        var keyword = COLUMN_KEYWORDS[i][1];
        if (header.indexOf(keyword) !== -1 && !(idx in fieldMap)) {
          fieldMap[idx] = field;
          break;
        }
      }
    });
    return fieldMap;
  }

  // Mirrors _body_rows: skip the header row when there's no explicit tbody.
  function bodyRows(table) {
    var tbody = table.querySelector('tbody');
    if (tbody) return Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var rows = Array.prototype.slice.call(table.querySelectorAll('tr'));
    return rows.slice(1);
  }

  // Mirrors parse_document_row.
  function parseDocumentRow(row, fieldMap, baseUrl) {
    var cells = Array.prototype.slice.call(row.querySelectorAll('td,th'));
    if (cells.length === 0) return null;

    var doc = { date: null, filed_by: null, description: null, confidentiality: null, url: null };

    cells.forEach(function (cell, idx) {
      var field = fieldMap[idx];
      var text = collapse(cell.textContent);
      if (doc.url === null) {
        var link = cell.querySelector('a[href]');
        if (link) {
          try {
            doc.url = new URL(link.getAttribute('href'), baseUrl).href;
          } catch (e) {
            doc.url = link.getAttribute('href');
          }
          if (!text) text = collapse(link.textContent);
        }
      }
      if (field && !doc[field]) doc[field] = text;
    });

    doc.date = normaliseDate(doc.date);
    doc.description = cleanDescription(doc.description);
    doc.confidentiality = normaliseConfidentiality(doc.confidentiality);

    if (!doc.url && !doc.description) return null;
    return doc;
  }

  // Mirrors parse_matter_page: first table has section = null, later tables
  // carry the nearest preceding <h3> text as section.
  function parseMatterPage() {
    var root = contentRoot();
    var nodes = Array.prototype.slice.call(root.querySelectorAll('h3, table'));
    var documents = [];
    var currentSection = null;
    var tableIndex = 0;
    var baseUrl = location.href;

    nodes.forEach(function (node) {
      if (node.tagName === 'H3') {
        currentSection = collapse(node.textContent) || null;
        return;
      }
      var section = tableIndex === 0 ? null : currentSection;
      tableIndex += 1;

      var fieldMap = headerFieldMap(node);
      if (Object.keys(fieldMap).length === 0) return;

      bodyRows(node).forEach(function (row) {
        var doc = parseDocumentRow(row, fieldMap, baseUrl);
        if (!doc) return;
        if (section !== null) doc.section = section;
        documents.push(doc);
      });
    });

    return documents;
  }

  function downloadJson(filename, payload) {
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  var documents = parseMatterPage();
  if (documents.length === 0) {
    alert(
      'Tribunal scrape bookmarklet: no document tables found on this page.\n\n' +
      'Make sure you\'re on a matter page (not the matter list), and that the ' +
      'page has finished loading.'
    );
    return;
  }

  var slug = location.pathname.replace(/\/+$/, '').split('/').pop() || 'tribunal-matter';
  var filename = 'tribunal-' + slug + '.json';
  downloadJson(filename, {
    tribunal_url: location.href,
    scraped_at: new Date().toISOString(),
    documents: documents,
  });

  alert(
    'Downloaded ' + filename + ' — ' + documents.length + ' document(s) found.\n\n' +
    'Run: python scripts/ingest_tribunal_snapshot.py ~/Downloads/' + filename
  );
})();
