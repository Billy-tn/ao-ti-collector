# Audit SEAO – 2026-06-04

## Objectif

Valider l'ensemble des données réellement disponibles dans le format OCDS publié par SEAO afin de déterminer le potentiel d'intelligence de marché du portail.

---

## Résumé exécutif

Conclusion principale :

SEAO fournit beaucoup plus qu'une simple liste d'appels d'offres.

Les données publiées permettent de construire une véritable plateforme d'intelligence de marché incluant :

* Historique des contrats
* Fournisseurs gagnants
* Montants attribués
* Dates de signature
* Dates de fin de contrat
* Concurrence
* Nombre de soumissionnaires
* Classification UNSPSC
* Relations entre appels d'offres

---

## Ressources disponibles

Nombre de ressources détectées :

* 409 ressources JSON

Exemples :

* mensuel_20260501_20260531.json
* mensuel_20260401_20260430.json
* hebdo_20260525_20260531.json

Les ressources couvrent plusieurs années d'historique.

---

## Structure OCDS observée

Chaque release contient potentiellement :

* buyer
* parties
* tender
* awards
* contracts
* bids
* relatedProcesses

Exemple de clés observées :

* ocid
* id
* date
* language
* tag
* initiationType
* buyer
* parties
* tender
* awards
* contracts
* bids
* relatedProcesses

---

## Buyer

Informations disponibles :

* Nom de l'acheteur
* Identifiant organisation

Exemple :

* OP-70180

---

## Parties

Les parties contiennent :

* Acheteurs
* Fournisseurs

Informations observées :

* id
* name
* address
* roles

Exemple :

roles = ["buyer"]

ou

roles = ["supplier"]

---

## Tender

Informations disponibles :

* title
* status
* procuringEntity
* procurementMethod
* procurementMethodDetails
* mainProcurementCategory
* additionalProcurementCategories
* tenderPeriod
* numberOfTenderers
* tenderers
* items
* documents

---

## Tender Period

Informations observées :

* startDate
* endDate
* durationInDay

Exemple :

durationInDay = 27

---

## Tenderers

Informations disponibles :

* id
* name

Exemple :

numberOfTenderers = 223 (maximum observé)

---

## Items

Informations disponibles :

* classification UNSPSC
* description

Exemple :

UNSPSC = 78101803

Description :

Services de transport de véhicules

---

## Awards

Informations disponibles :

* id
* status
* date
* value
* suppliers

Exemple :

Montant attribué
Fournisseur gagnant
Devise

---

## Contracts

Informations disponibles :

* id
* awardID
* status
* value
* dateSigned
* period.endDate

Exemple :

dateSigned = 2005-06-07

endDate = 2006-02-28

---

## Analyse des contrats

Audit historique :

* 2804 contrats observés
* 2804 avec endDate
* couverture = 100 %

Audit récent (mai 2026) :

* 15830 contrats observés
* 9465 avec endDate
* couverture = 59.79 %

Constat :

Les contrats actifs ne possèdent pas toujours de date de fin.

---

## Statuts observés

Contrats actifs :

* 9816

Contrats terminés :

* 5949

Contrats terminés avec endDate :

* 5949

---

## Bids

Informations disponibles :

* id
* value
* valueUnit
* relatedLots

Exemple :

id = FO-1144276418

value = 82974.92

---

## Analyse de la concurrence

Maximum observé :

* 598 bids

Fournisseurs uniques :

* 42

Conclusion :

SEAO permet l'analyse concurrentielle.

---

## Related Processes

Informations disponibles :

* relationship
* title
* identifier

Exemple :

relationship = prior

Conclusion :

Permet d'identifier les renouvellements et les contrats récurrents.

---

## Documents

Informations disponibles :

* tender.documents.url

Chaque release observée possède un lien vers la page officielle SEAO.

Maximum observé :

* 1 document par release

---

## Conclusion

SEAO constitue une source d'intelligence de marché complète.

Les données permettent la création future des entités suivantes :

* organizations
* tenders_mi
* awards
* contracts
* bids
* tenderers
* related_processes
* documents

L'objectif de la branche market-intelligence est d'exploiter 100 % de ces données tout en conservant la compatibilité avec les connecteurs futurs (CanadaBuys, SAM.gov, MERX et portails provinciaux).
