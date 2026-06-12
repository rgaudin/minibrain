# pyright: strict, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from humanfriendly import format_size
from peewee import PostgresqlDatabase
from rich.console import Console
from rich.status import Status
from rich.table import Table
from rich.text import Text

from minibrain.context import Context
from minibrain.db import Server, database
from minibrain.utils.db import get_mb_version
from minibrain.utils.misc import format_dt

context = Context.get()
logger = context.logger


def get_single_int(db: PostgresqlDatabase, query: str, args: tuple[str | int]) -> int:
    return get_single(db, query, args)  # pyright:  ignore


def get_single(
    db: PostgresqlDatabase, query: str, args: tuple[str | int]
) -> str | int | bytes | list[int]:
    return next(db.execute_sql(query, args))[0]  # pyright: ignore


def mbstatus() -> int:

    context = Context.get()

    logger.info(f"Starting status for {context.dsn}")
    logger.warning(f"Connected to mirrorbrain DB version {get_mb_version()}")

    table = Table(title="Minibrain Status")

    table.add_column("Mirror", justify="left", style="cyan", no_wrap=True)
    table.add_column("Status")
    table.add_column("Nb. files", justify="right", style="green")
    table.add_column("Last scan", justify="right", style="")
    table.add_column("Size", justify="right", style="")

    with Status(status="Querying database…"):
        for server in Server.select().order_by(
            Server.enabled.desc(), Server.identifier.asc()
        ):
            nb_files: int = get_single_int(
                database, "SELECT mirr_get_nfiles(%s);", (server.id,)
            )

            total_size: int = (
                get_single_int(
                    database,
                    "SELECT SUM(hash.size) as total FROM hash "
                    "INNER JOIN filearr ON filearr.id = hash.file_id "
                    "WHERE %s = ANY(filearr.mirrors);",
                    (server.id,),
                )
                or 0
            )

            style = "dim" if not server.enabled else ""
            table.add_row(
                Text(f"{server.identifier}", style=style),
                Text("DISABLED", style=style)
                if not server.enabled
                else (
                    Text("ONLINE", style="green")
                    if server.status_baseurl
                    else Text("OFFLINE", style="red")
                ),
                Text(f"{nb_files:,}", style=style),
                Text(
                    f"{format_dt(server.last_scan) if server.last_scan else 'n/a'}",
                    style=style,
                ),
                Text(format_size(total_size)),
            )

    console = Console()
    console.print("")
    console.print(table)

    return 0
