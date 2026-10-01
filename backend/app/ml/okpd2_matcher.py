class OKPD2Matcher:
    """Иерархический поиск и фильтрация по префиксам ОКПД2 (2, 4, 6 знаков)."""

    def __init__(self):
        pass

    def match_prefix(self, code: str, target_code: str) -> int:
        """Возвращает уровень совпадения (exact=6, sub=4, class=2, none=0)."""
        return 0
