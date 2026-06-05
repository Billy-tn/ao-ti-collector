CREATE TABLE IF NOT EXISTS organizations (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,

    org_id TEXT NOT NULL,

    name TEXT NOT NULL,

    org_type TEXT,

    street_address TEXT,

    city TEXT,

    region TEXT,

    postal_code TEXT,

    country TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source, org_id)
);