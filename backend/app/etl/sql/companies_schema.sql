-- Companies from external registries (script 03). Keys and roles come after the load.

DROP TABLE IF EXISTS companies;

CREATE TABLE companies (
    inn              text    NOT NULL,  -- key
    name             text,
    is_individual    boolean NOT NULL,
    region_code      text,
    msp_category     smallint,          -- 1 micro, 2 small, 3 medium
    headcount        integer,
    msp_since        date,              -- in the SME registry since
    okved_main       text,
    okved_main_name  text,
    okved_extra      text[]  NOT NULL,
    products         text[]  NOT NULL,  -- codes of products the company declares it makes
    source           text    NOT NULL,  -- rmsp: FNS SME registry
    role             text,              -- MANUFACTURER / DISTRIBUTOR / SUPPLIER
    role_reason      text,              -- why, for the explanation in the UI
    in_history       boolean            -- has bids in the procurement data
);
