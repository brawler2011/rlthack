-- Open FNS data about suppliers: names of companies outside the SME registry (large companies,
-- state institutions) from EGRUL, OKVED and status from the accounting statements registry,
-- revenue, expenses, taxes, tax debt and headcount from FNS open data. Shown next to the
-- recommendations; the model does not use it.
DROP TABLE IF EXISTS organizations;
CREATE TABLE organizations (
    inn        text PRIMARY KEY,
    name       text,           -- only for companies outside the SME registry
    full_name  text,
    registered date,
    okved      text,           -- from the accounting statements, for companies outside the registry
    status     text,           -- ACTIVE, LIQUIDATED, ...
    revenue    numeric(18, 2), -- income for the last year, RUB
    expenses   numeric(18, 2),
    taxes_paid numeric(18, 2),
    tax_debt   numeric(18, 2), -- arrears, penalties and fines
    headcount  integer,
    source     text NOT NULL
);
