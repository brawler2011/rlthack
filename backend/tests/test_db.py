"""CSV loading and marts on a small dataset with the hackathon dataset columns.

Database tests run only when TEST_DATABASE_URL is set: the schema in that database
gets recreated, so never point it at a working database.
"""

import os

import pytest
from psycopg.rows import dict_row

from app.etl import pipeline
from app.etl.sources import detect_sources, inspect_file

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")

# Notices: UTF-8, ';' delimiter. Lot 1 is repeated, lot 'abc' has a broken id.
NOTICES = """\
procedure_id;lot_id;start_price;reqnum;procedure_name;subject;is_smp;customer_inn;customer_kpp;is_eshop_or_aisgz
10;1;1000.50;0172200004923000344;Поставка бумаги;Бумага А4;true;7814096706;781401001;АИС ГЗ
11;2;2000;;Ремонт техники;Ремонт;false;;;Электронный магазин
12;3;3000.00;0172200004923000345;Картриджи;Картриджи;false;7801140073;780101001;АИС ГЗ
10;1;1000.50;0172200004923000344;Поставка бумаги;Бумага А4;true;7814096706;781401001;АИС ГЗ
13;abc;10;;Мусор;Мусор;false;;;АИС ГЗ
"""

# TRU items: cp1251, ',' delimiter, a comma inside quotes, code 33.12.1 has no 'kind' level.
ITEMS = """\
lot_id,product_name,okpd2_code
1,"Бумага, А4",17.12.14.110
2,Ремонт оборудования,33.12.1
3,Картридж,20.59.12.120
3,Тонер,не код
"""

# Suppliers: UTF-8 with BOM. Pair (1, 7802587594) is repeated, the INN in exponent form is
# garbage, lot 99 is missing from notices, 500100732259 is an individual without KPP.
BIDS = """\
lot_id,supplier_inn,supplier_kpp,is_winner
1,7802587594,780201001,true
1,7811383967,781101001,false
1,7802587594,780201001,false
2,7802587594,780201001,true
3,7802587594,780201001,false
3,500100732259,,true
3,"6,362E+11",780601001,false
99,7811383967,781101001,false
"""


@pytest.fixture
def raw_dir(tmp_path):
    (tmp_path / "Извещения.csv").write_text(NOTICES, encoding="utf-8")
    (tmp_path / "ТРУ.csv").write_text(ITEMS, encoding="cp1251")
    (tmp_path / "Поставщики.csv").write_text(BIDS, encoding="utf-8-sig")
    (tmp_path / "readme.txt").write_text("not a CSV", encoding="utf-8")
    return tmp_path


def test_detect_sources(raw_dir):
    sources = detect_sources(raw_dir)

    notices, items, bids = sources["notices"][0], sources["items"][0], sources["bids"][0]
    assert (notices.encoding, notices.delimiter) == ("utf-8", ";")
    assert (items.encoding, items.delimiter) == ("cp1251", ",")
    assert (bids.encoding, bids.delimiter) == ("utf-8", ",")
    assert bids.columns[0] == "lot_id"  # BOM did not leak into the column name


def test_missing_required_column(tmp_path):
    path = tmp_path / "bids.csv"
    path.write_text("lot_id,supplier_inn\n1,7802587594\n", encoding="utf-8")

    with pytest.raises(ValueError, match="is_winner"):
        inspect_file(path)


def test_missing_source(tmp_path):
    (tmp_path / "bids.csv").write_text(BIDS, encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="notices"):
        detect_sources(tmp_path)


@pytest.fixture
def db(raw_dir):
    with pipeline.connect(TEST_DATABASE_URL) as conn:
        pipeline.run_sql_file(conn, "schema.sql")
        pipeline.load_raw(conn, detect_sources(raw_dir))
        pipeline.run_sql_file(conn, "clean.sql")
        pipeline.run_sql_file(conn, "marts.sql")
        conn.commit()
        yield conn


def fetch(db, query):
    return db.cursor(row_factory=dict_row).execute(query).fetchall()


