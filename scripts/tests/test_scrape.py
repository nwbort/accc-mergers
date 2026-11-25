"""Tests for scripts/scrape/scrape.py — the register scraper.

The cleaner is the part that has to be exact. It replaced a perl one-liner in
scrape.sh, and every page in data/raw/matters/ was written by that perl: if
the two disagreed by a byte, the first run after the switch would rewrite
every stored matter page. The real-page fixtures were cleaned by the perl, and
the synthetic expectations below were taken from it too, so these tests pin
the port to the original rather than to itself.
"""

import gzip
from pathlib import Path

import pytest

from scripts.paths import REPO_ROOT
from scripts.scrape import scrape

FIXTURES = Path(__file__).parent / 'fixtures' / 'scrape'
STORED_MATTERS = REPO_ROOT / 'data' / 'raw' / 'matters'


def _fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / name).read_bytes())


# --- clean_html_bytes ------------------------------------------------------

@pytest.mark.parametrize('merger_id', ['MN-01064', 'WA-75008'])
def test_cleaner_matches_perl_on_real_pages(merger_id):
    """Raw pages as the ACCC served them, against what scrape.sh's perl wrote."""
    raw = _fixture(f'{merger_id}.raw.html.gz')
    expected = _fixture(f'{merger_id}.cleaned.html.gz')
    assert raw != expected  # the fixture really does carry per-request churn
    assert scrape.clean_html_bytes(raw) == expected


@pytest.mark.parametrize('merger_id', ['MN-01064', 'WA-75008'])
def test_cleaner_is_idempotent(merger_id):
    cleaned = _fixture(f'{merger_id}.cleaned.html.gz')
    assert scrape.clean_html_bytes(cleaned) == cleaned


def test_stored_matter_pages_are_already_clean():
    """Every stored page is a fixed point of cleaning and trimming, so a
    re-clean (--all, --clean-stored, or the pipeline's post-rebase pass)
    can't rewrite unchanged matters."""
    pages = sorted(STORED_MATTERS.glob('*.html'))
    if not pages:
        pytest.skip('no stored matter pages in this checkout')
    dirty = [p.name for p in pages if scrape.prepare_page(p.read_bytes())[0] != p.read_bytes()]
    assert dirty == []


def test_stored_matter_pages_are_trimmed():
    """No stored page fell back to being kept whole."""
    pages = sorted(STORED_MATTERS.glob('*.html'))
    if not pages:
        pytest.skip('no stored matter pages in this checkout')
    untrimmed = [p.name for p in pages if b'role="contentinfo"' in p.read_bytes()]
    assert untrimmed == []


