Étape 0 – Figurer ce qu’on veut mesurer (2 décisions)

Avant de coder, il faut figer 2 choses :

Liste de catégories / secteurs
Exemple (à adapter) :

Services TI – Conseil

Infonuagique / Cloud

ERP / Odoo / SAP / Oracle

DevOps / Infra

Cybersécurité

Support & maintenance logiciel

Autres services professionnels (non TI)

Liste de mots-clés “business” pour tes rapports
(ceux que tu veux suivre de près)
Ex : servicenow, odoo, oracle, crm, ats, cloud, azure, aws, gcp, cybersécurité…

👉 À faire : juste un petit tableau dans un fichier markdown ou Excel, on le traduira ensuite dans le code.

🔹 Étape 1 – Stabiliser le modèle “Tender” côté backend

Objectif : que chaque AO ait les champs dont on aura besoin plus tard.

Dans ta DB / backend, on vise ce modèle minimal :

id

title

portal

source

buyer

country

region

url

published_at

closing_at (deadline)

budget (nombre ou texte)

category (1 catégorie principale)

matched_keywords (liste / string “crm, odoo, servicenow”)

score (0–100, même calcul simple au début)

👉 Actions concrètes :

Ajouter les colonnes manquantes dans SQLite (ao.db)

via migration simple ou recréation à partir d’un CSV enrichi.

Mettre à jour les modèles Python (Pydantic / ORM) pour inclure ces champs.

Adapter les scripts de sync (SEAO / CanadaBuys) :

même si tu ne peux pas encore remplir budget / category parfaitement, mets au moins :

category = "Services TI" si certains mots-clés TI matchent

matched_keywords = concat des mots-clés trouvés

score = (nb de mots-clés TI trouvés) × 10, par exemple.

Vérifier que /api/tenders renvoie bien tous ces champs.

Quand ça, c’est fait, tout le reste (UI + rapports) devient beaucoup plus simple.

🔹 Étape 2 – Exposer des endpoints “stats” pour les rapports

On évite de recalculer tout le temps côté front.

👉 Ajouter quelques endpoints dans l’API :

/api/stats/summary

total d’AO

nb d’AO filtrées (selon pays / portail / dates, etc.)

nb d’AO avec deadline < 7 jours

nb d’AO TI (category = TI / Cloud / ERP…)

/api/stats/by-category

retourne un tableau : [ { category: "Services TI", count: 45 }, ... ]

/api/stats/by-keyword

basé sur matched_keywords

ex : [ { keyword: "odoo", count: 12 }, { keyword: "servicenow", count: 8 } ]

(Plus tard) /api/stats/by-portal

[ { portal: "SEAO", count: 33 }, { portal: "CanadaBuys", count: 21 } ]

Ces endpoints utilisent les mêmes filtres que la liste principale (pays, portail, période, mot-clé) pour que les stats reflètent ce que tu regardes.

🔹 Étape 3 – UI “wow” sur la page liste

On part de ton écran actuel et on ajoute, dans cet ordre pour ne pas tout casser :

3.1 Slide-over de détails

Actions :

Ajouter un state selectedTender dans App.tsx.

Mettre un onClick sur les <tr> (ou une icône) pour ouvrir la fiche.

Créer un composant <TenderDetailDrawer> :

titre + portail + pays + acheteur

budget + deadline + score mis en valeur

mots-clés sous forme de petits badges

bouton “Ouvrir la page officielle”

Ajouter un overlay sombre & animation de slide.

Résultat : quand tu cliques sur une ligne → fiche pro comme dans un vrai SaaS.

3.2 Filtres avancés & badges

Actions :

Ajouter un filtre “Échéance” dans le formulaire :
Toutes | < 7 jours | < 30 jours | Expirées.

Colorer la date de fermeture dans le tableau :

rouge si < 7j

orange si < 30j

gris si passée

Sous le formulaire, afficher les filtres actifs en badges :

ex: [Canada ✕] [SEAO ✕] [mot-clé : odoo ✕] [Échéance : < 7 jours ✕]

Cliquer sur ✕ enlève le filtre correspondant.

3.3 Dashboard light au-dessus du tableau

Actions :

Appeler /api/stats/summary à chaque recherche.

Afficher 3–4 cartes :

“AO affichés”

“AO qui ferment < 7 jours”

“AO TI”

plus tard “Budget estimé total”

Design simple : 3 blocs sur une ligne, fond blanc, nombre en gros.

🔹 Étape 4 – Page “Rapports” séparée

Là on commence la partie “vision globale” (ce que tu demandes : nb par secteur, mot-clé, catégorie).

Actions :

Ajouter une nouvelle route côté front : /rapports

bouton “Rapports” dans le header.

Sur cette page, organiser en 3 sections :

A. Par catégorie / secteur

appel /api/stats/by-category

affichage :

tableau “Catégorie / Nombre d’AO”

petit bar chart (quand tu voudras, avec recharts par ex.)

B. Par mot-clé

appel /api/stats/by-keyword

tableau des mots-clés suivis + nb d’AO associés.

C. Par portail / pays

appel /api/stats/by-portal

tableau “Portail / Nb d’AO”.

Ajouter un bouton “Exporter CSV”

soit en appelant un endpoint /api/stats/export,

soit en générant un CSV côté front à partir des données déjà chargées.

🔹 Étape 5 – Notes & suivi interne (optionnel mais puissant)

Une fois le reste en place :

Ajouter dans la fiche détaillée :

statut interne (À analyser / En cours / Décidé / Soumis / Gagné / Perdu)

champ “Notes”.

Stocker ça dans une petite table interne (même DB).

Dans la page Rapports, ajouter :

un bloc “Pipeline AO” (combien en cours, combien soumis, etc.).