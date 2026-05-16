from sylion.api.cron_status_formatter import CronStatusFormatter


def test_format_status_empty():
    assert CronStatusFormatter.format_status({}) == (
        "Total Commits | Recent | Drafts KB\n"
        "------------- | ------ | ---------\n"
        "0             | 0      | 0"
    )


def test_format_status_full():
    status = {"total_commits": 12, "recent_commits": [{"hash": "a", "subject": "x"}, {"hash": "b", "subject": "y"}], "drafts_size_kb": 345}
    assert CronStatusFormatter.format_status(status) == (
        "Total Commits | Recent | Drafts KB\n"
        "------------- | ------ | ---------\n"
        "12            | 2      | 345"
    )
