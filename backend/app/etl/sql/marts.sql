-- Supplier marts built from the clean tables lots, lot_items, bids.
-- Recreated from scratch; keys and indexes come after the load, it is faster.

DROP TABLE IF EXISTS supplier_profile, supplier_okpd2, supplier_customer, supplier_text;

-- Supplier profile: one row per INN.
CREATE TABLE supplier_profile (
    inn                text NOT NULL,              -- key
    main_kpp           text,                       -- most frequent KPP in bids
    region_code        text,                       -- from KPP, from INN for individuals
    is_spb_lo          boolean NOT NULL,           -- region 78 or 47
    n_bids             integer NOT NULL,           -- lots with a bid
    n_wins             integer NOT NULL,           -- lots won
    -- WinRate only over contested lots (2+ bidders): AIS GZ records just the winner
    n_contested_bids   integer NOT NULL,
    n_contested_wins   integer NOT NULL,
    win_rate           double precision,           -- NULL without contested bids
    -- WinRate pulled towards the average: 1 win out of 1 bid must not beat 70 out of 100
    win_rate_smoothed  double precision NOT NULL,
    won_amount         numeric(20, 2),             -- total start price of lots won
    avg_won_price      numeric(18, 2),             -- average start price of lots won (average check)
    median_won_price   numeric(18, 2),
    avg_bid_price      numeric(18, 2),             -- average start price of lots with a bid
    n_customers        integer NOT NULL,           -- distinct customers among lots won
    n_okpd2_classes    integer NOT NULL,           -- distinct OKPD2 classes: profile breadth
    -- bids in SME-only procurements: an indirect sign the supplier is an SME itself
    n_smp_bids         integer NOT NULL
);

-- Supplier experience by OKPD2 code on three levels: candidates are selected from it.
CREATE TABLE supplier_okpd2 (
    inn         text     NOT NULL,
    level       smallint NOT NULL,  -- 2, 4 or 6 digits
    prefix      text     NOT NULL,  -- 61 / 61.10 / 61.10.11
    n_bids      integer  NOT NULL,
    n_wins      integer  NOT NULL,
    won_amount  numeric(20, 2)
);  -- key (inn, level, prefix)

-- Supplier history with a specific customer.
CREATE TABLE supplier_customer (
    inn           text    NOT NULL,
    customer_inn  text    NOT NULL,
    n_bids        integer NOT NULL,
    n_wins        integer NOT NULL
);  -- key (inn, customer_inn)

-- Text for text search: the most frequent TRU names from the supplier's lots.
CREATE TABLE supplier_text (
    inn      text    NOT NULL,  -- key
    n_names  integer NOT NULL,  -- distinct names in total
    text     text    NOT NULL   -- up to 100 most frequent, one per line
);

