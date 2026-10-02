"""Script 08: Supplier recommendations for lots from CSV files, written to a CSV.

Reads a notices CSV and an items (TRU) CSV in the format of the training data and runs every lot
through the engine as a new procurement. A lot sees the bids before the start of its month, all
of them for lots after the data, so a lot that is in the data does not see its own winner.

Output: a row per lot and suggested supplier, best first (is_new = 0), then companies from the
SME registry that never bid (is_new = 1, with --new). With --answers (a suppliers CSV) it also
prints how often a real winner is in the top K.
"""

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.etl.new_lots import read_lots, read_winners  # noqa: E402
from app.ml.semantic_retriever import encode  # noqa: E402
from app.ml.text import lot_text  # noqa: E402
from app.schemas.lot import LotCard  # noqa: E402
from app.schemas.supplier import SearchFilters  # noqa: E402
from app.services.engine import Engine, month_start  # noqa: E402

FIELDS = (
    "lot_id",
    "rank",
    "supplier_inn",
    "supplier_name",
    "role",
    "score",
    "is_new",
    "n_wins",
    "n_bids",
    "win_rate",
    "reason",
)
KS = (1, 5, 10, 20)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notices", type=Path, required=True, help="notices (извещения) CSV")
    parser.add_argument("--items", type=Path, required=True, help="items (ТРУ) CSV")
    parser.add_argument("--out", type=Path, default=Path("predictions.csv"))
    parser.add_argument("--top", type=int, default=20, help="known suppliers per lot")
    parser.add_argument("--new", type=int, default=0, help="new registry companies per lot")
    parser.add_argument("--sep", default=";", help="output delimiter")
    parser.add_argument("--answers", type=Path, help="suppliers CSV to check the top K")
    return parser.parse_args()


def main():
    args = parse_args()
    with pipeline.timed("[08] Reading lots"):
        lots = read_lots(args.notices, args.items)
    print(f"    lots: {len(lots)}, with OKPD2 codes: {sum(bool(lot.okpd2_codes) for lot in lots)}")
    with pipeline.timed("[08] Loading the engine"):
        engine = Engine()
    with pipeline.timed(f"[08] Encoding {len(lots)} lot texts"):
        texts = [lot_text(lot.subject, lot.items) for lot in lots]
        vectors = encode(engine.encoder, texts, progress=True)

    filters = SearchFilters(roles=[], only_spb_lo=False, only_smp=False, min_win_rate=0)
    # Month by month: the engine keeps a few history snapshots.
    order = sorted(range(len(lots)), key=lambda i: lots[i].publish_date or date.max)
    predicted: dict[int, list[str]] = {}
    started = time.perf_counter()
    with (
        psycopg.connect(settings.database_url, row_factory=dict_row) as conn,
        args.out.open("w", newline="", encoding="utf-8") as f,
        pipeline.timed(f"[08] Recommending suppliers for {len(lots)} lots"),
    ):
        writer = csv.writer(f, delimiter=args.sep)
        writer.writerow(FIELDS)
        for done, i in enumerate(order, start=1):
            lot = lots[i]
            day = (lot.publish_date - date(1970, 1, 1)).days if lot.publish_date else engine.today
            # A lot id makes the engine take the snapshot of the lot's month; later lots use all.
            in_data_period = month_start(day) < engine.today
            query = engine.data.new_query(
                vectors[i],
                lot.okpd2_codes,
                lot.customer_inn,
                lot.start_price,
                lot.channel,
                lot.is_smp,
                day,
            )
            card = LotCard(
                lot_id=lot.lot_id if in_data_period else None,
                publish_date=lot.publish_date,
                subject=lot.subject,
                procedure_name=lot.procedure_name,
                start_price=lot.start_price,
                okpd2_codes=lot.okpd2_codes,
                items=lot.items,
                customer_inn=lot.customer_inn,
                channel=lot.channel,
                is_smp=lot.is_smp,
                actual_winners=[],
            )
            result = engine.search(conn, card, query, lot.okpd2_codes, filters, args.top, args.new)
            for s in result.items:
                win_rate = "" if s.win_rate is None else round(s.win_rate, 3)
                writer.writerow(
                    (lot.lot_id, s.rank, s.inn, s.name or "", s.role, s.score, 0)
                    + (s.n_wins, s.n_bids, win_rate, s.explanation.summary)
                )
            for rank, s in enumerate(result.new_suppliers, start=1):
                writer.writerow(
                    (lot.lot_id, rank, s.inn, s.name or "", s.role, s.score, 1, "", "", "")
                    + (s.reason,)
                )
            predicted[lot.lot_id] = [s.inn for s in result.items]
            if done % 500 == 0:
                rate = (time.perf_counter() - started) / done
                print(f"    {done} of {len(lots)}, {rate:.2f} s per lot", flush=True)
    print(f"    saved to {args.out}")

    if args.answers:
        winners = read_winners(args.answers)
        checked = [lot_id for lot_id in predicted if winners.get(lot_id)]
        hits = [
            next((r for r, inn in enumerate(predicted[lot_id], 1) if inn in winners[lot_id]), None)
            for lot_id in checked
        ]
        n = max(len(checked), 1)
        recall = "  ".join(
            f"@{k}: {sum(h is not None and h <= k for h in hits) / n:.3f}" for k in KS
        )
        print(f"    lots with a known winner: {len(checked)}; winner in the top {recall}")


if __name__ == "__main__":
    main()
