CREATE TABLE IF NOT EXISTS tender_classifications (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tender_id INTEGER NOT NULL,

    classification_type TEXT NOT NULL,

    code TEXT NOT NULL,

    description TEXT,

    is_primary INTEGER DEFAULT 0,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tender_id)
        REFERENCES tenders_mi(id),

    UNIQUE(
        tender_id,
        classification_type,
        code
    )
);