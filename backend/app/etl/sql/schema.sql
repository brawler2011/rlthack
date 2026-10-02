-- Database schema of the supplier matching service.
-- Script 01 recreates it from scratch: everything is built from the source CSVs, so DROP is safe.

DROP TABLE IF EXISTS
    supplier_text, supplier_customer, supplier_okpd2, supplier_profile,
    bids, lot_items, lots
CASCADE;

-- Cleaning functions for raw values (staging keeps everything as text) ----------

CREATE OR REPLACE FUNCTION clean_text(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(v), '')
$$;

CREATE OR REPLACE FUNCTION clean_bigint(v text) RETURNS bigint
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{1,18}$' THEN btrim(v)::bigint END
$$;

-- Money: allow spaces as thousands separators and a decimal comma.
CREATE OR REPLACE FUNCTION clean_money(v text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN x ~ '^-?\d+(\.\d+)?$' THEN round(x::numeric, 2) END
    FROM (SELECT replace(replace(replace(btrim(v), ' ', ''), chr(160), ''), ',', '.') AS x) s
$$;

CREATE OR REPLACE FUNCTION clean_date(v text) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{4}-\d{2}-\d{2}' THEN left(btrim(v), 10)::date END
$$;

CREATE OR REPLACE FUNCTION clean_bool(v text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN lower(btrim(v)) IN ('true', 't', '1', 'yes', 'y', 'да') THEN true
        WHEN lower(btrim(v)) IN ('false', 'f', '0', 'no', 'n', 'нет') THEN false
    END
$$;

-- INN: 10 digits for a company, 12 for an individual entrepreneur. Anything else is garbage.
CREATE OR REPLACE FUNCTION clean_inn(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^(\d{10}|\d{12})$' THEN btrim(v) END
$$;

-- KPP: 9 characters, the 5th and 6th may be latin letters.
CREATE OR REPLACE FUNCTION clean_kpp(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN upper(btrim(v)) ~ '^\d{4}[0-9A-Z]{2}\d{3}$' THEN upper(btrim(v)) END
$$;

-- OKPD2 like 61.10.11.110; shorter codes (33.12.1) are valid too.
CREATE OR REPLACE FUNCTION clean_okpd2(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{2}(\.\d{1,3})*$' THEN btrim(v) END
$$;

-- OKPD2 prefix of n digits: 2 = class, 4 = group, 6 = kind. NULL if the code is shorter.
CREATE OR REPLACE FUNCTION okpd2_prefix(code text, n int) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE n
        WHEN 2 THEN substring(code FROM '^\d{2}')
        WHEN 4 THEN substring(code FROM '^\d{2}\.\d{2}')
        WHEN 6 THEN substring(code FROM '^\d{2}\.\d{2}\.\d{2}')
    END
$$;

-- Region from KPP (first 2 digits = tax office region); individuals have no KPP, so use INN.
CREATE OR REPLACE FUNCTION region_code(inn text, kpp text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT left(coalesce(kpp, inn), 2)
$$;

-- Clean data (script 01) -------------------------------------------------------
-- Keys and indexes are created in clean.sql after the load: it is faster.

-- Procurement notices: one row per lot.
CREATE TABLE lots (
    lot_id          bigint NOT NULL,  -- key
    procedure_id    bigint,
    publish_date    date,
    reqnum          text,            -- registry number, empty for some notices
    procedure_name  text,
    subject         text,            -- procurement subject
    start_price     numeric(18, 2),  -- initial max price; the data has no other prices
    is_smp          boolean,         -- SME-only procurement: a lot flag, not a supplier one
    customer_inn    text,
    customer_kpp    text,
    channel         text             -- is_eshop_or_aisgz as is: AIS GZ or e-shop
);

-- TRU items: several per lot.
CREATE TABLE lot_items (
    lot_id        bigint NOT NULL,
    product_name  text,
    okpd2_code    text,
    okpd2_l2      text,  -- class: 61
    okpd2_l4      text,  -- group: 61.10
    okpd2_l6      text   -- kind: 61.10.11
);

-- Supplier bids: one row per (lot, INN) pair.
CREATE TABLE bids (
    lot_id        bigint  NOT NULL,
    supplier_inn  text    NOT NULL,
    supplier_kpp  text,
    is_winner     boolean NOT NULL
);  -- key (lot_id, supplier_inn)
