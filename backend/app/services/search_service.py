from fastapi import HTTPException

from app.schemas.lot import LotCard, LotListItem
from app.schemas.supplier import SearchRequest, SearchResponse
from app.services.engine import engine_state

LOT_SQL = """
SELECT lot_id, publish_date, subject, procedure_name, start_price::float8 AS start_price,
       customer_inn, channel, coalesce(is_smp, false) AS is_smp
FROM lots WHERE lot_id = %s
"""
ITEMS_SQL = "SELECT product_name, okpd2_code FROM lot_items WHERE lot_id = %s"
WINNERS_SQL = "SELECT supplier_inn FROM bids WHERE lot_id = %s AND is_winner"
FIND_SQL = """
SELECT lot_id, publish_date, subject, start_price::float8 AS start_price, channel, customer_inn
FROM lots WHERE {where} ORDER BY publish_date DESC, lot_id DESC LIMIT %(limit)s
"""


class SearchService:
    """Supplier matching for a lot, and the lots themselves."""

    def search(self, conn, request: SearchRequest) -> SearchResponse:
        engine = engine_state.engine
        if engine is None:
            raise HTTPException(503, f"Модель ещё не готова: {engine_state.status}")
        if request.lot_id is not None:
            card = self.lot_card(conn, request.lot_id)
            query = engine.data.query(engine.lot_row(request.lot_id), engine.emb)
        else:
            lot = request.lot
            card = LotCard(**lot.model_dump())
            query = engine.new_lot_query(lot)
        return engine.search(
            conn, card, query, card.okpd2_codes, request.filters, request.limit, request.new_limit
        )

    def find_lots(self, conn, query: str, limit: int) -> list[LotListItem]:
        query = query.strip()
        if query.isdigit():
            where, params = "lot_id = %(id)s OR reqnum = %(q)s", {"id": int(query), "q": query}
        elif query:
            where, params = "subject ILIKE %(like)s", {"like": f"%{query}%"}
        else:
            where, params = "true", {}
        rows = conn.execute(FIND_SQL.format(where=where), {**params, "limit": limit}).fetchall()
        return [LotListItem(**r) for r in rows]

    def lot_card(self, conn, lot_id: int) -> LotCard:
        lot = conn.execute(LOT_SQL, (lot_id,)).fetchone()
        if lot is None:
            raise HTTPException(404, f"Лот {lot_id} не найден")
        items = conn.execute(ITEMS_SQL, (lot_id,)).fetchall()
        winners = conn.execute(WINNERS_SQL, (lot_id,)).fetchall()
        return LotCard(
            **lot,
            items=[i["product_name"] for i in items if i["product_name"]],
            okpd2_codes=sorted({i["okpd2_code"] for i in items if i["okpd2_code"]}),
            actual_winners=[w["supplier_inn"] for w in winners],
        )


search_service = SearchService()
