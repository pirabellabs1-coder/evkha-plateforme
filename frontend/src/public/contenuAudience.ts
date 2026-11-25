/** La case de la lettre et la mention des deux documents gratuits, telles
 * que RELEVÉES sur l'ancien site (formulaires de la boîte à outils).
 *
 * UNE source pour la boîte à outils et l'accueil (règle 5) : le même
 * consentement s'affiche au même libellé partout. Module à part, et léger :
 * l'accueil le lit sans embarquer tout le relevé des pages ressources
 * (`contenuRessources.ts`, hors du fichier d'entrée). `FORMULAIRES` y lit ses
 * deux cases d'ici.
 *
 * Les deux libellés diffèrent sur le site d'origine ; ils sont gardés tels
 * quels, à harmoniser si la cliente le souhaite.
 */
export const RELEVES_DES_DOCUMENTS = {
  checklist: {
    consentement: "Oui, je souhaite recevoir les nouveautés et informations EVKHA",
    mention: "Votre email ne sera jamais partagé",
  },
  lexique: {
    consentement: "Oui, j'accepte d'être informé(e) sur les nouveautés EVKHA",
    mention: "Votre email ne sera jamais partagé",
  },
} as const;

export function texteDuFormulaire(formulaire: keyof typeof RELEVES_DES_DOCUMENTS): {
  consentement: string;
  mention: string;
} {
  return RELEVES_DES_DOCUMENTS[formulaire];
}
