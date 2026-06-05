CREATE TABLE IF NOT EXISTS awards (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tender_id INTEGER NOT NULL,

    organization_id INTEGER,

    award_status TEXT,

    award_date TEXT,

    amount REAL,

    currency TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tender_id)
        REFERENCES tenders_mi(id),

    FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
);