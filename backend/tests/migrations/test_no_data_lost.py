"""Every migration keeps every row (R-QA-04): run for each step and for each chain to the latest.

The database at the earlier version is filled with rows in every table, built
from what the schema says (types, keys, links between tables), so that a new
migration is covered without changing this file. After the upgrade, every
table that was there has the same number of rows and the same keys. This is
the test that catches a migration that rebuilds a table and, with foreign
keys on, deletes the rows that point at it.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.types import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    TypeEngine,
)

from tests.migrations.helpers import new_database, upgrade_to
from ytmirror.adapters.db.engine import for_reading
from ytmirror.adapters.db.schema import alembic_config

ROWS = 3
"""How many rows each table gets."""


def revisions() -> list[str]:
    """Return every revision, the first one first."""
    script = ScriptDirectory.from_config(alembic_config())
    return [revision.revision for revision in reversed(list(script.walk_revisions()))]


def upgrades() -> Iterator[tuple[str, str]]:
    """Each step, and each chain from an earlier version to the latest."""
    chain = revisions()
    for index, start in enumerate(chain[:-1]):
        yield start, chain[index + 1]
        if chain[index + 1] != chain[-1]:
            yield start, chain[-1]


def in_order(engine: Engine) -> list[str]:
    """Return the tables, each after the tables it points at."""
    schema = inspect(for_reading(engine))
    tables = [name for name in schema.get_table_names() if name != "alembic_version"]
    parents = {
        name: {link["referred_table"] for link in schema.get_foreign_keys(name)} - {name}
        for name in tables
    }
    ordered: list[str] = []
    while len(ordered) < len(tables):
        ready = sorted(n for n in tables if n not in ordered and parents[n] <= set(ordered))
        assert ready, f"tables that point at each other: {set(tables) - set(ordered)}"
        ordered += ready
    return ordered


def value_for(kind: TypeEngine[Any], table: str, column: str, number: int) -> object:
    """A value of the right type, different for each row."""
    if isinstance(kind, Boolean):
        return number % 2
    if isinstance(kind, Integer | Numeric | Float | Date | DateTime):
        return number
    if isinstance(kind, LargeBinary):
        return f"{table}.{column}.{number}".encode()
    return f"{table}.{column}.{number}"


def fill(engine: Engine) -> None:
    """Put rows in every table, with the links between tables pointing at real rows."""
    schema = inspect(for_reading(engine))
    # The schema is read before the transaction that writes holds the database.
    plan = [
        (
            table,
            schema.get_columns(table),
            schema.get_pk_constraint(table)["constrained_columns"],
            {
                link["constrained_columns"][0]: link["referred_table"]
                for link in schema.get_foreign_keys(table)
            },
        )
        for table in in_order(engine)
    ]
    keys: dict[str, list[object]] = {}
    with engine.begin() as connection:
        for table, columns, primary, links in plan:
            keys[table] = []
            for number in range(1, ROWS + 1):
                row: dict[str, object] = {}
                for column in columns:
                    name = column["name"]
                    if name in links and keys.get(links[name]):
                        targets = keys[links[name]]
                        row[name] = targets[number % len(targets)]
                    elif name in primary and isinstance(column["type"], Integer):
                        row[name] = number
                    else:
                        row[name] = value_for(column["type"], table, name, number)
                names = ", ".join(f'"{name}"' for name in row)
                places = ", ".join(f":{name}" for name in row)
                connection.execute(text(f'INSERT INTO "{table}" ({names}) VALUES ({places})'), row)
                keys[table].append(row[primary[0]] if primary else number)


def contents(engine: Engine) -> dict[str, tuple[int, list[tuple[object, ...]]]]:
    """Return, for every table, how many rows it has and their keys."""
    schema = inspect(for_reading(engine))
    found: dict[str, tuple[int, list[tuple[object, ...]]]] = {}
    with for_reading(engine).connect() as connection:
        for table in in_order(engine):
            primary = schema.get_pk_constraint(table)["constrained_columns"] or ["rowid"]
            columns = ", ".join(f'"{name}"' for name in primary)
            ordered = f'SELECT {columns} FROM "{table}" ORDER BY {columns}'
            keys = [tuple(row) for row in connection.execute(text(ordered))]
            found[table] = (len(keys), keys)
    return found


@pytest.mark.parametrize(("start", "end"), list(upgrades()), ids=lambda value: str(value))
def test_an_upgrade_keeps_every_row_of_every_table(tmp_path: Path, start: str, end: str) -> None:
    """R-QA-04: no migration loses a row, alone or in a chain to the latest version."""
    engine = new_database(tmp_path)
    upgrade_to(engine, start)
    fill(engine)
    before = contents(engine)

    upgrade_to(engine, end)

    after = contents(engine)
    assert {table: after[table] for table in before} == before
    # The first version has no table of its own yet; every later one is filled.
    assert {count for count, _ in before.values()} <= {ROWS}


def test_the_chain_starts_at_the_first_version_and_fills_the_linked_tables(
    tmp_path: Path,
) -> None:
    """infra: the check above covers the first version, and the tables linked to channels."""
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    fill(engine)

    filled = contents(engine)
    assert revisions()[0] == "0001"
    for table in ("channels", "videos", "jobs", "video_events", "pending_side_files"):
        assert filled[table][0] == ROWS
