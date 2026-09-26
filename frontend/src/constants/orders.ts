// Le ton d'un statut de commande n'est plus décidé ici : c'est la table
// unique de `Pastille` (`espace/composants/Interface.tsx`) qui le porte. Elle
// donne, statut pour statut, les tons des anciennes couleurs Radix que
// décidait `orderStatusColor` — reçue (inconnue de la table) et annulée
// neutres, formulaire attendu en alerte, en traitement en information,
// livrée en succès, échec en échec. Deux tables auraient divergé au premier
// statut ajouté (règle 5).

export const ORDER_STATUS_LABELS: Record<string, string> = {
  received: "Reçue",
  waiting_intake: "En attente formulaire",
  processing: "En traitement",
  delivered: "Livrée",
  failed: "Échec",
  cancelled: "Annulée",
};
