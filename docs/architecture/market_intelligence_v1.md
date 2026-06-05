# Market Intelligence V1

## Tables V2

- organizations
- tenders_mi
- awards
- contracts
- bids
- related_processes
- documents

## Décisions

- organizations devient la source de vérité pour les acheteurs et fournisseurs.

## Relations V1

organizations
    |
    +-- tenders_mi (buyer_org_id)
    |
    +-- awards (supplier_org_id)
    |
    +-- contracts (supplier_org_id)
    |
    +-- bids (supplier_org_id)
    |
    +-- tenderers (supplier_org_id)

tenders_mi
    |
    +-- awards
    |
    +-- contracts
    |
    +-- bids
    |
    +-- tenderers
    |
    +-- related_processes
    |
    +-- documents

Clé métier principale :
- ocid

Principe :
- Une organisation existe une seule fois.
- Un appel d'offres peut avoir plusieurs soumissions.
- Un appel d'offres peut avoir plusieurs contrats.
- Un appel d'offres peut avoir plusieurs attributions.
- Les relations historiques sont conservées via related_processes.


- Décision : tenderers devient tender_participants pour supporter buyer, supplier et tenderer dans un modèle unique.
