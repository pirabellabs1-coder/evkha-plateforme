/** Le texte des quatre pages légales publiques.
 *
 * TEXTE REPRIS TEL QUEL du site www.evkha.fr (Systeme.io), relevé le
 * 25/10/2026 dans `docs/refonte/inventaire-site-evkha.md` (pages 30 à 33).
 * NON RELU PAR UNE JURISTE. À VALIDER AVANT MISE EN LIGNE sur la nouvelle
 * plateforme : voir `POINTS_A_FAIRE_VALIDER` en bas de fichier.
 *
 * Rien n'a été ajouté, retiré, reformulé ni « mis à jour ». Seules retouches :
 * - le menu et le pied de page répétés sur chaque page sont retirés ;
 * - les espaces parasites avant une virgule ou un point, laissées par le
 *   relevé autour des mots en gras, sont retirées ;
 * - six coquilles de frappe sans effet sur le sens sont corrigées :
 *   « SOUR LE SIRET » → « SOUS LE SIRET », « à propose de » → « à propos de »,
 *   « Formatio ns » → « Formations », « lecaching » → « le caching »,
 *   « audelà » → « au-delà », « virement.. » → « virement. » ;
 * - quatre titres que le relevé avait collés au paragraphe voisin sont
 *   redevenus des titres (RGPD 1.2, 1.3 et 7 ; « Safari » / « Google Chrome »,
 *   dont les consignes étaient entremêlées sur deux colonnes).
 * Les autres fautes (accords, accents, « par la présence ») sont laissées :
 * les corriger revient à la personne qui validera le texte.
 *
 * Les chemins sont ceux de l'ancien site, pour garder le référencement. Ils
 * ne sont pas écrits ici : chaque page lit le sien dans `contenuSite.CHEMINS`,
 * la seule source des adresses du site (règle 5).
 */
import { CHEMINS } from "./contenuSite";

export type CheminLegal = (typeof CHEMINS)[
  | "mentionsLegales"
  | "rgpd"
  | "cgv"
  | "confidentialite"];

export type BlocLegal =
  | { type: "paragraphe"; texte: string }
  | { type: "liste"; elements: string[] };

export type SectionLegale = {
  titre: string;
  /** 2 : article ou grande partie ; 3 : sous-partie de la section de niveau 2
   *  qui précède. Une section de niveau 2 sans bloc (« ANNEXES ») ne fait que
   *  coiffer les sections de niveau 3 qui la suivent. */
  niveau: 2 | 3;
  blocs: BlocLegal[];
};

export type PageLegale = {
  chemin: CheminLegal;
  titreOnglet: string;
  metaDescription: string;
  titre: string;
  /** Telle que la page l'écrit après « Date de dernière mise à jour : »,
   *  casse comprise ; `null` quand la page n'en donne pas. */
  dateDeMiseAJour: string | null;
  /** Ce que la page écrit entre son titre et sa première section. Vide quand
   *  la page commence directement par un titre de section. */
  introduction: BlocLegal[];
  sections: SectionLegale[];
};

export type PointAFaireValider = {
  page: CheminLegal | "toutes";
  /** Citation exacte du texte tel qu'il figure dans `PAGES_LEGALES`. */
  passage: string;
  pourquoi: string;
};

function p(texte: string): BlocLegal {
  return { type: "paragraphe", texte };
}

function liste(elements: string[]): BlocLegal {
  return { type: "liste", elements };
}

// ── /mentions-legales ───────────────────────────────────────────────────────

const MENTIONS_LEGALES: PageLegale = {
  chemin: CHEMINS.mentionsLegales,
  titreOnglet: "Mentions légales – EVKHA Business & Formations",
  metaDescription:
    "Toutes les informations légales concernant EVKHA : identité de l’éditeur, statut juridique, hébergeur, propriété intellectuelle, RGPD et cookies.",
  titre: "Mentions Légales",
  dateDeMiseAJour: "28 AVRIL 2026",
  introduction: [],
  sections: [
    {
      titre: "Article 1 : Mentions légales",
      niveau: 2,
      blocs: [
        p(
          "Le site internet www.evkha.fr est édité par KHAILI EVANGELINE, sous le nom commercial EVKHA BUSINESS & FORMATIONS, entrepreneur individuel inscrit au registre du commerce et des sociétés sous le numéro 751 737 610 R.C.S. Lille Métropole.",
        ),
        p("Nom de l’entreprise : EVKHA BUSINESS & FORMATIONS"),
        p("SIRET (siège) : 751 737 610 00020"),
        p("Forme juridique : Entrepreneur individuel"),
        p("Numéro de TVA : FR90751737610"),
        p("Adresse du siège social : 41 rue Jacquemars Giélée, 59800 Lille, France"),
        p("Contact : contact@evkha.fr"),
        p(
          "Le directeur de la publication du Site est Evangeline Khaili. Le Site est hébergé par IONOS SARL, dont le siège social est situé 7, place de la Gare - BP 70109, 57201 Sarreguemines, France.",
        ),
        p("Numero NDA, organisme de formation: 32591302259"),
      ],
    },
    {
      titre: "1 bis. Prestations sur devis et contenu non disponible à la vente en ligne",
      niveau: 3,
      blocs: [
        p(
          "Certaines prestations proposées par EVKHA BUSINESS & FORMATIONS ne sont pas directement achetables en ligne (par exemple : études de marché personnalisées, packs de création d’entreprise, accompagnements spécifiques). Ces services font l’objet de devis personnalisés.",
        ),
        p(
          "Toute commande de ce type n’est considérée comme ferme qu’à réception d’un acompte de 50 %, le solde étant dû à la livraison. Ces conditions sont détaillées dans les Conditions Générales de Vente disponibles sur le Site",
        ),
      ],
    },
    {
      titre: "Article 2 : Conditions générales d’utilisation",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "2.1 Champ d'application et objet",
      niveau: 3,
      blocs: [
        p(
          "L’accès au Site et son utilisation sont régis par les présentes conditions générales d’utilisation (les « CGU »). En accédant ou en naviguant sur le Site, l’Utilisateur accepte les présentes CGU, consultables à tout moment. Les CGU en vigueur sont celles affichées au moment de la navigation sur le Site.",
        ),
        p(
          "EVKHA BUSINESS & FORMATIONS s’efforce de garantir l’exactitude des informations publiées, mais se réserve le droit de modifier le Site et les CGU à tout moment. Toute utilisation après la publication des modifications implique l’acceptation des nouvelles CGU.",
        ),
      ],
    },
    {
      titre: "2.2 Propriété intellectuelle",
      niveau: 3,
      blocs: [
        p(
          "Les marques, éléments textuels, visuels et graphiques présents sur le Site sont la propriété exclusive d’EVKHA BUSINESS & FORMATIONS ou sous licence. Toute reproduction, représentation ou utilisation, sous quelque forme que ce soit, sans autorisation préalable, est strictement interdite.",
        ),
        p(
          "EVKHA accorde aux Utilisateurs un droit limité d’accès et d’utilisation du Site pour des fins personnelles et non commerciales, sous réserve du respect des présentes CGU.",
        ),
      ],
    },
    {
      titre: "2.3 Responsabilité",
      niveau: 3,
      blocs: [
        p(
          "Le Site est fourni \"en l’état\" et EVKHA BUSINESS & FORMATIONS ne garantit pas son accès ininterrompu ou exempt d’erreurs. Toute utilisation du Site se fait sous la seule responsabilité de l'Utilisateur, qui est tenu de protéger ses équipements contre les virus et intrusions éventuelles.",
        ),
        p(
          "EVKHA décline toute responsabilité pour des dommages résultant de l’utilisation du Site ou de l’internet.",
        ),
        p(
          "Les informations, outils, ressources et livrables proposés par EVKHA BUSINESS & FORMATIONS ne sauraient être interprétés comme des garanties de résultat. L’Utilisateur ou le Client reste seul responsable de l’utilisation qu’il fait des informations fournies.",
        ),
      ],
    },
    {
      titre: "2.4 Données personnelles et cookies",
      niveau: 3,
      blocs: [
        p(
          "Le Site utilise des cookies afin d’améliorer l’expérience utilisateur. Les Utilisateurs sont invités à consulter la Politique de confidentialité et de cookies d’EVKHA pour en savoir plus.",
        ),
        p(
          "Le traitement des données personnelles collectées via le Site est réalisé conformément au Règlement Général sur la Protection des Données (RGPD). Pour plus de détails, les Utilisateurs sont invités à consulter la Politique de confidentialité accessible depuis le pied de page du Site.",
        ),
      ],
    },
    {
      titre: "Article 3 : Lien vers des sites tiers",
      niveau: 2,
      blocs: [
        p(
          "EVKHA ne contrôle pas les sites externes vers lesquels des liens peuvent être fournis. Elle décline toute responsabilité quant à leur contenu, produits ou services.",
        ),
      ],
    },
    {
      titre: "Article 4 : Droit applicable",
      niveau: 2,
      blocs: [
        p(
          "Les présentes CGU sont régies par le droit français. Tout différend sera soumis à une tentative de résolution amiable, puis aux juridictions compétentes en cas d’échec.",
        ),
      ],
    },
  ],
};

// ── /rgpd ───────────────────────────────────────────────────────────────────

