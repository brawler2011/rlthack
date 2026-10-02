from datetime import date

from app.etl.new_lots import read_lots, read_winners

NOTICES = (
    '"publish_date";"procedure_id";"lot_id";"start_price";"reqnum";"procedure_name";"subject";'
    '"is_smp";"customer_inn";"customer_kpp";"is_eshop_or_aisgz"\n'
    '2025-11-17;1;10;"1 500,50";;Поставка;Поставка бумаги;true;"7807024475";"780701001";ЭМ\n'
    "2025-12-01;2;11;;;Услуги связи;;false;12345;;АИС ГЗ\n"
)
ITEMS = (
    '"lot_id";"product_name";"okpd2_code"\n'
    '10;Бумага А4;"17.12.14.129"\n'
    '10;Бумага А3;"17.12.14.129"\n'
    "11;Связь;bad code\n"
    "99;Лот не из извещений;61.10.11.110\n"
)
BIDS = (
    '"lot_id";"supplier_inn";"supplier_kpp";"is_winner"\n'
    '10;"7700000001";;true\n10;"7700000002";;false\n11;"7700000003";;false\n'
)


def test_read_lots_cleans_values_like_the_loader(tmp_path):
    (tmp_path / "n.csv").write_text(NOTICES, encoding="utf-8")
    (tmp_path / "i.csv").write_text(ITEMS, encoding="utf-8")

    paper, telecom = read_lots(tmp_path / "n.csv", tmp_path / "i.csv")

    assert (paper.lot_id, paper.subject, paper.publish_date) == (
        10,
        "Поставка бумаги",
        date(2025, 11, 17),
    )
    assert (paper.start_price, paper.customer_inn, paper.channel, paper.is_smp) == (
        1500.5,
        "7807024475",
        "ЭМ",
        True,
    )
    assert paper.items == ["Бумага А4", "Бумага А3"] and paper.okpd2_codes == ["17.12.14.129"]
    # no subject: the procedure name; a bad INN and a bad OKPD2 code are dropped
    assert (telecom.subject, telecom.customer_inn, telecom.okpd2_codes) == (
        "Услуги связи",
        None,
        [],
    )


def test_read_winners(tmp_path):
    (tmp_path / "b.csv").write_text(BIDS, encoding="utf-8")
    assert read_winners(tmp_path / "b.csv") == {10: {"7700000001"}}