# Inputs and the perl's output for each, run through scrape.sh's clean_file.
PERL_CASES = {
    # The ?t rule runs over what the icons.svg rule left behind, so the
    # fragment goes too. Odd, but it is what every stored page says.
    'rule order': (
        b'<use href="/themes/icons.svg?t123abc#icon-search"/>\n<img src="/a.png?tok=1" alt="x">\n',
        b'<use href="/themes/icons.svg?tSTATIC"/>\n<img src="/a.png?tSTATIC" alt="x">\n',
    ),
    'pair reordering': (
        b'<link rel="canonical" href="https://x/a" />\n<link rel="shortlink" href="https://x/node/1" />\n'
        b'<meta name="dcterms.modified" content="2026-01-02" />\n'
        b'<meta name="dcterms.created" content="2026-01-01" />\n',
        b'<link rel="shortlink" href="https://x/node/1" />\n<link rel="canonical" href="https://x/a" />\n'
        b'<meta name="dcterms.created" content="2026-01-01" />\n'
        b'<meta name="dcterms.modified" content="2026-01-02" />\n',
    ),
    # A line-scoped rule must not reach across a newline in the slurped file.
    'line scoped': (
        b'<input id="edit-submit-accc-search-site--abc\nxyz" />\n'
        b'<input id="edit-submit-accc-search-site--Q1w2" />\n',
        b'<input id="edit-submit-accc-search-site--abc\nxyz" />\n'
        b'<input id="edit-submit-accc-search-site--STATIC" />\n',
    ),
    # The settings blob and megamenu rules had no /g, and do span lines.
    'first only, multi-line': (
        b'<script type="application/json" data-drupal-selector="drupal-settings-json">{"a":\n1}</script>\n'
        b'<script type="application/json" data-drupal-selector="drupal-settings-json">{"b":2}</script>\n'
        b'<nav class="accc-entity-hierarchy-megamenu" id="m">\n<a>1</a>\n</nav>'
        b'<nav class="accc-entity-hierarchy-megamenu"><a>2</a></nav>\n',
        b'<script type="application/json" data-drupal-selector="drupal-settings-json">STATIC_DRUPAL_SETTINGS</script>\n'
        b'<script type="application/json" data-drupal-selector="drupal-settings-json">{"b":2}</script>\n'
        b'<nav class="accc-entity-hierarchy-megamenu" id="m">STATIC_MEGAMENU</nav>'
        b'<nav class="accc-entity-hierarchy-megamenu"><a>2</a></nav>\n',
    ),
    'boomerang and blank lines': (
        b'<title>x</title>\n    \n  <script>!function(e){var n="https://s.go-mpulse.net/boomerang/";\n'
        b'foo}(window);</script></head>\n<body>\n\n\n\n\n<p>a</p>\n',
        b'<title>x</title>\n\n  </head>\n<body>\n\n<p>a</p>\n',
    ),
    'asset and form tokens': (
        b'<link href="/files/css/css_AbC-12_x.css?delta=0&amp;include=eJx1Ugzz" />\n'
        b'<script src="/files/js/js_Zz9.js?scope=footer"></script>\n'
        b'<a href="https://app.readspeaker.com/cgi-bin/rsent?customerid=1&amp;url=x">listen</a>\n'
        b'<div class="js-view-dom-id-' + b'ab' * 32 + b'"></div>\n'
        b'<div id="edit-actions--42"></div>\n'
        b'<input data-drupal-selector="form-AbC_1-x" type="hidden" name="form_build_id" value="form-AbC_1-x" />\n',
        b'<link href="/files/css/css_STATIC.css?delta=0&amp;include=STATIC" />\n'
        b'<script src="/files/js/js_STATIC.js?scope=footer"></script>\n'
        b'<a href="STATIC_READSPEAKER_URL">listen</a>\n'
        b'<div class="js-view-dom-id-STATIC"></div>\n'
        b'<div id="edit-actions"></div>\n'
        b'<input data-drupal-selector="form-STATIC" type="hidden" name="form_build_id" value="form-STATIC" />\n',
    ),
}


@pytest.mark.parametrize('raw, expected', PERL_CASES.values(), ids=PERL_CASES.keys())
def test_cleaner_matches_perl_on_each_rule(raw, expected):
    assert scrape.clean_html_bytes(raw) == expected


def test_clean_file_rewrites_only_when_needed(tmp_path):
    path = tmp_path / 'page.html'
    raw, expected = PERL_CASES['asset and form tokens']
    path.write_bytes(raw)
    assert scrape.clean_file(path) is True
    assert path.read_bytes() == expected
    assert scrape.clean_file(path) is False


def test_clean_file_cli(tmp_path):
    path = tmp_path / 'page.html'
    raw, expected = PERL_CASES['boomerang and blank lines']
    path.write_bytes(raw)
    assert scrape.main(['--clean-file', str(path)]) == 0
    assert path.read_bytes() == expected
    assert scrape.main(['--clean-file', str(tmp_path / 'missing.html')]) == 1


# --- trim_chrome -----------------------------------------------------------

# Untrimmed pages as cleaned, covering the shapes a matter page comes in: the
# old consultation format (MN-01064), a waiver (WA-75008), Phase 2 with a
# Tribunal review (MN-65005) and the new structured consultation (MN-10042).
UNTRIMMED = {
    'MN-01064': 'MN-01064.cleaned.html.gz',
    'WA-75008': 'WA-75008.cleaned.html.gz',
    'MN-65005': 'MN-65005.cleaned.html.gz',
    'MN-10042': 'MN-10042.cleaned.html.gz',
}


def _parse(page: bytes, tmp_path, monkeypatch, name: str) -> dict:
    """What extract_mergers reads from ``page``, without downloading anything."""
    from scripts import extract_mergers
    monkeypatch.setattr(extract_mergers, 'download_attachment', lambda *a, **k: None)
    path = tmp_path / name
    path.write_bytes(page)
    return extract_mergers.parse_merger_file(str(path), None, set(), {})


