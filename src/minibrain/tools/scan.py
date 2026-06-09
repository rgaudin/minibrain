# pyright: strict, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import datetime
import urllib.parse
from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

import humanfriendly
from peewee import DoesNotExist

from minibrain.context import Context
from minibrain.db import Server, database
from minibrain.utils.alerts import AlertDestination
from minibrain.utils.db import get_mb_version
from minibrain.utils.http import get_nginx_listing
from minibrain.utils.rsync import get_rsync_listing

context = Context.get()
logger = context.logger


def get_listing(
    url: str, top_includes: list[str], excludes: list[str], rsync_excludes: list[str]
) -> list[str]:
    scheme = urllib.parse.urlsplit(url).scheme
    try:
        listing_func, timeout = {
            "rsync": (get_rsync_listing, context.rsync_scan_timeout),
            "http": (get_nginx_listing, context.http_scan_timeout),
            "https": (get_nginx_listing, context.http_scan_timeout),
        }[scheme]
    except KeyError as exc:
        logger.critical(f"Unsupported URL scheme {scheme}: {exc!s}")
        raise OSError(f"Unsupported URL scheme {scheme}") from exc
    if scheme == "rsync":
        excludes = rsync_excludes + excludes
    return listing_func(
        url=url, top_includes=top_includes, excludes=excludes, timeout=timeout
    )


def mirr_add_bypath(serverid: int, path: str) -> int:
    """file ID of matching file after added/updating/skipping mirror in mirrors col"""
    cursor = database.execute_sql("SELECT mirr_add_bypath(%s, %s);", (serverid, path))

    # TODO:
    # use custom new function that does not create a file entry for each file
    # on each mirror (ie: trust only our own files from hashes)
    return next(cursor)[0]


def mirr_del_byid(serverid: int, file_id: int) -> bool:
    """whether serverid was removed from this file's mirrors column"""
    cursor = database.execute_sql("SELECT mirr_del_byid(%d, %d);", (serverid, file_id))
    return next(cursor) == 1


def get_fileid(path: str) -> int:
    cursor = database.execute_sql("SELECT id FROM filearr WHERE path = %s", (path,))
    try:
        return next(cursor)[0]
    # there is no file in DB for this path
    except StopIteration:
        return 0


def get_existing_files(mirror_ident: str) -> Generator[int]:
    cursor = database.execute_sql(
        (
            "SELECT id FROM filearr WHERE "
            "(SELECT id from server where identifier = %s) = ANY(mirrors)"
        ),
        (mirror_ident,),
    )
    for row in cursor:
        yield row[0]


class ScanResult(NamedTuple):
    nb_scanned: int
    nb_purged: int
    files_per_mn: int


def run_mirror_scan(
    *,
    mirror_id: int,
    mirror_ident: str,
    url: str,
    dry_run: bool,
    top_includes: list[str],
    excludes: list[str],
    rsync_excludes: list[str],
) -> ScanResult:

    files_in_db = list(get_existing_files(mirror_ident=mirror_ident))
    files_in_db.sort()  # will make removing faster

    scan_started_on = datetime.datetime.now(tz=datetime.UTC)
    scanned_files = get_listing(
        url=url,
        top_includes=top_includes,
        excludes=excludes,
        rsync_excludes=rsync_excludes,
    )
    nb_scanned = len(scanned_files)
    scan_ended_on = datetime.datetime.now(tz=datetime.UTC)
    scan_duration = scan_ended_on - scan_started_on
    files_per_mn = int(nb_scanned / scan_duration.total_seconds() * 60)
    nb_purged = 0

    scanned_files.sort()
    logger.info(f"FOUND {nb_scanned} files on {mirror_ident}")

    with database.atomic():
        for path in scanned_files:
            if dry_run:
                file_id = get_fileid(path)
            else:
                # add mirror ID to file's mirrors column (failsafe function)
                file_id = mirr_add_bypath(mirror_id, path)

            # remove from list of files on mirror (we've seen it)
            if file_id:  # in case it's a non-mirrored file
                files_in_db.remove(file_id)

        # now files_in_db is composed exclusively of files that we once
        # recorded as present in mirror but are not present anymore
        nb_purged = len(files_in_db)
        if dry_run:
            logger.info(f"WOULD PURGE {nb_purged} files previously on {mirror_ident}")
            return ScanResult(
                nb_scanned=nb_scanned, nb_purged=nb_purged, files_per_mn=files_per_mn
            )

        logger.info(f"PURGING {nb_purged} files previously on {mirror_ident}")

        for file_id in files_in_db:
            mirr_del_byid(serverid=mirror_id, file_id=file_id)

        return ScanResult(
            nb_scanned=nb_scanned, nb_purged=nb_purged, files_per_mn=files_per_mn
        )


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

    if not mirror.status_baseurl:
        logger.critical(f"Server `{mirror_id}` is offline ; not scanning")
        return 2

    scan = run_mirror_scan(
        mirror_id=mirror.id,
        mirror_ident=mirror.identifier,
        url=mirror.baseurl_rsync or mirror.baseurl_ftp or mirror.baseurl,
        dry_run=dry_run,
        top_includes=context.mb_scan_top_include,
        excludes=context.mb_scan_exclude,
        rsync_excludes=context.mb_scan_exclude_rsync,
    )

    if dry_run:
        return 0

    if not mirror.enabled and scan.nb_scanned > 0 and enable:
        logger.info("ENABLING mirror {mirror.identifier} after successful scan")
        mirror.enable = True

    logger.info("Recording last_scan={form}")
    mirror.last_scan = datetime.datetime.now(tz=datetime.UTC)
    mirror.scan_fpm = scan.files_per_mn
    mirror.save()

    return 0
