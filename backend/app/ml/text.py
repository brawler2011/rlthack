"""Text cleaning for embeddings: strip procurement boilerplate that says nothing about the subject.

The rules come from the most frequent prefixes and tails of real notice subjects. There is no
lemmatization on purpose: embedding models handle word forms themselves.
"""

import re
from collections.abc import Iterable

MAX_LOT_PARTS = 11  # the subject plus up to 10 distinct item names

_PREFIX = re.compile(
    r"^(оказание\s+услуг[аи]?\s+(по\s+)?|выполнение\s+работ\s+(по\s+)?|поставка\s+"
    r"|приобретение\s+|закупка\s+)"
)
# The customer usually goes last: "... для нужд СПб ГБУЗ «Поликлиника № 93» в 2024 году".
# Only customer-like words after "для" count: "для офисной техники" is part of the subject.
_CUSTOMER_TAIL = re.compile(
    r",?\s*для\s+(нужд|обеспечения\s+нужд|государственн|санкт-петербургск|субъектов\s+малого"
    r"|(спб\s+)?(гб[а-я]*у[а-я]*|гку|гау|гуп|фгб[а-я]*)\b).*$"
)
_MONTHS = r"(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*"
_NOISE = re.compile(
    r"\([^)]*(фз|ст\.|лот)[^)]*\)"  # (п.33 ч.1 ст.93 ... 44-ФЗ), (лот 2)
    rf"|\b(в|на)\s+{_MONTHS}"
    r"|\b(в|на)\s+20\d\d(\s*-\s*20\d\d)?\s*(г\.|год[а-я]*)?"
    r"|(?<!\d)20\d\d\s*(г\.|год[а-я]*)"
    r"|№\s*[\w/-]+"
    r"|\b\d+([.,]\d+)?\s*(шт|ед|упак)\b\.?"
)
_QUOTES = re.compile(r"[«»\"“”„']")
_SPACES = re.compile(r"\s+")
_EDGE_PUNCT = " ,.;:-"


def clean_for_embedding(text: str | None) -> str:
    """Lowercase the text and drop boilerplate; falls back to the plain text if nothing is left."""
    if not text:
        return ""
    plain = _SPACES.sub(" ", text.lower().replace("ё", "е").replace("_", " ")).strip()
    s = _NOISE.sub(" ", _QUOTES.sub(" ", plain))
    s = _CUSTOMER_TAIL.sub("", s)
    s = _SPACES.sub(" ", s).strip(_EDGE_PUNCT)
    s = _PREFIX.sub("", s).strip(_EDGE_PUNCT)
    return s or plain


def lot_text(subject: str | None, item_names: Iterable[str | None]) -> str:
    """Text of a lot for embedding: the cleaned subject plus distinct cleaned item names."""
    parts: list[str] = []
    for raw in (subject, *item_names):
        cleaned = clean_for_embedding(raw)
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    return "; ".join(parts[:MAX_LOT_PARTS])