@pytest.mark.parametrize('merger_id', UNTRIMMED)
def test_trimmed_page_extracts_identically(merger_id, tmp_path, monkeypatch):
    """Every selector extract_mergers uses survives the trim."""
    from scripts import extract_mergers
    page = _fixture(UNTRIMMED[merger_id])
    trimmed, was_trimmed = scrape.prepare_page(page)
    assert was_trimmed and len(trimmed) < len(page)
    before = _parse(page, tmp_path, monkeypatch, 'before.html')
    after = _parse(trimmed, tmp_path, monkeypatch, 'after.html')
    assert before is not None and before['merger_id'] == merger_id
    assert after == before
    assert extract_mergers.get_merger_id_from_file(str(tmp_path / 'after.html')) == merger_id


@pytest.mark.parametrize('merger_id', ['MN-01064', 'WA-75008'])
def test_raw_page_trims_to_the_same_as_its_cleaned_copy(merger_id):
    raw = _fixture(f'{merger_id}.raw.html.gz')
    cleaned = _fixture(f'{merger_id}.cleaned.html.gz')
    assert scrape.prepare_page(raw) == scrape.prepare_page(cleaned)


@pytest.mark.parametrize('merger_id', UNTRIMMED)
def test_trim_is_idempotent(merger_id):
    once, _ = scrape.prepare_page(_fixture(UNTRIMMED[merger_id]))
    assert scrape.prepare_page(once) == (once, True)
    assert scrape.clean_html_bytes(once) == once


def test_trim_drops_the_chrome_and_keeps_the_head():
    from lxml import html as lxml_html
    page = _fixture(UNTRIMMED['MN-65005'])
    trimmed, _ = scrape.prepare_page(page)
    before = lxml_html.document_fromstring(page)
    after = lxml_html.document_fromstring(trimmed)

    for xpath in ('//footer', '//*[@id="skip-links"]', '//nav',
                  '//*[contains(@class, "breadcrumb-wrapper")]',
                  '//*[contains(@class, "acquisitions-subscribe")]',
                  '//form[@id="acquisition-subscribe-form"]',
                  '//script', '//link[@rel="stylesheet"]'):
        assert before.xpath(xpath), xpath  # the fixture has it to drop
        assert not after.xpath(xpath), xpath

    def head(document):
        return [(e.tag, dict(e.attrib), e.text_content()) for e in document.find('head')
                if e.tag in ('meta', 'title') or (e.tag == 'link' and e.get('rel') != 'stylesheet')]
    assert head(after) == head(before)
    assert after.xpath('//meta[@name="dcterms.modified"]')
    assert after.xpath('//link[@rel="canonical"]')

    # Everything in the hero and <main> is kept, bar the subscribe widget.
    def text(document, xpath):
        for element in document.xpath('//*[contains(@class, "acquisitions-subscribe")]'):
            element.drop_tree()
        return [' '.join(e.text_content().split()) for e in document.xpath(xpath)]
    for xpath in ('//main', '//h1'):
        assert text(after, xpath) == text(before, xpath)


def _page(body: str, head: str = '') -> bytes:
    return (
        '<!DOCTYPE html>\n<html><head>\n<meta name="dcterms.modified" content="x">\n'
        f'<link rel="stylesheet" href="/a.css">\n{head}</head>\n<body>\n'
        '<div id="skip-links"><a href="#m">Skip</a></div>\n'
        '<div class="nav-container"><nav>menu</nav></div>\n'
        '<div class="content-wrapper">\n'
        '<main><article><div class="field--name-dynamic-token-fieldnode-acccgov-merger-id">'
        '<div class="field__item"><p>MN-12345</p></div></div></article></main>\n'
        f'{body}</div>\n'
        '<footer role="contentinfo"><div class="field--name-body">Copyright</div></footer>\n'
        '<script src="/a.js"></script>\n</body></html>\n'
    ).encode()


def test_trim_keeps_what_it_does_not_name():
    """A section the ACCC adds outside <main>, an unknown head tag and
    structured data are all kept: the trim is a denylist of chrome."""
    page = _page(
        '<section class="tribunal-decision"><h2>Tribunal decision</h2><p>Set aside</p></section>\n',
        head='<meta name="something.new" content="y">\n'
             '<script type="application/ld+json">{"@type": "GovernmentService"}</script>\n',
    )
    trimmed = scrape.trim_chrome(page)
    assert trimmed is not None
    for kept in (b'Tribunal decision', b'Set aside', b'something.new', b'GovernmentService',
                 b'dcterms.modified', b'MN-12345'):
        assert kept in trimmed
    for dropped in (b'Skip', b'menu', b'Copyright', b'/a.js', b'/a.css'):
        assert dropped not in trimmed


