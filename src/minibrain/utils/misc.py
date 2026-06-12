import datetime

import humanfriendly


def format_size(size: int) -> str:
    return f"{size!s} ({humanfriendly.format_size(size, True)})"


def format_dt(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d @ %H:%M:%S")  # noqa: RUF001


def format_ts(ts: int) -> str:
    return format_dt(datetime.datetime.fromtimestamp(ts, tz=datetime.UTC))
