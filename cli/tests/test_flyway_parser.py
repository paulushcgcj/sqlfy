"""
test_flyway_parser.py
====================
Unit tests for upgraded Flyway version parser and reconstructor handling
nested directory paths, sub-versions, and non-Flyway SQL files.
"""

from __future__ import annotations

from sqlfy.migrations.parser import parse_flyway_ver
from sqlfy.reconstructor import Reconstructor


def test_parse_simple_flyway_ver():
    p = parse_flyway_ver("V1__init.sql")
    assert p["version"] == "1"
    assert p["description"] == "init"
    assert p["is_flyway"] is True
    assert p["order"] == (0, (1,))


def test_parse_sub_version_dotted():
    p = parse_flyway_ver("V1.2.3__create_table.sql")
    assert p["version"] == "1.2.3"
    assert p["description"] == "create table"
    assert p["is_flyway"] is True
    assert p["order"] == (0, (1, 2, 3))


def test_parse_sub_version_underscores():
    p = parse_flyway_ver("V1_2_3_4__migration.sql")
    assert p["version"] == "1.2.3.4"
    assert p["description"] == "migration"
    assert p["is_flyway"] is True
    assert p["order"] == (0, (1, 2, 3, 4))


def test_parse_nested_directory_path():
    p = parse_flyway_ver("THE/scripts/subfolder/V2.10.1__add_indexes.sql")
    assert p["version"] == "2.10.1"
    assert p["description"] == "add indexes"
    assert p["is_flyway"] is True
    assert p["order"] == (0, (2, 10, 1))


def test_version_sorting_order():
    filenames = [
        "V1.10.0__tenth.sql",
        "V1.2.0__second.sql",
        "V1.1.2__one_one_two.sql",
        "V1.1.1__one_one_one.sql",
        "V1.1.1.1__one_one_one_one.sql",
        "R__seed.sql",
        "random_script.sql",
    ]

    parsed = [parse_flyway_ver(fn) for fn in filenames]
    sorted_parsed = sorted(parsed, key=lambda p: p["order"])

    sorted_versions = [p["version"] for p in sorted_parsed]
    expected_versions = [
        "1.1.1",
        "1.1.1.1",
        "1.1.2",
        "1.2.0",
        "1.10.0",
        "R__seed",
        "random_script.sql",
    ]
    assert sorted_versions == expected_versions


def test_non_flyway_fallback():
    p1 = parse_flyway_ver("THE/scripts/01_create.sql")
    p2 = parse_flyway_ver("THE/scripts/02_insert.sql")

    assert p1["is_flyway"] is False
    assert p2["is_flyway"] is False
    assert p1["version"] == "THE/scripts/01_create.sql"
    assert p2["version"] == "THE/scripts/02_insert.sql"


def test_reconstructor_does_not_skip_nested_non_flyway_files():
    files = [
        {
            "filename": "THE/scripts/01_users.sql",
            "sql": "CREATE TABLE users (id INT PRIMARY KEY);",
        },
        {
            "filename": "THE/scripts/02_orders.sql",
            "sql": "CREATE TABLE orders (id INT PRIMARY KEY, user_id INT);",
        },
        {
            "filename": "THE/sub/V1.1.1__products.sql",
            "sql": "CREATE TABLE products (id INT PRIMARY KEY);",
        },
    ]

    r = Reconstructor()
    graph = r.apply_all(files)

    assert "USERS" in graph.tables
    assert "ORDERS" in graph.tables
    assert "PRODUCTS" in graph.tables
    assert len(graph.tables) == 3