const RGPD: PageLegale = {
  chemin: CHEMINS.rgpd,
  titreOnglet: "RGPD – EVKHA",
  metaDescription:
    "Découvre comment EVKHA collecte, utilise et protège tes données personnelles. Conformité RGPD, cookies, newsletter, formulaires : tout est transparent.",
  titre: "CHARTE SUR LE RESPECT DE LA VIE PRIVÉE",
  dateDeMiseAJour: "LE 28 AVRIL 2026",
  introduction: [
    p(
      "La présente charte sur le respect de la vie privée (la « Charte ») a pour objectif de formaliser notre engagement quant au respect de la vie privée des utilisateurs du site internet WWW.evkha.fr (le « Site ») exploité par EVKHA BUSINESS & FORMATIONS, ENTREPRENEUR INDIVIDUEL SOUS LE SIRET 75173761000020.",
    ),
    p("Numero NDA, organisme de formation: 32591302259"),
    p(
      "La Charte et les Conditions Générales du Site forment un ensemble contractuel. Tous les termes en majuscules non-définis dans la présente Charte sont définis dans les Conditions Générales consultables SUR LE SITE www.evkha.fr.",
    ),
    p(
      "Dans le cadre de la mise à disposition de notre Site, nous traitons vos données à caractère personnel dans le respect du Règlement Général sur la Protection des Données 2016/679 du 27 avril 2016 (« RGPD ») et dans les conditions exposées ci- après.",
    ),
    p(
      "Une donnée à caractère personnel désigne toute information se rapportant à une personne physique identifiée ou identifiable. Nous collectons et traitons des données à caractère personnel dans le cadre de la fourniture de nos Services ou de la communication à propos de ces Services exclusivement, en stricte conformité avec le RGPD.",
    ),
    p(
      "Nous collectons uniquement des données à caractère personnel adéquates, pertinentes et limitées à ce qui est nécessaire au regard des finalités pour lesquelles elles sont traitées. Ainsi, il ne vous sera jamais demandé de renseigner des données à caractère personnel considérées comme « sensibles », telles que vos origines raciales ou ethniques, vos opinions politiques, philosophiques ou religieuses.",
    ),
    p(
      "En vous enregistrant sur le Site, vous nous autorisez à traiter vos données à caractère personnel conformément à la Charte. Si vous refusez les termes de cette Charte, veuillez vous abstenir d’utiliser le Site ainsi que les Services.",
    ),
  ],
  sections: [
    {
      titre:
        "1. Dans quels cas collectons-nous vos données à caractère personnel et quelles données sont collectées ?",
      niveau: 2,
      blocs: [
        p(
          "Nous sommes susceptibles de recueillir et de conserver vos données à caractère personnel, notamment lorsque vous :",
        ),
        liste([
          "naviguez sur le Site",
          "Actions sur le Site ou Services entrainant la collecte de données à caractère personnel. Exemples : création de compte, paiement en ligne, demande de renseignements, de contacts etc.",
          "nous contactez.",
        ]),
        p(
          "Nous utilisons vos données à caractère personnel pour permettre la mise en œuvre et la gestion des Services du Site et répondre à vos demandes spécifiques. Nous utilisons également vos données à caractère personnel dans le but d'exploiter et d'améliorer nos Services, notre Site et notre démarche. Ces informations sont utilisées uniquement par nos soins et nous permettent de mieux adapter nos Services à vos attentes.",
        ),
        p(
          "Si vous avez décidé de recevoir des courriels et messages de notre part lors de la création de votre Compte, vous recevrez alors des messages électroniques et alphanumériques portant sur nos produits et promotions. Nous utiliserons alors les données à caractère personnel que vous avez fournies lors de votre enregistrement. Vous pouvez vous désabonner de ces envois à tout moment.",
        ),
      ],
    },
    {
      titre: "1.1 Navigation sur le Site",
      niveau: 3,
      blocs: [
        p(
          "Données de connexion. À chaque fois que vous vous connectez à notre Site, nous recueillons des données à caractère personnel telles que, notamment, votre adresse IP et l’adresse MAC de votre ordinateur, la date et l'heure de connexion, ainsi que des informations sur le navigateur que vous utilisez.",
        ),
        p(
          "Données de navigation. Nous recueillons également les informations permettant d'identifier de quelle façon vous accédez au Site, quelles sont les pages consultées et pendant combien de temps. Dans ce cadre, nous pouvons avoir recours à l'utilisation de Cookies tel que précisé au paragraphe 6 ci-dessous.",
        ),
      ],
    },
    {
      titre: "1.2 Création d’un Compte",
      niveau: 3,
      blocs: [
        p(
          "L’accès à certains de nos Services nécessitent la création préalable d’un Compte. Conformément aux Conditions Générales, il vous sera demandé de renseigner un certain nombre de données à caractère personnel lors de la création de votre Compte, notamment vos noms et prénoms, votre adresse postale, votre adresse email et votre numéro de téléphone.",
        ),
      ],
    },
    {
      titre: "1.3 Paiement",
      niveau: 3,
      blocs: [
        p(
          "Certains des Services disponibles sont payants. A cette fin, vous acceptez que nous puissions avoir recours à des prestataires de services externes qui peuvent collecter des données à caractère personnel dans le but de permettre le bon fonctionnement des services de traitement des paiements par carte de crédit ou tout autre moyen de paiement et, le cas échéant, de livraison de produits ou services.",
        ),
        p(
          "Pour régler votre achat, vous devez fournir vos coordonnées de facturation ainsi que vos coordonnées de paiement, et notamment le numéro de votre carte bancaire, la date de validité, le code de sécurité et le nom du titulaire de la carte en cas de paiement par carte bancaire",
        ),
        p(
          "Il peut également vous être demandé de fournir le nom de votre opérateur télécom, le modèle de votre téléphone portable et un numéro de portable valide afin de pouvoir fournir les instructions d’achat directement à travers votre téléphone mobile.",
        ),
        p(
          "Nous conservons les détails de vos paiements, ainsi que les détails des achats que vous effectuez. Le détail des transactions est conservé soit dans nos systèmes soit chez le prestataire externe. Cette conservation est effectuée à des fins internes, notamment pour la comptabilité, la conformité et à des fins juridiques, conformément au paragraphe 5 de la présente Charte.",
        ),
      ],
    },
    {
      titre: "1.4 Adhésion à notre Newsletter",
      niveau: 3,
      blocs: [
        p(
          "Lors de la création de votre Compte, vous pouvez donner votre consentement préalable à la réception de nos lettres d’information concernant des actualités, des nouveaux produits, services et promotions, dans le cadre des Services.",
        ),
        p(
          "Vous pouvez également consentir directement à la réception de nos lettres d’information en renseignant votre adresse email aux endroits prévus à cet effet sur le Site.",
        ),
        p(
          "En tout état de cause, vous disposez du droit de retirer votre consentement à la réception de telles lettres d’information à tout moment et sans frais dans les conditions prévues au paragraphe 6 de la Charte.",
        ),
      ],
    },
    {
      titre: "1.5 Contacts",
      niveau: 3,
      blocs: [
        p(
          "Afin de donner suite aux demandes que vous pourriez effectuer auprès de notre Service Client et de confirmer les informations vous concernant, nous pourrons utiliser vos nom, prénom, adresse de courrier électronique et numéro de téléphone.",
        ),
      ],
    },
    {
      titre: "1.6 Données collectées dans le cadre de prestations personnalisées",
      niveau: 3,
      blocs: [
        p(
          "Dans le cadre des prestations sur mesure (études de marché, business plans, accompagnement personnalisé, packs de création…), EVKHA peut être amenée à collecter des informations confidentielles fournies volontairement par le Client (données financières, stratégiques, commerciales ou organisationnelles).",
        ),
        p(
          "Ces données ne sont utilisées que dans le cadre strict de la réalisation de la mission commandée. Elles sont hébergées de manière sécurisée, ne sont jamais partagées à des fins commerciales",
        ),
        p("Voici les durées de conservation:"),
        liste([
          "documents générés : 12 mois ;",
          "données clients administratives : 3 ans ;",
          "sauvegardes techniques : durée limitée de 12 mois .sauf demande contraire du Client ou obligation légale.",
        ]),
        p(
          "EVKHA s’engage à garantir la confidentialité absolue de ces informations, dans le respect du RGPD, de la présente Charte, et des CGV.",
        ),
      ],
    },
    {
      titre: "2. Comment protégeons-nous vos données à caractère personnel ?",
      niveau: 2,
      blocs: [
        p(
          "Nous avons mis en place des mesures de sécurité techniques et organisationnelles en vue de garantir la sécurité, l’intégrité et la confidentialité de toutes vos données à caractère personnel, afin d’empêcher que celles-ci soient déformées, endommagées ou que des tiers non autorisés y aient accès. Nous assurons un niveau de sécurité approprié, compte tenu de l'état des connaissances, des coûts de mise en œuvre et de la nature, de la portée, du contexte et des finalités du traitement ainsi que des risques et de leur probabilité.",
        ),
        p(
          "Toutefois, il est précisé qu’aucune mesure de sécurité n’étant infaillible, nous ne sommes pas en mesure de garantir une sécurité absolue à vos données à caractère personnel.",
        ),
        p(
          "Par ailleurs, il vous incombe d'assurer la confidentialité du mot de passe vous permettant d’accéder à votre Compte. Ne communiquez cette information à personne. Si vous partagez votre ordinateur, n'oubliez pas de vous déconnecter avant de quitter un Service.",
        ),
        p(
          "Les données échangées dans le cadre de prestations confidentielles (études personnalisées, stratégie, analyse concurrentielle, etc.) sont stockées sur des serveurs sécurisés et ne sont accessibles qu’aux membres autorisés de l’équipe EVKHA.",
        ),
      ],
    },
    {
      titre: "3. Dans quels cas partageons-nous vos données à caractère personnel ?",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "3.1 Partage de vos données personnelles avec des sociétés tierces",
      niveau: 3,
      blocs: [
        p(
          "Lors de votre navigation sur le Site, vos données à caractère personnel peuvent être transmises à des prestataires extérieurs. Ces tiers assurent un service pour notre compte et en notre nom dans le but de permettre le bon fonctionnement des paiements par carte de crédit et autres Services.",
        ),
        p(
          "Nous ne partagerons jamais, sans avoir obtenu votre consentement préalable, vos données à caractère personnel avec des sociétés tierces à des fins marketings et/ou commerciales.",
        ),
      ],
    },
    {
      titre: "3.2 Partage avec les autorités",
      niveau: 3,
      blocs: [
        p(
          "Nous pouvons être amené à divulguer vos données à caractère personnel aux autorités administrative ou judiciaire lorsque leur divulgation est nécessaire à l'identification, l'interpellation ou la poursuite en justice de tout individu susceptible de porter préjudice à nos droits, de tout autre utilisateur ou d’un tiers. Nous pouvons enfin être légalement tenu de divulguer vos données à caractère personnel et ne pouvons dans ce cas nous y opposer.",
        ),
      ],
    },
    {
      titre: "4. Combien de temps conservons-nous vos données à caractère personnel ?",
      niveau: 2,
      blocs: [
        p(
          "Nous ne conserverons vos données à caractère personnel que le temps de votre inscription sur le Site afin d'assurer votre identification lors de votre connexion à votre Compte et de permettre la fourniture des Services.",
        ),
        p(
          "Ainsi, si vous procédez à votre désinscription du Site, vos données à caractère personnel seront effacées et uniquement conservées sous forme d’archive aux fins d’établissement de la preuve d’un droit ou d’un contrat.",
        ),
        p(
          "En tout état de cause, nous conserverons vos données à caractère personnel pendant une durée n'excédant pas celle nécessaire au regard des finalités pour lesquelles elles sont traitées conformément aux utilisations exposées dans la présente Charte et dans le respect des lois et règlements.",
        ),
      ],
    },
    {
      titre: "5. Cookies : comment les utilisons-nous ?",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "5.1 Qu’est-ce qu’un cookie ?",
      niveau: 3,
      blocs: [
        p(
          "Un cookie est un fichier texte susceptible d’être déposé dans un terminal lors de la consultation d’un service en ligne avec un logiciel de navigation. Un fichier cookie permet notamment à son émetteur, pendant sa durée de validité, de reconnaître le terminal concerné à chaque fois que ce terminal accède à un contenu numérique comportant des cookies du même émetteur.",
        ),
        p(
          "En tout état de cause, les cookies déposés sur votre terminal de navigation avec votre accord sont détruits 13 mois après leur dépôt sur votre terminal.",
        ),
      ],
    },
    {
      titre: "5.2 A quoi servent les cookies émis sur notre Site ?",
      niveau: 3,
      blocs: [
        p("Les cookies que nous émettons nous permettent :"),
        liste([
          "d'établir des statistiques et volumes de fréquentation et d'utilisation des divers éléments composant notre Site (rubriques et contenus visités, parcours), nous permettant d'améliorer l'intérêt et l'ergonomie du Site et, le cas échéant, de nos produits et services ;",
          "d'adapter la présentation de notre Site aux préférences d'affichage de votre terminal (langue utilisée, résolution d'affichage, système d'exploitation utilisé, etc.) lors de vos visites sur notre Site, selon les matériels et les logiciels de visualisation ou de lecture que votre terminal comporte ;",
          "de mémoriser des informations relatives à un formulaire que vous avez rempli sur notre Site (inscription ou accès à votre compte) ou à des produits, services ou informations que vous avez choisis sur notre Site (service souscrit, contenu d'un panier de commande, etc.) ;",
          "de vous permettre d'accéder à des espaces réservés et personnels de notre Site, tels que votre Compte, grâce à des identifiants ou des données que vous nous avez éventuellement antérieurement confiées et de mettre en œuvre des mesures de sécurité, par exemple lorsqu’il vous est demandé de vous connecter à nouveau à un contenu ou à un service après une certain laps de temps.",
        ]),
        p(
          "Lors de votre navigation sur le Site, des cookies des réseaux sociaux peuvent être générés notamment par l’intermédiaire des boutons de partage qui collectent des données à caractère personnel.",
        ),
        p(
          "Lors de votre première visite sur le Site, un bandeau cookies apparaîtra en page d’accueil. Un lien cliquable permet d’en savoir plus sur la finalité et le fonctionnement des cookies et renvoie vers la présente Charte. La poursuite de la navigation sur une autre page du site ou la sélection d’un élément du Site (notamment : image, texte, lien, etc.) matérialise votre acceptation au dépôt des cookies visés sur votre ordinateur.",
        ),
      ],
    },
    {
      titre: "5.3 Comment pouvez-vous contrôler les cookies utilisés ?",
      niveau: 3,
      blocs: [
        p(
          "Vous pouvez à tout moment configurer votre logiciel de navigation de manière à ce que des cookies soient enregistrés dans votre terminal ou, au contraire, qu'ils soient rejetés (soit systématiquement, soit selon leur émetteur). Vous pouvez également configurer votre logiciel de navigation de manière à ce que l'acceptation ou le refus des cookies vous soit proposé ponctuellement, avant qu'un cookie puisse être enregistré dans votre terminal.",
        ),
        p(
          "Attention: tout paramétrage est susceptible de modifier votre navigation sur Internet et vos conditions d'accès à certains services nécessitant l'utilisation de cookies. Nous déclinons toute responsabilité s’agissant des conséquences liées au fonctionnement dégradé de nos services résultant de l'impossibilité d'enregistrer ou de consulter les cookies nécessaires à leur fonctionnement et que vous auriez refusés ou supprimés. Tel serait le cas si vous tentiez d'accéder à nos contenus ou services qui nécessitent de vous identifier. Tel serait également le cas lorsque nous (ou nos prestataires) ne pourrions pas reconnaître, à des fins de compatibilité technique, le type de navigateur utilisé par votre terminal, ses paramètres de langue et d'affichage ou le pays depuis lequel votre terminal semble connecté à Internet.",
        ),
      ],
    },
    {
      titre: "5.4 Comment configurer votre logiciel de navigation ?",
      niveau: 3,
      blocs: [
        p(
          "Pour la gestion des cookies et de vos choix, la configuration de chaque navigateur est différente. Elle est décrite dans le menu d'aide de votre navigateur, qui vous permettra de savoir de quelle manière modifier vos souhaits en matière de cookies. Vous trouverez ci-dessous des informations concernant les principaux navigateurs.",
        ),
        p("Internet Explorer / Edge"),
        p(
          "Dans Internet Explorer, cliquez sur le bouton Outils, puis sur Options Internet. Sous l'onglet Général, sous Historique de navigation, cliquez sur Paramètres. Cliquez sur le bouton Afficher les fichiers.",
        ),
        p("Firefox"),
        liste([
          "Allez dans l'onglet Outils du navigateur puis sélectionnez le menu Options",
          "Dans la fenêtre qui s'affiche, choisissez Vie privée et cliquez sur Affichez les cookies",
        ]),
        p("Safari"),
        liste([
          "Accédez aux Paramètres via le menu du navigateur (Safari > Préférences)",
          "Cliquez sur Confidentialité.",
        ]),
        p("Google Chrome"),
        liste([
          "Accédez aux Paramètres via le bouton à droite de la barre d’URL ou via le menu du navigateur (Chrome > Préférences).",
          "Sélectionnez Paramètres Avancées",
          "Cliquez sur Paramètres du contenu puis sur Cookies.",
        ]),
        p(
          "Pour obtenir plus d’information sur les cookies, vous pouvez consulter le site internet de la CNIL.",
        ),
      ],
    },
    {
      titre: "6. Quels sont vos droits ?",
      niveau: 2,
      blocs: [
        p(
          "Vous êtes seuls à nous avoir communiqué les données en notre possession, par l’intermédiaire du Site. Vous disposez de droits sur vos données à caractère personnel. Conformément à la réglementation en matière de protection des données à caractère personnel, notamment les articles 15 à 22 du RGPD, et après avoir justifié de votre identité, vous avez le droit de nous demander l'accès aux données à caractère personnel vous concernant, la rectification ou l'effacement de celles-ci.",
        ),
        p(
          "En outre, dans les limites posées par la loi, vous disposez également du droit de vous opposer au traitement, de le limiter, de décider du sort postmortem de vos données, de retirer votre consentement à tout moment et du droit à la portabilité des données à caractère personnel fournies. Vous pouvez contactez nos Services afin d’exercer vos droits à l’adresse électronique suivante : contact@evkha.fr ou à l’adresse postale suivante : 41 rue jacquemars giélée 59800 Lille, en joignant à votre demande une copie d’un titre d’identité.",
        ),
        p(
          "Par ailleurs, vous pouvez à tout moment vous désabonner de notre newsletter en cliquant sur le lien qui permet le désabonnement en bas de chaque email. Vous pouvez également vous désabonner en envoyant un message à l’adresse suivante : contact@evkha.fr",
        ),
      ],
    },
    {
      titre: "7. Pouvons-nous modifier la Charte ?",
      niveau: 2,
      blocs: [
        p(
          "Nous nous réservons le droit de modifier la Charte à tout moment. Il est vous est donc recommandé de la consulter régulièrement. En cas de modification, nous publierons ces changements sur cette page et aux endroits que nous jugerons appropriés en fonction de l’objet et de l’importance des changements apportés.",
        ),
        p(
          "Votre utilisation du Site après toute modification signifie que vous acceptez ces modifications. Si vous n'acceptez pas certaines modifications substantielles apportées à la présente Charte, vous devez arrêter d'utiliser le Site.",
        ),
      ],
    },
    {
      titre: "ANNEXES",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "UTILISATION D'OUTILS D'INTELLIGENCE ARTIFICIELLE",
      niveau: 3,
      blocs: [
        p(
          "Dans le cadre de certaines prestations ou fonctionnalités proposées par EVKHA BUSINESS & FORMATIONS, des outils d'intelligence artificielle peuvent être utilisés afin d'assister la production de documents, l'analyse de données, la structuration d'informations ou la génération de contenus professionnels.",
        ),
        p(
          "Les informations transmises sont exclusivement utilisées dans le cadre de l'exécution des services demandés.",
        ),
        p(
          "Lorsque les fournisseurs concernés le permettent, EVKHA BUSINESS & FORMATIONS active les paramètres visant à limiter ou empêcher l'utilisation des données soumises à des fins d'entraînement, d'amélioration ou de réutilisation des modèles d'intelligence artificielle.",
        ),
        p("Les traitements réalisés sont limités aux finalités prévues par la relation contractuelle."),
        p(
          "EVKHA BUSINESS & FORMATIONS sélectionne des prestataires reconnus mettant en œuvre des mesures de sécurité adaptées à la protection des données traitées.",
        ),
        p(
          "Dans les paramètres techniques, EVKHA BUSINESS & FORMATIONS active les options visant à empêcher l'utilisation des données clients à des fins d'entraînement ou d'amélioration des modèles d'intelligence artificielle",
        ),
      ],
    },
    {
      titre: "DONNÉES CONFIDENTIELLES ET STRATÉGIQUES",
      niveau: 3,
      blocs: [
        p(
          "Dans le cadre de ses prestations, EVKHA BUSINESS & FORMATIONS peut être amenée à traiter des informations confidentielles ou stratégiques relatives aux projets, activités, innovations, données financières ou documents professionnels de ses clients.",
        ),
        p("Ces informations sont exclusivement utilisées pour la réalisation des prestations commandées."),
        p(
          "Aucune exploitation commerciale, revente, diffusion ou communication à des tiers non autorisés n'est réalisée.",
        ),
        p(
          "L'accès à ces données est strictement limité aux personnes habilitées à intervenir dans l'exécution des prestations concernées.",
        ),
      ],
    },
    {
      titre: "SOUS-TRAITANTS ET PRESTATAIRES TECHNIQUES",
      niveau: 3,
      blocs: [
        p(
          "Afin d'assurer le bon fonctionnement de ses services, EVKHA BUSINESS & FORMATIONS peut faire appel à des prestataires techniques agissant en qualité de sous-traitants au sens du Règlement Général sur la Protection des Données (RGPD).",
        ),
        p("Ces prestataires peuvent notamment intervenir pour :"),
        liste([
          "l'hébergement du site internet et des données ;",
          "la gestion des paiements en ligne ;",
          "l'envoi d'e-mails et de newsletters ;",
          "l'hébergement et l'exploitation de plateformes de formation ;",
          "l'automatisation de certains processus ;",
          "l'utilisation d'outils d'intelligence artificielle ;",
          "le stockage sécurisé des données.",
        ]),
        p(
          "À la date de mise à jour de la présente politique, les principaux prestataires utilisés peuvent notamment inclure :",
        ),
        liste([
          "Ionos (hébergement) ;",
          "Stripe (paiement sécurisé) ;",
          "Systeme.io (gestion marketing et tunnel de vente) ;",
          "fournisseurs d'intelligence artificielle tels qu'OpenAI, Anthropic ou équivalents ;",
          "solutions d'e-mailing et d'automatisation utilisées dans le cadre de l'activité.",
        ]),
        p(
          "EVKHA BUSINESS & FORMATIONS sélectionne des prestataires présentant des garanties raisonnables en matière de sécurité et de protection des données personnelles.",
        ),
      ],
    },
    {
      titre: "TRANSFERTS DE DONNÉES HORS DE L'UNION EUROPÉENNE",
      niveau: 3,
      blocs: [
        p(
          "Certains prestataires techniques utilisés par EVKHA BUSINESS & FORMATIONS peuvent être amenés à traiter ou héberger certaines données en dehors de l'Union Européenne.",
        ),
        p(
          "C'est notamment le cas de certains fournisseurs de services numériques, de solutions d'intelligence artificielle, d'hébergement cloud ou d'outils de communication internationaux.",
        ),
        p(
          "Lorsque de tels transferts sont susceptibles d'avoir lieu, EVKHA BUSINESS & FORMATIONS veille à sélectionner des prestataires mettant en œuvre des garanties appropriées conformément à la réglementation applicable en matière de protection des données.",
        ),
        p(
          "Les données ne sont transférées que dans la mesure nécessaire à l'exécution des services proposés et dans le respect des obligations légales applicables.",
        ),
      ],
    },
  ],
};

