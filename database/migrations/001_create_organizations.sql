CREATE TABLE IF NOT EXISTS organizations (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,

    org_id TEXT,

    name TEXT NOT NULL,

    org_type TEXT,

    city TEXT,

    region TEXT,

    postal_code TEXT,

    country TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