def test_trim_refuses_to_drop_matter_content():
    """If matter content ever turns up inside the chrome, keep the page whole."""
    page = _page('').replace(
        b'<nav>menu</nav>',
        b'<nav><div class="field--name-field-acccgov-merger-status">Approved</div></nav>')
    assert scrape.trim_chrome(page) is None
    assert scrape.prepare_page(page) == (scrape.clean_html_bytes(page), False)


@pytest.mark.parametrize('page', [b'', b'  \n', (
    b'<html><body><div class="accc-collapsed-card__header"><a href="/x">X</a></div>'
    b'<footer>f</footer></body></html>')])
def test_trim_leaves_pages_that_are_not_matters(page):
    """The register listing page is cleaned but never trimmed."""
    assert scrape.trim_chrome(page) is None


# --- Parsing ---------------------------------------------------------------

LISTING = b'''<html><head><title> ACCC
  register </title></head><body>
<div class="accc-collapsed-card"><div class="accc-collapsed-card__header">
  <a href="/public-registers/x/acquisitions-register/a-b">A - B</a>
  <a href="#card-123">toggle</a></div></div>
<div class="accc-collapsed-card"><div class="accc-collapsed-card__header">
  <a href="/public-registers/x/acquisitions-register/c-%E2%80%93-d">C - D</a></div></div>
<a href="/elsewhere">not a card</a>
<nav><a title="Go to last page" href="?init=1&amp;items_per_page=50&amp;page=17">Last</a>
<a title="Go to last page" href="?init=1&amp;items_per_page=50&amp;page=18">Last</a></nav>
</body></html>'''


def test_listing_links_skips_card_anchors():
    assert scrape.listing_links(LISTING) == [
        '/public-registers/x/acquisitions-register/a-b',
        '/public-registers/x/acquisitions-register/c-%E2%80%93-d',
    ]


def test_last_page_number_takes_the_last_match():
    assert scrape.last_page_number(LISTING) == 18
    assert scrape.last_page_number(b'<p>no pager</p>') == 0


def test_parsers_tolerate_an_empty_body():
    """A listing page whose fetch failed arrives as b'' and has no links."""
    for body in (b'', b'   \n', b'<!-- -->'):
        assert scrape.listing_links(body) == []
        assert scrape.last_page_number(body) == 0
        assert scrape.matter_number(body) == ''


def _matter(number: bytes) -> bytes:
    return (b'<div class="field--name-dynamic-token-fieldnode-acccgov-merger-id">'
            b'<p>' + number + b'</p></div>')


def test_matter_number_strips_whitespace():
    assert scrape.matter_number(_matter(b'\n   MN-12345 \n')) == 'MN-12345'
    assert scrape.matter_number(b'<p>MN-12345</p>') == ''


@pytest.mark.parametrize('value, safe', [
    ('MN-12345', True),
    ('WA-75008', True),
    ('mn_1', True),
    ('../../etc/passwd', False),
    ('MN-1/2', False),
    ('MN.1', False),
    ('', False),
])
def test_is_safe_matter_number(value, safe):
    assert scrape.is_safe_matter_number(value) is safe


@pytest.mark.parametrize('link, name', [
    ('/public-registers/x/acquisitions-register/a-b', 'a-b'),
    ('/public-registers/x/acquisitions-register/a-b/', 'a-b'),
    ('/public-registers/x/c-%E2%80%93-d', 'c-E28093-d'),
    ('/x/a b?c=1', 'abc1'),
    ('/', ''),
    ('', ''),
])
def test_fallback_filename(link, name):
    assert scrape.fallback_filename(link) == name


# --- fetch_matter_page -----------------------------------------------------

def _run_fetch(tmp_path, link, result):
    manifest = scrape.Manifest(tmp_path / 'report' / 'fetched.tsv')
    matters = tmp_path / 'matters'
    matters.mkdir()

    def fetch(url):
        assert url == scrape.BASE_URL + link
        if isinstance(result, Exception):
            raise result
        return result

    error = scrape.fetch_matter_page(link, manifest, fetch=fetch, matters_dir=matters)
    rows = (tmp_path / 'report' / 'fetched.tsv').read_text(encoding='utf-8')
    return error, rows, matters


