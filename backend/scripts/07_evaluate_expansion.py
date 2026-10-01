"""Script 07: How well the registry expansion finds winners the bidding history has never seen.

Takes lots after the cutoff whose winners had no bids before it, and checks whether a winner is
in the SME registry, whether its main OKVED group is among the groups we expect for the lot,
and where the company ranks among the new companies suggested for the lot.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.etl import pipeline  # noqa: E402
from app.ml.expansion import affinity_from_db, expand, load_registry  # noqa: E402

KS = (1, 5, 10, 20, 50, 100)
GROUP_KS = (1, 3, 5, 10)

KNOWN_SQL = """
SELECT DISTINCT b.supplier_inn FROM bids b JOIN lots l USING (lot_id) WHERE l.publish_date < %s
"""
WINNERS_SQL = """
SELECT b.lot_id, l.publish_date - DATE '1970-01-01', array_agg(b.supplier_inn)
FROM bids b JOIN lots l USING (lot_id)
WHERE l.publish_date >= %s AND b.is_winner
GROUP BY b.lot_id, l.publish_date
"""
CODES_SQL = """
SELECT lot_id, array_agg(DISTINCT okpd2_code)
FROM lot_items WHERE okpd2_code IS NOT NULL AND lot_id = ANY(%s)
GROUP BY lot_id
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2025, 10, 1))
    args = parser.parse_args()

    with pipeline.connect() as conn, pipeline.timed("[07] Reading data"):
        known = {r[0] for r in conn.execute(KNOWN_SQL, (args.cutoff,))}
        lots = conn.execute(WINNERS_SQL, (args.cutoff,)).fetchall()
        cold = [(lot, day, inns) for lot, day, inns in lots if not known.intersection(inns)]
        codes = dict(conn.execute(CODES_SQL, ([lot for lot, _, _ in cold],)).fetchall())
        registry = load_registry(conn)
        affinity = affinity_from_db(conn, args.cutoff)

    exclude = np.isin(registry.inns, list(known))
    row_of = {inn: i for i, inn in enumerate(registry.inns.tolist())}
    in_registry = available = 0
    ranks, group_ranks, pool_sizes = [], [], []
    for lot, day, inns in cold:
        rows = [row_of[i] for i in inns if i in row_of]
        in_registry += bool(rows)
        rows = [r for r in rows if registry.since_day[r] <= day]
        available += bool(rows)
        lot_codes = codes.get(lot, [])
        shares = affinity.for_codes(lot_codes)
        groups = sorted(shares, key=shares.get, reverse=True)
        winner_groups = {registry.main_group[r] for r in rows}
        group_ranks.append(
            min((i + 1 for i, g in enumerate(groups) if g in winner_groups), default=None)
        )
        order, _, _ = expand(registry, affinity, lot_codes, exclude, day, top=None)
        pool_sizes.append(len(order))
        hits = np.flatnonzero(np.isin(order, rows))
        ranks.append(int(hits[0]) + 1 if len(hits) else None)

    n = len(cold)
    print(f"    lots after {args.cutoff} with a winner: {len(lots)}")
    print(f"    winner never bid before the cutoff: {n} ({n / len(lots):.1%})")
    print(f"    winner in the SME registry: {in_registry} ({in_registry / n:.1%}),")
    print(f"      already registered on the lot date: {available} ({available / n:.1%})")
    print(f"    median pool of new companies per lot: {int(np.median(pool_sizes))}")

    def recall(values, ks):
        return "  ".join(
            f"@{k}: {sum(r is not None and r <= k for r in values) / n:.3f}" for k in ks
        )

    print(f"    winner's OKVED group among expected groups:   {recall(group_ranks, GROUP_KS)}")
    print(f"    winner among suggested new companies:         {recall(ranks, KS)}")
    print("    (shares of all cold lots)")


if __name__ == "__main__":
    main()
