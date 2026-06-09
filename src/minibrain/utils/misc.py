import datetime

import humanfriendly


def format_size(size: int) -> str:
    return f"{size!s} ({humanfriendly.format_size(size, True)})"


def format_ts(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=datetime.UTC).strftime(
        "%Y-%m-%d@%H:%M:%S"
    )
