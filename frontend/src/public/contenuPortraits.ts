/** LES PORTRAITS DU BLOG : les porteurs de projet de « La Lettre des Porteurs ».
 *
 * La gérante présente, dans sa lettre d'information, des personnes qu'elle a
 * accompagnées ou avec qui elle travaille. Elle a demandé le 20/11/2026 que
 * ces portraits paraissent aussi sur le blog, et a transmis les deux premières
 * lettres avec leurs photos.
 *
 * ## Ce sont SES textes, et ils sont PUBLIÉS
 *
 * Contrairement aux guides de `contenuGuides.ts`, écrits pour la plateforme et
 * retenus tant qu'elle ne les a pas relus, ces textes sont les siens : ils
 * sont inscrits dans `contenuBlog.ARTICLES` sans drapeau.
 *
 * Ils sont repris mot pour mot. Rien n'est ajouté : aucun fait, aucun chiffre,
 * aucune promesse. Chaque chiffre des lettres est gardé.
 *
 * ## Ce qui a été retouché, et rien d'autre
 *
 * - le découpage : chapô, parties, conclusion. Les INTERTITRES des parties
 *   sont écrits ici quand la lettre n'en portait pas (lettre n° 1) ; ils
 *   reprennent ses mots. Ceux de la lettre n° 2 sont les siens ;
 * - des lignes courtes de la lettre réunies en paragraphes, mots inchangés ;
 * - une coquille : « Et bien, on y est ! » → « Eh bien, on y est ! » ;
 * - les capitales d'insistance d'un courriel (« CAR CHAQUE PETIT PAS MÈNE À
 *   UN OBJECTIF. », « Jeffrey YEYE ») rendues en écriture courante ;
 * - le lecteur est vouvoyé partout : « le projet sort de ta tête » devient
 *   « de votre tête ». Les QUESTIONS posées à Jeffrey restent au « tu »,
 *   comme dans la lettre : ce sont les paroles échangées ;
 * - « répondez à ce mail » n'a pas de sens sur une page : l'invitation de fin
 *   garde « contactez-moi directement », et son bouton ouvre un courriel ;
 * - la lettre n° 2 écrit le nom et la marque de deux façons (« Le Cordier »
 *   et « LECORDIER », « Le Bœuf Club » et « LEBOEUF CLUB ») : les formes du
 *   texte courant sont retenues ;
 * - la signature est « Evangéline », comme sur l'article existant.
 *
 * ## Ce que les lettres ne disent pas
 *
 * - LEUR DATE DE PARUTION : `publieLe: null`. Elle ne se suppose pas ;
 * - de qui est « l'inspiration du mois » de la lettre n° 2 : la citation est
 *   rendue sans auteur.
 *
 * Les photos sont celles que la gérante a jointes, converties en WebP
 * (`public/blog/`). `largeur` × `hauteur` sont les dimensions des fichiers.
 *
 * Ce fichier ne compose rien : `contenuBlog.ARTICLES` le fait, et calcule le
 * temps de lecture.
 */
import type { SourceDArticle } from "./contenuBlog";
import {
  courrielAvecObjet,
  ROUTES_RESSOURCES,
  type Passerelle,
} from "./contenuRessources";

/** L'invitation qui ferme chaque lettre, UNE fois pour tous les portraits.
 *  Le bouton ouvre un courriel : la plateforme n'a pas de formulaire, et la
 *  lettre n'en veut pas (« Pas de formulaire compliqué »). */
const APPEL: SourceDArticle["appel"] = {
  titre: "La Lettre des Porteurs",
  document: "Vous souhaitez qu'on parle de vous dans la prochaine Lettre des Porteurs ?",
  corps:
    "C'est simple : contactez-moi directement. Pas de formulaire compliqué. Pas de blabla. Juste votre histoire, vos avancées, votre projet. Votre parcours mérite d'être raconté, et je serai ravie de le mettre en lumière.",
  bouton: {
    libelle: "Proposer mon parcours par e-mail",
    lien: courrielAvecObjet("Mon parcours pour La Lettre des Porteurs"),
  },
};

/** La passerelle des portraits : les études, sans prix. Écrite pour la
 *  plateforme ; son titre reprend la question qui ferme la lettre n° 1. */
const VERS_LES_ETUDES: Passerelle = {
  titre: { avant: "Et votre projet,", fin: "où en est-il ?" },
  corps:
    "Étude de marché, étude de la concurrence, business plan, stratégie : les études EVKHA sont rédigées sur votre projet.",
  bouton: { libelle: "Voir les études", lien: ROUTES_RESSOURCES.etudes },
};

