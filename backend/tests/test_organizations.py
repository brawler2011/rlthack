"""Bulk FNS parsing and enrichment of registry companies without procurement history."""

import csv
import importlib
import zipfile
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace

organizations = importlib.import_module("scripts.09_organizations")
INN = "7800000001"
OTHER = "7700000001"


def archive(directory, name, body):
    xml = f'<?xml version="1.0" encoding="windows-1251"?><Файл>{body}</Файл>'
    with zipfile.ZipFile(directory / f"{name}.zip", "w") as z:
        z.writestr("report.xml", xml.encode("cp1251"))
        z.writestr("readme.txt", "Not XML")


def test_bulk_reports_preserve_zero_and_missing_values_and_ignore_other_companies(tmp_path):
    archive(
        tmp_path,
        "revexp",
        f'<Документ><СведНП ИННЮЛ="{INN}"/>'
        '<СведДохРасх СумРасход="15.25" СумДоход="0"/></Документ>'
        f'<Документ><СведНП ИННЮЛ="{OTHER}"/>'
        '<СведДохРасх СумДоход="100" СумРасход="50"/></Документ>',
    )
    archive(
        tmp_path,
        "paytax",
        f'<Документ><СведНП ИННЮЛ="{INN}"/>'
        '<СвУплНал СумУплНал="10.5"/><СвУплНал СумУплНал="4"/></Документ>',
    )
    archive(tmp_path, "debtam", f'<Документ><СведНП ИННЮЛ="{INN}"/></Документ>')
    archive(
        tmp_path,
        "sshr",
        f'<Документ><СведНП ИННЮЛ="{INN}"/><СведССЧР КолРаб="0"/></Документ>',
    )
    assert organizations.fns_open_data(tmp_path, {INN}) == {
        INN: {"revenue": 0, "expenses": 15.25, "taxes_paid": 14.5, "tax_debt": 0, "headcount": 0}
    }
    assert organizations.fns_open_data(tmp_path, {"500100732259"}) == {}


def test_bulk_build_keeps_existing_metadata_and_adds_a_registry_company_without_bids(
    tmp_path, monkeypatch
):
    path = tmp_path / "organizations.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, organizations.FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerow(
            {
                "inn": OTHER,
                "name": "Existing supplier",
                "registered": "2010-01-01",
                "tax_debt": "900000",
                "source": "egrul",
            }
        )
    archive(
        tmp_path,
        "revexp",
        f'<Документ><СведНП ИННЮЛ="{INN}"/>'
        '<СведДохРасх СумДоход="1000000" СумРасход="2000000"/></Документ>',
    )
    archive(tmp_path, "debtam", f'<Документ><СведНП ИННЮЛ="{INN}"/></Документ>')
    conn = SimpleNamespace(
        execute=lambda query: SimpleNamespace(
            fetchall=lambda: [(OTHER, False), (INN, True), ("500100732259", True)]
        )
    )
    monkeypatch.setattr(organizations.pipeline, "connect", lambda: nullcontext(conn))
    monkeypatch.setattr(organizations, "egrul", lambda inn: pytest_fail())
    monkeypatch.setattr(organizations, "statements", lambda inn: pytest_fail())
    organizations.build(path, tmp_path, bulk_only=True)
    with path.open(encoding="utf-8") as f:
        rows = {row["inn"]: row for row in csv.DictReader(f, delimiter=";")}
    assert Decimal(rows[INN]["revenue"]) == 1000000
    assert rows[INN]["source"] == "fns"
    assert rows[INN]["registered"] == ""
    assert rows[OTHER]["name"] == "Existing supplier"
    assert rows[OTHER]["registered"] == "2010-01-01"
    assert rows[OTHER]["tax_debt"] == ""
    assert "500100732259" not in rows


def pytest_fail():
    raise AssertionError("Bulk-only refresh must not make per-company network requests")


def test_snapshot_dates_use_the_latest_record_and_keep_penalties_separate(tmp_path):
    archive(
        tmp_path,
        "debtam",
        f'<Документ ДатаСост="01.09.2026"><СведНП ИННЮЛ="{INN}"/>'
        '<СведНедоим ОбщСумНедоим="120000"/></Документ>'
        f'<Документ ДатаСост="01.06.2026"><СведНП ИННЮЛ="{INN}"/>'
        '<СведНедоим ОбщСумНедоим="900000"/></Документ>',
    )
    archive(
        tmp_path,
        "taxoffence",
        f'<Документ ДатаСост="31.12.2024"><СведНП ИННЮЛ="{INN}"/>'
        '<СведНаруш СумШтраф="50000"/></Документ>',
    )
    assert organizations.fns_open_data(tmp_path, {INN})[INN] == {
        "tax_debt": 120000,
        "tax_debt_as_of": "2026-09-01",
        "tax_fines": 50000,
        "tax_fines_as_of": "2024-12-31",
    }


def test_resource_refresh_needs_no_registry_or_database_and_preserves_metadata(
    tmp_path, monkeypatch
):
    path = tmp_path / "organizations.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, organizations.FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerow({"inn": INN, "name": "Existing", "source": "egrul"})
    archive(
        tmp_path,
        "debtam",
        f'<Документ ДатаСост="01.09.2026"><СведНП ИННЮЛ="{INN}"/>'
        '<СведНедоим ОбщСумНедоим="70000"/></Документ>',
    )
    monkeypatch.setattr(organizations.pipeline, "connect", pytest_fail)
    organizations.build(path, tmp_path, bulk_only=True, resource_only=True)
    with path.open(encoding="utf-8") as f:
        row = next(csv.DictReader(f, delimiter=";"))
    assert row["name"] == "Existing" and row["source"] == "egrul"
    assert Decimal(row["tax_debt"]) == 70000 and row["tax_debt_as_of"] == "2026-09-01"
    assert row["refreshed_at"]


def test_financial_sums_keep_exact_kopecks(tmp_path):
    for dataset, attribute, field in (
        ("paytax", "СумУплНал", "taxes_paid"),
        ("debtam", "ОбщСумНедоим", "tax_debt"),
        ("taxoffence", "СумШтраф", "tax_fines"),
    ):
        archive(
            tmp_path,
            dataset,
            f'<Документ><СведНП ИННЮЛ="{INN}"/>'
            f'<Суммы {attribute}="0.10"/><Суммы {attribute}="0.20"/></Документ>',
        )
    row = organizations.fns_open_data(tmp_path, {INN})[INN]
    for field in ("taxes_paid", "tax_debt", "tax_fines"):
        assert str(row[field]) == "0.30"
