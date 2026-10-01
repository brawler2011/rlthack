-- Roles from OKVED: section C (codes 10-33) or declared own products -> manufacturer,
-- wholesale (46) -> distributor, anything else -> supplier.

UPDATE companies SET
    role = CASE
        WHEN cardinality(products) > 0 OR okved_main ~ '^(1\d|2\d|3[0-3])(\.|$)' THEN 'MANUFACTURER'
        WHEN okved_main ~ '^46(\.|$)' THEN 'DISTRIBUTOR'
        ELSE 'SUPPLIER'
    END,
    role_reason = CASE
        WHEN cardinality(products) > 0
            THEN 'Заявляет собственную продукцию в реестре МСП (код ' || products[1] || ')'
        WHEN okved_main IS NULL THEN 'ОКВЭД не указан'
        ELSE 'Основной ОКВЭД ' || okved_main || ' «' || coalesce(okved_main_name, '') || '»'
    END,
    in_history = inn IN (SELECT supplier_inn FROM bids);

ALTER TABLE companies ADD PRIMARY KEY (inn);
CREATE INDEX companies_okved_main_idx ON companies (okved_main);
CREATE INDEX companies_okved_extra_idx ON companies USING gin (okved_extra);
CREATE INDEX companies_products_idx ON companies USING gin (products);
CREATE INDEX companies_licenses_idx ON companies USING gin (licenses);

ANALYZE companies;
