class OKPD2Matcher:
    """Hierarchical search and filtering by OKPD2 code prefixes (2, 4, 6 digits)."""

    def __init__(self):
        pass

    def match_prefix(self, code: str, target_code: str) -> int:
        """Return match level (exact=6, sub=4, class=2, none=0)."""
        return 0
