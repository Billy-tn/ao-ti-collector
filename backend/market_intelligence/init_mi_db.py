from pathlib import Path
import sqlite3


ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "database" / "ao_collector.db"
MIGRATIONS_DIR = ROOT_DIR / "database" / "migrations"


def apply_migrations():
    print(f"[INFO] Base cible : {DB_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Recréation propre de la base à chaque exécution
    if DB_PATH.exists():
        print(f"[INFO] Suppression de l'ancienne base : {DB_PATH}")
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        migration_files = sorted(
            MIGRATIONS_DIR.glob("*.sql")
        )

        print(f"[INFO] Migrations trouvées : {len(migration_files)}")

        for migration_file in migration_files:
            print(f"[INFO] Application : {migration_file.name}")

            sql = migration_file.read_text(
                encoding="utf-8"
            )

            cursor.executescript(sql)

        conn.commit()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """
        )

        tables = cursor.fetchall()

        print("\n[OK] Tables créées :")

        for table in tables:
            print(f" - {table[0]}")

    finally:
        conn.close()


if __name__ == "__main__":
    apply_migrations()