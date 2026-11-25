/** LES GUIDES DU BLOG : trois articles écrits pour la plateforme le 20/11/2026.
 *
 * Ils répondent, sans détour, aux questions que les porteurs de projet tapent
 * dans un moteur de recherche ou posent à un moteur de réponse — relevées sur
 * les pages les mieux placées (`docs/referencement/etat-et-plan.md`) :
 * comment faire une étude de marché, ce qu'un business plan doit contenir pour
 * une banque, quel document faire en premier.
 *
 * ## Ce qu'ils s'interdisent
 *
 * - AUCUN PRIX, aucun montant : ceux d'EVKHA sont lus au serveur, ceux du
 *   marché ne sont pas mesurés ici (le test des pages du blog le verrouille).
 * - AUCUN CHIFFRE sur EVKHA (clients, ancienneté, délais) : seulement ce que
 *   les pages du site disent déjà, par renvoi.
 * - Rien qui dépende d'un point non confirmé (financement, CPF, Qualiopi).
 * - Les organismes cités (Insee, Bpifrance Création, CCI, CMA, BGE,
 *   France Travail) le sont pour ce qu'ils publient ou demandent de notoriété
 *   publique, sans chiffre.
 *
 * ## À FAIRE VALIDER PAR LA CLIENTE AVANT MISE EN LIGNE
 *
 * Ces textes ne sont PAS relevés sur son site : ils sont proposés. Ils portent
 * sa signature, comme l'article existant — c'est à elle de les relire, de les
 * corriger et de dire s'ils peuvent paraître sous son nom. Sans date de
 * publication (`publieLe: null`) tant qu'ils ne sont pas en ligne : une date
 * ne se suppose pas.
 *
 * Ce fichier ne compose rien : `contenuBlog.ARTICLES` le fait, et calcule le
 * temps de lecture.
 */
import type { SourceDArticle } from "./contenuBlog";
import type { Passerelle } from "./contenuRessources";
import { CHEMINS } from "./contenuSite";

/** L'appel de fin de guide : la boîte à outils, où la checklist et le
 *  lexique se téléchargent contre une adresse (`FormulaireAudience`). */
const APPEL: SourceDArticle["appel"] = {
  titre: "Deux documents gratuits pour préparer votre création",
  document: "La boîte à outils EVKHA",
  corps: "Une checklist et un lexique à télécharger gratuitement.",
  bouton: { libelle: "Ouvrir la boîte à outils", lien: CHEMINS.boiteAOutils },
};

const VERS_LES_ETUDES: Passerelle = {
  titre: { avant: "Pas le temps de tout faire vous-même ?", fin: "Faites-la rédiger." },
  corps:
    "L'étude de marché EVKHA est rédigée sur votre projet et sur votre zone, dans un français clair, pour être présentée à une banque ou à un organisme d'accompagnement.",
  bouton: { libelle: "Découvrir les études", lien: CHEMINS.etudes },
};

const SALUT = "Bonne préparation !";
/** La signature de l'article existant, gardée telle que la cliente signe. */
const SIGNATURE = "Evangéline";

/** LES GUIDES SONT-ILS PUBLIÉS ? Non, tant que la cliente ne les a pas relus.
 *
 *  Ils portent sa signature et la déclarent comme auteur aux moteurs : les
 *  mettre en ligne avant son accord serait trancher à sa place. À `false`,
 *  ils ne sont ni dans la liste du blog, ni dans le plan du site, ni dans
 *  `sitemap.xml`, ni dans `llms.txt` — leur adresse rend « article
 *  introuvable ».
 *
 *  LE JOUR OÙ ELLE LES VALIDE : passer cette ligne à `true`, donner à chaque
 *  guide sa date de publication (`publieLe`), et rien d'autre. Tout le reste
 *  suit de `contenuBlog.ARTICLES`. */
export const GUIDES_PUBLIES: boolean = false;

