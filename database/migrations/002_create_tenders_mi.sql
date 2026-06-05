CREATE TABLE IF NOT EXISTS tenders_mi (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,

    ocid TEXT NOT NULL UNIQUE,

    title TEXT NOT NULL,

    status TEXT,

    buyer_org_id INTEGER,

    published_at TEXT,

    tender_start_date TEXT,

    tender_end_date TEXT,

    tender_duration_days INTEGER,

    procurement_method TEXT,

    procurement_method_details TEXT,

    main_procurement_category TEXT,

    number_of_tenderers INTEGER,

    notice_type TEXT,

    url TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (buyer_org_id)
        REFERENCES organizations(id)
);
