class SemanticRetriever:
    """Semantic vector search using cointegrated/rubert-tiny2."""

    def __init__(self, model_name: str = "cointegrated/rubert-tiny2"):
        self.model_name = model_name

    def retrieve(self, query: str, top_k: int = 100) -> list[str]:
        """Return candidates ranked by vector cosine similarity."""
        return []
