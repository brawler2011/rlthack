-- Схема БД сервиса подбора поставщиков.
-- Скрипт 01 пересоздаёт её с нуля: всё строится из исходных CSV, поэтому DROP безопасен.

DROP TABLE IF EXISTS
    supplier_text, supplier_customer, supplier_okpd2, supplier_profile,
    bids, lot_items, lots
CASCADE;

-- Функции очистки сырых значений (в staging всё лежит как text) ---------------

CREATE OR REPLACE FUNCTION clean_text(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(btrim(v), '')
$$;

CREATE OR REPLACE FUNCTION clean_bigint(v text) RETURNS bigint
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{1,18}$' THEN btrim(v)::bigint END
$$;

-- Деньги: допускаем пробелы-разделители тысяч и десятичную запятую.
CREATE OR REPLACE FUNCTION clean_money(v text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN x ~ '^-?\d+(\.\d+)?$' THEN round(x::numeric, 2) END
    FROM (SELECT replace(replace(replace(btrim(v), ' ', ''), chr(160), ''), ',', '.') AS x) s
$$;

CREATE OR REPLACE FUNCTION clean_bool(v text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN lower(btrim(v)) IN ('true', 't', '1', 'yes', 'y', 'да') THEN true
        WHEN lower(btrim(v)) IN ('false', 'f', '0', 'no', 'n', 'нет') THEN false
    END
$$;

-- ИНН: 10 цифр у юрлица, 12 у ИП. Остальное считаем мусором.
CREATE OR REPLACE FUNCTION clean_inn(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^(\d{10}|\d{12})$' THEN btrim(v) END
$$;

-- КПП: 9 знаков, 5-й и 6-й могут быть латинскими буквами.
CREATE OR REPLACE FUNCTION clean_kpp(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN upper(btrim(v)) ~ '^\d{4}[0-9A-Z]{2}\d{3}$' THEN upper(btrim(v)) END
$$;

-- ОКПД2 вида 61.10.11.110; укороченные коды (33.12.1) тоже допустимы.
CREATE OR REPLACE FUNCTION clean_okpd2(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{2}(\.\d{1,3})*$' THEN btrim(v) END
$$;

-- Начало кода ОКПД2 из n цифр: 2 — класс, 4 — группа, 6 — вид. NULL, если код короче.
CREATE OR REPLACE FUNCTION okpd2_prefix(code text, n int) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE n
        WHEN 2 THEN substring(code FROM '^\d{2}')
        WHEN 4 THEN substring(code FROM '^\d{2}\.\d{2}')
        WHEN 6 THEN substring(code FROM '^\d{2}\.\d{2}\.\d{2}')
    END
$$;

-- Регион по КПП (первые 2 цифры — регион налоговой); у ИП КПП нет, берём по ИНН.
CREATE OR REPLACE FUNCTION region_code(inn text, kpp text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT left(coalesce(kpp, inn), 2)
$$;

-- Очищенные данные (скрипт 01) ------------------------------------------------
-- Ключи и индексы создаются в clean.sql после заливки: так быстрее.

-- Извещения: одна строка на лот.
CREATE TABLE lots (
    lot_id          bigint NOT NULL,  -- ключ
    procedure_id    bigint,
    reqnum          text,            -- реестровый номер, у части извещений пуст
    procedure_name  text,
    subject         text,            -- предмет закупки
    start_price     numeric(18, 2),  -- НМЦК; других цен в данных нет
    is_smp          boolean,         -- закупка только для СМП: признак лота, а не поставщика
    customer_inn    text,
    customer_kpp    text,
    channel         text             -- is_eshop_or_aisgz как есть: АИС ГЗ или электронный магазин
);

-- Позиции ТРУ: несколько на лот.
CREATE TABLE lot_items (
    lot_id        bigint NOT NULL,
    product_name  text,
    okpd2_code    text,
    okpd2_l2      text,  -- класс: 61
    okpd2_l4      text,  -- группа: 61.10
    okpd2_l6      text   -- вид: 61.10.11
);

-- Участия поставщиков в лотах: одна строка на пару (лот, ИНН).
CREATE TABLE bids (
    lot_id        bigint  NOT NULL,
    supplier_inn  text    NOT NULL,
    supplier_kpp  text,
    is_winner     boolean NOT NULL
);  -- ключ (lot_id, supplier_inn)
