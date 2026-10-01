import time
from datetime import date

from app.schemas.batch import BatchLotResult, BatchResponse, Invitation
from app.schemas.lot import LotListItem
from app.schemas.supplier import SearchFilters, SearchRequest
from app.services.search_service import search_service

LOTS_OF_DAY_SQL = """
SELECT lot_id, publish_date, subject, start_price::float8 AS start_price, channel, customer_inn
FROM lots
WHERE publish_date = coalesce(%(day)s, (SELECT max(publish_date) FROM lots))
ORDER BY start_price DESC NULLS LAST, lot_id
LIMIT %(limit)s
"""


class BatchService:
    """The background robot: every day it takes the newly published notices, picks suppliers
    for each and prepares invitations, known suppliers and new ones from the registry."""

    def run_daily_match(
        self, conn, day: date | None, max_lots: int, per_lot: int, new_per_lot: int
    ) -> BatchResponse:
        started = time.perf_counter()
        lots = [
            LotListItem(**r)
            for r in conn.execute(LOTS_OF_DAY_SQL, {"day": day, "limit": max_lots}).fetchall()
        ]
        results = []
        for lot in lots:
            request = SearchRequest(
                lot_id=lot.lot_id, filters=SearchFilters(), limit=per_lot, new_limit=new_per_lot
            )
            found = search_service.search(conn, request)
            invitations = [
                Invitation(
                    inn=s.inn,
                    name=s.name,
                    role_display=s.role_display,
                    score=s.score,
                    reason=s.explanation.summary,
                    is_new=False,
                )
                for s in found.items
            ] + [
                Invitation(
                    inn=s.inn,
                    name=s.name,
                    role_display=s.role_display,
                    score=s.score,
                    reason=s.reason,
                    is_new=True,
                )
                for s in found.new_suppliers
            ]
            winners = found.lot.actual_winners
            results.append(
                BatchLotResult(
                    lot=lot,
                    invitations=invitations,
                    actual_winners=winners,
                    winner_invited=any(i.inn in winners for i in invitations),
                )
            )
        return BatchResponse(
            day=lots[0].publish_date if lots else (day or date.today()),
            lots=results,
            total_invitations=sum(len(r.invitations) for r in results),
            timing_ms=round((time.perf_counter() - started) * 1000, 1),
        )


batch_service = BatchService()
