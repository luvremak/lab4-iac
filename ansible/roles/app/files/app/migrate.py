"""Database migration script for mywebapp.

Run as a module:  python -m app.migrate

The script connects to the database described by the configuration file and
brings its schema up to the version required by this build of the
application.

Assumptions (as required by the assignment):
  * the target database is either completely empty, or
  * it was created by a previous (or the same) version of this script.

Versioning is tracked in the ``schema_version`` table. Each migration is
applied exactly once, in ascending order. If the database is *newer* than
the application supports, the script aborts with a non-zero exit code so
that the systemd unit refuses to start an incompatible service.
"""

from __future__ import annotations

import sys

import psycopg

from .config import dsn, load_config

# ---------------------------------------------------------------------------
# Ordered list of migrations: (version, [sql statements]).
# To evolve the schema in a future release, append a new tuple — never edit
# an already-released migration.
# ---------------------------------------------------------------------------
MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            """
            CREATE TABLE items (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                quantity    INTEGER NOT NULL CHECK (quantity >= 0),
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX idx_items_created_at ON items (created_at)",
            "CREATE INDEX idx_items_name ON items (name)",
        ],
    ),
]


def target_version() -> int:
    return max((v for v, _ in MIGRATIONS), default=0)


def current_version(conn: psycopg.Connection) -> int:
    """Return the schema version recorded in the database (0 if empty)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    row = conn.execute("SELECT max(version) AS v FROM schema_version").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def migrate(conn: psycopg.Connection) -> None:
    """Apply every migration newer than the database's current version."""
    version = current_version(conn)
    target = target_version()

    if version > target:
        raise SystemExit(
            f"Database schema version {version} is newer than this "
            f"application supports ({target}). Aborting."
        )

    if version == target:
        print(f"Schema is already at version {version}; nothing to do.")
        conn.commit()
        return

    for migration_version, statements in sorted(MIGRATIONS):
        if migration_version <= version:
            continue
        print(f"Applying migration {migration_version}...")
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (%s)",
            (migration_version,),
        )

    conn.commit()
    print(f"Schema migrated to version {target}.")


def main() -> None:
    config = load_config()
    print("Connecting to the database for migration...")
    try:
        with psycopg.connect(dsn(config.database)) as conn:
            migrate(conn)
    except psycopg.OperationalError as exc:
        print(f"Could not connect to the database: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Migration finished successfully.")


if __name__ == "__main__":
    main()
