import argparse
import signal
import sys
from pathlib import Path
from types import FrameType

from minibrain.__about__ import __version__
from minibrain.context import DEFAULT_CONFIG_PATH, Context

logger = Context.logger


def prepare_context(raw_args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scan", description="Kiwix MirrorBrain Mirror Scanner"
    )

    parser.add_argument(
        "-c",
        "--config",
        help="Config file to use",
        dest="fpath",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
    )

    parser.add_argument(
        "-i",
        "--instance",
        help="Config file to use",
        dest="instance_name",
        default="",
    )

    parser.add_argument(
        "--dry-run",
        help="Don't make any change to DB",
        action="store_true",
        dest="dry_run",
    )

    parser.add_argument(
        "--only-scan",
        help="Just the remote server scan (alowed even if mirror is disabled)",
        action="store_true",
        dest="only_scan",
    )

    parser.add_argument(
        "--allow-insert",
        help="Trust this mirror's scanned files listing and insert File entry for each",
        action="store_true",
        dest="trusted_mirror",
    )

    parser.add_argument(
        "--enable",
        help="Enable mirror upon success",
        action="store_true",
        dest="enable",
    )

    # parser.add_argument(
    #     "-d",
    #     "--directory",
    #     help="Only scan this path under baseUrl",
    #     type=Path,
    #     dest="directory",
    # )

    parser.add_argument(
        "--debug",
        help="Enable verbose output",
        action="store_true",
        default=Context.debug,
    )

    parser.add_argument(
        "--version",
        help="Display version and exit",
        action="version",
        version=__version__,
    )

    parser.add_argument(help="Mirror to scan", dest="mirror")

    args = parser.parse_args(raw_args)
    Context.from_file(
        fpath=args.fpath, instance_name=args.instance_name, debug=args.debug
    )
    return args


def main() -> int:
    debug = Context.debug
    try:
        args = prepare_context(sys.argv[1:])
        context = Context.get()
        debug = context.debug

        from minibrain.db import database  # noqa: PLC0415
        from minibrain.tools.scan import mirrorscan  # noqa: PLC0415

        def exit_gracefully(signum: int, frame: FrameType | None):  # noqa: ARG001
            print("\n", flush=True)  # noqa: T201
            logger.info(f"Received {signal.Signals(signum).name}/{signum}. Exiting")
            sys.exit(4)

        signal.signal(signal.SIGTERM, exit_gracefully)
        signal.signal(signal.SIGINT, exit_gracefully)
        signal.signal(signal.SIGQUIT, exit_gracefully)

        try:
            database.connect()
            return mirrorscan(
                mirror_id=args.mirror,
                dry_run=args.dry_run,
                only_scan=args.only_scan,
                trusted_mirror=args.trusted_mirror,
                enable=args.enable,
                # directory=args.directory,
            )
        finally:
            database.close()
    except Exception as exc:
        logger.error(f"General failure: {exc!r}")
        if debug:
            logger.exception(exc)
        return 1


def entrypoint():
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