INSERT INTO supplier_profile
WITH lot_size AS (
    SELECT lot_id, count(*) > 1 AS contested FROM bids GROUP BY lot_id
),
prior AS (
    -- Average win share in contested lots: WinRate with little history is pulled to it.
    SELECT avg(b.is_winner::int)::float8 AS p
    FROM bids b JOIN lot_size s USING (lot_id)
    WHERE s.contested
),
agg AS (
    SELECT
        b.supplier_inn                                              AS inn,
        mode() WITHIN GROUP (ORDER BY b.supplier_kpp)               AS main_kpp,
        count(*)                                                    AS n_bids,
        count(*) FILTER (WHERE b.is_winner)                         AS n_wins,
        count(*) FILTER (WHERE s.contested)                         AS n_contested_bids,
        count(*) FILTER (WHERE s.contested AND b.is_winner)         AS n_contested_wins,
        sum(l.start_price) FILTER (WHERE b.is_winner)               AS won_amount,
        avg(l.start_price) FILTER (WHERE b.is_winner)               AS avg_won_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY l.start_price)
            FILTER (WHERE b.is_winner)                              AS median_won_price,
        avg(l.start_price)                                          AS avg_bid_price,
        count(DISTINCT l.customer_inn) FILTER (WHERE b.is_winner)   AS n_customers,
        count(*) FILTER (WHERE l.is_smp)                            AS n_smp_bids
    FROM bids b
    JOIN lot_size s USING (lot_id)
    LEFT JOIN lots l USING (lot_id)
    GROUP BY b.supplier_inn
),
classes AS (
    SELECT b.supplier_inn AS inn, count(DISTINCT i.okpd2_l2) AS n_okpd2_classes
    FROM bids b
    JOIN lot_items i USING (lot_id)
    GROUP BY b.supplier_inn
)
SELECT
    a.inn,
    a.main_kpp,
    region_code(a.inn, a.main_kpp),
    region_code(a.inn, a.main_kpp) IN ('78', '47'),
    a.n_bids,
    a.n_wins,
    a.n_contested_bids,
    a.n_contested_wins,
    a.n_contested_wins::float8 / NULLIF(a.n_contested_bids, 0),
    -- 5 = weight of the average, as if every supplier had 5 extra average contested bids
    (a.n_contested_wins + 5 * prior.p) / (a.n_contested_bids + 5),
    a.won_amount,
    round(a.avg_won_price, 2),
    round(a.median_won_price::numeric, 2),
    round(a.avg_bid_price, 2),
    a.n_customers,
    coalesce(c.n_okpd2_classes, 0),
    a.n_smp_bids
FROM agg a
CROSS JOIN prior
LEFT JOIN classes c USING (inn);

INSERT INTO supplier_okpd2
WITH lot_prefix AS (
    SELECT DISTINCT i.lot_id, p.level, p.prefix
    FROM lot_items i
    CROSS JOIN LATERAL (
        VALUES (2, i.okpd2_l2), (4, i.okpd2_l4), (6, i.okpd2_l6)
    ) AS p (level, prefix)
    WHERE p.prefix IS NOT NULL
)
SELECT
    b.supplier_inn,
    lp.level,
    lp.prefix,
    count(*),
    count(*) FILTER (WHERE b.is_winner),
    sum(l.start_price) FILTER (WHERE b.is_winner)
FROM bids b
JOIN lot_prefix lp USING (lot_id)
LEFT JOIN lots l USING (lot_id)
GROUP BY b.supplier_inn, lp.level, lp.prefix;

INSERT INTO supplier_customer
SELECT
    b.supplier_inn,
    l.customer_inn,
    count(*),
    count(*) FILTER (WHERE b.is_winner)
FROM bids b
JOIN lots l USING (lot_id)
WHERE l.customer_inn IS NOT NULL
GROUP BY b.supplier_inn, l.customer_inn;

INSERT INTO supplier_text
WITH names AS (
    SELECT b.supplier_inn AS inn, i.product_name, count(*) AS cnt
    FROM bids b
    JOIN lot_items i USING (lot_id)
    WHERE i.product_name IS NOT NULL
    GROUP BY b.supplier_inn, i.product_name
),
ranked AS (
    SELECT
        inn,
        product_name,
        row_number() OVER (PARTITION BY inn ORDER BY cnt DESC, product_name) AS rn,
        count(*) OVER (PARTITION BY inn) AS n_names
    FROM names
)
SELECT inn, max(n_names), string_agg(product_name, E'\n' ORDER BY rn)
FROM ranked
WHERE rn <= 100
GROUP BY inn;

ALTER TABLE supplier_profile ADD PRIMARY KEY (inn);
ALTER TABLE supplier_okpd2 ADD PRIMARY KEY (inn, level, prefix);
ALTER TABLE supplier_customer ADD PRIMARY KEY (inn, customer_inn);
ALTER TABLE supplier_text ADD PRIMARY KEY (inn);
CREATE INDEX supplier_okpd2_prefix_idx ON supplier_okpd2 (level, prefix);
CREATE INDEX supplier_customer_customer_idx ON supplier_customer (customer_inn);

ANALYZE supplier_profile, supplier_okpd2, supplier_customer, supplier_text;
