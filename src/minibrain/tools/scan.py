# pyright: strict, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from pathlib import Path

from peewee import DoesNotExist

from minibrain.context import Context
from minibrain.db import Server, Version, database
from minibrain.utils.alerts import AlertDestination, send_probe_status_change_alert
from minibrain.utils.db import get_mb_version
from minibrain.utils.probe import probe_mirror

context = Context.get()
logger = context.logger


def get_listing():
    ...
    # my ($priv, $name, $len, $mode, $mtime, @info) = @_;
    # path, identifier, serverid, mod_re, ign_re

    # my $sql_insert_file = "INSERT INTO file (path) VALUES (?);";

    # my $sql = "SELECT mirr_add_bypath(?, ?);";

    # rsync --no-motd -rlpt --delete --ignore-errors -n --out-format="%o %B %i %M %l %n%L"
    # %o: operation
    # %B: permission bits
    # %i: itemized list of what is being updated
    # %M: last-modified time of the file
    # %l: length of the file in bytes
    # %n: filename (short form; trailing lq/rq on dir)
    # %L: the string lq -> SYMLINKrq, lq => HARDLINKrq, or lqrq (where SYMLINK or HARDLINK is a filename)
    #
    #
    # %f the filename (long form on sender; no trailing lq/rq)

    command = [
        "rsync",
        "--no-motd",
        "--recursive",
        "--links",
        "--perms",
        "--times",
        "--delete",
        "--ignore-errors",
        "--dry-run",
        "--out-format=%l %M %n",
        "rsync://192.168.1.61:1873/zim",
        "./dest/",
    ]


def mirrorscan(
    mirror_id: str,
    *,
    dry_run: bool,
    enable: bool,
    directory: Path,
    alerts: list[AlertDestination],
) -> int:

    context = Context.get()
    if dry_run:
        enable = False

    logger.info(f"Starting mirrorscan for {context.dsn}")

    if not all(dest.is_valid for dest in alerts):
        logger.warning("You have invalid --alerts")

    logger.info(f"Connected to mirrorbrain DB version {get_mb_version()}")

    try:
        mirror = Server.select().where(Server.identifier == mirror_id).get()
    except DoesNotExist:
        logger.critical(f"Server `{mirror_id}` was not found in DB")
        return 1

    if not mirror.enabled and not enable:
        logger.critical(
            f"Server `{mirror_id}` is not enabled. Use --enable or --dry-run to scan."
        )
        return 2

    if not mirror.statusBaseUrl:
        logger.critical(f"Server `{mirror_id}` is offline ; not scanning")
        return 2

    # scan_top_include
    # scan_exclude
    # scan_exclude_rsync

    # $sql = "UPDATE server SET last_scan = NOW(), scan_fpm = $fpm WHERE id = $row->{id};";
    # if($enable_after_scan && $file_count > 1 && !$row->{enabled}) {
    # $sql = "UPDATE server SET enabled = '1' WHERE id = $row->{id};";

    return 0
