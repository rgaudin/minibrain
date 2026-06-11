import datetime
import os
from collections.abc import Sequence
from pathlib import Path

import humanfriendly  # pyright: ignore[reportMissingTypeStubs]
import requests
from werkzeug.datastructures import MultiDict

from minibrain.context import AlertDestination, Context
from minibrain.utils.probe import ProbeResponse

context = Context.get()
logger = context.logger


class Incident:
    @classmethod
    def mirror_path(cls, mirror: str) -> Path:
        return context.incidents_folder.joinpath(mirror)

    @classmethod
    def exists(cls, mirror: str) -> bool:
        try:
            return cls.mirror_path(mirror).exists()
        except:
            raise
        return False

    @classmethod
    def get(cls, mirror: str) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(
            cls.mirror_path(mirror).stat().st_mtime, tz=datetime.UTC
        )

    @classmethod
    def set(cls, mirror: str, on: datetime.datetime):
        cls.mirror_path(mirror).parent.mkdir(parents=True, exist_ok=True)
        cls.mirror_path(mirror).touch()
        os.utime(cls.mirror_path(mirror), times=(on.timestamp(), on.timestamp()))

    @classmethod
    def remove(cls, mirror: str):
        cls.mirror_path(mirror).unlink(missing_ok=True)


type AddressList = list[str] | tuple[str] | str


def send_mailgun_email(
    to: str,
    subject: str,
    contents: str,
    cc: AddressList | None = None,
    bcc: AddressList | None = None,
    headers: dict[str, str] | None = None,  # noqa: ARG001
    attachments: Sequence[Path] | None = None,
) -> str:
    # ***<module>.send_mailgun_email: Failure: Different bytecode
    values: list[tuple[str, str | AddressList]] = [
        ("from", context.mail_from),
        ("subject", subject),
        ("html", contents),
    ]
    values += [("to", to if isinstance(to, list | tuple) else [to])]
    if cc:
        values += [("cc", [cc] if isinstance(cc, str) else cc)]
    if bcc:
        values += [("bcc", [bcc] if isinstance(bcc, str) else bcc)]
    data = MultiDict(values)
    resp = requests.post(
        url=f"{context.mailgun_api_url}/messages",
        auth=("api", context.mailgun_api_key),
        data=data,
        files=[
            ("attachment", (fpath.name, fpath.read_bytes())) for fpath in attachments
        ]
        if attachments
        else [],
        timeout=6,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def send_email_mirror_status_change(target: str, probe: ProbeResponse):
    if not context.mail_configured:
        return None
    emoji = ":large_green_circle:" if probe.succeeded else ":red_circle:"
    try:
        send_mailgun_email(
            to=target,
            subject=f"{emoji} Incident {('resolved' if probe.succeeded else 'started')}"
            f" on {probe.mirror}",
            contents=f"Probed on: {probe.on.strftime('%c')}\n"
            f"Checked URL: {probe.url}\n"
            f"Root Cause: {probe.response}",
        )
    except Exception as exc:
        logger.error(f"Failed to submit email notification: {exc}")
        logger.exception(exc)


def send_probe_status_change_alert(
    probe: ProbeResponse, alerts: list[AlertDestination]
):
    for alert in alerts:
        if not alert.is_valid:
            logger.warning(f"Not sending alert to {alert} (invalid)")
            continue
        elif alert.proto == "slack":
            send_slack_mirror_status_change(target=alert.address, probe=probe)


def send_slack_mirror_status_change(target: str, probe: ProbeResponse):
    if not context.slack_url:
        return

    emoji = ":large_green_circle:" if probe.succeeded else ":red_circle:"
    try:
        time_field: dict[str, str]
        # we're back online, we might have a duration
        if probe.succeeded and Incident.exists(probe.mirror):
            duration = probe.on - Incident.get(probe.mirror)
            time_field = {
                "title": "Duration",
                "value": humanfriendly.format_timespan(duration),  # pyright: ignore[reportUnknownMemberType]
            }
        elif probe.succeeded:
            time_field = {
                "title": "Probed on",
                "value": f"{probe.on.strftime('%a %B %d, %Y at %H:%M:%S')} UTC",
            }
        else:
            time_field = {
                "title": "Started on",
                "value": f"{probe.on.strftime('%a %B %d, %Y at %H:%M:%S')} UTC",
            }
            Incident.set(probe.mirror, on=probe.on)

        requests.post(
            url=context.slack_url,
            timeout=context.slack_timeout,
            json={
                "channel": f"{target}",
                "username": "Mirrorbrain Probe",
                "icon_url": "https://get.kiwix.org/favicon-96x96.png",
                "attachments": [
                    {
                        "fallback": (
                            f"{emoji} {('REVIVED' if probe.succeeded else 'FAILED')} "
                            f"{probe!s}"
                        ),
                        "pretext": (
                            f"{emoji} "
                            f"Incident {('resolved' if probe.succeeded else 'started')}"
                            f" on {probe.mirror}"
                        ),
                        "color": "#24B064" if probe.succeeded else "#DF3717",
                        "fields": [
                            time_field,
                            {"title": "Checked URL", "value": f"{probe.url}"},
                            {"title": "Root Cause", "value": f"`{probe.response}`"},
                        ],
                    }
                ],
            },
        )
    except Exception as exc:
        logger.error(f"Failed to submit slack notification: {exc}")
        logger.exception(exc)
    else:
        if probe.succeeded:
            Incident.remove(probe.mirror)
