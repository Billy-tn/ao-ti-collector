# ao-ti-collector

cd frontend
npm install
npm run dev -- --host


cd /workspaces/ao-ti-collector
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000


sqlite3 ao.db "SELECT COUNT(*) FROM tenders_v2;"