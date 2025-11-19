AO COLLECTOR – MÉMO REDEMARRAGE (VERSION ACTUELLE)
==================================================

But : relancer rapidement le backend (API) + le frontend (interface) dans Codespaces
et revenir exactement au point où on est maintenant.

--------------------------------------------------
0. OUVRIR LE CODESPACE
--------------------------------------------------
Pourquoi : démarrer ton environnement de dev sur GitHub.

1) Aller sur GitHub → repo : ao-ti-collector
2) Bouton vert "Code" → onglet "Codespaces"
3) Ouvrir le Codespace existant (musical-succotash-…)
4) Attendre que VS Code dans le navigateur soit chargé

--------------------------------------------------
1. DEMARRER LE BACKEND (API FASTAPI)
--------------------------------------------------
Pourquoi : c’est l’API qui fournit /api/portals et /api/tenders au frontend.

Dans un terminal (onglet TERMINAL) :

    cd /workspaces/ao-ti-collector
    source .venv/bin/activate
    lsof -ti :8000 | xargs -r kill -9
    python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

➜ À laisser tourner (NE PAS fermer ce terminal).

Ce que fait chaque commande :
- cd …                         → se placer dans le dossier du projet
- source .venv/bin/activate    → activer l’environnement Python du projet
- lsof … kill …                → fermer d’anciens serveurs sur le port 8000
- uvicorn …                    → lancer l’API AO Collector

--------------------------------------------------
2. TESTER LE BACKEND
--------------------------------------------------
Pourquoi : être sûr que l’API est bien en ligne avant de lancer le front.

1) Aller dans l’onglet "Ports" de Codespaces
2) Sur la ligne du port 8000, cliquer sur le lien (icône de globe)
3) Dans le navigateur, tu dois voir un JSON du style :

   { "app": "AO Collector", "message": "API en ligne. Utilise /api/portals et /api/tenders." }

➜ Si oui, le backend est OK.

--------------------------------------------------
3. DEMARRER LE FRONTEND (VITE / REACT)
--------------------------------------------------
Pourquoi : c’est l’interface AO Collector — Recherche.

IMPORTANT : on garde le terminal backend ouvert et on ouvre un **nouveau terminal**.

Dans ce nouveau terminal :

    cd /workspaces/ao-ti-collector/frontend

(Si tu viens de recréer le Codespace et que c’est la toute première fois) :
    npm install

Puis pour lancer le front (à chaque redémarrage) :

    npm run dev -- --host 0.0.0.0 --port 5173

➜ Laisser ce terminal tourner lui aussi.

Rappel configuration actuelle :
- fichier frontend/.env : ligne VITE_API_BASE_URL est commentée, par ex. :
  # VITE_API_BASE_URL=...
- fichier vite.config.ts : proxy /api → http://localhost:8000

Donc le front parle au backend via le proxy Vite.

--------------------------------------------------
4. TESTER LE FRONTEND
--------------------------------------------------
Pourquoi : vérifier que l’IHM répond.

1) Aller dans l’onglet "Ports"
2) Sur la ligne du port 5173, cliquer sur le lien
3) Tu dois voir la page :

   AO Collector — Recherche

avec les filtres (Pays, Portail, Mot-clé) et le tableau avec colonnes :
ID | Titre | Portail | Source | Acheteur | Pays | Budget | Date | Lien

--------------------------------------------------
5. VERIFIER QUE FRONT + BACK DISCUTENT BIEN
--------------------------------------------------
Pourquoi : s’assurer que les données affichées viennent bien de l’API.

1) Sur la page du front (port 5173), appuyer sur F5 pour rafraîchir
2) Regarder le terminal du backend (où tourne uvicorn)

Tu dois voir apparaître des lignes du style :

    INFO: ... "GET /api/portals HTTP/1.1" 200 OK
    INFO: ... "GET /api/tenders?limit=200 HTTP/1.1" 200 OK
    (et d’autres quand tu fais une recherche avec mot-clé)

➜ Si tu vois ces GET /api/… en 200 OK : front + backend = OK.

--------------------------------------------------
6. SI QUELQUE CHOSE NE MARCHE PAS
--------------------------------------------------

A) Rien sur le port 8000 / JSON ne s’affiche pas :
   - Reprendre l’étape 1 (démarrage backend)
   - Vérifier que la dernière ligne du terminal backend ressemble à :
     "Uvicorn running on http://0.0.0.0:8000"

