import functools
import re
from queue import Queue
from typing import NamedTuple

import requests

from minibrain.context import Context
from minibrain.utils.fs import get_normalized_path
from minibrain.utils.misc import format_size

context = Context.get()
logger = context.logger


def to_re(regex: str) -> re.Pattern[str]:
    """Perl-style regex to Python re"""
    # using slashes syntax
    if len(regex) >= 2 and regex[0] == "/" and regex[-1] == "/":  # noqa: PLR2004
        regex = regex[1:-1]
    return re.compile(rf"{regex}")


def get_content_from(url: str, timeout: int) -> str:
    """raw text html from an nginx index listing url"""
    if not url.endswith("/"):
        raise ValueError("Only directory pattern allowed")
    resp = requests.get(
        url=url, headers={"User-Agent": "Minibrain Scanner"}, timeout=timeout
    )
    resp.raise_for_status()
    if not resp.headers.get("content-type", "").startswith("text/html"):
        raise OSError(f"{url} content-type is not HTML")

    if not re.search(
        r'<h1>Index of .*</h1><hr><pre><a href="../">../</a>',
        resp.text,
        re.MULTILINE,
    ):
        logger.debug(resp.text)
        raise OSError(f"{url} response does not look like an nginx index")
    return resp.text


@functools.total_ordering
class File(NamedTuple):
    fname: str
    size: int
    date: str

    def __eq__(self, value: object, /) -> bool:
        return self.fname.__eq__(value)

    def __lt__(self, value: object, /) -> bool:
        return self.fname.__lt__(str(value))

    def __hash__(self) -> int:
        return self.fname.__hash__()


type Files = list[File]
# type Filenames = list[str]
type Dirnames = list[str]


class FolderListing(NamedTuple):
    files: Files
    dirnames: Dirnames


def get_nginx_folder_listing(url: str, timeout: int) -> FolderListing:
    """Singe folder listing"""
    files: Files = []
    dirnames: Dirnames = []

    html = get_content_from(url, timeout=timeout)
    for line in html.splitlines():
        # <a href="zim/">zim/</a>\
        #                                               29-Oct-2022 03:39\
        #                   -
        if m := re.match(
            r"^<a href=\"(?P<path>[^\"]+)\">[^<]+</a>\s*"
            r"(?P<date>[\w\s:-]+)\s+(?P<size>-|[\d\.]+)",
            line,
        ):
            path = m.groupdict()["path"]
            size = -1 if m.groupdict()["size"] == "-" else int(m.groupdict()["size"])
            date = m.groupdict()["date"].strip()
            if size == -1:
                dirnames.append(path)
                logger.debug(f"http dir: {url}{path}")
            else:
                files.append(File(fname=path, size=size, date=date))

    dirnames.sort()
    files.sort()
    return FolderListing(files, dirnames)


def get_nginx_listing(
    url: str, top_includes: list[str], excludes: list[str], timeout: int
) -> list[str]:

    excludes = list({*excludes, r"/.~tmp~/"})
    excludes_re: list[re.Pattern[str]] = [to_re(exclude) for exclude in excludes]

    scanned_files: list[str] = []

    queue: Queue[str] = Queue()

    # start with base_url
    queue.put(url)

    while not queue.empty():
        current_url = queue.get()

        files, dirnames = get_nginx_folder_listing(current_url, timeout=timeout)

        for dirname in dirnames:
            # top_includes only applies to root
            if current_url == url and top_includes:
                if dirname.rstrip("/") not in top_includes:
                    logger.debug(f"not in top_include_list: {dirname}")
                    continue
            queue.put(f"{current_url}{dirname}")

        # add relative (to base_url) filepath to list of files
        for file in files:
            rel_path = f"{current_url}{file.fname}"[len(url) :]
            desc = f"{format_size(file.size)} {file.date} {rel_path}"
            if any(exclude.search(rel_path) for exclude in excludes_re):
                logger.warning(f"http skip excluded: {desc}")
                continue

            scanned_files.append(get_normalized_path(rel_path))
            logger.debug(f"http ADD: {desc}")

    return scanned_files