// ── /cgv ────────────────────────────────────────────────────────────────────

const CGV: PageLegale = {
  chemin: CHEMINS.cgv,
  titreOnglet: "Conditions Générales d’Utilisation et de Vente – EVKHA",
  metaDescription:
    "Consulte les conditions d’utilisation du site EVKHA.fr et les conditions générales de vente applicables à nos formations et prestations sur mesure.",
  titre: "CGV / CGU EVKHA",
  dateDeMiseAJour: null,
  introduction: [],
  sections: [
    {
      titre: "Préambule et définitions générales",
      niveau: 2,
      blocs: [
        p(
          "Les présentes Conditions Générales de Vente (CGV) sont proposées par EVKHA Business et Formations, entreprise immatriculée sous le SIREN 751 737 610, ayant pour activité la vente de formations en ligne et en présentiel, d’accompagnement personnalisé, et d’études de marché. Le siège social est situé au 41 rue Jacquemars giélée. Toute commande passée sur le site www.evkha.fr implique l’acceptation sans réserve des présentes CGV par le Client.",
        ),
        p("Numero NDA, organisme de formation: 32591302259"),
        p("Définitions :"),
        liste([
          "Société : EVKHA Business et Formations.",
          "Site : www.evkha.fr.",
          "Client : Toute personne physique ou morale commandant un service.",
          "CGV : Conditions Générales de Vente.",
          "CGU : Conditions Générales d’utilisation.",
          "Formation : Programme de formation en ligne ou en présentiel proposé par EVKHA.",
          "Accompagnement : Service personnalisé d'accompagnement entrepreneurial.",
        ]),
      ],
    },
    {
      titre: "Article 1. Objet des CGV",
      niveau: 2,
      blocs: [
        p(
          "Les présentes CGV définissent les conditions de vente des programmes de formation, de prestations de conseil et d’accompagnement, ainsi que des études de marché. Elles couvrent les modalités de passation de commande, de paiement, de livraison, et les droits des parties.",
        ),
      ],
    },
    {
      titre: "Article 2. Champ d'application",
      niveau: 2,
      blocs: [
        p(
          "Ces CGV s'appliquent à tous les produits et services achetés via le site www.evkha.fr, incluant :",
        ),
        liste([
          "Les formations en ligne et en présentiel sur la création d'entreprise et la gestion de projets.",
          "Les accompagnements personnalisés.",
          "Les études de marché clés en main ou sur mesure.",
          "Toutes autres prestations proposées et vendues par EVKHA Business & Formations",
        ]),
      ],
    },
    {
      titre: "Article 3. Inscription et réservation aux formations",
      niveau: 2,
      blocs: [
        p(
          "Le Client peut s’inscrire aux formations en ligne et en présentiel directement sur le site. Certaines formations sont accessibles toute l’année, tandis que d’autres sont organisées en sessions. Une fois le paiement validé, le Client reçoit un email de confirmation contenant les informations et accès nécessaires pour débuter la formation.",
        ),
        p(
          "Le Client atteste, par la présence, disposer d’un équipement électronique adéquat pour utiliser les services de la Société, à savoir : un ordinateur, une souris, une caméra, un microphone, des écouteurs, une connexion internet à haut débit, une application performante telle que Google Chrome et une carte bancaire active.",
        ),
        p("Modalités de commande :"),
        p(
          "1. Le Client sélectionne une formation sur le site et accède à une page de validation de commande.",
        ),
        p(
          "2. Le Client valide les CGV et procède au paiement sécurisé par carte bancaire ou virement.",
        ),
        p(
          "3. Un email de confirmation et les informations d’accès sont envoyés une fois le paiement validé.",
        ),
        p(
          "EVKHA se réserve le droit de refuser une inscription si le profil du Client ne correspond pas aux objectifs du programme.",
        ),
      ],
    },
    {
      titre: "Modalités de livraison",
      niveau: 3,
      blocs: [
        p(
          "Le Rapport sera réputé livré dès lors que le Client aura reçu son Login et son mot de passe pour accéder à son Espace client ou un courriel avec un lien internet vers le Rapport commandé.",
        ),
      ],
    },
    {
      titre: "ETUDES DE MARCHÉS:",
      niveau: 3,
      blocs: [
        p("Toute commande d'études se fait directement en ligne sur le site evkha.fr."),
        p("Les etudes et livrables personnalisés"),
        p(
          "Lors de l'achat et de la commande, le client est redirigé automatiquement vers un formulaire à compléter. Le livrable sera ensuite généré et envoyé par mail sous 24H maximum.",
        ),
        p("Les etudes clé en main"),
        p(
          "Lors de l'achat et de la commande, le client précise l'étude qu'il souhaite ( voir la liste des etudes immédiates disponibles indiquée sur le site evkha.fr) Le livrable sera ensuite envoyé par mail sous 24H maximum.",
        ),
      ],
    },
    {
      titre: "Article 4: Durée et accès aux programmes de formation",
      niveau: 2,
      blocs: [
        p(
          "Les Clients ont accès aux programmes et aux supports (écrits, vidéos, audio) pour une durée minimale de 24 mois. Cette durée correspond à la commercialisation active du programme par EVKHA et peut être prolongée. En cas de retrait anticipé, un préavis de 3 mois est accordé.",
        ),
        p(
          "L’accès aux formations débute dès validation du paiement. En cas de retard de paiement, les accès seront suspendus jusqu’à réception des fonds.",
        ),
      ],
    },
    {
      titre: "Article 5. Paiement et financement des formations",
      niveau: 2,
      blocs: [
        p(
          "Le tarif est indiqué sur le site au moment de la commande et comprend toutes les taxes applicables. Le prix s’entend TTC. Le paiement peut être effectué par carte bancaire ou virement, en une seule fois ou en plusieurs échéances selon les options disponibles.",
        ),
        p(
          "Le paiement échelonné engage le Client à régler la totalité des échéances. Tout impayé entraînera la suspension des accès à la formation, et le recouvrement des sommes dues pourra faire l'objet de poursuites judiciaires.",
        ),
        p(
          "Tout retard de paiement entraîne des pénalités calculées au taux légal majoré de 10 points de pourcentage, ainsi qu'une indemnité forfaitaire pour frais de recouvrement de 40\u00a0€ HT. En cas de défaut de paiement prolongé, EVKHA se réserve le droit de résilier la commande et d’engager des poursuites judiciaires.",
        ),
      ],
    },
    {
      titre:
        "Article 5 bis – Modalités de paiement pour les prestations sur devis ou personnalisées",
      niveau: 2,
      blocs: [
        p(
          "Pour toute commande ne faisant pas l’objet d’un achat direct en ligne sur www.evkha.fr (notamment les prestations sur devis), un acompte de 70 % du montant total TTC est exigé avant le démarrage de la mission.",
        ),
        p(
          "Le solde de 30 % est dû à la livraison des livrables définis dans le devis accepté par le Client.",
        ),
        p(
          "La commande n’est considérée comme ferme qu’à réception de l’acompte. En cas de non-paiement du solde à la date convenue, EVKHA se réserve le droit de suspendre la remise du livrable final et d'engager toute procédure de recouvrement nécessaire.",
        ),
      ],
    },
    {
      titre: "Article 6. Droit de rétractation",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "Contestations",
      niveau: 3,
      blocs: [
        p(
          "Le Client dispose d’un délai de 3 jours francs à compter de la date de réception du Rapport pour effectuer toutes réclamations relatives à un défaut de conformité entre le contenu du rapport et les stipulations du bon de commande.",
        ),
        p(
          "Les réclamations devront être adressées à EVKHA BUSINESS & FORMATIONS par courriel à l’adresse suivante : contact@evkha.fr",
        ),
        p("Passé ce délai, aucune réclamation ne pourra être prise en compte."),
        p(
          "Dans l’hypothèse où la contestation se révèle fondée, EVKHA fournira au Client, sans frais supplémentaire, un nouveau Rapport conforme à la demande du Client ou remboursera le Client.",
        ),
      ],
    },
    {
      titre: "Droit de retractation",
      niveau: 3,
      blocs: [
        p(
          "En vertu de l’article L221-28 du Code de la consommation, le droit de rétractation ne s’applique pas aux prestations de service numériques ou sur mesure, dont l'exécution commence dès la commande. Les formations en présentiel sont remboursables si l’annulation intervient au moins 7 jours avant la session. Les formations en ligne et études de marché livrées ne sont ni échangeables ni remboursables.",
        ),
        p(
          "FORMATIONS EN PRESENTIEL: Conformément à l'article L.221-18 du Code de la consommation, le Client dispose d'un délai de rétractation de 14 jours pour annuler sans frais sa commande de formation en présentiel, à condition que l'accès aux contenus ou aux préparatifs de la formation n'ait pas été activé ou utilisé avant la fin de ce délai. Dans le cas où l'accès aurait été utilisé avant l’expiration des 14 jours, le droit de rétractation sera considéré comme renoncé. Pour toute annulation intervenant après le délai de rétractation mais au moins 7 jours avant le début de la session, un remboursement de 50 % du montant de la formation sera effectué. Au-delà de ce délai de 7 jours, aucun remboursement ne sera accordé.",
        ),
        p(
          "ETUDES DE MARCHÉ et FORMATIONS EN LIGNE : Suivant l’article L. 221-28 du Code de la consommation, le droit de rétractation ne s’applique pas aux études de marché de EVKHA considérant qu’il s’agit des téléchargements en ligne d’un contenu numérique ou sur mesure et que l’utilisation du produit est commencé pendant le délai de rétractation ( l'exécution commence dès la commande). En prenant connaissance des Conditions Générales de Vente, le client renonce expressément à son droit de retractation sur ce produit.",
        ),
      ],
    },
    {
      titre: "Article 7. Propriété intellectuelle des supports de formation",
      niveau: 2,
      blocs: [
        p(
          "Les contenus et supports pédagogiques (écrits, vidéos, audios) sont protégés par le droit d’auteur et restent la propriété exclusive d’EVKHA. Ils sont destinés à un usage personnel, et toute reproduction, modification ou diffusion sans autorisation préalable est interdite.",
        ),
        p(
          "Chaque support de programme en ligne (papier, numérique, électronique, oral…) reste sous la propriété intellectuelle et le droit d’auteur de la Société. Cela concerne également les fiches synthèses et de travail données au Client par la Société.",
        ),
        p(
          "Le Client s’engage à ne pas utiliser, transmettre ou reproduire tout ou partie de ces documents en vue de l’organisation ou de l’animation de séances de formation.",
        ),
        p(
          "Il est strictement interdit au Client de procéder au don ou à la revente des supports écrits, oraux ou vidéos délivrés par la Société, sous peine de poursuites judiciaires. Dans le cas contraire, et dès le premier incident, le Client s’expose également à un bannissement du programme sans remboursement.",
        ),
        p(
          "Il est strictement interdit au Client, pendant deux ans à compter de la date de fin du programme, de réaliser une activité concurrente à la Société, et de créer une offre similaire à ce(s) programme(s), après sa participation, sans son autorisation préalable écrite. Le Client reconnaît que la violation de cette clause engendrera des poursuites judiciaires et un bannissement du programme sans remboursement.",
        ),
        p(
          "Sous réserve du respect des présentes CGV / CGU, la Société accorde aux Utilisateurs un droit personnel, non-exclusif et non-transférable d’accès et d’utilisation du Site, du Contenu et/ou des Marques uniquement pour l’utilisation personnelle et privée des Utilisateurs et à des fins non commerciales. Par voie de conséquence, il est strictement interdit de :",
        ),
        liste([
          "copier, reproduire, représenter/afficher, diffuser, distribuer et/ou publier, de façon définitive ou provisoire, tout ou partie du Site et/ou du Contenu et/ou des Marques par tout moyen ou procédé (notamment, le caching, le framing, etc.) et ce, sur tout support connu ou inconnu à ce jour ;",
          "créer des œuvres dérivées à partir du Site et/ou du Contenu et/ou des Marques ;",
          "modifier, traduire, adapter ou transformer tout ou partie du Site et/ou du Contenu et/ou des Marques ;",
          "désassembler ou décompiler le Site et/ou le Contenu ou procéder à leur ingénierie inverse ;",
          "distribuer, transmettre, transférer, diffuser, vendre, louer, concéder sous licence ou exploiter, de quelque manière que ce soit, tout ou partie du Site et/ou du Contenu et/ou des Marques.",
        ]),
      ],
    },
    {
      titre: "Article 8. Confidentialité et discrétion",
      niveau: 2,
      blocs: [
        p(
          "EVKHA s’engage à maintenir la confidentialité des informations échangées dans le cadre de ses missions.",
        ),
        p(
          "À noter, qu'une étude commandée sur un thème pourra être réutilisée pour la vendre en tant qu'etude clé en main. Celle ci sera modifiée de manière à généraliser le thème. Aucune allusion aux caracteristiques d'un client ou à la localisation, aucune information quelle qu'elle soit concernant le client ne sera utilisée ou affichée dans l'etude remaniée puis vendue en tant qu'étude \"clé en main\". Une étude personnalisée, reste et restera personnalisée pour le client acheteur et confidentielle. Seuls les éléments généraux liés à l'étude seront réutilisés.",
        ),
        p(
          "De son côté, le Client s’engage à respecter la confidentialité des contenus pédagogiques et des échanges. Toute violation de cette clause peut entraîner des poursuites judiciaires.",
        ),
      ],
    },
    {
      titre: "Article 9. Responsabilité",
      niveau: 2,
      blocs: [
        p(
          "EVKHA met en œuvre les moyens nécessaires pour garantir la qualité des services, mais ne saurait être tenue responsable des résultats obtenus par le Client. EVKHA n'est tenue qu’à une obligation de moyens dans le cadre de ses prestations, et décline toute responsabilité en cas de pertes financières directes ou indirectes suite à l'utilisation des formations ou études de marché.",
        ),
      ],
    },
    {
      titre: "Article 10 : Utilisation des sources et références externes",
      niveau: 2,
      blocs: [
        p(
          "Dans le cadre de ses études de marché, EVKHA Business et Formations utilise et cite des sources publiques et privées (rapports, études sectorielles, bases de données, articles, etc.) afin de fournir une analyse rigoureuse et actualisée. Ces sources sont sélectionnées et évaluées pour leur fiabilité et leur pertinence vis-à-vis des objectifs de chaque étude.",
        ),
      ],
    },
    {
      titre: "10.1 Nature et transparence des sources utilisées",
      niveau: 3,
      blocs: [
        p(
          "Les informations externes, telles que les statistiques, rapports d’organisations, publications académiques et données d’instituts de recherche, sont mentionnées dans les études de marché pour appuyer les conclusions de l’analyse. EVKHA s'engage à indiquer, autant que possible, les références complètes pour chaque source utilisée afin de garantir la transparence.",
        ),
      ],
    },
    {
      titre: "10.2 Responsabilité et droits des tiers",
      niveau: 3,
      blocs: [
        p(
          "Les sources externes citées dans les études de marché sont protégées par le droit d’auteur et restent la propriété de leurs éditeurs respectifs. EVKHA ne peut garantir l'exactitude ou l’exhaustivité de ces informations tierces, bien que leur sélection repose sur des critères de fiabilité et de pertinence. Les clients reconnaissent que l’usage de ces informations se fait sous leur propre responsabilité.",
        ),
        p(
          "En fournissant des liens vers ces Sites Internet Tiers, la Société n’approuve pas le contenu de ces Sites Internet Tiers, ne s’y associe pas et ne fait aucune déclaration le concernant. Par ailleurs, ces liens ne sauraient indiquer une quelconque association entre la Société et les propriétaires et/ou auteurs, concepteurs, responsables, administrateurs ou hébergeurs de ces Sites Internet Tiers. Ces liens sont fournis uniquement à titre informatif et vous reconnaissez que vous êtes seul responsable de toute décision de votre part d’activer les liens vers ces Sites Internet Tiers. La Société décline également toute responsabilité en cas de dommages ou de pertes avérés ou présumés en lien avec, ou découlant de, votre utilisation du contenu, des produits et des services disponibles sur ces Sites Internet Tiers, ou de la confiance que vous avez placée en eux.",
        ),
      ],
    },
    {
      titre: "10.3 Utilisation des sources par le Client",
      niveau: 3,
      blocs: [
        p(
          "Les études de marché fournies sont destinées à un usage interne, et la diffusion des informations, y compris des sources citées, est restreinte aux besoins du Client. Toute reproduction ou diffusion au-delà de l’usage strictement privé peut nécessiter des autorisations spécifiques de la part des détenteurs de droits de propriété intellectuelle des sources.",
        ),
      ],
    },
    {
      titre: "Article 11. Médiation et litiges",
      niveau: 2,
      blocs: [
        p(
          "En cas de litige, le Client peut recourir au médiateur désigné : Société Médiation Professionnelle - Alteritae",
        ),
        p("5, rue Salvaing 12000 Rodez"),
      ],
    },
    {
      titre: "Conditions Générales d'Utilisation (CGU) - EVKHA Business et Formations",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "Préambule",
      niveau: 3,
      blocs: [
        p(
          "Les présentes Conditions Générales d'Utilisation (CGU) régissent l’utilisation du site www.evkha.fr. Elles définissent les droits et obligations des utilisateurs et les conditions d’accès aux services proposés par EVKHA, notamment les formations et les études de marché.",
        ),
      ],
    },
    {
      titre: "Article 1. Objet des CGU",
      niveau: 3,
      blocs: [
        p(
          "Ces CGU définissent les modalités d'accès au site www.evkha.fr et d’utilisation des services proposés. Tout utilisateur naviguant ou effectuant une commande sur le site accepte les présentes CGU.",
        ),
      ],
    },
    {
      titre: "Article 2. Accès aux services",
      niveau: 3,
      blocs: [
        p(
          "Le site est accessible 24h/24 et 7j/7, sous réserve des interruptions de maintenance. Certains services (formations, accompagnement) sont réservés aux clients inscrits.",
        ),
      ],
    },
    {
      titre: "Article 3. Propriété intellectuelle",
      niveau: 3,
      blocs: [
        p(
          "Tous les contenus du site (textes, images, vidéos, audios) sont protégés par le droit d’auteur et sont la propriété d’EVKHA. Aucun contenu ne peut être reproduit, distribué ou commercialisé sans l’autorisation préalable écrite d’EVKHA.",
        ),
      ],
    },
    {
      titre: "Article 3-2 : Utilisation des sources et données externes sur le site",
      niveau: 3,
      blocs: [
        p(
          "Dans le cadre des études de marché publiées ou réalisées pour ses clients, EVKHA Business et Formations se réserve le droit de citer des sources externes pour fournir des analyses approfondies et informées. Les données et contenus issus de tiers (publications, statistiques, rapports) sont utilisés sous réserve du respect des droits d’auteur et sont indiqués comme tels dans les documents remis aux clients.",
        ),
      ],
    },
    {
      titre: "3.2. a Responsabilité des informations tierces",
      niveau: 3,
      blocs: [
        p(
          "Les informations provenant de sources externes ne sont garanties ni en termes d'exactitude, ni d'exhaustivité. EVKHA sélectionne cependant les sources avec soin pour assurer la qualité des études de marché. EVKHA ne pourra être tenue responsable des dommages directs ou indirects résultant de l’utilisation des informations tierces.",
        ),
      ],
    },
    {
      titre: "3.2 .b Droits et limites d’utilisation",
      niveau: 3,
      blocs: [
        p(
          "Les sources citées dans les études de marché sont destinées exclusivement à l'usage interne du Client. Toute reproduction, distribution ou exploitation commerciale des contenus, y compris des sources, est interdite sans autorisation expresse des titulaires des droits.",
        ),
      ],
    },
    {
      titre: "Article 4. Durée de l'accès aux programmes",
      niveau: 3,
      blocs: [
        p(
          "Les formations en ligne sont accessibles pendant toute leur période de commercialisation active. En cas de cessation de commercialisation, un préavis de 3 mois est accordé pour permettre aux clients de finaliser leur apprentissage.",
        ),
      ],
    },
    {
      titre: "Article 5. Responsabilité de l’utilisateur",
      niveau: 3,
      blocs: [
        p(
          "L’utilisateur s’engage à utiliser le site de manière légale et respectueuse. Toute tentative de piratage ou d’utilisation abusive entraînera l'exclusion de l’utilisateur du site et pourra faire l’objet de poursuites.",
        ),
      ],
    },
    {
      titre: "Article 6. Données personnelles",
      niveau: 3,
      blocs: [
        p(
          "EVKHA collecte et traite les données personnelles conformément au RGPD. Les utilisateurs disposent d’un droit d'accès, de rectification et de suppression de leurs données. La politique de confidentialité est accessible sur www.evkha.fr.",
        ),
      ],
    },
    {
      titre: "Article 7. Modification des CGU",
      niveau: 3,
      blocs: [
        p(
          "EVKHA se réserve le droit de modifier les présentes CGU. Les modifications seront notifiées aux utilisateurs par email ou via une annonce sur le site, et prendront effet immédiatement pour les nouvelles commandes.",
        ),
      ],
    },
    {
      titre: "ANNEXES",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "UTILISATION DES SERVICES NUMÉRIQUES ET DE L'INTELLIGENCE ARTIFICIELLE",
      niveau: 3,
      blocs: [
        p(
          "EVKHA BUSINESS & FORMATIONS propose des prestations de conseil, de formation, d'accompagnement entrepreneurial ainsi que des services numériques automatisés permettant notamment la génération de livrables, études de marché, analyses concurrentielles, business plans, prévisionnels financiers, stratégies d'entreprise, synthèses ou tout autre document professionnel.",
        ),
        p(
          "Dans ce cadre, EVKHA BUSINESS & FORMATIONS peut recourir à des outils d'intelligence artificielle, d'automatisation, d'analyse de données, de traitement documentaire ou de génération assistée.",
        ),
        p(
          "Ces outils constituent exclusivement une assistance technique destinée à optimiser la qualité, la rapidité et la structuration des livrables.",
        ),
        p(
          "Le Client reconnaît que les contenus générés reposent notamment sur les informations fournies, les hypothèses renseignées, les données publiques disponibles et les modèles d'analyse utilisés au moment de la génération.",
        ),
        p(
          "Les prestations fournies ne constituent en aucun cas un conseil juridique, fiscal, comptable, financier, bancaire ou réglementaire au sens des professions réglementées.",
        ),
        p(
          "Le Client demeure seul responsable de l'utilisation qu'il fait des livrables et informations remis.",
        ),
        p(
          "Dans les paramètres techniques, EVKHA BUSINESS & FORMATIONS active les options visant à empêcher l'utilisation des données clients à des fins d'entraînement ou d'amélioration des modèles d'intelligence artificielle",
        ),
      ],
    },
    {
      titre: "RESPONSABILITÉ DES INFORMATIONS FOURNIES PAR LE CLIENT",
      niveau: 3,
      blocs: [
        p(
          "Le Client garantit l'exactitude, la sincérité, la complétude et l'actualité des informations, données, hypothèses, documents et éléments transmis à EVKHA BUSINESS & FORMATIONS.",
        ),
        p(
          "Le Client demeure seul responsable des informations saisies dans les questionnaires, formulaires, espaces membres ou tout autre support mis à disposition.",
        ),
        p("EVKHA BUSINESS & FORMATIONS ne pourra être tenue responsable des conséquences résultant :"),
        liste([
          "d'informations erronées ;",
          "d'informations incomplètes ;",
          "d'informations obsolètes ;",
          "d'omissions volontaires ou involontaires ;",
          "d'estimations irréalistes fournies par le Client ;",
          "d'hypothèses de marché ou de chiffre d'affaires non fondées.",
        ]),
        p(
          "Le Client reconnaît que la qualité des livrables dépend directement de la qualité des informations fournies.",
        ),
        p(
          "Aucune responsabilité ne pourra être engagée à l'encontre d'EVKHA BUSINESS & FORMATIONS lorsque les résultats générés découlent directement des données communiquées par le Client.",
        ),
      ],
    },
    {
      titre: "CONFIDENTIALITÉ, PROTECTION DES DONNÉES ET CONSERVATION DES DOCUMENTS",
      niveau: 3,
      blocs: [
        p(
          "EVKHA BUSINESS & FORMATIONS s'engage à traiter comme strictement confidentiels l'ensemble des informations, documents, stratégies, données commerciales, données financières, informations techniques et éléments transmis par le Client.",
        ),
        p("Ces informations sont utilisées exclusivement pour l'exécution des prestations commandées."),
        p(
          "EVKHA BUSINESS & FORMATIONS ne revend, ne cède, ne loue et ne diffuse aucune donnée confidentielle appartenant au Client.",
        ),
        p(
          "Lorsque des outils tiers sont utilisés dans le cadre de l'exécution des prestations, EVKHA BUSINESS & FORMATIONS veille à sélectionner des prestataires offrant un niveau de sécurité raisonnablement adapté aux traitements réalisés.",
        ),
        p(
          "Lorsque les paramètres techniques le permettent, les options visant à limiter l'utilisation des données à des fins d'entraînement ou d'amélioration des modèles d'intelligence artificielle sont activées.",
        ),
        p(
          "Sauf obligation légale contraire, les documents, données et informations transmis par le Client pourront être conservés pendant une durée maximale de douze (12) mois à compter de la fin de la prestation ou de la résiliation de l'abonnement.",
        ),
        p(
          "À l'issue de cette période, EVKHA BUSINESS & FORMATIONS pourra procéder à leur suppression définitive sans préavis.",
        ),
      ],
    },
    {
      titre: "CONDITIONS PARTICULIÈRES DES ABONNEMENTS",
      niveau: 3,
      blocs: [
        p(
          "Les abonnements proposés par EVKHA BUSINESS & FORMATIONS sont souscrits pour une durée minimale d'engagement de trois (3) mois à compter de leur activation.",
        ),
        p(
          "Pendant cette période minimale, aucune résiliation anticipée ne pourra donner lieu à remboursement des sommes restant dues.",
        ),
        p(
          "À l'issue de cette période initiale, l'abonnement est reconduit automatiquement par périodes successives d'un (1) mois sauf résiliation.",
        ),
        p(
          "Toute demande de résiliation doit être effectuée depuis l'espace client ou par courrier électronique au moins sept (7) jours avant la prochaine échéance de renouvellement.",
        ),
        p("Tout mois commencé demeure intégralement dû."),
        p(
          "Les crédits, quotas, générations ou droits d'utilisation inclus dans chaque formule sont strictement limités à la période d'abonnement concernée.",
        ),
        p(
          "Les crédits non utilisés ne sont ni remboursables, ni reportables, ni transférables vers une période ultérieure.",
        ),
        p(
          "La suspension ou l'arrêt volontaire de l'utilisation du service par le Client n'interrompt pas les prélèvements liés à la période d'engagement en cours.",
        ),
      ],
    },
    {
      titre: "LIMITATION DE RESPONSABILITÉ",
      niveau: 3,
      blocs: [
        p(
          "Les prestations, analyses, études, prévisionnels, stratégies, recommandations et livrables fournis par EVKHA BUSINESS & FORMATIONS constituent exclusivement des outils d'aide à la décision.",
        ),
        p(
          "Aucune garantie de succès commercial, de rentabilité, de chiffre d'affaires, d'obtention de financement, d'obtention de subvention, de validation bancaire, d'immatriculation, de développement commercial ou de réussite entrepreneuriale n'est accordée.",
        ),
        p(
          "EVKHA BUSINESS & FORMATIONS est tenue à une obligation de moyens et non à une obligation de résultat.",
        ),
        p(
          "La responsabilité d'EVKHA BUSINESS & FORMATIONS ne pourra être engagée pour tout dommage indirect, perte de chiffre d'affaires, perte d'exploitation, perte de clientèle, perte de données, perte d'opportunité, perte de marché ou manque à gagner.",
        ),
        p(
          "En toute hypothèse, et sauf faute lourde ou dolosive démontrée, le montant total de l'indemnisation susceptible d'être mise à la charge d'EVKHA BUSINESS & FORMATIONS ne pourra excéder le montant effectivement payé par le Client au titre de la prestation ou de l'abonnement concerné au cours des douze derniers mois.",
        ),
      ],
    },
    {
      titre: "UTILISATION AUTORISÉE DU SERVICE",
      niveau: 3,
      blocs: [
        p(
          "L'accès aux services proposés par EVKHA BUSINESS & FORMATIONS est strictement réservé au Client ayant souscrit l'abonnement ou la prestation.",
        ),
        p(
          "Le Client s'engage à utiliser les services de manière loyale, raisonnable et conforme à leur destination.",
        ),
        p("Sont notamment interdits :"),
        liste([
          "la revente, la location ou la sous-licence de l'accès à la plateforme ;",
          "la mise à disposition des identifiants à des tiers ;",
          "l'utilisation du service pour le compte de personnes non autorisées ;",
          "l'extraction massive ou automatisée des contenus générés ;",
          "la tentative de copie, reproduction ou rétro-ingénierie du système ;",
          "toute utilisation visant à contourner les limitations prévues par l'abonnement souscrit ;",
          "toute utilisation contraire aux lois et règlements en vigueur.",
        ]),
        p(
          "Le Client demeure seul responsable de l'utilisation qu'il fait des services mis à sa disposition.",
        ),
      ],
    },
    {
      titre: "UTILISATION ABUSIVE OU FRAUDULEUSE",
      niveau: 3,
      blocs: [
        p(
          "EVKHA BUSINESS & FORMATIONS se réserve le droit de surveiller l'utilisation générale des services afin d'assurer leur bon fonctionnement et la sécurité de l'ensemble des utilisateurs.",
        ),
        p("Constituent notamment des utilisations abusives :"),
        liste([
          "un volume anormalement élevé de générations de documents ;",
          "l'utilisation de robots ou scripts automatisés ;",
          "le partage d'un même compte entre plusieurs utilisateurs ;",
          "les tentatives de contournement des limitations techniques ou commerciales ;",
          "toute activité susceptible de compromettre la stabilité ou la sécurité du système.",
        ]),
        p(
          "En cas de suspicion raisonnable d'utilisation abusive ou frauduleuse, EVKHA BUSINESS & FORMATIONS pourra :",
        ),
        liste([
          "suspendre temporairement l'accès au service ;",
          "demander des justificatifs complémentaires ;",
          "limiter certaines fonctionnalités ;",
          "résilier l'abonnement sans préavis en cas de fraude avérée.",
        ]),
        p("Cette suspension ou résiliation n'ouvre droit à aucun remboursement."),
      ],
    },
    {
      titre: "PROPRIÉTÉ INTELLECTUELLE",
      niveau: 3,
      blocs: [
        p(
          "L'ensemble des éléments composant les services proposés par EVKHA BUSINESS & FORMATIONS demeure sa propriété exclusive.",
        ),
        p("Cela comprend notamment :"),
        liste([
          "la méthodologie EVKHA ;",
          "les questionnaires ;",
          "les structures de livrables ;",
          "les modèles d'analyse ;",
          "les bases documentaires ;",
          "les processus de traitement ;",
          "les contenus pédagogiques ;",
          "les systèmes automatisés ;",
          "les interfaces ;",
          "les éléments graphiques ;",
          "les textes ;",
          "les bases de données ;",
          "les prompts et instructions utilisés dans les systèmes d'intelligence artificielle.",
        ]),
        p(
          "Toute reproduction, adaptation, extraction, copie, diffusion ou exploitation non autorisée est strictement interdite.",
        ),
        p(
          "La souscription à un abonnement ou à une prestation n'emporte aucun transfert de propriété intellectuelle au profit du Client.",
        ),
      ],
    },
    {
      titre: "DISPONIBILITÉ DU SERVICE",
      niveau: 3,
      blocs: [
        p(
          "EVKHA BUSINESS & FORMATIONS s'efforce d'assurer l'accessibilité du service de manière continue.",
        ),
        p(
          "Toutefois, le Client reconnaît que le fonctionnement des services numériques peut être affecté par :",
        ),
        liste([
          "des opérations de maintenance ;",
          "des mises à jour ;",
          "des incidents techniques ;",
          "des défaillances de fournisseurs tiers ;",
          "des interruptions des réseaux de télécommunication ;",
          "des événements de force majeure.",
        ]),
        p("Aucune disponibilité permanente ne peut être garantie."),
        p(
          "Les interruptions temporaires ne peuvent donner lieu à aucun remboursement, indemnisation ou réparation sauf disposition légale contraire.",
        ),
      ],
    },
    {
      titre: "INTERVENTION DE PRESTATAIRES TIERS",
      niveau: 3,
      blocs: [
        p(
          "Le Client reconnaît que certains services proposés par EVKHA BUSINESS & FORMATIONS reposent sur des infrastructures, logiciels ou services exploités par des prestataires tiers.",
        ),
        p(
          "EVKHA BUSINESS & FORMATIONS ne saurait être tenue responsable des dysfonctionnements, interruptions, limitations ou modifications affectant les services de ces prestataires externes.",
        ),
        p(
          "Les obligations d'EVKHA BUSINESS & FORMATIONS demeurent limitées à sa propre sphère de contrôle.",
        ),
      ],
    },
  ],
};

