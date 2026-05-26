"""Configuration loading for mywebapp.

Variant V2 = 2 -> the application is configured via a configuration file.
The file format chosen for this work is TOML (parsed with the standard
library ``tomllib``, available since Python 3.11; Ubuntu 24.04 ships 3.12).

Default path: /etc/mywebapp/config.toml
It can be overridden with the MYWEBAPP_CONFIG environment variable, which is
convenient for development and testing.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass

DEFAULT_CONFIG_PATH = "/etc/mywebapp/config.toml"
ENV_CONFIG_PATH = "MYWEBAPP_CONFIG"


@dataclass(frozen=True)
class ServerConfig:
    """Network configuration of the web application itself."""

    host: str
    port: int


@dataclass(frozen=True)
class DatabaseConfig:
    """Connection parameters for the PostgreSQL database."""

    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    database: DatabaseConfig


def config_path() -> str:
    """Return the configuration file path (env override or default)."""
    return os.environ.get(ENV_CONFIG_PATH, DEFAULT_CONFIG_PATH)


def load_config(path: str | None = None) -> Config:
    """Load and validate the configuration file.

    Raises FileNotFoundError if the file is missing and KeyError if a
    mandatory option is absent — both are fatal and must stop the service.
    """
    path = path or config_path()
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    server = ServerConfig(
        host=str(raw["server"]["host"]),
        port=int(raw["server"]["port"]),
    )
    database = DatabaseConfig(
        host=str(raw["database"]["host"]),
        port=int(raw["database"]["port"]),
        name=str(raw["database"]["name"]),
        user=str(raw["database"]["user"]),
        password=str(raw["database"]["password"]),
    )
    return Config(server=server, database=database)


def dsn(database: DatabaseConfig) -> str:
    """Build a libpq connection string for psycopg.

    ``connect_timeout`` keeps a single connection attempt short so that the
    readiness probe fails fast when the database is unreachable instead of
    hanging on the operating-system default timeout.
    """
    return (
        f"host={database.host} "
        f"port={database.port} "
        f"dbname={database.name} "
        f"user={database.user} "
        f"password={database.password} "
        f"connect_timeout=5"
    )
