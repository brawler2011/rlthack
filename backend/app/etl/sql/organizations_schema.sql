-- Open FNS data about suppliers: names of companies outside the SME registry (large companies,
-- state institutions) from EGRUL, OKVED and status from the accounting statements registry,
-- revenue, expenses, taxes, tax debt and headcount for all registry legal entities, including
-- companies without procurement history. Current risks adjust online recommendation scores;
-- offline historical model training and evaluation do not use these later reports.
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
    source     text NOT NULL,
    tax_fines  numeric(18, 2), -- unpaid penalties in the tax-offence dataset
    revenue_as_of date,
    taxes_paid_as_of date,
    tax_debt_as_of date,
    headcount_as_of date,
    tax_fines_as_of date,
    refreshed_at date
);
