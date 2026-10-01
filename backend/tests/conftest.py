"""Shared fixtures: a small dataset with the hackathon CSV columns, loaded into a test database.

Database fixtures need TEST_DATABASE_URL: the schema there gets recreated, so never point it at a
working database.
"""

import os

import pytest

from app.etl import pipeline
from app.etl.sources import detect_sources

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# Notices: UTF-8, ';' delimiter. Lot 1 is repeated, lot 'abc' has a broken id.
NOTICES = """\
publish_date;procedure_id;lot_id;start_price;reqnum;procedure_name;subject;is_smp;customer_inn;customer_kpp;is_eshop_or_aisgz
2024-03-01;10;1;1000.50;0172200004923000344;Бумага;Бумага А4;true;7814096706;781401001;АИС ГЗ
2024-03-02;11;2;2000;;Ремонт техники;Ремонт;false;;;Электронный магазин
2024-03-03;12;3;3000.00;0172200004923000345;Картриджи;Картриджи;false;7801140073;780101001;АИС ГЗ
2024-03-01;10;1;1000.50;0172200004923000344;Бумага;Бумага А4;true;7814096706;781401001;АИС ГЗ
;13;abc;10;;Мусор;Мусор;false;;;АИС ГЗ
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


@pytest.fixture
def db(raw_dir):
    with pipeline.connect(TEST_DATABASE_URL) as conn:
        pipeline.run_sql_file(conn, "schema.sql")
        pipeline.load_raw(conn, detect_sources(raw_dir))
        pipeline.run_sql_file(conn, "clean.sql")
        pipeline.run_sql_file(conn, "marts.sql")
        conn.commit()
        yield conn