B) Le front ne se lance pas :
   - Vérifier que tu es bien dans :
     /workspaces/ao-ti-collector/frontend
   - Vérifier que npm run dev tourne sans erreur dans le terminal

C) Le front s’affiche mais pas de données, message “Aucun résultat…” et
   dans le backend tu ne vois PAS /api/tenders :
   - Vérifier :
     - frontend/.env : la ligne VITE_API_BASE_URL est bien commentée (# ...)
     - frontend/vite.config.ts contient bien un bloc proxy :

       proxy: {
         "/api": {
           target: "http://localhost:8000",
           changeOrigin: true,
           secure: false,
         },
       }

   - Relancer le front : Ctrl+C dans le terminal du front, puis :

       cd /workspaces/ao-ti-collector/frontend
       npm run dev -- --host 0.0.0.0 --port 5173

   - Rafraîchir la page et vérifier à nouveau les logs du backend.

--------------------------------------------------
7. POINT D’ARRÊT ACTUEL (OÙ TU T’ES ARRETÉ)
--------------------------------------------------
À ce stade, quand tout est bien redémarré :

- Backend :
  - tourne sur le port 8000
  - renvoie /api/portals et /api/tenders
- Frontend :
  - tourne sur le port 5173 via Vite
  - affiche :
    - filtres (Pays, Portail, Mot-clé)
    - tableau stylé avec :
      ID | Titre | Portail | Source | Acheteur | Pays | Budget | Date | Lien
  - la colonne Budget existe mais est encore vide (—), en attente
    d’évolution du backend / des données.

C’est depuis ce point que tu pourras reprendre plus tard
(pour ajouter budget réel, analyse PDF, alertes Merx, etc.).



////----------------------------------------
ÉTAT ACTUEL DE L’INTERFACE (FRONT)
----------------------------------------

- Page principale "AO Collector — Recherche".
- Filtres disponibles :
  - Pays
  - Portail
  - Mot-clé
- Tableau des résultats avec colonnes dynamiques.
  - Une barre "Colonnes :" permet d’activer/désactiver en live :
    - ID, Titre, Portail, Source, Acheteur, Pays, Région, Budget,
      Publiée, Fermeture, Catégorie, Mots-clés matchés, Score, Lien.
- Certaines colonnes (budget, catégorie, score, etc.) sont déjà prévues
  dans le modèle mais pas encore toutes alimentées par le backend.




///// IDÉES D’AMÉLIORATION UI/UX (À METTRE EN PLACE PROGRESSIVEMENT)
==============================================================

1) FICHE DÉTAILLÉE EN SLIDE-OVER (EFFET WAW)
-------------------------------------------
- Clic sur une ligne du tableau → ouverture d’un panneau latéral à droite.
- Contenu du panneau :
  - Titre complet, portail, pays, acheteur
  - Budget, dates (publication / fermeture) avec badges de couleur
  - Catégorie, score, mots-clés matchés
  - Boutons d’action : "Ouvrir la page officielle", "Ouvrir le PDF" (plus tard), "Copier le lien"
  - Zone "Notes internes" (pour commentaires rapides)
- Technique :
  - State React selectedTender (null ou Tender)
  - Drawer / overlay en Tailwind (position fixed, transition slide-in)

2) FILTRES AMÉLIORÉS
--------------------
- Badges de filtres actifs sous le formulaire :
  - Ex: [🇨🇦 Canada ✕] [SEAO ✕] [mot-clé : servicenow ✕]
  - Un clic sur ✕ supprime le filtre correspondant.
- Filtre "Échéance" :
  - Options : Toutes | < 7 jours | < 30 jours | Expirées
  - Couleur des deadlines dans le tableau :
    - Rouge : < 7 jours
    - Orange : < 30 jours
    - Gris : expiré
- Tri par colonne :
  - Clic sur l’en-tête (Budget, Publiée, Fermeture, etc.) → tri asc/desc.
  - Afficher un chevron ▲▼ pour indiquer l’ordre.

3) PETIT DASHBOARD DE SYNTHÈSE
------------------------------
- Bandeau de 3-4 cartes au-dessus du tableau, calculées sur les résultats filtrés :
  - "Nb d’appels d’offres affichés"
  - "Budget total estimé" (quand disponible)
  - "Nb d’AO qui ferment dans les 7 jours"
  - "Nb d’AO TI (catégories TI / Cloud / ERP / ATS / CRM…)"
- Objectif : donner une vision rapide avant de parcourir le tableau.

Note : Ces idées sont prévues pour être ajoutées progressivement
après stabilisation du backend (budget, deadline, catégorie, score).