const SALUT = "À très vite,";
/** La signature de l'article existant, gardée telle que la cliente signe. */
const SIGNATURE = "Evangéline";

// ── La Lettre des Porteurs n° 1 ─────────────────────────────────────────────

const JEFFREY = "Jeffrey Yeye";

const PORTRAIT_JEFFREY: SourceDArticle = {
  slug: "portrait-jeffrey-yeye-mondossierptp",
  titre: "Jeffrey Yeye, fondateur de MonDossierPTP",
  /** La phrase que la lettre met en exergue sous le titre du portrait. */
  sousTitre: "« On apprend énormément en avançant. »",
  theme: "portraits",
  publieLe: null,
  entete: {
    titreOnglet: "Portrait : Jeffrey Yeye, fondateur de MonDossierPTP",
    description:
      "Jeffrey Yeye a fondé MonDossierPTP pour les salariés en reconversion perdus face aux démarches. Sa plus grande difficulté, son déclic et son conseil.",
  },
  image: {
    src: "/blog/portrait-jeffrey-yeye.webp",
    alt: "Jeffrey Yeye, fondateur de MonDossierPTP",
    largeur: 1200,
    hauteur: 800,
    // Le visage est dans le tiers haut de la photo.
    cadrage: "50% 22%",
  },
  /** Le chapô est l'annonce de la lettre : sur une carte, sa première phrase
   *  ne dirait pas de qui l'article parle. */
  accroche:
    "Jeffrey, c'est quelqu'un qui a vu un problème que personne ne réglait vraiment… et qui a décidé de s'en occuper lui-même.",
  chapo: {
    intertitre: "Elle est là. Enfin.",
    paragraphes: [
      "Après plusieurs mois de préparation, de collecte de vos retours et de vos histoires… La Lettre des Porteurs voit officiellement le jour.",
      "Vous vous souvenez ? En fin d'année dernière, je vous avais parlé de ce projet : créer un espace pour vous, pour raconter vos parcours, vos lancements, vos galères, vos victoires.",
      "Eh bien, on y est !",
      "Et pour cette toute première édition, je suis très fière de vous présenter un porteur de projet que j'ai accompagné et dont le parcours mérite vraiment d'être raconté.",
    ],
  },
  sections: [
    {
      intertitre: "Un problème que personne ne réglait vraiment",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Jeffrey, c'est quelqu'un qui a vu un problème que personne ne réglait vraiment… et qui a décidé de s'en occuper lui-même.",
        },
        {
          genre: "paragraphe",
          texte:
            "Son constat ? Des milliers de salariés veulent se reconvertir via le Projet de Transition Professionnelle, mais se retrouvent perdus face aux démarches administratives. Trop de paperasse, trop de flou, pas assez d'accompagnement humain.",
        },
        {
          genre: "paragraphe",
          texte:
            "Sa réponse : MonDossierPTP — une plateforme qui apporte clarté, sérénité et un accompagnement adapté à chaque situation.",
        },
        {
          genre: "lien",
          libelle: "Découvrir MonDossierPTP sur mondossierptp.fr",
          lien: "https://www.mondossierptp.fr",
        },
        {
          genre: "paragraphe",
          texte: "Mais comme tout projet entrepreneurial… rien n'a été simple.",
        },
      ],
    },
    {
      intertitre: "Trois questions à Jeffrey",
      elements: [],
      sousSections: [
        {
          intertitre: "Jeffrey, quelle a été ta plus grande difficulté ?",
          elements: [
            {
              genre: "citation",
              texte:
                "Le financement. Obtenir un financement bancaire quand on lance une activité sans historique ni chiffre d'affaires, c'est un vrai parcours du combattant. Il a fallu faire preuve de persévérance et continuer à avancer malgré les obstacles.",
              auteur: JEFFREY,
            },
            {
              genre: "paragraphe",
              texte:
                "Et comme si ça ne suffisait pas, Jeffrey a dû tout apprendre en parallèle : création de site, référencement, publicité en ligne, automatisations, expérience utilisateur, stratégie marketing… Tout. Seul.",
            },
          ],
        },
        {
          intertitre: "Et à quel moment tu t'es dit : « ça y est, c'est réel » ?",
          elements: [
            {
              genre: "citation",
              texte:
                "Quand les premières personnes ont utilisé le site, répondu au quiz et sollicité un accompagnement. À ce moment-là, ce n'était plus une idée. C'était un vrai service, capable d'aider concrètement des gens en reconversion.",
              auteur: JEFFREY,
            },
            {
              genre: "paragraphe",
              texte:
                "C'est ça, le déclic entrepreneurial. Ce moment où le projet sort de votre tête… et entre dans la vie des autres.",
            },
          ],
        },
        {
          intertitre: "Et si tu devais donner UN conseil à quelqu'un qui hésite encore ?",
          elements: [
            {
              genre: "citation",
              texte:
                "Ne pas attendre que tout soit parfait avant de commencer. L'important, c'est de passer à l'action, de tester, d'améliorer progressivement. Chaque petit pas compte — et la persévérance fait souvent la différence.",
              auteur: JEFFREY,
            },
          ],
        },
      ],
    },
  ],
  conclusion: {
    intertitre: "L'esprit de cette Lettre",
    elements: [
      {
        genre: "paragraphe",
        texte:
          "On ne pouvait pas mieux résumer l'esprit de cette Lettre. Car chaque petit pas mène à un objectif.",
      },
      { genre: "paragraphe", texte: "Jeffrey l'a prouvé. Et vous, où en êtes-vous ?" },
    ],
    salut: SALUT,
    signature: SIGNATURE,
  },
  appel: APPEL,
  passerelle: VERS_LES_ETUDES,
};

