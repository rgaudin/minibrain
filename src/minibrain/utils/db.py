# pyright: strict, reportUnknownMemberType=false, reportUnknownVariableType=false
from minibrain.db import Version


def get_mb_version() -> str:
    version: Version = Version.get(id=1)
    return f"{version.major!s}.{version.minor!s}.{version.patchlevel!s}"
