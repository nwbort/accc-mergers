"""Tests for scripts/check_deploy_assets.py — the safety net that notices a file
too big for Cloudflare Pages to deploy and feeds the tracking issue."""

import json
import re
import sys
import unittest.mock

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from scripts.check_deploy_assets import (  # noqa: E402
    DEPLOY_SOURCES,
    build_issue_body,
    find_oversized,
    main,
)
from scripts.compress_pdfs import PAGES_ASSET_LIMIT  # noqa: E402

MIB = 1024 * 1024


def write(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    return path


def make_tree(root):
    """A repo-shaped tree with both deployment sources present."""
    (root / "data/raw/matters/MN-1").mkdir(parents=True)
    (root / "frontend/public").mkdir(parents=True)
    return root


class TestFindOversized:
    def test_finds_an_oversized_matter_pdf(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/big.pdf", 30 * MIB)
        write(tmp_path / "data/raw/matters/MN-1/small.pdf", 1 * MIB)

        assert find_oversized(tmp_path) == [("data/raw/matters/MN-1/big.pdf", 30 * MIB)]

    def test_finds_an_oversized_file_in_the_public_dir(self, tmp_path):
        # Vite copies publicDir into dist verbatim, so anything oversized in
        # there breaks the deploy just as a PDF would.
        make_tree(tmp_path)
        write(tmp_path / "frontend/public/huge.png", 26 * MIB)

        assert find_oversized(tmp_path) == [
            ("frontend/public/huge.png", 26 * MIB)
        ]

    def test_ignores_non_pdfs_under_the_matters_dir(self, tmp_path):
        # build.sh only copies *.pdf out of data/raw/matters, so a big DOCX
        # there never reaches the deployment and isn't a problem.
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/big.docx", 30 * MIB)

        assert find_oversized(tmp_path) == []

    def test_ignores_files_outside_the_deployment_sources(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/processed/huge.json", 30 * MIB)

        assert find_oversized(tmp_path) == []

    def test_a_file_exactly_at_the_limit_is_fine(self, tmp_path):
        # Must agree with build.sh's copy filter and compress_pdfs.py's boundary.
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/exact.pdf", PAGES_ASSET_LIMIT)

        assert find_oversized(tmp_path) == []

    def test_reports_largest_first(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/medium.pdf", 30 * MIB)
        write(tmp_path / "data/raw/matters/MN-1/biggest.pdf", 60 * MIB)

        assert [p for p, _ in find_oversized(tmp_path)] == [
            "data/raw/matters/MN-1/biggest.pdf",
            "data/raw/matters/MN-1/medium.pdf",
        ]

    def test_missing_source_directories_are_not_an_error(self, tmp_path):
        assert find_oversized(tmp_path) == []

    def test_sources_match_what_build_sh_deploys(self):
        # A reminder to update this list if the build ever copies something new
        # into dist — the check and the workflow's paths filter both depend on it.
        assert DEPLOY_SOURCES == (
            ("data/raw/matters", "*.pdf"),
            ("frontend/public", "*"),
        )


class TestIssueBody:
    def test_lists_every_offending_file_with_its_size(self):
        body = build_issue_body([
            ("data/raw/matters/MN-1/big.pdf", 30 * MIB),
            ("data/raw/matters/MN-2/bigger.pdf", 60 * MIB),
        ])

        assert "`data/raw/matters/MN-1/big.pdf` | 30.0 MiB" in body
        assert "`data/raw/matters/MN-2/bigger.pdf` | 60.0 MiB" in body
        assert "2 file(s)" in body

    def test_says_the_site_still_builds(self):
        # The whole point of the issue is that this no longer breaks the build,
        # so the body has to explain what actually happens.
        body = build_issue_body([("a.pdf", 30 * MIB)])

        assert "left out of the deployed site" in body
        assert "redirected to" in body

    def test_points_at_the_compression_script(self):
        body = build_issue_body([("a.pdf", 30 * MIB)])

        assert "python -m scripts.compress_pdfs" in body

    def test_escapes_characters_that_would_break_the_table(self):
        # ACCC filenames are free-form; a pipe would otherwise split the row
        # into extra cells and a backtick would close the code span early.
        body = build_issue_body([("data/raw/matters/MN-1/a|b`c.pdf", 30 * MIB)])
        row = [ln for ln in body.splitlines() if "a\\|b" in ln]

        assert len(row) == 1
        # Three unescaped pipes: the row's opening, middle and closing delimiters.
        assert len(re.findall(r"(?<!\\)\|", row[0])) == 3
        # And the filename's backtick no longer closes the code span early.
        assert row[0].count("`") == 2


class TestMain:
    def test_exit_code_is_zero_by_default(self, tmp_path, capsys):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/big.pdf", 30 * MIB)

        assert main(["--root", str(tmp_path)]) == 0

    def test_fail_flag_makes_it_exit_non_zero(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/big.pdf", 30 * MIB)

        assert main(["--root", str(tmp_path), "--fail"]) == 1

    def test_fail_flag_still_exits_zero_when_clean(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/small.pdf", 1 * MIB)

        assert main(["--root", str(tmp_path), "--fail"]) == 0

    def test_json_payload_drives_the_workflow(self, tmp_path):
        make_tree(tmp_path)
        write(tmp_path / "data/raw/matters/MN-1/big.pdf", 30 * MIB)
        out = tmp_path / "oversized.json"

        main(["--root", str(tmp_path), "--json", str(out)])
        payload = json.loads(out.read_text())

        assert payload["count"] == 1
        assert payload["files"] == [
            {"path": "data/raw/matters/MN-1/big.pdf", "size": 30 * MIB}
        ]
        assert payload["title"]
        assert "big.pdf" in payload["body"]

    def test_json_payload_is_written_even_when_clean(self, tmp_path):
        # The workflow reads count unconditionally, and uses count == 0 as its
        # cue to close an open issue — so the file has to exist either way.
        make_tree(tmp_path)
        out = tmp_path / "oversized.json"

        main(["--root", str(tmp_path), "--json", str(out)])
        payload = json.loads(out.read_text())

        assert payload["count"] == 0
        assert payload["files"] == []
        assert payload["body"] == ""
