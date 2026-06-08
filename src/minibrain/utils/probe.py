import datetime
from dataclasses import dataclass
from http import HTTPStatus

import requests

USER_AGENT = "Minibrain Probe (see https://lb.download.kiwix.org/probe_info)"
TIMEOUT = 10


@dataclass
class ProbeResponse:
    on: datetime.datetime
    mirror: str
    url: str
    status_code: HTTPStatus | None = None
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status_code == HTTPStatus.OK

    @property
    def response(self) -> str:
        if self.status_code:
            return f"{self.status_code!s}: {self.status_code.name}"
        return self.error

    def __str__(self) -> str:
        return f"{self.mirror} ({self.url}): {self.response}"


def probe_mirror(mirror: str, base_url: str) -> ProbeResponse:
    now = datetime.datetime.now(tz=datetime.UTC)
    try:
        resp = requests.get(
            url=base_url,
            headers={"Accept": "*/*", "User-Agent": USER_AGENT},
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT,
        )
    except Exception as exc:
        return ProbeResponse(on=now, mirror=mirror, url=base_url, error=str(exc))

    return ProbeResponse(
        on=now, mirror=mirror, url=base_url, status_code=HTTPStatus(resp.status_code)
    )
