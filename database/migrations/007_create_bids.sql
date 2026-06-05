CREATE TABLE IF NOT EXISTS bids (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tender_id INTEGER NOT NULL,

    organization_id INTEGER,

    bid_reference TEXT,

    amount REAL,

    currency TEXT,

    lot_reference TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tender_id)
        REFERENCES tenders_mi(id),

    FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
);