-- Витрины поставщиков из очищенных таблиц lots, lot_items, bids.
-- Пересоздаются целиком; ключи и индексы — после заливки, так быстрее.

DROP TABLE IF EXISTS supplier_profile, supplier_okpd2, supplier_customer, supplier_text;

-- Профиль поставщика: одна строка на ИНН.
CREATE TABLE supplier_profile (
    inn                text NOT NULL,              -- ключ
    main_kpp           text,                       -- самый частый КПП в участиях
    region_code        text,                       -- по КПП, у ИП по ИНН
    is_spb_lo          boolean NOT NULL,           -- регион 78 или 47
    n_bids             integer NOT NULL,           -- лотов, где участвовал
    n_wins             integer NOT NULL,           -- лотов, где победил
    win_rate           double precision NOT NULL,
    -- WinRate, подтянутый к средней доле побед: 1 победа из 1 участия не должна обгонять 70 из 100
    win_rate_smoothed  double precision NOT NULL,
    won_amount         numeric(20, 2),             -- сумма НМЦК выигранных лотов
    avg_won_price      numeric(18, 2),             -- средняя НМЦК выигранных лотов («средний чек»)
    median_won_price   numeric(18, 2),
    avg_bid_price      numeric(18, 2),             -- средняя НМЦК лотов, где участвовал
    n_customers        integer NOT NULL,           -- разных заказчиков среди выигранных лотов
    n_okpd2_classes    integer NOT NULL,           -- разных классов ОКПД2: широта профиля
    -- участий в закупках только для СМП: косвенный признак, что поставщик сам СМП
    n_smp_bids         integer NOT NULL
);

-- Опыт поставщика по кодам ОКПД2 на трёх уровнях: по этой таблице отбираются кандидаты.
CREATE TABLE supplier_okpd2 (
    inn         text     NOT NULL,
    level       smallint NOT NULL,  -- 2, 4 или 6 цифр
    prefix      text     NOT NULL,  -- 61 / 61.10 / 61.10.11
    n_bids      integer  NOT NULL,
    n_wins      integer  NOT NULL,
    won_amount  numeric(20, 2)
);  -- ключ (inn, level, prefix)

-- История поставщика с конкретным заказчиком.
CREATE TABLE supplier_customer (
    inn           text    NOT NULL,
    customer_inn  text    NOT NULL,
    n_bids        integer NOT NULL,
    n_wins        integer NOT NULL
);  -- ключ (inn, customer_inn)

-- Текст для текстового поиска: самые частые наименования ТРУ из лотов поставщика.
CREATE TABLE supplier_text (
    inn      text    NOT NULL,  -- ключ
    n_names  integer NOT NULL,  -- всего разных наименований
    text     text    NOT NULL   -- до 100 самых частых, по одному на строку
);

INSERT INTO supplier_profile
WITH prior AS (
    -- Средняя доля побед по всем участиям: к ней подтягиваем WinRate поставщиков с малой историей.
    SELECT avg(is_winner::int)::float8 AS p FROM bids
),
agg AS (
    SELECT
        b.supplier_inn                                              AS inn,
        mode() WITHIN GROUP (ORDER BY b.supplier_kpp)               AS main_kpp,
        count(*)                                                    AS n_bids,
        count(*) FILTER (WHERE b.is_winner)                         AS n_wins,
        sum(l.start_price) FILTER (WHERE b.is_winner)               AS won_amount,
        avg(l.start_price) FILTER (WHERE b.is_winner)               AS avg_won_price,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY l.start_price)
            FILTER (WHERE b.is_winner)                              AS median_won_price,
        avg(l.start_price)                                          AS avg_bid_price,
        count(DISTINCT l.customer_inn) FILTER (WHERE b.is_winner)   AS n_customers,
        count(*) FILTER (WHERE l.is_smp)                            AS n_smp_bids
    FROM bids b
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
    a.n_wins::float8 / a.n_bids,
    -- 5 — «вес» средней доли побед, как будто у каждого есть 5 условных участий
    (a.n_wins + 5 * prior.p) / (a.n_bids + 5),
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