def test_fetch_saves_the_cleaned_page_under_its_number(tmp_path, capsys):
    page = _fixture(UNTRIMMED['MN-01064'])
    error, rows, matters = _run_fetch(tmp_path, '/r/a-b', page)
    assert error is None
    assert rows == 'ok\tMN-01064\t/r/a-b\n'
    assert (matters / 'MN-01064.html').read_bytes() == scrape.prepare_page(page)[0]
    assert '::warning::' not in capsys.readouterr().out


def test_fetch_stores_an_untrimmable_page_whole(tmp_path, capsys):
    page = _page('').replace(
        b'<nav>menu</nav>',
        b'<nav><div class="field--name-field-acccgov-merger-status">Approved</div></nav>')
    error, rows, matters = _run_fetch(tmp_path, '/r/a-b', page)
    assert error is None
    assert (matters / 'MN-12345.html').read_bytes() == scrape.clean_html_bytes(page)
    assert '::warning::Stored MN-12345.html whole' in capsys.readouterr().out


def test_clean_stored_cli(tmp_path, monkeypatch):
    matters = tmp_path / 'matters'
    matters.mkdir()
    page = _fixture(UNTRIMMED['WA-75008'])
    (matters / 'WA-75008.html').write_bytes(page)
    monkeypatch.setattr(scrape, 'RAW_DIR', tmp_path)
    monkeypatch.setattr(scrape, 'MATTERS_DIR', matters)
    assert scrape.main(['--clean-stored']) == 0
    assert (matters / 'WA-75008.html').read_bytes() == scrape.prepare_page(page)[0]


def test_fetch_rejects_an_unsafe_number_for_the_fallback(tmp_path, capsys):
    error, rows, matters = _run_fetch(tmp_path, '/r/a-b', _matter(b'../../evil'))
    assert error is None
    assert 'Rejected unsafe matter number' in capsys.readouterr().err
    assert [p.name for p in matters.iterdir()] == ['a-b.html']
    assert rows == 'ok\tUNKNOWN\t/r/a-b\n'


def test_fetch_with_no_safe_name_saves_nothing(tmp_path):
    error, rows, matters = _run_fetch(tmp_path, '/', b'<p>no number</p>')
    assert error.endswith('(no safe filename)')
    assert list(matters.iterdir()) == []
    assert rows == 'failed\tUNKNOWN\t/\n'


def test_fetch_failure_is_recorded(tmp_path):
    url = scrape.BASE_URL + '/r/a-b'
    error, rows, matters = _run_fetch(tmp_path, '/r/a-b', scrape.FetchError(url, 403))
    assert error == f'{url} (HTTP 403)'
    assert rows == 'failed\tUNKNOWN\t/r/a-b\n'
    assert list(matters.iterdir()) == []


# --- HTTP retry policy -----------------------------------------------------

class _Response:
    def __init__(self, status, content=b'body'):
        self.status_code = status
        self.content = content


def _fake_get(monkeypatch, outcomes):
    calls = []

    def get(url, timeout):
        calls.append(url)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)

    monkeypatch.setattr(scrape, '_get', get)
    return calls


def test_fetch_page_retries_a_403(monkeypatch):
    calls = _fake_get(monkeypatch, [403, 200])
    sleeps = []
    assert scrape.fetch_page('u', sleep=sleeps.append) == b'body'
    assert len(calls) == 2 and sleeps == [5]


def test_fetch_page_gives_up_after_three_attempts(monkeypatch):
    calls = _fake_get(monkeypatch, [404, scrape.accc_http.RequestException('reset'), 404])
    with pytest.raises(scrape.FetchError) as exc:
        scrape.fetch_page('u', sleep=lambda s: None)
    assert exc.value.status == 404 and len(calls) == 3


def test_fetch_page_reports_000_without_a_response(monkeypatch):
    _fake_get(monkeypatch, [scrape.accc_http.RequestException('timeout')] * 3)
    with pytest.raises(scrape.FetchError) as exc:
        scrape.fetch_page('u', sleep=lambda s: None)
    assert exc.value.status == 0
    assert '(HTTP 000)' in str(exc.value)


def test_register_index_keeps_a_block_page(monkeypatch):
    """A 403 isn't transient to curl's --retry, and its body is kept."""
    calls = _fake_get(monkeypatch, [403])
    assert scrape.fetch_register_index(sleep=lambda s: None) == (403, b'body')
    assert len(calls) == 1


def test_register_index_retries_a_transient_status_once(monkeypatch):
    calls = _fake_get(monkeypatch, [503, 503])
    sleeps = []
    assert scrape.fetch_register_index(sleep=sleeps.append) == (503, b'body')
    assert len(calls) == 2 and sleeps == [30]


