-- Move data from staging (all columns text) into typed tables.
-- Rows without a valid key are dropped; script 01 reports how many.

INSERT INTO lots
SELECT DISTINCT ON (lot_id) *
FROM (
    SELECT
        clean_bigint(lot_id)          AS lot_id,
        clean_bigint(procedure_id)    AS procedure_id,
        clean_date(publish_date)      AS publish_date,
        clean_text(reqnum)            AS reqnum,
        clean_text(procedure_name)    AS procedure_name,
        clean_text(subject)           AS subject,
        clean_money(start_price)      AS start_price,
        clean_bool(is_smp)            AS is_smp,
        clean_inn(customer_inn)       AS customer_inn,
        clean_kpp(customer_kpp)       AS customer_kpp,
        clean_text(is_eshop_or_aisgz) AS channel
    FROM stg_notices
) s
WHERE lot_id IS NOT NULL
ORDER BY lot_id;

INSERT INTO lot_items
SELECT
    lot_id,
    product_name,
    okpd2_code,
    okpd2_prefix(okpd2_code, 2),
    okpd2_prefix(okpd2_code, 4),
    okpd2_prefix(okpd2_code, 6)
FROM (
    SELECT
        clean_bigint(lot_id)       AS lot_id,
        clean_text(product_name)   AS product_name,
        clean_okpd2(okpd2_code)    AS okpd2_code
    FROM stg_items
) s
WHERE lot_id IS NOT NULL;

-- Collapse repeated (lot, INN) pairs: a win if any of the rows is a win.
INSERT INTO bids
SELECT
    lot_id,
    supplier_inn,
    mode() WITHIN GROUP (ORDER BY supplier_kpp),
    coalesce(bool_or(is_winner), false)
FROM (
    SELECT
        clean_bigint(lot_id)      AS lot_id,
        clean_inn(supplier_inn)   AS supplier_inn,
        clean_kpp(supplier_kpp)   AS supplier_kpp,
        clean_bool(is_winner)     AS is_winner
    FROM stg_bids
) s
WHERE lot_id IS NOT NULL AND supplier_inn IS NOT NULL
GROUP BY lot_id, supplier_inn;

ALTER TABLE lots ADD PRIMARY KEY (lot_id);
ALTER TABLE bids ADD PRIMARY KEY (lot_id, supplier_inn);
CREATE INDEX lot_items_lot_id_idx ON lot_items (lot_id);
CREATE INDEX bids_supplier_inn_idx ON bids (supplier_inn);

ANALYZE lots, lot_items, bids;
