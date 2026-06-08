# pyright: strict, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from peewee import DoesNotExist

from minibrain.context import Context
from minibrain.db import Server, database
from minibrain.utils.alerts import AlertDestination, send_probe_status_change_alert
from minibrain.utils.db import get_mb_version
from minibrain.utils.probe import probe_mirror

context = Context.get()
logger = context.logger


def mirrorprobe(
    mirror_id: str,
    *,
    dry_run: bool,
    enable_revived: bool,
    alerts: list[AlertDestination],
) -> int:

    context = Context.get()
    if dry_run:
        enable_revived = False

    logger.info(f"Starting mirrorprobe for {context.dsn}")

    if not all(dest.is_valid for dest in alerts):
        logger.warning("You have invalid --alerts")

    logger.info(f"Connected to mirrorbrain DB version {get_mb_version()}")

    try:
        mirror = Server.select().where(Server.identifier == mirror_id).get()
    except DoesNotExist:
        logger.critical(f"Server `{mirror_id}` was not found in DB")
        return 1
    if not mirror.enabled:
        logger.critical(f"Server `{mirror_id}` is not enabled.")
        return 1

    probe = probe_mirror(mirror=mirror.identifier, base_url=mirror.baseurl)

    # still failing
    if not mirror.status_baseurl and not probe.succeeded:
        logger.info(f"still dead: {probe!s}")

    # still alive
    elif mirror.status_baseurl and probe.succeeded:
        logger.info(f"alive: {probe!s}")
        if not mirror.enabled and enable_revived:
            logger.info(f"re-enabling {mirror.identifier}")
            mirror.enabled = True
            mirror.save()

    # just failed!
    elif mirror.status_baseurl and not probe.succeeded:
        logger.info(
            f"FAIL: {probe!s}" % (mirror.identifier, mirror.baseurl, mirror.response)
        )
        if not dry_run:
            send_probe_status_change_alert(probe=probe, alerts=alerts)
            logger.info(
                f"setting status_baseurl=0 for {mirror.identifier} (id={mirror.id})"
            )
            mirror.statusBaseurl = False
            mirror.save()

    # came back online!
    elif mirror.status_baseurl and probe.succeeded:
        logger.info(f"REVIVED: {mirror.identifier}")
        if not dry_run:
            send_probe_status_change_alert(probe=probe, alerts=alerts)
            logger.info(
                f"setting status_baseurl=0 for {mirror.identifier} (id={mirror.id})"
            )
            mirror.statusBaseurl = True
            if enable_revived:
                logger.info(f"re-enabling {mirror.identifier}")
                mirror.enabled = True
            mirror.save()

    database.close()

    return 0