def test_register_index_raises_without_any_response(monkeypatch):
    _fake_get(monkeypatch, [scrape.accc_http.RequestException('dns')] * 2)
    with pytest.raises(scrape.FetchError):
        scrape.fetch_register_index(sleep=lambda s: None)


# --- scrape() --------------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point every path the scraper writes at tmp_path."""
    raw = tmp_path / 'raw'
    monkeypatch.setattr(scrape, 'RAW_DIR', raw)
    monkeypatch.setattr(scrape, 'MAIN_PAGE_FILE', raw / 'acquisitions-register.html')
    monkeypatch.setattr(scrape, 'MATTERS_DIR', raw / 'matters')
    monkeypatch.setattr(scrape, 'MERGERS_JSON', tmp_path / 'mergers.json')
    return tmp_path


def test_scrape_fetches_every_listed_matter(sandbox, monkeypatch):
    monkeypatch.setattr(scrape, 'fetch_register_index', lambda sleep: (200, LISTING))
    monkeypatch.setattr(scrape, 'fetch_listing_page', lambda page: b'')
    numbers = {'/public-registers/x/acquisitions-register/a-b': b'MN-00001',
               '/public-registers/x/acquisitions-register/c-%E2%80%93-d': b'WA-00002'}
    monkeypatch.setattr(scrape, 'fetch_page',
                        lambda url: _matter(numbers[url[len(scrape.BASE_URL):]]))

    report = sandbox / 'report'
    assert scrape.scrape(report_dir=report) == 0
    assert sorted(p.name for p in (sandbox / 'raw' / 'matters').iterdir()) == \
        ['MN-00001.html', 'WA-00002.html']
    rows = sorted((report / 'fetched.tsv').read_text().splitlines())
    assert rows == ['ok\tMN-00001\t/public-registers/x/acquisitions-register/a-b',
                    'ok\tWA-00002\t/public-registers/x/acquisitions-register/c-%E2%80%93-d']
    assert (report / 'targets.json').exists()


def test_scrape_with_no_links_fails_with_diagnostics(sandbox, monkeypatch, capsys):
    block = b'<html><head><title>Access   Denied</title></head><body>nope</body></html>'
    monkeypatch.setattr(scrape, 'fetch_register_index', lambda sleep: (403, block))

    def head(url, **kwargs):
        response = _Response(403)
        response.headers = {'Server': 'AkamaiGHost', 'X-Unrelated': 'x'}
        return response

    monkeypatch.setattr(scrape.accc_http, 'head', head)
    assert scrape.scrape() == 1
    out = capsys.readouterr().out
    assert '::error::No acquisition links found on the register (HTTP 403)' in out
    assert 'Title:  Access Denied' in out
    assert 'Server: AkamaiGHost' in out and 'X-Unrelated' not in out
    # The page is left on disk for the workflow's failure artifact.
    assert (sandbox / 'raw' / 'acquisitions-register.html').read_bytes() == block


def test_scrape_recrawls_for_an_emailed_matter(sandbox, monkeypatch, capsys):
    """A new matter the first crawl dropped is picked up on a re-crawl."""
    monkeypatch.setattr(scrape, 'fetch_register_index', lambda sleep: (200, LISTING))
    card = (b'<div class="accc-collapsed-card"><div class="accc-collapsed-card__header">'
            b'<a href="/r/new-matter">New</a></div>'
            b'<div class="field--name-field-acccgov-mcmsmergermatterno">'
            b'<div class="field__item">MN-99999</div></div></div>')
    crawls = []

    def listing_page(page):
        crawls.append(page)
        # Pages 1..18 of the first crawl serve nothing new; the re-crawl's
        # page 0 serves the emailed matter.
        return card if len(crawls) > 18 and page == 0 else b''

    monkeypatch.setattr(scrape, 'fetch_listing_page', listing_page)
    monkeypatch.setattr(scrape, 'fetch_page', lambda url: _matter(b'MN-99999'))
    assert scrape.scrape(expect_ids='MN-99999', recrawl_delay=0, sleep=lambda s: None) == 0
    out = capsys.readouterr().out
    assert 'Crawl 1 served 1 matter(s) the earlier crawl(s) missed.' in out
    assert 'Every emailed matter found after 1 extra listing crawl(s).' in out
    assert (sandbox / 'raw' / 'matters' / 'MN-99999.html').exists()
