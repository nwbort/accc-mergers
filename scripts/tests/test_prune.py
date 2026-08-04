"""Tests for static_data.prune — removal of no-longer-generated output files."""

import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from static_data.prune import prune_stale_files


def _touch(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text('{}')


class TestPruneStaleFiles:
    def test_removes_files_not_written_this_run(self, tmp_path):
        _touch(tmp_path, 'keep.json', 'stale.json')
        removed = prune_stale_files(tmp_path, {'keep.json'})
        assert removed == ['stale.json']
        assert {p.name for p in tmp_path.glob('*')} == {'keep.json'}

    def test_keeps_everything_when_nothing_is_stale(self, tmp_path):
        _touch(tmp_path, 'a.json', 'b.json')
        assert prune_stale_files(tmp_path, {'a.json', 'b.json'}) == []
        assert len(list(tmp_path.glob('*.json'))) == 2

    def test_empty_keep_set_prunes_nothing(self, tmp_path):
        # A generator that wrote no files is assumed to have hit an empty or
        # failed load — never a reason to empty the directory.
        _touch(tmp_path, 'a.json', 'b.json')
        assert prune_stale_files(tmp_path, set()) == []
        assert len(list(tmp_path.glob('*.json'))) == 2

    def test_ignores_files_outside_the_pattern(self, tmp_path):
        _touch(tmp_path, 'keep.json', 'stale.json')
        (tmp_path / 'notes.txt').write_text('hello')
        prune_stale_files(tmp_path, {'keep.json'})
        assert (tmp_path / 'notes.txt').exists()

    def test_excluded_globs_are_never_pruned(self, tmp_path):
        _touch(tmp_path, 'keep.json', 'list-page-1.json', 'list-meta.json', 'stale.json')
        removed = prune_stale_files(
            tmp_path, {'keep.json'}, exclude=('list-page-*.json', 'list-meta.json')
        )
        assert removed == ['stale.json']
        assert (tmp_path / 'list-page-1.json').exists()
        assert (tmp_path / 'list-meta.json').exists()

    def test_restricting_the_pattern_scopes_the_prune(self, tmp_path):
        _touch(tmp_path, 'MN-1.json', 'list-page-1.json', 'list-page-2.json')
        removed = prune_stale_files(
            tmp_path, {'list-page-1.json'}, pattern='list-page-*.json'
        )
        assert removed == ['list-page-2.json']
        assert (tmp_path / 'MN-1.json').exists()

    def test_subdirectories_are_left_alone(self, tmp_path):
        _touch(tmp_path, 'keep.json')
        (tmp_path / 'nested.json').mkdir()
        prune_stale_files(tmp_path, {'keep.json'})
        assert (tmp_path / 'nested.json').is_dir()

    def test_missing_directory_is_a_no_op(self, tmp_path):
        assert prune_stale_files(tmp_path / 'absent', {'a.json'}) == []
