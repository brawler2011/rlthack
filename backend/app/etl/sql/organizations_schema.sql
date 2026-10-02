-- Names of suppliers outside the SME registry (large companies, state institutions), from the
-- public EGRUL search and FNS open data. Shown where the registry has no name.
DROP TABLE IF EXISTS organizations;
CREATE TABLE organizations (
    inn        text PRIMARY KEY,
    name       text NOT NULL,
    full_name  text,
    registered date,
    source     text NOT NULL  -- egrul or fns
);