// ── /politique-de-confidentialite ───────────────────────────────────────────

const POLITIQUE_DE_CONFIDENTIALITE: PageLegale = {
  chemin: CHEMINS.confidentialite,
  titreOnglet: "Politique de confidentialité – EVKHA",
  metaDescription:
    "EVKHA protège tes données : politique RGPD, cookies, newsletter et formulaires. Lis notre engagement en toute transparence.",
  titre: "Politique de confidentialité et de cookies d’EVKHA",
  dateDeMiseAJour: "28 octobre 2026",
  introduction: [
    p(
      "La présente politique de confidentialité décrit comment EVKHA BUSINESS & FORMATIONS, immatriculée sous le numéro 751 737 610 R.C.S. Lille Métropole, traite les informations personnelles collectées lorsque vous utilisez le site www.evkha.fr (le « Site »).",
    ),
    p("Numero NDA, organisme de formation: 32591302259"),
  ],
  sections: [
    {
      titre: "1. Responsable du traitement",
      niveau: 2,
      blocs: [
        p(
          "Le responsable de traitement des données personnelles collectées via le Site est KHAILI EVANGELINE, opérant sous le nom commercial EVKHA BUSINESS & FORMATIONS.",
        ),
        p(
          "Pour toute question relative à la collecte ou au traitement des données personnelles, contactez-nous à : contact@evkha.fr",
        ),
      ],
    },
    {
      titre: "2. Données collectées",
      niveau: 2,
      blocs: [
        p(
          "Les données personnelles que nous collectons dépendent de votre interaction avec le Site. Nous collectons principalement les informations suivantes :",
        ),
        liste([
          "Données d’identification : nom, adresse e-mail, numéro de téléphone.",
          "Données de connexion : adresse IP, type de navigateur, temps de visite et pages consultées.",
        ]),
      ],
    },
    {
      titre: "3. Finalités du traitement",
      niveau: 2,
      blocs: [
        p("Les données sont collectées pour les finalités suivantes :"),
        liste([
          "Gestion et suivi de la relation client, de la correspondance et des demandes d’information.",
          "Amélioration du Site et des services.",
          "Envoi de communications marketing, avec consentement préalable de l’Utilisateur.",
        ]),
      ],
    },
    {
      titre: "3 bis. Données collectées dans le cadre des prestations sur devis",
      niveau: 2,
      blocs: [
        p(
          "Dans le cadre des prestations personnalisées (études de marché, business plans, accompagnement), EVKHA peut être amenée à collecter des données professionnelles ou confidentielles fournies volontairement par le Client (éléments stratégiques, données financières, informations sur le projet ou l'entreprise).",
        ),
        p(
          "Ces informations ne sont utilisées que dans le cadre strict de la mission confiée et ne font l’objet d’aucune diffusion ou réutilisation sans autorisation écrite du Client. Elles sont traitées de manière confidentielle, conformément aux engagements de discrétion indiqués dans les CGV, et stockées de manière sécurisée pendant la durée nécessaire à l’exécution de la prestation.",
        ),
      ],
    },
    {
      titre: "4. Base légale du traitement",
      niveau: 2,
      blocs: [
        p("Le traitement des données est fondé sur :"),
        liste([
          "L’exécution du contrat : pour les utilisateurs ayant souscrit aux services proposés.",
          "Le consentement : pour l’envoi de newsletters ou de communications marketing.",
          "L’intérêt légitime : pour assurer le bon fonctionnement du Site.",
        ]),
      ],
    },
    {
      titre: "5. Conservation des données",
      niveau: 2,
      blocs: [
        p(
          "Les données personnelles sont conservées pendant une durée de 3 ans à compter de la dernière interaction, ou conformément aux exigences légales.",
        ),
      ],
    },
    {
      titre: "6. Droits des utilisateurs",
      niveau: 2,
      blocs: [
        p("Conformément au RGPD, les utilisateurs disposent des droits suivants :"),
        liste([
          "Accès et rectification : vous pouvez demander l’accès à vos données ou leur rectification si elles sont incorrectes.",
          "Effacement : droit à l’oubli de vos données personnelles sous certaines conditions.",
          "Limitation et opposition : vous pouvez limiter ou vous opposer au traitement de vos données.",
          "Portabilité : vous pouvez demander le transfert de vos données vers un autre responsable de traitement.",
        ]),
        p("Pour exercer ces droits, envoyez votre demande à : contact@evkha.fr"),
      ],
    },
    {
      titre: "7. Sécurité des données",
      niveau: 2,
      blocs: [
        p(
          "Nous mettons en œuvre des mesures de sécurité techniques et organisationnelles appropriées pour protéger vos données personnelles contre tout accès non autorisé, perte ou altération.",
        ),
      ],
    },
    {
      titre: "8. Utilisation des cookies",
      niveau: 2,
      blocs: [
        p(
          "Le Site utilise des cookies pour améliorer votre expérience de navigation et pour des finalités statistiques. Un cookie est un petit fichier texte enregistré sur votre appareil lors de la visite du Site. Types de cookies utilisés :",
        ),
        liste([
          "Cookies nécessaires : indispensables pour le bon fonctionnement du Site.",
          "Cookies analytiques : utilisés pour recueillir des informations statistiques sur l’utilisation du Site.",
          "Cookies de publicité : utilisés pour diffuser des publicités personnalisées.",
          "Gestion des cookies : Lors de votre première visite sur le Site, un bandeau de cookies apparaît pour vous informer de l’utilisation des cookies et obtenir votre consentement. Vous pouvez à tout moment modifier vos préférences via les paramètres de votre navigateur ou refuser l’utilisation de certains cookies.",
        ]),
      ],
    },
    {
      titre: "9. Modification de la politique de confidentialité",
      niveau: 2,
      blocs: [
        p(
          "EVKHA se réserve le droit de modifier cette politique à tout moment. Les utilisateurs seront informés de toute mise à jour via le Site.",
        ),
      ],
    },
    {
      titre: "10. Contact",
      niveau: 2,
      blocs: [p("Pour toute question sur cette politique, contactez-nous à contact@evkha.fr")],
    },
    {
      titre: "ANNEXES",
      niveau: 2,
      blocs: [],
    },
    {
      titre: "CATÉGORIES DE DONNÉES COLLECTÉES",
      niveau: 3,
      blocs: [
        p(
          "Selon les services utilisés, EVKHA BUSINESS & FORMATIONS peut être amenée à collecter les catégories de données suivantes :",
        ),
        liste([
          "données d'identification (nom, prénom, adresse e-mail, numéro de téléphone) ;",
          "données de facturation et de paiement ;",
          "informations relatives aux projets entrepreneuriaux ;",
          "informations professionnelles et commerciales ;",
          "données renseignées dans les questionnaires et formulaires ;",
          "documents transmis volontairement par les clients ;",
          "données de connexion et de navigation sur le site ;",
          "échanges réalisés avec le support client.",
        ]),
        p(
          "Les données collectées sont limitées à celles strictement nécessaires à l'exécution des services proposés.",
        ),
      ],
    },
    {
      titre: "FINALITÉS DES TRAITEMENTS",
      niveau: 3,
      blocs: [
        p("Les données personnelles collectées sont utilisées pour :"),
        liste([
          "répondre aux demandes de contact ;",
          "assurer l'exécution des prestations commandées ;",
          "générer les livrables demandés ;",
          "gérer les abonnements et les paiements ;",
          "assurer le suivi commercial et administratif ;",
          "fournir l'accès aux formations et espaces membres ;",
          "améliorer les services proposés ;",
          "assurer la sécurité et le bon fonctionnement des plateformes ;",
          "respecter les obligations légales et réglementaires applicables.",
        ]),
        p("Les données ne sont jamais revendues à des tiers à des fins commerciales."),
      ],
    },
    {
      titre: "TRAITEMENTS AUTOMATISÉS",
      niveau: 3,
      blocs: [
        p(
          "Certaines fonctionnalités proposées par EVKHA BUSINESS & FORMATIONS peuvent s'appuyer sur des processus automatisés ou des outils d'intelligence artificielle afin d'assister la production de documents, d'analyses ou de recommandations.",
        ),
        p(
          "Ces traitements ont pour objectif d'améliorer la rapidité et la qualité des services proposés.",
        ),
        p(
          "Aucune décision produisant des effets juridiques ou ayant un impact significatif sur la personne concernée n'est prise de manière exclusivement automatisée.",
        ),
        p(
          "Lorsque les paramètres techniques le permettent, EVKHA BUSINESS & FORMATIONS active les options visant à empêcher l'utilisation des données clients à des fins d'entraînement ou d'amélioration des modèles d'intelligence artificielle.",
        ),
      ],
    },
  ],
};

