"""Tests for scripts/check_deploy_assets.py — the safety net over both Cloudflare
Pages limits that fail silently: a file too big to deploy, and a deployment with
too many files in it. Both feed tracking issues."""

import json
import re
import sys
import unittest.mock

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from scripts.check_deploy_assets import (  # noqa: E402
    DEPLOY_SOURCES,
    FILE_COUNT_WARN_RATIO,
    PAGES_FILE_LIMIT,
    PRERENDERED_STATIC_PAGES,
    VITE_BUILD_FILES,
    build_file_count_issue_body,
    build_issue_body,
    count_deploy_files,
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


def make_deployment(root, *, mergers=0, parties=0, industries=0, pdfs=0, public_extra=0):
    """A repo-shaped tree that the file counter can measure.

    Mirrors what the pipeline actually writes: per-merger and per-industry data
    files, a parties.json index, and matter PDFs.
    """
    data = root / "frontend/public/data"
    (data / "mergers").mkdir(parents=True, exist_ok=True)
    (data / "industries").mkdir(parents=True, exist_ok=True)
    (root / "data/raw/matters/MN-1").mkdir(parents=True, exist_ok=True)

    for i in range(mergers):
        (data / "mergers" / f"MN-{i:05d}.json").write_text("{}")
    for i in range(industries):
        (data / "industries" / f"{i:04d}.json").write_text("{}")
    (data / "parties.json").write_text(
        json.dumps({"parties": [{"id": f"p-{i}"} for i in range(parties)]})
    )
    for i in range(pdfs):
        write(root / "data/raw/matters/MN-1" / f"doc-{i}.pdf", 1024)
    for i in range(public_extra):
        (root / "frontend/public" / f"asset-{i}.txt").write_text("x")
    return root


class TestCountDeployFiles:
    def test_counts_each_source_the_way_the_build_produces_it(self, tmp_path):
        make_deployment(tmp_path, mergers=3, parties=5, industries=2, pdfs=4, public_extra=6)
        counts = count_deploy_files(tmp_path)

        # public/ holds the 6 extra files plus parties.json, 3 merger files and
        # 2 industry files — Vite copies the whole tree verbatim.
        assert counts["breakdown"]["public"] == 6 + 1 + 3 + 2
        assert counts["breakdown"]["pdfs"] == 4
        assert counts["breakdown"]["build"] == VITE_BUILD_FILES
        assert counts["prerendered_detail"] == {
            "mergers": 3, "parties": 5, "industries": 2,
            "static": PRERENDERED_STATIC_PAGES,
        }
        assert counts["total"] == sum(counts["breakdown"].values())

    def test_prerendered_pages_are_one_per_record(self, tmp_path):
        """prerender.js writes one HTML file per merger, party and industry, and
        that HTML is over half the deployment — a count that ignored it would be
        wrong by thousands."""
        make_deployment(tmp_path, mergers=10, parties=20, industries=5)
        counts = count_deploy_files(tmp_path)

        assert counts["breakdown"]["prerendered"] == 10 + 20 + 5 + PRERENDERED_STATIC_PAGES

    def test_party_pages_come_from_the_index_not_the_shard_buckets(self, tmp_path):
        """prerender.js renders the parties listed in parties.json; ids folded
        into a canonical group still sit in a bucket but get no page."""
        make_deployment(tmp_path, parties=3)
        buckets = tmp_path / "frontend/public/data/parties"
        buckets.mkdir(parents=True)
        (buckets / "shard-00.json").write_text(
            json.dumps({"parties": {f"p-{i}": {} for i in range(50)}})
        )

        assert count_deploy_files(tmp_path)["prerendered_detail"]["parties"] == 3

    def test_only_matter_files_count_as_merger_pages(self, tmp_path):
        """mergers/ also holds list-page-N.json and list-meta.json, which are
        data rather than pages."""
        make_deployment(tmp_path, mergers=2)
        d = tmp_path / "frontend/public/data/mergers"
        (d / "list-page-1.json").write_text("{}")
        (d / "list-meta.json").write_text("{}")

        assert count_deploy_files(tmp_path)["prerendered_detail"]["mergers"] == 2

    def test_oversized_pdfs_are_not_counted(self, tmp_path):
        """scripts/build.sh leaves them out of dist/, so they cost nothing
        against the file budget."""
        make_deployment(tmp_path, pdfs=2)
        write(tmp_path / "data/raw/matters/MN-1/huge.pdf", 30 * MIB)

        assert count_deploy_files(tmp_path)["breakdown"]["pdfs"] == 2

    def test_survives_a_missing_or_malformed_parties_index(self, tmp_path):
        make_deployment(tmp_path, mergers=1)
        (tmp_path / "frontend/public/data/parties.json").write_text("not json{")

        counts = count_deploy_files(tmp_path)
        assert counts["prerendered_detail"]["parties"] == 0
        assert counts["total"] > 0

    def test_empty_tree_does_not_explode(self, tmp_path):
        counts = count_deploy_files(tmp_path)
        assert counts["total"] == VITE_BUILD_FILES + PRERENDERED_STATIC_PAGES


class TestFileCountIssueBody:
    def _counts(self, total, limit=PAGES_FILE_LIMIT):
        return {
            "breakdown": {"public": total, "prerendered": 0, "pdfs": 0, "build": 0},
            "prerendered_detail": {"mergers": 0, "parties": 0, "industries": 0, "static": 0},
            "total": total,
            "limit": limit,
            "warn_at": int(limit * FILE_COUNT_WARN_RATIO),
        }

    def test_approaching_says_it_is_not_yet_a_problem(self):
        body = build_file_count_issue_body(self._counts(17_000))
        assert "17,000" in body
        assert "Not a problem yet" in body
        assert "Deployments are failing" not in body

    def test_over_the_limit_says_deployments_are_failing(self):
        body = build_file_count_issue_body(self._counts(21_000))
        assert "Deployments are failing" in body
        # The reader needs to know the site is stale rather than down.
        assert "frozen" in body

    def test_lists_where_the_files_come_from(self):
        body = build_file_count_issue_body(self._counts(17_000))
        assert "prerender.js" in body
        assert "frontend/public/" in body


class TestMainFileCount:
    def test_reports_the_count_on_a_healthy_deployment(self, tmp_path, capsys):
        make_deployment(tmp_path, mergers=2, parties=2, industries=1, pdfs=1)

        assert main(["--root", str(tmp_path)]) == 0
        assert "files in the next deployment" in capsys.readouterr().out

    @staticmethod
    def _limit_putting_us_at(tmp_path, ratio):
        """A --file-limit this deployment sits at ``ratio`` of.

        Derived from the real count rather than hardcoded so the test says what
        it means and doesn't drift when VITE_BUILD_FILES or the static-page
        allowance changes.
        """
        return str(int(count_deploy_files(tmp_path)["total"] / ratio))

    def test_approaching_the_limit_is_reported_but_not_a_failure(self, tmp_path, capsys):
        """The site still deploys fine — this is lead time, not an outage, so a
        red run here would be crying wolf."""
        make_deployment(tmp_path, mergers=5)
        limit = self._limit_putting_us_at(tmp_path, 0.9)

        assert main(["--root", str(tmp_path), "--file-limit", limit, "--fail"]) == 0
        assert "Approaching the file limit" in capsys.readouterr().err

    def test_over_the_limit_fails_under_the_fail_flag(self, tmp_path, capsys):
        """This is the silent failure the check exists for: past the limit,
        Pages refuses the deployment and the site stops updating while every
        workflow stays green."""
        make_deployment(tmp_path, mergers=5)
        limit = self._limit_putting_us_at(tmp_path, 1.1)

        assert main(["--root", str(tmp_path), "--file-limit", limit, "--fail"]) == 1
        assert "OVER THE FILE LIMIT" in capsys.readouterr().err

    def test_json_payload_carries_the_file_count(self, tmp_path):
        make_deployment(tmp_path, mergers=5)
        limit = self._limit_putting_us_at(tmp_path, 0.9)
        out = tmp_path / "deploy.json"

        main(["--root", str(tmp_path), "--json", str(out), "--file-limit", limit])
        payload = json.loads(out.read_text())["file_count"]

        # Every key the workflow's jq reaches for.
        assert payload["approaching"] is True
        assert payload["over_limit"] is False
        assert payload["total"] > 0
        assert payload["limit"] == int(limit)
        assert payload["title"]
        assert payload["body"]

    def test_body_is_empty_when_not_approaching(self, tmp_path):
        """The workflow closes the issue on approaching == false and never reads
        the body, so it costs nothing to leave it empty."""
        make_deployment(tmp_path, mergers=1)
        out = tmp_path / "deploy.json"

        main(["--root", str(tmp_path), "--json", str(out)])
        payload = json.loads(out.read_text())["file_count"]

        assert payload["approaching"] is False
        assert payload["body"] == ""
