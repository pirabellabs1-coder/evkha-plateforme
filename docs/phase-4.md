# Phase 4 — Gamma et livraison

Cette phase branche les sorties du moteur de generation vers la livraison
client, en restant CI-safe grace a des adaptateurs stubs deterministes.

## Inclus

- `integrations/gamma.py` :
  - contrat `GammaClient` ;
  - stub deterministe create -> wait -> export ;
  - adaptateur reel non cable explicitement tant que l'API Gamma n'est pas
    configuree.
- `integrations/brevo.py` :
  - contrat `TransactionalEmailClient` ;
  - stub d'envoi transactionnel ;
  - adaptateur reel Brevo a cabler plus tard.
- `delivery/services.py` :
  - assemblage du lien Google Docs ;
  - creation du PDF de livraison ;
  - Gamma optionnel selon `offer.gamma_enabled` ;
  - creation / mise a jour du `DeliveryBatch` ;
  - envoi email ;
  - passage de la commande a `DELIVERED` ;
  - incident operationnel sur echec.
- `delivery/tasks.py` :
  - livraison Celery ;
  - purge des artefacts expires.

## Garde-fous verifies

- livraison `lien + PDF` meme si Gamma est desactive ;
- Gamma saute proprement si `gamma_enabled=false` ;
- PDF + PPTX Gamma generes si `gamma_enabled=true` ;
- purge auto a J+7 via `purge_expired_artifacts()` ;
- incident cree si la livraison echoue.

## Exclu

- n8n JSON de workflow livraison / erreur critique ;
- cablage API Gamma reel ;
- cablage API Brevo reel.
