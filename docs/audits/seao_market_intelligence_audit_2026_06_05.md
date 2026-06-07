# SEAO Market Intelligence - Audit fonctionnel et technique

## Date : 2026-06-05

# 1. Objectif

L'objectif de ce travail était de construire une base de données d'intelligence de marché à partir des exports OCDS du SEAO afin de :

* Comprendre la structure réelle des données publiques du SEAO
* Construire un modèle relationnel exploitable
* Conserver l'historique complet disponible
* Préparer la documentation fonctionnelle avant toute couche analytique ou IA

Cette phase ne vise pas la visualisation ou les tableaux de bord.

La priorité est :

1. Collecte
2. Qualité des données
3. Documentation
4. Analyse fonctionnelle
5. Exploitation future

---

# 2. Source de données

Source principale :

SEAO OCDS (Open Contracting Data Standard)

Connecteur utilisé :

backend/connectors/seao_connector.py

Nombre de ressources détectées :

409 ressources

Après déduplication :

58 fichiers mensuels uniques

Période couverte :

2021-03 à 2026-05

---

# 3. Chargement historique complet

Chargement effectué :

58 mois

Volume traité :

697 804 releases OCDS

Temps d'exécution :

4 minutes 13 secondes

Observation importante :

Une release OCDS n'est pas un appel d'offres.

Plusieurs releases peuvent appartenir au même processus d'approvisionnement.

Le véritable identifiant métier est :

OCID

---

# 4. Volumétrie finale

| Table                  |    Nombre |
| ---------------------- | --------: |
| organizations          |   290 458 |
| tenders_mi             |   365 495 |
| awards                 |   664 838 |
| contracts              |   439 449 |
| bids                   | 1 068 857 |
| documents              |   647 220 |
| related_processes      |    11 062 |
| tender_classifications |         0 |
| tender_participants    |         0 |

Total d'enregistrements principaux :

3 476 317+

---

# 5. Architecture fonctionnelle

Cycle métier observé :

Acheteur
↓
Appel d'offres (Tender)
↓
Soumissions (Bids)
↓
Attribution (Award)
↓
Contrat (Contract)

---

# 6. Analyse des tables

## organizations

Rôle :

Référentiel des acteurs.

Contient :

* Acheteurs
* Fournisseurs

Sources OCDS :

buyer.id
buyer.name

awards.suppliers[].id
awards.suppliers[].name

Clé métier :

(source, org_id)

Observations :

Les champs suivants existent dans le modèle mais ne sont pas alimentés :

* street_address
* city
* region
* postal_code
* country

Test réalisé :

Le buyer OCDS contient uniquement :

{
"name": "...",
"id": "OP-70180"
}

Conclusion :

La donnée géographique n'est pas actuellement disponible dans les exports chargés.

---

## tenders_mi

Rôle :

Table centrale du modèle.

Représente un processus d'approvisionnement unique.

Clé métier :

ocid

Observation :

697 804 releases
↓
365 495 tenders uniques

Conclusion :

Un OCID peut posséder plusieurs releases.

---

## awards

Rôle :

Représente l'attribution d'un marché.

Source OCDS :

awards[]

Volume :

664 838

Observation :

Un appel d'offres peut produire plusieurs attributions.

Exemples :

* lots multiples
* fournisseurs multiples
* attributions partielles

---

## contracts

Rôle :

Représente le contrat effectivement signé.

Source OCDS :

contracts[]

Volume :

439 449

Observation :

Award ≠ Contract

Tous les awards ne produisent pas nécessairement un contrat publié.

Qualité :

317 182 contrats possèdent une date de fin.

Taux de couverture :

72 %

---

## bids

Rôle :

Représente une soumission.

Volume :

1 068 857

Qualité :

1 061 349 possèdent un montant.

Taux de couverture :

99,3 %

Limite actuelle :

organization_id n'est pas encore relié de façon fiable au soumissionnaire.

Investigation future requise.

---

## documents

Rôle :

Documents associés à un appel d'offres.

Volume :

647 220

Qualité :

647 220 URLs valides

Taux de couverture :

100 %

Potentiel futur :

* extraction de texte
* IA documentaire
* recherche sémantique
* analyse d'exigences

---

## related_processes

Rôle :

Relations entre processus d'approvisionnement.

Volume :

11 062

Exemple observé :

relationship = prior

Utilité :

* renouvellements
* qualifications préalables
* processus liés
* historique d'un dossier

---

# 7. Questions ouvertes

## tender_classifications

Volume actuel :

0

Hypothèses :

* non fourni par SEAO
* présent ailleurs dans la structure OCDS

Investigation future :

* items.classification
* additionalClassifications
* awards.items

---

## tender_participants

Volume actuel :

0

Hypothèses :

* non fourni par SEAO
* présent dans une autre section OCDS

Investigation future :

* parties[]
* participants[]
* structures dérivées

---

# 8. Conclusions

Le modèle actuel est valide et exploitable.

Les composantes suivantes sont confirmées :

✓ Organisations

✓ Appels d'offres

✓ Attributions

✓ Contrats

✓ Soumissions

✓ Documents

✓ Relations entre processus

Les principales zones d'investigation restantes sont :

* tender_classifications
* tender_participants

À ce stade, la priorité n'est plus la collecte mais :

1. Documentation complète
2. Analyse fonctionnelle détaillée
3. Validation de la qualité des données
4. Compréhension exhaustive du modèle OCDS SEAO

Les couches d'analyse, de visualisation et d'IA seront abordées dans une phase ultérieure.