export const PAGES_LEGALES: PageLegale[] = [
  MENTIONS_LEGALES,
  RGPD,
  CGV,
  POLITIQUE_DE_CONFIDENTIALITE,
];

// ── À faire relire avant mise en ligne ──────────────────────────────────────

/** Ce qu'une juriste ou la cliente doit relire avant que ces textes soient
 *  servis par la nouvelle plateforme. Rien n'est tranché ici : chaque ligne
 *  signale un passage et dit pourquoi il mérite un regard. */
export const POINTS_A_FAIRE_VALIDER: PointAFaireValider[] = [
  // Hébergeur, éditeur, adresse du site
  {
    page: CHEMINS.mentionsLegales,
    passage:
      "Le Site est hébergé par IONOS SARL, dont le siège social est situé 7, place de la Gare - BP 70109, 57201 Sarreguemines, France.",
    pourquoi:
      "Mention de l'hébergeur : l'hébergement change avec la refonte (l'ancien site était servi par Systeme.io, que cette page ne cite pas). Faire confirmer le nom, la forme sociale et l'adresse de l'hébergeur réel de la nouvelle plateforme.",
  },
  {
    page: "toutes",
    passage: "www.evkha.fr",
    pourquoi:
      "Les quatre textes définissent « le Site » comme www.evkha.fr. La nouvelle plateforme répond aussi sous d'autres adresses (app2.evkha.fr, api2.evkha.fr) : faire préciser le périmètre couvert.",
  },
  {
    page: CHEMINS.rgpd,
    passage: "Systeme.io (gestion marketing et tunnel de vente) ;",
    pourquoi:
      "Sous-traitant de l'ancien site. À retirer ou à maintenir selon ce qui reste réellement chez Systeme.io après le basculement (formations, newsletter).",
  },
  {
    page: CHEMINS.rgpd,
    passage: "Ionos (hébergement) ;",
    pourquoi:
      "À rapprocher de l'hébergeur réel de la nouvelle plateforme et de la mention des mentions légales.",
  },
  {
    page: CHEMINS.rgpd,
    passage: "Stripe (paiement sécurisé) ;",
    pourquoi:
      "La nouvelle plateforme encaisse par Stripe : mention à confirmer, ainsi que l'absence de tout autre prestataire de paiement.",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "fournisseurs d'intelligence artificielle tels qu'OpenAI, Anthropic ou équivalents ;",
    pourquoi:
      "Liste à aligner sur les fournisseurs réellement appelés par la plateforme (et sur les éventuels services de recherche en ligne qu'elle utilise).",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "solutions d'e-mailing et d'automatisation utilisées dans le cadre de l'activité.",
    pourquoi:
      "Prestataire d'envoi d'e-mails non nommé. La nouvelle plateforme envoie ses propres courriels (livraison, compte, abonnement) : faire nommer le prestataire.",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "Certains prestataires techniques utilisés par EVKHA BUSINESS & FORMATIONS peuvent être amenés à traiter ou héberger certaines données en dehors de l'Union Européenne.",
    pourquoi:
      "À faire vérifier prestataire par prestataire (paiement, intelligence artificielle, e-mails) pour la nouvelle plateforme, avec les garanties correspondantes.",
  },

  // Vente en ligne, acompte, livraison
  {
    page: CHEMINS.mentionsLegales,
    passage:
      "Certaines prestations proposées par EVKHA BUSINESS & FORMATIONS ne sont pas directement achetables en ligne (par exemple : études de marché personnalisées, packs de création d’entreprise, accompagnements spécifiques). Ces services font l’objet de devis personnalisés.",
    pourquoi:
      "Faux aujourd'hui : les études et les packs s'achètent en ligne (point 7 du plan de refonte). Contredit aussi les CGV : « Toute commande d'études se fait directement en ligne sur le site evkha.fr. »",
  },
  {
    page: CHEMINS.mentionsLegales,
    passage:
      "Toute commande de ce type n’est considérée comme ferme qu’à réception d’un acompte de 50 %, le solde étant dû à la livraison.",
    pourquoi:
      "Contradiction avec les CGV, article 5 bis : « un acompte de 70 % du montant total TTC est exigé avant le démarrage de la mission » et « Le solde de 30 % ».",
  },
  {
    page: CHEMINS.confidentialite,
    passage: "3 bis. Données collectées dans le cadre des prestations sur devis",
    pourquoi:
      "Le titre parle de prestations « sur devis » alors que les études et business plans cités dans le paragraphe se commandent en ligne.",
  },
  {
    page: CHEMINS.cgv,
    passage: "Le livrable sera ensuite généré et envoyé par mail sous 24H maximum.",
    pourquoi:
      "Délai contractuel. Les autres pages du site écrivent tantôt « moins de 24 h », tantôt « 24 h ouvrées » (point 5 du plan de refonte) : faire trancher la formule qui engage.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Le Rapport sera réputé livré dès lors que le Client aura reçu son Login et son mot de passe pour accéder à son Espace client ou un courriel avec un lien internet vers le Rapport commandé.",
    pourquoi:
      "À rapprocher du mode de livraison réel de la nouvelle plateforme (espace client, lien, pièce jointe). Le terme « Rapport » n'est pas défini dans les définitions.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Lors de l'achat et de la commande, le client précise l'étude qu'il souhaite ( voir la liste des etudes immédiates disponibles indiquée sur le site evkha.fr) Le livrable sera ensuite envoyé par mail sous 24H maximum.",
    pourquoi:
      "Les études prêtes sont annoncées ailleurs en « téléchargement immédiat » ; ici, envoi sous 24 h. Parcours à aligner sur la boutique de la nouvelle plateforme.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Le paiement peut être effectué par carte bancaire ou virement, en une seule fois ou en plusieurs échéances selon les options disponibles.",
    pourquoi:
      "À confirmer pour la nouvelle plateforme : le virement et le paiement en plusieurs fois y sont-ils proposés ?",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Tout retard de paiement entraîne des pénalités calculées au taux légal majoré de 10 points de pourcentage, ainsi qu'une indemnité forfaitaire pour frais de recouvrement de 40\u00a0€ HT.",
    pourquoi:
      "Clause à faire relire : elle s'applique ici sans distinguer clients professionnels et particuliers.",
  },

  // Rétractation, réclamations, médiation
  {
    page: CHEMINS.cgv,
    passage:
      "Les formations en présentiel sont remboursables si l’annulation intervient au moins 7 jours avant la session.",
    pourquoi:
      "Contradiction dans le même article : le paragraphe suivant prévoit « un remboursement de 50 % du montant de la formation » pour une annulation au moins 7 jours avant la session.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "En prenant connaissance des Conditions Générales de Vente, le client renonce expressément à son droit de retractation sur ce produit.",
    pourquoi:
      "Renonciation au droit de rétractation et références aux articles L221-28 et L.221-18 du Code de la consommation : à faire valider par une juriste, ainsi que la façon dont la nouvelle plateforme recueille cette renonciation au moment du paiement.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Le Client dispose d’un délai de 3 jours francs à compter de la date de réception du Rapport pour effectuer toutes réclamations relatives à un défaut de conformité entre le contenu du rapport et les stipulations du bon de commande.",
    pourquoi:
      "Délai de réclamation à faire relire ; ce passage figure sous l'article intitulé « Droit de rétractation », dont il ne relève pas.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "En cas de litige, le Client peut recourir au médiateur désigné : Société Médiation Professionnelle - Alteritae",
    pourquoi:
      "Nom et adresse du médiateur (« 5, rue Salvaing 12000 Rodez ») à vérifier, de même que la validité actuelle de l'adhésion. L'article ne dit rien du tribunal compétent.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Il est strictement interdit au Client, pendant deux ans à compter de la date de fin du programme, de réaliser une activité concurrente à la Société, et de créer une offre similaire à ce(s) programme(s), après sa participation, sans son autorisation préalable écrite.",
    pourquoi: "Clause de non-concurrence imposée aux clients : à faire relire par une juriste.",
  },

  // Abonnements
  {
    page: CHEMINS.cgv,
    passage:
      "Toute demande de résiliation doit être effectuée depuis l'espace client ou par courrier électronique au moins sept (7) jours avant la prochaine échéance de renouvellement.",
    pourquoi:
      "La nouvelle plateforme annonce un arrêt « sur simple demande », par e-mail, et non depuis l'espace client (`espace/engagement.ts`). Le préavis de sept jours n'y est pas repris. À aligner dans un sens ou dans l'autre.",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Les crédits non utilisés ne sont ni remboursables, ni reportables, ni transférables vers une période ultérieure.",
    pourquoi:
      "À rapprocher des règles de crédits réellement appliquées par la nouvelle plateforme (crédits supplémentaires, recharges, changement de formule).",
  },

  // Durées de conservation : quatre réponses différentes
  {
    page: CHEMINS.rgpd,
    passage:
      "sauvegardes techniques : durée limitée de 12 mois .sauf demande contraire du Client ou obligation légale.",
    pourquoi:
      "Phrase mal ponctuée, laissée telle quelle : on ne sait pas si « sauf demande contraire du Client ou obligation légale » vaut pour la dernière ligne ou pour les trois durées.",
  },
  {
    page: "toutes",
    passage:
      "Les données personnelles sont conservées pendant une durée de 3 ans à compter de la dernière interaction, ou conformément aux exigences légales.",
    pourquoi:
      "Quatre durées de conservation coexistent : politique de confidentialité (3 ans après la dernière interaction) ; charte RGPD 1.6 (« documents générés : 12 mois », « données clients administratives : 3 ans ») ; charte RGPD 4 (« que le temps de votre inscription sur le Site ») ; CGV (« durée maximale de douze (12) mois à compter de la fin de la prestation ou de la résiliation de l'abonnement »). À unifier, et à rapprocher de ce que la plateforme supprime réellement.",
  },
  {
    page: "toutes",
    passage:
      "Ces informations ne sont utilisées que dans le cadre strict de la mission confiée et ne font l’objet d’aucune diffusion ou réutilisation sans autorisation écrite du Client.",
    pourquoi:
      "Contradiction entre la politique de confidentialité et les CGV, article 8 : « une étude commandée sur un thème pourra être réutilisée pour la vendre en tant qu'etude clé en main ». La charte RGPD dit aussi : « Aucune exploitation commerciale, revente, diffusion ou communication à des tiers non autorisés n'est réalisée. »",
  },
  {
    page: CHEMINS.cgv,
    passage:
      "Les Clients ont accès aux programmes et aux supports (écrits, vidéos, audio) pour une durée minimale de 24 mois.",
    pourquoi:
      "Contradiction avec les CGU de la même page (« accessibles pendant toute leur période de commercialisation active ») et avec les pages de vente des formations, qui promettent un « accès à vie ».",
  },

  // Données collectées, cookies
  {
    page: CHEMINS.rgpd,
    passage: "votre adresse IP et l’adresse MAC de votre ordinateur",
    pourquoi:
      "À faire vérifier : la nouvelle plateforme ne relève pas l'adresse MAC des visiteurs.",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "Il peut également vous être demandé de fournir le nom de votre opérateur télécom, le modèle de votre téléphone portable et un numéro de portable valide afin de pouvoir fournir les instructions d’achat directement à travers votre téléphone mobile.",
    pourquoi:
      "Collecte qui ne correspond à aucun parcours d'achat de la nouvelle plateforme (paiement par Stripe). De même pour le paragraphe qui précède sur le numéro de carte : à faire préciser qui le reçoit.",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "La poursuite de la navigation sur une autre page du site ou la sélection d’un élément du Site (notamment : image, texte, lien, etc.) matérialise votre acceptation au dépôt des cookies visés sur votre ordinateur.",
    pourquoi:
      "Mode de recueil du consentement à faire relire par une juriste, et à rapprocher du bandeau réellement affiché par la nouvelle plateforme. La politique de confidentialité décrit autrement le même bandeau (« obtenir votre consentement »).",
  },
  {
    page: CHEMINS.confidentialite,
    passage: "Cookies de publicité : utilisés pour diffuser des publicités personnalisées.",
    pourquoi:
      "À confirmer : la nouvelle plateforme dépose-t-elle des cookies publicitaires ou analytiques ? Même question pour la charte RGPD : « des cookies des réseaux sociaux peuvent être générés notamment par l’intermédiaire des boutons de partage ».",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "Dans Internet Explorer, cliquez sur le bouton Outils, puis sur Options Internet.",
    pourquoi:
      "Consignes de navigateur périmées (Internet Explorer n'est plus distribué ; les menus décrits pour Firefox, Safari et Chrome ont changé).",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "Dans ce cadre, nous pouvons avoir recours à l'utilisation de Cookies tel que précisé au paragraphe 6 ci-dessous.",
    pourquoi:
      "Renvois internes décalés : les cookies sont au paragraphe 5, la conservation au paragraphe 4 (le texte renvoie au « paragraphe 5 de la présente Charte »), et le désabonnement est renvoyé au « paragraphe 6 ».",
  },
  {
    page: CHEMINS.rgpd,
    passage:
      "Tous les termes en majuscules non-définis dans la présente Charte sont définis dans les Conditions Générales consultables SUR LE SITE www.evkha.fr.",
    pourquoi:
      "« Compte », « Services », « Service Client » ne sont définis ni ici ni dans les CGV. À rapprocher du compte de l'espace client de la nouvelle plateforme.",
  },
  {
    page: CHEMINS.rgpd,
    passage: "ne sont accessibles qu’aux membres autorisés de l’équipe EVKHA",
    pourquoi:
      "À faire confirmer : EVKHA est une entreprise individuelle, et la nouvelle plateforme a ses propres accès d'administration et prestataires techniques.",
  },
  {
    page: "toutes",
    passage: "Politique de confidentialité et de cookies d’EVKHA",
    pourquoi:
      "Deux textes couvrent le même sujet avec des contenus différents : la charte de /rgpd et la politique de /politique-de-confidentialite. Les mentions légales et les CGV renvoient à « la Politique de confidentialité » sans dire laquelle. Faire décider s'il faut garder les deux.",
  },

  // Dates, numéros, adresses
  {
    page: CHEMINS.confidentialite,
    passage: "28 octobre 2026",
    pourquoi:
      "Date de mise à jour postérieure au relevé du site (25/10/2026), et différente de celle des mentions légales et de la charte RGPD (28 avril 2026). À vérifier, puis à remplacer par la date réelle de mise en ligne des textes validés.",
  },
  {
    page: CHEMINS.cgv,
    passage: "CGV / CGU EVKHA",
    pourquoi:
      "Les CGV / CGU ne portent aucune date de mise à jour ni numéro de version, alors qu'elles disent s'appliquer telles qu'acceptées à la commande.",
  },
  {
    page: CHEMINS.cgv,
    passage: "Le siège social est situé au 41 rue Jacquemars giélée.",
    pourquoi:
      "Adresse incomplète (ni code postal ni ville) et identification par le seul SIREN ; les mentions légales donnent l'adresse complète, le SIRET et le numéro de TVA. La charte RGPD écrit « 41 rue jacquemars giélée 59800 Lille ».",
  },
  {
    page: "toutes",
    passage: "Numero NDA, organisme de formation: 32591302259",
    pourquoi:
      "Numéro de déclaration d'activité répété sur les quatre pages : numéro et formulation réglementaire à faire vérifier.",
  },
  {
    page: CHEMINS.mentionsLegales,
    passage: "SIRET (siège) : 751 737 610 00020",
    pourquoi:
      "Numéros d'identification à faire confirmer par la cliente : SIRET, RCS « 751 737 610 R.C.S. Lille Métropole », TVA « FR90751737610 ».",
  },

  // Forme
  {
    page: "toutes",
    passage:
      "Découvre comment EVKHA collecte, utilise et protège tes données personnelles. Conformité RGPD, cookies, newsletter, formulaires : tout est transparent.",
    pourquoi:
      "Trois des quatre descriptions de page tutoient le lecteur (« Découvre », « Consulte », « Lis ») alors que les textes le vouvoient. Elles apparaissent dans les résultats de recherche.",
  },
  {
    page: CHEMINS.cgv,
    passage: "Le Client atteste, par la présence, disposer d’un équipement électronique adéquat",
    pourquoi:
      "Fautes laissées telles quelles parce qu'elles touchent des mots : « par la présence » (sans doute « par la présente »), « Il est vous est donc recommandé », « Vous pouvez contactez », « une certain laps de temps », « est commencé », « etudes », « retractation », « Numero ». À corriger par la personne qui validera le texte.",
  },
];
