"""Encaissement des abonnements B2B par Stripe Checkout.

Ce paquet est la SEULE porte par laquelle un credit entre desormais dans un
portefeuille sans geste humain. Il tient donc en trois pieces courtes, chacune
avec une responsabilite qu'on peut enoncer en une phrase :

- `stripe_api`   : parle a Stripe, et refuse de le faire sans cle.
- `abonnements`  : traduit un evenement de paiement en souscription EVKHA.
- `vues`         : recoit le webhook, verifie sa signature, refuse le reste.

Il n'a **aucun modele**. C'etait un choix : `Formule.reference_paiement` et
`AbonnementOrganisation.reference_paiement` existaient deja, vides depuis le
lot 4, precisement pour accueillir les identifiants du prestataire. Creer une
table « paiement » a cote aurait donne deux endroits ou lire l'etat d'un
abonnement, c'est-a-dire deux reponses possibles a la meme question (regle 5).
"""
