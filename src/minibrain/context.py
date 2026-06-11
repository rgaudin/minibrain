import configparser
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_origin

DEFAULT_CONFIG_PATH = os.getenv("MIRRORBRAIN_CONFIG_FILE", "/etc/mirrorbrain.conf")
DEFAULT_INCIDENTS_FOLDER: Path = (
    Path(os.getenv("INCIDENTS_FOLDER", "incidents")).expanduser().resolve()
)


@dataclass(kw_only=True)
class AlertDestination:
    proto: str
    address: str

    @classmethod
    def parse(cls, text: str) -> AlertDestination:
        parts = text.split(":", 1)
        return cls(proto=parts[0], address=parts[-1])

    @property
    def is_valid(self):
        """email"""
        match self.proto:
            case "email":
                return re.match(
                    r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$)", self.address
                )
            case "slack":
                return re.match(r"^[#@][a-zA-Z0-9._-]", self.address)
            case _:
                pass
        return False


@dataclass
class Context:
    _instance: Context | None = None
    mail_from: str = os.getenv("MAIL_FROM", "")
    mailgun_api_url: str = os.getenv("MAILGUN_API_URL", "")
    mailgun_api_key: str = os.getenv("MAILGUN_API_KEY", "")
    slack_url: str = os.getenv("SLACK_URL", "")
    slack_timeout: int = int(os.getenv("SLACK_TIMEOUT", "10"))
    incidents_folder: Path = DEFAULT_INCIDENTS_FOLDER

    # timeouts in seconds
    http_scan_timeout: int = int(os.getenv("HTTP_SCAN_TIMEOUT", "20"))
    rsync_scan_timeout: int = int(os.getenv("RSYNC_SCAN_TIMEOUT", "20"))

    debug: bool = False

    mb_name: str = ""
    mb_dbuser: str = ""
    mb_dbdriver: str = ""
    mb_dbhost: str = ""
    mb_dbport: int = 5432
    mb_dbname: str = ""
    mb_dbpass: str = ""
    mb_chunk_size: int = 262144
    mb_zsync_hashes: bool = False
    mb_chunked_hashes: bool = True
    mb_apache_documentroot: str = ""

    mb_scan_top_include: list[str] = field(default_factory=list[str])
    mb_scan_exclude_rsync: list[str] = field(default_factory=list[str])
    mb_scan_exclude: list[str] = field(default_factory=list[str])

    mirrorprobe_logfile: str = ""
    mirrorprobe_loglevel: str = ""

    logger: logging.Logger = logging.getLogger("mb")  # noqa: RUF009

    @classmethod
    def setup(cls, **kwargs: Any):
        if cls._instance:
            raise OSError("Already inited Context")
        cls._instance = cls(**kwargs)
        cls.setup_logger()

    @classmethod
    def setup_logger(cls):
        debug = cls._instance.debug if cls._instance else cls.debug
        if cls._instance:
            cls._instance.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        else:
            cls.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(levelname)-8s | %(message)s",
            datefmt="%(asctime)s ",
        )

    @classmethod
    def get(cls) -> Context:
        if not cls._instance:
            raise OSError("Uninitialized context")  # pragma: no cover
        return cls._instance

    def __post_init__(self):
        if self.mb_chunk_size % 4096 != 0:
            raise OSError("chunk_size not a multiple of 4096")

    @classmethod
    def from_file(cls, fpath: Path, *, instance_name: str, debug: bool) -> Context:
        data: dict[str, bool | int | str | list[str]] = {"debug": debug}
        config = configparser.ConfigParser()
        config.read(fpath)

        instances = [
            section
            for section in config.sections()
            if section not in ("general", "mirrorprobe")
        ]
        instance_name = next(
            name for name in config["general"]["instances"].split() if name in instances
        )

        for section in (instance_name, "mirrorprobe"):
            prefix = "mirrorprobe" if section == "mirrorprobe" else "mb"
            for key in config[section]:
                try:
                    ftype = Context.__dataclass_fields__[f"{prefix}_{key}"].type
                    if type(ftype) is not type:
                        ftype = get_origin(ftype)
                except KeyError:
                    continue

                if ftype is bool:
                    value = config[section].getboolean(key)

                value = config[section].get(key, "")

                if ftype is int:
                    value = int(value)

                elif ftype is list:
                    value = value.split()

                data[f"{prefix}_{key!s}"] = value
        data["mb_name"] = instance_name
        cls.setup(**data)
        assert cls._instance is not None  # noqa: S101
        return cls._instance

    @property
    def dsn(self) -> str:
        return f"{self.mb_dbdriver}://{self.mb_dbuser}@{self.mb_dbhost}:{self.mb_dbport}/{self.mb_dbname}"

    @property
    def mail_configured(self) -> bool:
        return all(
            [
                bool(self.mail_from),
                bool(self.mailgun_api_url),
                bool(self.mailgun_api_key),
            ]
        )

    @property
    def slack_configured(self):
        return bool(self.slack_url)
