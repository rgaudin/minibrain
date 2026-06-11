# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""minibrain copydb

Independent script to copy data from an existing mirrorbrain demo to another one.
Main use is to start a new mirrorbrain instance from a previous one.
It allows to start fresh, by copying only files (filearr) which are present
on a specific mirror (your master) yet keeping associated hashes
"""

# /// script
# dependencies = [
#   "psycopg[binary]==3.3.4",
#   "peewee==4.0.6",
#   "tqdm==4.68.2",
# ]
# ///

import argparse
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from peewee import PostgresqlDatabase
from psycopg import Cursor
from tqdm import tqdm

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("copydb")
logging.getLogger("peewee").setLevel(logging.INFO)


@dataclass(kw_only=True)
class Context:
    source_dsn: urllib.parse.ParseResult
    target_dsn: urllib.parse.ParseResult
    mirror: str
    truncate: bool = False
    keep_onmirror: bool = False

    @property
    def source_db(self) -> PostgresqlDatabase:
        return self._source_db

    @property
    def target_db(self) -> PostgresqlDatabase:
        return self._target_db

    def __post_init__(self):
        self._source_db: PostgresqlDatabase = PostgresqlDatabase(
            self.source_dsn.path[1:],
            user=self.source_dsn.username or "",
            password=self.source_dsn.password or "",
            host=self.source_dsn.hostname or "",
            port=self.source_dsn.port or 5432,
        )

        self._target_db: PostgresqlDatabase = PostgresqlDatabase(
            self.target_dsn.path[1:],
            user=self.target_dsn.username or "",
            password=self.target_dsn.password or "",
            host=self.target_dsn.hostname or "",
            port=self.target_dsn.port or 5432,
        )


def entrypoint() -> int:
    parser = argparse.ArgumentParser(
        prog="copydb", description="Copy Mirrorbrain DB data"
    )

    parser.add_argument(
        "--source",
        help="DSN of source Database",
        dest="source_dsn",
        type=urllib.parse.urlparse,
        required=True,
    )

    parser.add_argument(
        "--target",
        help="DSN of target Database",
        dest="target_dsn",
        type=urllib.parse.urlparse,
        required=True,
    )

    parser.add_argument(
        "--truncate",
        help="Truncate every table before inserting",
        dest="truncate",
        action="store_true",
    )

    parser.add_argument(
        "--keep-onmirror-info",
        help="Also copy file on mirror info",
        dest="keep_onmirror",
        action="store_true",
    )

    parser.add_argument(
        help="Mirror on source DB that is used as source of truth", dest="mirror"
    )

    args = parser.parse_args()
    context = Context(
        source_dsn=args.source_dsn,
        target_dsn=args.target_dsn,
        mirror=args.mirror,
        truncate=args.truncate,
        keep_onmirror=args.keep_onmirror,
    )

    try:
        context.source_db.connect()
        context.target_db.connect()
        return run(context=context)
    except Exception as exc:
        logger.critical(f"Failed to run copydb: {exc!s}", exc_info=True)
        return 1
    finally:
        context.source_db.close()
        context.target_db.close()


def get_single(db: PostgresqlDatabase, query: str, *args: str) -> Any:
    return next(db.execute_sql(query, args))[0]  # pyright: ignore


def run(context: Context) -> int:
    source_db = context.source_db
    target_db = context.target_db
    mirror_ident = context.mirror

    logger.info(
        "Starting copydb\n"
        f"FROM {context.source_dsn.geturl()}\n"
        f"TO {context.target_dsn.geturl()}\n"
        f"trusting {mirror_ident}"
    )

    nb_files_on_source: int = get_single(
        source_db, "SELECT mirr_get_nfiles(%s);", mirror_ident
    )
    nb_files_on_target: int = get_single(
        target_db, "SELECT mirr_get_nfiles(%s);", mirror_ident
    )

    logger.info(f"SOURCE recorded files for {mirror_ident}: {nb_files_on_source}")
    logger.info(f"TARGET recorded files for {mirror_ident}: {nb_files_on_target}")

    if nb_files_on_target > nb_files_on_source:
        logger.critical("More files on target than source. Looks like a mistake.")
        return 2

    logger.info("COPY version")
    version_res: Cursor = source_db.execute_sql(
        "SELECT id, component, major, minor, patchlevel FROM version ORDER BY id ASC;"
    )
    with target_db.atomic():
        target_db.execute_sql("TRUNCATE table version RESTART IDENTITY;")
        for version_row in version_res:
            target_db.execute_sql(
                "INSERT INTO version (id, component, major, minor, patchlevel) "
                "VALUES (%s, %s, %s, %s, %s)",
                version_row,
            )

    logger.info("COPY country")
    country_res: Cursor = source_db.execute_sql(
        "SELECT code, name FROM country ORDER BY code, name ASC;"
    )
    with target_db.atomic():
        if context.truncate:
            target_db.execute_sql("TRUNCATE table country RESTART IDENTITY;")
        for country_row in country_res:
            target_db.execute_sql(
                "INSERT INTO country (code, name) VALUES (%s, %s)",
                country_row,
            )

    logger.info("COPY region")
    region_res: Cursor = source_db.execute_sql(
        "SELECT code, name FROM region ORDER BY code, name ASC;"
    )
    with target_db.atomic():
        if context.truncate:
            target_db.execute_sql("TRUNCATE table region RESTART IDENTITY;")
        for region_row in region_res:
            target_db.execute_sql(
                "INSERT INTO region (code, name) VALUES (%s, %s)",
                region_row,
            )

    logger.info("COPY server")
    server_ids_map: dict[int, int] = {}  # source_id, target_id
    source_mirror_id = target_mirror_id = 0

    server_res: Cursor = source_db.execute_sql(
        "SELECT id, identifier, "
        "baseurl, baseurl_ftp, baseurl_rsync, enabled, status_baseurl, "
        "region, country, asn, prefix, ipv6_only, score, scan_fpm, "
        "last_scan, comment, operator_name, operator_url, public_notes, "
        "admin, admin_email, "
        "lat, lng, country_only, region_only, as_only, prefix_only, other_countries, "
        "file_maxsize FROM server ORDER BY id ASC;"
    )
    with target_db.atomic():
        if context.truncate:
            target_db.execute_sql("TRUNCATE table server RESTART IDENTITY;")
        for server_row in server_res:
            source_id = server_row[0]
            insert_cursor = target_db.execute_sql(
                "INSERT INTO server (identifier, "
                "baseurl, baseurl_ftp, baseurl_rsync, enabled, status_baseurl, "
                "region, country, asn, prefix, ipv6_only, score, scan_fpm, "
                "last_scan, comment, operator_name, operator_url, public_notes, "
                "admin, admin_email, "
                "lat, lng, "
                "country_only, region_only, as_only, prefix_only, other_countries, "
                "file_maxsize) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id;",
                server_row[1:],
            )
            target_id = next(insert_cursor)[0]
            server_ids_map[source_id] = target_id
            if server_row[1] == mirror_ident:
                source_mirror_id = source_id
                target_mirror_id = target_id

    assert source_mirror_id  # noqa: S101
    assert target_mirror_id  # noqa: S101

    logger.info("COPY filearr and hash")
    filearr_res: Cursor = source_db.execute_sql(
        "SELECT id, path, mirrors FROM filearr WHERE %s = ANY(mirrors) "
        "ORDER BY id ASC;",
        (source_mirror_id,),
    )
    with target_db.atomic(), tqdm(total=nb_files_on_source) as pbar:
        if context.truncate:
            target_db.execute_sql("TRUNCATE table hash RESTART IDENTITY CASCADE;")
            target_db.execute_sql("TRUNCATE table filearr RESTART IDENTITY CASCADE;")

        for filearr_row in filearr_res:
            insert_cursor: Cursor = target_db.execute_sql(
                "INSERT INTO filearr (path, mirrors) VALUES (%s, %s) RETURNING id;",
                (
                    filearr_row[1],
                    [server_ids_map[sid] for sid in filearr_row[2]]
                    if context.keep_onmirror
                    else [target_mirror_id],
                ),
            )
            new_file_id = next(insert_cursor)[0]
            thishash_res: Cursor = source_db.execute_sql(
                "SELECT mtime, size, md5, sha1, sha256, sha1piecesize, "
                "sha1pieces, btih from hash WHERE file_id = %s;",
                (filearr_row[0],),
            )
            for thishash_row in thishash_res:
                target_db.execute_sql(
                    "INSERT INTO hash (file_id, mtime, size, md5, sha1, sha256, "
                    "sha1piecesize, sha1pieces, btih, "
                    "pgp, zblocksize, zhashlens, zsums) "
                    "VALUES (%s, %s, %s, %b, %b, %b, %b, %b, %b, '', 0, '', '');",
                    (new_file_id, *thishash_row),
                )
            pbar.update(1)

    return 0


if __name__ == "__main__":
    entrypoint()
