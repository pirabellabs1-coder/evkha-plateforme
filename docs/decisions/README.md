# Decisions

Les decisions techniques non triviales doivent etre tracees ici sous forme d'ADR.

La Phase 0 reprend les decisions gelees du `docs/master-plan.html` :

- Gamma est pilote par un flag `gamma_enabled` au niveau de l'offre.
- La livraison client se fait par lien + PDF.
- La retention temporaire cible est de 7 jours.
- Les emails transactionnels passent par Brevo.

## ADR — Conservation des pieces jointes deposees par le client (08/08/2026)

**Constat.** `purge_expired_artifacts` ne purgeait que les `DocumentArtifact`,
c'est-a-dire ce que NOUS produisons. Les `PieceJointe` deposees depuis l'espace
client — bilans, comptes de resultat, documents d'entreprise — n'avaient aucune
echeance et restaient indefiniment sur le volume. Ce n'etait pas un defaut de
controle d'acces : la signature horodatee de `evkha/signatures.py` les protege
comme les autres fichiers.

**Decision.** Douze mois, comptes depuis le depot (`created_at`), reglage global
`EVKHA_PIECES_JOINTES_RETENTION_DAYS`.

- **Douze mois** et non sept jours : un livrable se regenere, le bilan d'un
  tiers ne se reconstitue pas. Douze mois est le cycle d'un bilan — l'abonne
  depose le nouvel exercice et l'ancien s'efface de lui-meme.
- **Depuis le depot** : une seule date a lire, une purge verifiable.
- **Reglage global, pas par organisation.** `Offer.retention_days` n'est pas
  reutilisable ici : `PieceJointe.commande` existe dans le modele et n'est
  assignee nulle part, l'ecran de commande n'envoyant que les reponses au
  questionnaire. Il n'existe donc aucun chemin `PieceJointe -> order -> offer`.
  Ajouter un champ par organisation avant qu'un abonne l'ait demande aurait
  cree un reglage sans lecteur — precisement le defaut que `evkha/retention.py`
  documente pour `EVKHA_DEFAULT_RETENTION_DAYS`.
- **Les logos sont exclus.** `organisation.logo_url` pointe sur le fichier et le
  moteur le charge a chaque generation. Les purger eteindrait la marque de tous
  les livrables suivants d'un abonne fidele. Un logo est de la configuration,
  pas un depot.

**Mise en service.** La premiere execution reelle supprimera des documents
appartenant a de vrais clients, et les tests tournent sur des doublures et sur
SQLite — ils ne disent rien du volume de production (regle 7). Un mode
« compte sans supprimer » permet de lire ce qui partira avant de laisser la
purge mordre :

```bash
python manage.py purger_les_pieces_jointes --simulation
```

Il enumere chaque fichier (date de depot, organisation, nom, taille) et
n'ecrit ni en base ni sur le disque. Simulation et purge partagent la MEME
requete (`purge._expirees`) : un essai qui selectionnerait autrement
rassurerait sur un ensemble different de celui qu'on supprime ensuite
(regle 2). Verifie sur base neuve le 08/08/2026 — la simulation a annonce
exactement les deux documents que la purge a ensuite emportes, en ecartant le
depot recent et le logo.

**Corollaire, decouvert en implementant.** Trois des quatre chemins de
suppression d'une piece jointe laissaient le fichier sur le disque (remplacement
de logo, CASCADE, script de remise a zero) : seule la route de suppression
manuelle le libere. Chaque changement de logo abandonnait donc deja un orphelin,
sans attendre aucune retention. L'effacement est desormais porte par un unique
`post_delete` dans `organisations/purge.py`, qui couvre tous les chemins — y
compris la purge ajoutee ici, qui sans cela aurait reproduit le defaut.
