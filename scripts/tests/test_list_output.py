"""The merger list carries the register page's modified time for its sort."""

from scripts.generate.static_data.outputs import list as list_out


def test_lightweight_carries_page_modified_datetime():
    m = {"merger_id": "MN-1", "page_modified_datetime": "2026-10-01T17:43:53+10:00"}
    assert list_out._lightweight(m)["page_modified_datetime"] == "2026-10-01T17:43:53+10:00"


def test_lightweight_page_modified_datetime_absent_is_none():
    assert list_out._lightweight({"merger_id": "MN-1"})["page_modified_datetime"] is None