// ── La Lettre des Porteurs n° 2 ─────────────────────────────────────────────

const LEA = "Léa Marie Le Cordier";

const PORTRAIT_LEA: SourceDArticle = {
  slug: "portrait-lea-marie-le-cordier-le-boeuf-club",
  titre: "Léa Marie Le Cordier, fondatrice du Bœuf Club",
  /** Le titre de la lettre. */
  sousTitre: "Quand l'expertise ne suffit plus…",
  theme: "portraits",
  publieLe: null,
  entete: {
    titreOnglet: "Portrait : Léa Marie Le Cordier, fondatrice du Bœuf Club",
    description:
      "Après plus de dix ans en agence, Léa Marie Le Cordier a créé Le Bœuf Club : la marque comme actif de l'entreprise. Son constat, ses résultats, son conseil.",
  },
  image: {
    src: "/blog/portrait-lea-marie-le-cordier.webp",
    alt: "Léa Marie Le Cordier, fondatrice du Bœuf Club",
    largeur: 900,
    hauteur: 1350,
    // Photo verticale : le visage est dans le tiers haut, au centre. Un cadre
    // plus large que haut doit garder ce tiers-là.
    cadrage: "50% 18%",
  },
  /** Le chapô ouvre sur une généralité : la carte dit plutôt d'où part Léa. */
  accroche: "Après plus de dix ans passés en agence, Léa a fait un constat.",
  chapo: {
    intertitre: "Et si le problème n'était pas votre expertise ?",
    paragraphes: [
      "Chaque entrepreneur a une histoire. Chaque entreprise naît d'une idée, d'un besoin ou d'un constat.",
      "Dans La Lettre des Porteurs, j'ai envie de mettre en lumière celles et ceux qui ont décidé de transformer une conviction en projet.",
      "Aujourd'hui, j'ai le plaisir de vous présenter Léa Marie Le Cordier, fondatrice du Bœuf Club.",
    ],
  },
  sections: [
    {
      intertitre: "Le constat de Léa",
      elements: [
        {
          genre: "paragraphe",
          texte: "Après plus de dix ans passés en agence, Léa a fait un constat.",
        },
        {
          genre: "paragraphe",
          texte:
            "De nombreux dirigeants possèdent une véritable expertise terrain. Pourtant, ils restent invisibles ou sont perçus comme « low cost » face à leurs concurrents.",
        },
        {
          genre: "paragraphe",
          texte:
            "Non pas parce qu'ils sont moins compétents. Mais parce que personne n'a jamais travaillé leur marque comme un véritable actif de l'entreprise.",
        },
        {
          genre: "paragraphe",
          texte: "C'est ce constat qui lui a donné envie de créer Le Bœuf Club.",
        },
      ],
    },
    {
      intertitre: "Pourquoi Le Bœuf Club ?",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Léa ne souhaitait pas créer « encore une agence créa ». Sa motivation était différente.",
        },
        {
          genre: "paragraphe",
          texte:
            "Elle voulait arrêter de voir la marque traitée comme une simple dépense créative que l'on reporte pendant que l'on gère l'opérationnel.",
        },
        {
          genre: "paragraphe",
          texte:
            "Sa conviction est simple : une marque bien pensée est un levier commercial et un actif qui se valorise.",
        },
        {
          genre: "paragraphe",
          texte:
            "Elle accompagne notamment les dirigeants en phase de pivot ou de reprise qui possèdent une véritable expertise mais qui peinent à décrocher des projets premium ou voient leur chiffre d'affaires stagner sans toujours en comprendre les raisons.",
        },
        {
          genre: "paragraphe",
          texte:
            "À l'heure du digital et des réseaux sociaux, elle est convaincue que travailler sa marque, c'est aussi travailler la visibilité et le développement de son entreprise.",
        },
      ],
    },
    {
      intertitre: "Convaincre avec des résultats",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "La plus grande difficulté qu'elle a rencontrée n'a pas été de construire son offre. Elle a été de convaincre des dirigeants souvent échaudés par une ou plusieurs expériences avec des agences créatives, sans retour sur investissement réellement mesurable.",
        },
        {
          genre: "paragraphe",
          texte:
            "Plutôt que de présenter de belles maquettes, Léa a choisi de démontrer l'impact de son travail avec des résultats concrets.",
        },
        {
          genre: "liste",
          introduction: "Parmi eux :",
          // Les espaces insécables tiennent chaque nombre sur une ligne.
          points: [
            "+101,5\u00a0% de contacts qualifiés pour un client.",
            "Un taux de transformation multiplié par deux.",
            "Une communauté passée de 2\u00a0600 à 10\u00a0700 abonnés en seulement quatre mois.",
            "220 leads générés en deux mois.",
          ],
        },
        {
          genre: "paragraphe",
          texte:
            "Pour Léa, c'est à ce moment-là que son projet est devenu réellement concret. Les chiffres parlaient désormais à sa place.",
        },
      ],
    },
    {
      intertitre: "Le conseil de Léa",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Je lui ai demandé quel conseil elle donnerait aujourd'hui à une personne qui hésite encore à lancer son projet. Voici sa réponse.",
        },
        {
          genre: "citation",
          texte:
            "Si votre expertise terrain ne se voit pas dans vos résultats commerciaux, le problème n'est probablement pas votre métier mais votre marque. Le vrai risque n'est pas de vous tromper en travaillant dessus, c'est de rester invisible pendant que vos concurrents, moins bons que vous, prennent les deals premium.",
          auteur: LEA,
        },
      ],
    },
    {
      intertitre: "Découvrez Le Bœuf Club",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Si vous souhaitez découvrir l'univers de Léa Marie Le Cordier et son approche de la stratégie de marque, je vous invite à découvrir Le Bœuf Club.",
        },
        {
          genre: "lien",
          libelle: "Le Bœuf Club sur LinkedIn",
          lien: "https://www.linkedin.com/company/le-boeuf-club/",
        },
      ],
    },
    {
      intertitre: "L'inspiration du mois",
      elements: [
        {
          // La lettre ne dit pas de qui sont ces mots : pas d'auteur supposé.
          genre: "citation",
          texte:
            "Une marque n'est pas seulement ce que l'on montre. C'est aussi la manière dont une entreprise est perçue, reconnue… et choisie.",
        },
      ],
    },
  ],
  /** La dernière rubrique de la lettre, qui revient au parcours de Léa : elle
   *  ferme l'article. */
  conclusion: {
    intertitre: "Le mot du dirigeant : actif immatériel",
    elements: [
      {
        genre: "paragraphe",
        texte:
          "On parle souvent des locaux, du matériel ou du chiffre d'affaires d'une entreprise. Mais certains de ses actifs les plus précieux sont invisibles. On les appelle les actifs immatériels.",
      },
      {
        genre: "paragraphe",
        texte:
          "Ils regroupent notamment la marque, la réputation, le savoir-faire, les droits de propriété intellectuelle ou encore la confiance accordée par les clients.",
      },
      {
        genre: "paragraphe",
        texte:
          "Contrairement à ce que l'on pourrait penser, ces actifs créent une véritable valeur pour l'entreprise.",
      },
      {
        genre: "paragraphe",
        texte:
          "Le parcours de Léa en est une bonne illustration : une marque bien pensée ne se limite pas à une identité visuelle. Elle peut devenir un véritable levier commercial et participer à la valorisation d'une entreprise.",
      },
    ],
    salut: SALUT,
    signature: SIGNATURE,
  },
  appel: APPEL,
  passerelle: VERS_LES_ETUDES,
};

/** Les portraits, le plus récent en premier — dans l'ordre inverse des
 *  lettres : la n° 2, puis la n° 1. */
export const PORTRAITS: SourceDArticle[] = [PORTRAIT_LEA, PORTRAIT_JEFFREY];
