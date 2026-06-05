CREATE TABLE IF NOT EXISTS contracts (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tender_id INTEGER NOT NULL,

    organization_id INTEGER,

    contract_status TEXT,

    amount REAL,

    currency TEXT,

    date_signed TEXT,

    start_date TEXT,

    end_date TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tender_id)
        REFERENCES tenders_mi(id),

    FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
);