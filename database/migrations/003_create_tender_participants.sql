CREATE TABLE IF NOT EXISTS tender_participants (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tender_id INTEGER NOT NULL,

    organization_id INTEGER NOT NULL,

    role TEXT NOT NULL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tender_id)
        REFERENCES tenders_mi(id),

    FOREIGN KEY (organization_id)
        REFERENCES organizations(id),

    UNIQUE(
        tender_id,
        organization_id,
        role
    )
);