export const GUIDES: SourceDArticle[] = [
  // ── 1. Comment faire une étude de marché ──────────────────────────────────
  {
    slug: "comment-faire-une-etude-de-marche",
    titre: "Comment faire une étude de marché ?",
    sousTitre: "Les 6 étapes, dans l'ordre, pour un projet de création d'entreprise",
    theme: "etude-de-marche",
    publieLe: null,
    entete: {
      titreOnglet: "Comment faire une étude de marché : les 6 étapes",
      description:
        "Définition, sources gratuites, concurrents, clients, chiffre d'affaires prévisionnel : les 6 étapes pour faire l'étude de marché de votre projet de création d'entreprise.",
    },
    chapo: {
      intertitre: "L'étude de marché, en une phrase",
      paragraphes: [
        "Une étude de marché sert à vérifier, avant de vous lancer, qu'il existe assez de clients prêts à payer pour ce que vous voulez vendre, là où vous voulez le vendre.",
        "Elle n'est pas obligatoire pour créer une entreprise. Mais une banque, un organisme d'accompagnement ou un financeur vous la demandera presque toujours, parce que c'est elle qui justifie les chiffres de votre business plan.",
        "Voici les six étapes à suivre, dans l'ordre. Vous pouvez les mener vous-même : la plupart des sources sont publiques et gratuites.",
      ],
    },
    sections: [
      {
        intertitre: "Étape 1 – Écrire précisément ce que vous vendez, à qui, et où",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Une étude de marché ne porte pas sur « la restauration » ou « le bien-être » en général. Elle porte sur une offre précise, pour une clientèle précise, dans une zone précise.",
          },
          {
            genre: "liste",
            introduction: "Avant toute recherche, écrivez trois lignes :",
            points: [
              "Mon offre : le produit ou le service, et le problème qu'il règle",
              "Ma cible : les particuliers ou les entreprises à qui je m'adresse",
              "Ma zone : le quartier, la ville, la région, ou la France entière si je vends en ligne",
            ],
          },
          {
            genre: "exemple",
            amorce: "Exemple",
            texte:
              "« Un salon de coiffure mixte sans rendez-vous, pour les actifs du centre-ville, dans un rayon de dix minutes à pied » est un sujet d'étude. « Ouvrir un salon de coiffure » n'en est pas un.",
          },
        ],
      },
      {
        intertitre: "Étape 2 – Mesurer le marché avec les sources publiques",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Cette étape s'appelle l'étude documentaire. Elle répond à deux questions : quelle est la taille de ce marché, et est-il en croissance, stable ou en recul ?",
          },
          {
            genre: "liste",
            introduction: "Les sources à consulter en premier :",
            points: [
              "L'Insee, pour la population, les revenus et le nombre d'entreprises de votre zone",
              "Bpifrance Création, pour ses fiches par métier et ses dossiers sur la création d'entreprise",
              "La fédération ou le syndicat professionnel de votre secteur, qui publie souvent des chiffres clés",
              "Votre chambre de commerce et d'industrie (CCI) ou votre chambre de métiers et de l'artisanat (CMA)",
              "La presse spécialisée de votre métier",
            ],
          },
          {
            genre: "question",
            amorce: "Demandez-vous :",
            texte:
              "D'où vient chaque chiffre que j'écris, et de quelle année date-t-il ? Un chiffre sans source ne convaincra ni une banque ni vous-même.",
          },
        ],
      },
      {
        intertitre: "Étape 3 – Étudier vos concurrents",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Vos concurrents directs vendent la même chose que vous à la même clientèle. Vos concurrents indirects répondent au même besoin autrement : pour un restaurant du midi, la boulangerie d'en face et la livraison de repas en font partie.",
          },
          {
            genre: "liste",
            introduction: "Pour chaque concurrent de votre zone, notez :",
            points: [
              "Son emplacement et sa zone de chalandise",
              "Son offre et ses prix affichés",
              "Ce que ses clients en disent dans les avis en ligne",
              "Ce qu'il fait bien, et ce qu'il ne fait pas",
            ],
          },
          {
            genre: "paragraphe",
            texte:
              "Les comptes des sociétés qui les publient sont consultables gratuitement en ligne : ils donnent un ordre de grandeur du chiffre d'affaires réalisable dans votre métier.",
          },
        ],
      },
      {
        intertitre: "Étape 4 – Interroger vos futurs clients",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Les chiffres ne disent pas tout. Allez poser vos questions à des personnes qui ressemblent à vos futurs clients : par un questionnaire en ligne, des entretiens, ou simplement en observant un point de vente comparable.",
          },
          {
            genre: "liste",
            introduction: "Cherchez à savoir :",
            points: [
              "Comment elles règlent ce besoin aujourd'hui",
              "Ce qui leur manque dans les solutions existantes",
              "Le prix qu'elles jugent normal, et celui qu'elles jugent trop cher",
              "À quelle fréquence elles achèteraient",
            ],
          },
          {
            genre: "question",
            amorce: "Demandez-vous :",
            texte:
              "Ai-je interrogé de vrais clients potentiels, ou seulement mes proches ? L'avis de l'entourage est bienveillant : il ne mesure pas un marché.",
          },
        ],
      },
      {
        intertitre: "Étape 5 – Estimer votre chiffre d'affaires",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "C'est le résultat que votre banquier lira en premier. Il se calcule, il ne se devine pas : un nombre de clients réaliste, multiplié par un panier moyen, multiplié par une fréquence d'achat.",
          },
          {
            genre: "paragraphe",
            texte:
              "Faites trois hypothèses — prudente, réaliste, optimiste — et dites sur quoi chacune repose. Comparez ensuite le résultat à ce que réalisent les concurrents que vous avez étudiés : un écart important doit pouvoir s'expliquer.",
          },
        ],
      },
      {
        intertitre: "Étape 6 – Conclure : y aller, ajuster, ou renoncer",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Une étude de marché se termine par une décision. Elle doit dire si le projet est viable tel quel, à quelles conditions, et quels sont ses principaux risques.",
          },
          {
            genre: "liste",
            introduction: "Votre conclusion tient en quatre points :",
            points: [
              "Le marché : sa taille et sa tendance dans votre zone",
              "La concurrence : la place qui reste, et ce qui vous distingue",
              "La clientèle : qui achètera, à quel prix, à quelle fréquence",
              "Le chiffre d'affaires prévisionnel, avec ses hypothèses",
            ],
          },
        ],
      },
      {
        intertitre: "Questions fréquentes",
        elements: [
          {
            genre: "question",
            amorce: "L'étude de marché est-elle obligatoire ?",
            texte:
              "Non, aucun texte ne l'impose pour créer une entreprise, y compris une micro-entreprise. Elle devient indispensable dès que vous demandez un prêt ou une aide, parce que votre dossier doit justifier ses chiffres.",
          },
          {
            genre: "question",
            amorce: "Peut-on la faire soi-même ?",
            texte:
              "Oui. Les sources publiques suffisent pour un commerce, un service de proximité ou une activité indépendante. Il faut surtout du temps, de la méthode, et accepter de regarder les chiffres qui ne vont pas dans votre sens.",
          },
          {
            genre: "question",
            amorce: "Quelle différence avec une étude de concurrence ?",
            texte:
              "L'étude de la concurrence est une partie de l'étude de marché, poussée plus loin : elle compare vos concurrents un par un, sur leur offre, leurs prix et leur positionnement.",
          },
        ],
      },
    ],
    conclusion: {
      intertitre: "En résumé",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Une bonne étude de marché n'est pas un gros document. C'est un document où chaque chiffre a une source, et qui se termine par une décision claire.",
        },
        {
          genre: "paragraphe",
          texte:
            "Si vous manquez de temps ou de recul pour la mener, vous pouvez la faire rédiger : l'important est qu'elle porte sur votre projet et sur votre zone, pas sur un secteur en général.",
        },
      ],
      salut: SALUT,
      signature: SIGNATURE,
    },
    appel: APPEL,
    passerelle: VERS_LES_ETUDES,
  },

  // ── 2. Le business plan pour la banque ────────────────────────────────────
  {
    slug: "business-plan-pour-la-banque",
    titre: "Business plan pour la banque : que doit-il contenir ?",
    sousTitre: "Les parties attendues, et ce que votre banquier regarde vraiment",
    theme: "financement",
    publieLe: null,
    entete: {
      titreOnglet: "Business plan pour la banque : ce qu'il doit contenir",
      description:
        "Résumé, marché, stratégie, prévisionnel financier : ce qu'un business plan doit contenir pour une demande de prêt, et ce que le banquier regarde en premier.",
    },
    chapo: {
      intertitre: "Le business plan, en une phrase",
      paragraphes: [
        "Un business plan est le document qui présente votre projet d'entreprise et démontre, chiffres à l'appui, qu'il peut gagner de l'argent et rembourser ce qu'on lui prête.",
        "Il n'est pas obligatoire pour créer une entreprise. Il le devient en pratique dès que vous sollicitez un prêt professionnel, un prêt d'honneur ou une aide : c'est sur lui que votre interlocuteur décide.",
        "Un banquier ne cherche pas un beau document. Il cherche à comprendre le projet en quelques minutes, puis à vérifier que les chiffres tiennent.",
      ],
    },
    sections: [
      {
        intertitre: "Les six parties d'un business plan",
        elements: [
          {
            genre: "liste",
            introduction: "Dans l'ordre où elles se lisent :",
            points: [
              "Le résumé : le projet, le besoin de financement et les chiffres clés, sur une page",
              "Le porteur de projet : votre parcours, vos compétences, et pourquoi vous",
              "Le marché : les conclusions de votre étude de marché et de votre étude de la concurrence",
              "La stratégie : votre offre, vos prix, et la façon dont vous trouverez vos clients",
              "L'organisation : le statut juridique, le local, le matériel, l'équipe",
              "Le prévisionnel financier : les tableaux qui traduisent tout cela en chiffres",
            ],
          },
          {
            genre: "paragraphe",
            texte:
              "Le résumé s'écrit en dernier et se lit en premier. S'il ne donne pas envie de lire la suite, la suite ne sera pas lue avec la même attention.",
          },
        ],
      },
      {
        intertitre: "Le prévisionnel financier : les quatre tableaux attendus",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "C'est la partie que la banque examine le plus longuement. Elle se construit en général sur trois ans.",
          },
          {
            genre: "liste",
            points: [
              "Le plan de financement : ce dont vous avez besoin pour démarrer, et d'où vient l'argent (apport, prêt, aides)",
              "Le compte de résultat prévisionnel : le chiffre d'affaires, les charges et le résultat de chaque année",
              "Le plan de trésorerie : les entrées et les sorties d'argent, mois par mois, la première année",
              "Le seuil de rentabilité : le chiffre d'affaires à partir duquel l'entreprise couvre toutes ses charges",
            ],
          },
          {
            genre: "question",
            amorce: "Demandez-vous :",
            texte:
              "Si l'on me demande d'où vient mon chiffre d'affaires de la première année, ai-je une réponse en deux phrases, appuyée sur mon étude de marché ?",
          },
        ],
      },
      {
        intertitre: "Ce que le banquier regarde en premier",
        elements: [
          {
            genre: "liste",
            points: [
              "La cohérence : les chiffres du prévisionnel découlent-ils de l'étude de marché, ou sortent-ils de nulle part ?",
              "Votre apport personnel : ce que vous engagez vous-même dans le projet",
              "La capacité de remboursement : le résultat prévu couvre-t-il les échéances du prêt, même dans l'hypothèse prudente ?",
              "La trésorerie des premiers mois : l'entreprise tient-elle le temps que les clients arrivent ?",
              "Vous : votre expérience du métier et votre connaissance du dossier",
            ],
          },
          {
            genre: "exemple",
            amorce: "Exemple",
            texte:
              "Un prévisionnel qui annonce une salle pleine dès le premier mois inquiète plus qu'il ne rassure. Une montée en charge progressive, expliquée, montre que vous connaissez votre métier.",
          },
        ],
      },
      {
        intertitre: "Les erreurs qui font refuser un dossier",
        elements: [
          {
            genre: "liste",
            points: [
              "Un chiffre d'affaires sans justification",
              "Des charges oubliées : cotisations sociales, assurance, loyer, votre propre rémunération",
              "Aucune hypothèse prudente",
              "Un document trop long, où l'essentiel est noyé",
              "Un texte que vous ne savez pas défendre à l'oral, parce que vous ne l'avez pas compris",
            ],
          },
        ],
      },
      {
        intertitre: "Questions fréquentes",
        elements: [
          {
            genre: "question",
            amorce: "Combien de pages doit faire un business plan ?",
            texte:
              "Il n'existe pas de règle. Un document court et clair, complété par ses tableaux financiers, est mieux lu qu'un dossier épais. Ce qui compte, c'est que chaque partie attendue y soit.",
          },
          {
            genre: "question",
            amorce: "Qui peut rédiger mon business plan ?",
            texte:
              "Vous-même, avec un modèle ou un logiciel ; un expert-comptable ; un organisme d'accompagnement à la création ; ou un prestataire spécialisé. Dans tous les cas, vous devez le comprendre et savoir l'expliquer : c'est vous que le banquier interrogera.",
          },
          {
            genre: "question",
            amorce: "Le business plan garantit-il le prêt ?",
            texte:
              "Non. Il donne à votre interlocuteur de quoi décider. Un bon dossier augmente vos chances ; il ne remplace ni l'apport, ni la solidité du projet.",
          },
          {
            genre: "question",
            amorce: "Quelle différence entre business plan et prévisionnel ?",
            texte:
              "Le prévisionnel financier est la partie chiffrée du business plan. Le business plan y ajoute tout ce qui explique ces chiffres : le marché, la stratégie, l'organisation.",
          },
        ],
      },
    ],
    conclusion: {
      intertitre: "En résumé",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Un business plan convaincant raconte une seule histoire, du marché jusqu'aux chiffres. Si votre étude de marché est solide, la moitié du travail est faite.",
        },
        {
          genre: "paragraphe",
          texte:
            "Avant de le présenter, faites-le lire à quelqu'un qui ne connaît pas votre projet. S'il le comprend, votre banquier le comprendra.",
        },
      ],
      salut: SALUT,
      signature: SIGNATURE,
    },
    appel: APPEL,
    passerelle: {
      titre: { avant: "Un dossier à présenter à votre banque ?", fin: "Faites-le rédiger." },
      corps:
        "Le business plan EVKHA est rédigé sur votre projet, dans un français clair, pour être présenté à une banque ou à un organisme d'accompagnement.",
      bouton: { libelle: "Découvrir les études", lien: CHEMINS.etudes },
    },
  },

  // ── 3. Quel document faire, et dans quel ordre ────────────────────────────
  {
    slug: "etude-de-marche-ou-business-plan",
    titre: "Étude de marché, étude de concurrence, business plan : par quoi commencer ?",
    sousTitre: "À quoi sert chaque document, et dans quel ordre les faire",
    theme: "creation",
    publieLe: null,
    entete: {
      titreOnglet: "Étude de marché ou business plan : par quoi commencer ?",
      description:
        "Étude de marché, étude de la concurrence, business plan, stratégie commerciale : à quoi sert chaque document, à qui il s'adresse, et dans quel ordre les préparer.",
    },
    chapo: {
      intertitre: "Quatre documents, quatre questions",
      paragraphes: [
        "L'étude de marché dit s'il y a des clients. L'étude de la concurrence dit face à qui vous serez. Le business plan dit si le projet est finançable. La stratégie commerciale dit comment vous allez vendre.",
        "Ces documents ne se remplacent pas : chacun prépare le suivant. On les confond souvent, et l'on commence parfois par le dernier.",
      ],
    },
    sections: [
      {
        intertitre: "L'étude de marché : y a-t-il des clients ?",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Elle mesure la taille du marché dans votre zone, sa tendance, les attentes des clients et les risques du projet. Elle se termine par une estimation de votre chiffre d'affaires.",
          },
          {
            genre: "liste",
            points: [
              "Quand la faire : en premier, avant d'engager de l'argent",
              "Pour qui : pour vous d'abord, puis pour tous ceux qui liront votre dossier",
              "Ce qu'elle vous donne : la décision d'y aller, d'ajuster ou de renoncer",
            ],
          },
        ],
      },
      {
        intertitre: "L'étude de la concurrence : face à qui ?",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Elle compare vos concurrents directs et indirects un par un : leur offre, leurs prix, leur emplacement, leurs points forts et leurs points faibles. Elle en déduit la place que vous pouvez prendre.",
          },
          {
            genre: "liste",
            points: [
              "Quand la faire : après ou avec l'étude de marché, surtout si votre secteur est déjà bien occupé",
              "Pour qui : pour vous, et pour montrer à un financeur que vous connaissez le terrain",
              "Ce qu'elle vous donne : votre positionnement et vos arguments",
            ],
          },
        ],
      },
      {
        intertitre: "Le business plan : le projet est-il finançable ?",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Il rassemble le projet, le marché, la stratégie et le prévisionnel financier dans un seul dossier. C'est le document que demandent les banques et les organismes d'accompagnement.",
          },
          {
            genre: "liste",
            points: [
              "Quand le faire : une fois le marché étudié, parce que ses chiffres en découlent",
              "Pour qui : pour la banque, un financeur, un associé",
              "Ce qu'il vous donne : un dossier à défendre, et un cap pour vos premières années",
            ],
          },
        ],
      },
      {
        intertitre: "La stratégie commerciale : comment allez-vous vendre ?",
        elements: [
          {
            genre: "paragraphe",
            texte:
              "Elle traduit tout ce qui précède en plan d'action : à qui vous vous adressez en priorité, à quel prix, par quels canaux, et avec quels objectifs.",
          },
          {
            genre: "liste",
            points: [
              "Quand la faire : au moment de passer à l'action, ou quand une entreprise existante veut se développer",
              "Pour qui : pour vous et votre équipe",
              "Ce qu'elle vous donne : ce que vous faites lundi matin",
            ],
          },
        ],
      },
      {
        intertitre: "Dans quel ordre, selon votre situation",
        elements: [
          {
            genre: "liste",
            points: [
              "Vous avez une idée et vous doutez : commencez par l'étude de marché",
              "Votre secteur compte déjà beaucoup d'acteurs : ajoutez l'étude de la concurrence",
              "Vous demandez un prêt ou une aide : il vous faut le business plan, appuyé sur l'étude de marché",
              "Votre entreprise existe et vous voulez vendre plus : la stratégie commerciale",
            ],
          },
          {
            genre: "question",
            amorce: "Peut-on faire un business plan sans étude de marché ?",
            texte:
              "On peut l'écrire, mais ses chiffres ne reposeront sur rien. La première question d'un banquier porte presque toujours sur l'origine du chiffre d'affaires annoncé : c'est l'étude de marché qui y répond.",
          },
          {
            genre: "question",
            amorce: "Faut-il les quatre documents ?",
            texte:
              "Pas toujours. Pour une petite activité sans emprunt, une étude de marché sérieuse peut suffire. Pour un projet à financer, l'étude de marché et le business plan vont ensemble.",
          },
        ],
      },
    ],
    conclusion: {
      intertitre: "En résumé",
      elements: [
        {
          genre: "paragraphe",
          texte:
            "Le marché d'abord, la concurrence ensuite, puis le dossier pour la banque et le plan d'action. Chaque document répond à une question, et prépare la suivante.",
        },
      ],
      salut: SALUT,
      signature: SIGNATURE,
    },
    appel: APPEL,
    passerelle: {
      titre: { avant: "Vous savez quel document il vous faut ?", fin: "Voyez comment nous le rédigeons." },
      corps:
        "Étude de marché, étude de la concurrence, business plan, stratégie business : chaque document est rédigé sur votre projet.",
      bouton: { libelle: "Découvrir les études", lien: CHEMINS.etudes },
    },
  },
];
