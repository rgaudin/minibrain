import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

from minibrain.context import Context
from minibrain.utils.fs import get_normalized_path, is_world_readable, perms_to_mode
from minibrain.utils.misc import format_size

context = Context.get()
logger = context.logger


def get_rsync_listing(
    url: str, top_includes: list[str], excludes: list[str], timeout: int
) -> list[str]:
    excludes = list({*excludes, r"*/.~tmp~/", r"/.~tmp~/"})

    files: list[str] = []

    command = [
        "rsync",
        "--no-motd",
        "--recursive",
        "--links",
        "--perms",
        "--times",
        # "--delete",
        "--ignore-errors",
        "--dry-run",
        "--out-format=%B %l %M %n%L",
        "--contimeout",
        str(timeout),
    ]

    if top_includes:
        for include in top_includes:
            command += ["--include", f"/{include}"]
        command += ["--exclude", "/*"]

    for exclude in excludes:
        command += ["--exclude", exclude]

    # last arg is an empty dir (the fake rsync target)
    command += [url, str(Path(tempfile.gettempdir()).joinpath(uuid.uuid4().hex))]

    rsync = subprocess.run(command, text=True, capture_output=True, check=False)
    if rsync.returncode not in (0, 23):  # 23 is partial transfer
        rsync.check_returncode()

    for line in rsync.stdout.splitlines():
        # skip lines containing error
        if rsync.returncode and line.startswith("rsync: [sender]"):
            continue

        if "->" in line:  # symlink
            line, symlink = line.split(" -> ", 1)  # noqa: PLW2901
        elif "=>" in line:  # hardlink
            line, _ = line.split(" => ", 1)  # noqa: PLW2901
            symlink = ""
        else:
            symlink = ""
        perms, size_s, mtime_s, path = line.rsplit(" ", 3)

        perms = perms.strip()
        # file perms only
        if len(perms) <= 9:  # noqa: PLR2004
            ft = "-"
            if path.endswith("/"):
                ft = "d"
            elif symlink:
                ft = "l"
            perms = f"{ft}{perms}"
        mode = perms_to_mode(perms)

        desc = f"{perms} {format_size(int(size_s))} {mtime_s} {path}"

        # not recording folders
        if stat.S_ISDIR(mode):
            logger.debug(f"rsync dir: {desc}")
            continue

        if stat.S_ISLNK(mode):
            logger.debug(f"rsync link: {desc}")
            continue

        # only accept world-readable:
        if not stat.S_ISREG(mode) or not is_world_readable(mode):
            logger.warning(f"rsync skip: {desc}")
            continue

        logger.debug(f"rsync ADD: {desc}")
        files.append(get_normalized_path(path))

    return files
