"""Curated category rules for producing, distributing, or providing lot items."""

# Curated category rules, not an official universal OKPD2-to-OKVED crosswalk.
# Production and wholesale are separate valid activities for a goods supplier.
# Classifier definitions: https://rosstat.gov.ru/storage/mediabank/VRGUndRA/OKVED.pdf
RULES = (
    ("17.12", ("17.12", "46.76.1"), "Бумага и картон"),
    ("21.20", ("21.20", "46.46"), "Лекарственные препараты и медицинские материалы"),
    ("26.20", ("26.20", "46.51"), "Компьютеры и периферийное оборудование"),
    ("31.01", ("31.01", "46.65"), "Мебель для офисов и предприятий торговли"),
    ("31.02", ("31.02", "46.47.1"), "Кухонная мебель"),
    ("31.09", ("31.09", "46.47.1"), "Прочая мебель"),
    ("49.41", ("49.41",), "Грузовые автомобильные перевозки"),
    ("62.01", ("62.01",), "Разработка программного обеспечения"),
    ("81.21", ("81.21",), "Общая уборка зданий"),
    ("81.22", ("81.22",), "Специализированная уборка"),
)


def within(code: str, prefix: str) -> bool:
    return code == prefix or code.startswith(prefix + ".")