@requires_db
def test_clean_tables(db):
    lots = fetch(db, "SELECT * FROM lots ORDER BY lot_id")
    assert [lot["lot_id"] for lot in lots] == [1, 2, 3]
    assert lots[0]["reqnum"] == "0172200004923000344"  # leading zero kept
    assert lots[0]["is_smp"] is True
    assert lots[1]["customer_inn"] is None and lots[1]["reqnum"] is None

    items = fetch(db, "SELECT * FROM lot_items ORDER BY lot_id, product_name")
    assert items[0]["product_name"] == "Бумага, А4"
    assert (items[1]["okpd2_l4"], items[1]["okpd2_l6"]) == ("33.12", None)
    assert items[2]["okpd2_code"] == "20.59.12.120"
    assert items[3]["okpd2_code"] is None  # invalid code dropped, item kept

    bids = fetch(db, "SELECT * FROM bids ORDER BY lot_id, supplier_inn")
    assert len(bids) == 6
    assert bids[0] == {
        "lot_id": 1,
        "supplier_inn": "7802587594",
        "supplier_kpp": "780201001",
        "is_winner": True,
    }


@requires_db
def test_supplier_profile(db):
    rows = fetch(db, "SELECT * FROM supplier_profile")
    profiles = {row["inn"]: row for row in rows}
    assert set(profiles) == {"500100732259", "7802587594", "7811383967"}

    main = profiles["7802587594"]
    assert (main["n_bids"], main["n_wins"]) == (3, 2)
    assert main["win_rate"] == pytest.approx(2 / 3)
    assert main["region_code"] == "78" and main["is_spb_lo"] is True
    assert float(main["won_amount"]) == 3000.50
    assert float(main["avg_won_price"]) == 1500.25
    assert main["n_customers"] == 1  # the second lot won has no customer
    assert main["n_okpd2_classes"] == 3
    assert main["n_smp_bids"] == 1

    ip = profiles["500100732259"]
    assert (ip["main_kpp"], ip["region_code"], ip["is_spb_lo"]) == (None, "50", False)

    loser = profiles["7811383967"]
    assert (loser["n_bids"], loser["n_wins"]) == (2, 0)  # the bid on lot 99 counts too
    assert float(loser["avg_bid_price"]) == 1000.50
    assert 0 < loser["win_rate_smoothed"] < main["win_rate_smoothed"]


@requires_db
def test_supplier_okpd2_customer_text(db):
    prefixes = fetch(
        db,
        "SELECT level, prefix, n_bids, n_wins FROM supplier_okpd2 "
        "WHERE inn = '7802587594' ORDER BY level, prefix",
    )
    assert [(p["level"], p["prefix"]) for p in prefixes] == [
        (2, "17"),
        (2, "20"),
        (2, "33"),
        (4, "17.12"),
        (4, "20.59"),
        (4, "33.12"),
        (6, "17.12.14"),
        (6, "20.59.12"),
    ]
    assert prefixes[0]["n_wins"] == 1 and prefixes[1]["n_wins"] == 0

    customers = fetch(db, "SELECT * FROM supplier_customer WHERE inn = '7802587594'")
    assert {(c["customer_inn"], c["n_wins"]) for c in customers} == {
        ("7814096706", 1),
        ("7801140073", 0),
    }

    [text] = fetch(db, "SELECT * FROM supplier_text WHERE inn = '7802587594'")
    assert text["n_names"] == 4
    assert "Бумага, А4" in text["text"].split("\n")


@requires_db
def test_reports(db):
    report = pipeline.load_report(db)
    assert report["Notice rows in CSV"] == 5
    assert report["Lots after cleaning"] == 3
    assert report["Bids with an invalid INN"] == 1
    assert report["Bids on lots missing from notices"] == 1
    assert report["Distinct suppliers"] == 3

    channels = {row[0]: row[1:] for row in pipeline.channel_report(db)}
    assert channels["Электронный магазин"] == (1, 1, 1, 0)

    assert pipeline.mart_sizes(db)["supplier_profile"] == 3
