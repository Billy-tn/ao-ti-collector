# Plan d'améliorations prioritaires (branch: v4-dev-cursor)

Objectif général : continuer le développement sans casser la version v3 (checkpoint-mfa-swagger).
Règles suivies : changements petits, sûrs, pas de refactor massif.

## 1) Stabiliser l'API backend
- Priorité : haute (évite fuites de connexion, améliore stabilité serveur).
- Pourquoi : garantit que les connexions SQLite sont toujours fermées; réduit risques en production.
- Fichiers à modifier : `backend/main.py`
- Résumé du changement : entourer les usages de `get_db()` par `try ... finally` et appeler `con.close()` dans le `finally`.
- Commandes pour tester :
  - Lancer le backend : `uvicorn backend.main:app --reload --port 8000`
  - Vérifier health : `curl -s http://localhost:8000/ | jq .`
  - Vérifier endpoint : `curl -i http://localhost:8000/api/tenders`

## 2) Ajouter un mode `--dry-run` pour l'import CSV
- Priorité : moyenne (protège la base lors des backfills).
- Pourquoi : permet d'exécuter le script d'import sans écrire ni DROP la table, pour valider le parsing.
- Fichiers à modifier : `backend/sync_csv_to_db.py`
- Résumé du changement : ajouter `argparse` + param `--dry-run`; en `dry-run` ne pas exécuter `DROP TABLE`, `executemany` ni `commit`; afficher le comptage.
- Commandes pour tester :
  - Dry-run : `python3 backend/sync_csv_to_db.py --dry-run`
  - Dry-run ciblé : `python3 backend/sync_csv_to_db.py --dry-run --csv v1_stable/ao_output_v1.csv --db /tmp/test_ao.db`
  - Exécution normale (précaution) : `python3 backend/sync_csv_to_db.py`

## 3) Réduire la charge initiale côté frontend
- Priorité : faible (impact UI/perf, pas de risque sur données).
- Pourquoi : limiter la taille de la réponse initiale pour accélérer le chargement et réduire la charge serveur.
- Fichiers à modifier : `frontend/src/App.tsx`
- Résumé du changement : diminuer `DEFAULT_LIMIT` (ex. `200 -> 100`).
- Diff court (concept) :
  - `const DEFAULT_LIMIT = 200;` → `const DEFAULT_LIMIT = 100;`
- Commandes pour tester :
  - Lancer le frontend : `cd frontend && npm install && npm run dev`
  - Vérifier via curl avec token : `curl "http://localhost:8000/api/tenders?limit=100" -H "Authorization: Bearer <TOKEN>"`

