/** Commander un document (§9.3) — les quatre questionnaires EVKHA.
 *
 * Le formulaire n'est **pas** écrit ici : il est déclaré par le serveur et rendu
 * tel quel. Recopier les questions côté React les ferait diverger au premier
 * ajout, et c'est le défaut récurrent de ce dépôt.
 *
 * Trois étapes plutôt qu'une page unique : le questionnaire du business plan
 * compte vingt-quatre questions, dont plusieurs demandent de la réflexion. Les
 * poser d'un bloc fait fermer l'onglet.
 */
import { useCallback, useMemo, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  ErreurApi,
  espaceApi,
  type ChampFormulaire,
  type DocumentCatalogue,
} from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
import {
  dateDuBrouillon,
  enregistrerBrouillon,
  lireBrouillon,
  oublierBrouillon,
} from "../brouillon";
import {
  Bandeau,
  Carte,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../composants/Interface";
import {
  ListeFichiers,
  ZoneDepot,
} from "../composants/Televersement";

/** Un champ, rendu selon le type déclaré par le serveur. */
function Question({
  champ,
  valeur,
  onChange,
  manquant,
  verrouille,
}: {
  champ: ChampFormulaire;
  valeur: string;
  onChange: (valeur: string) => void;
  manquant: boolean;
  /** Imposé par la fiche du projet, et dit comme tel dans l'aide. */
  verrouille?: string;
}) {
  const id = `champ-${champ.identifiant}`;
  const aide = verrouille ?? champ.aide;
  const idAide = aide || champ.exemple ? `${id}-aide` : undefined;
  const commun = {
    id,
    name: champ.identifiant,
    className: "champ-saisie",
    value: valeur,
    readOnly: Boolean(verrouille),
    required: champ.obligatoire,
    "aria-invalid": manquant || undefined,
    "aria-describedby": idAide,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(e.target.value),
  };

  return (
    <div className="champ question">
      <label className="champ-libelle" htmlFor={id}>
        {champ.libelle}
        {champ.obligatoire && (
          <span className="question-requis" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {champ.type === "texte" ? (
        <input type="text" {...commun} />
      ) : (
        <textarea rows={champ.type === "nombres" ? 2 : 4} {...commun} />
      )}
      {(aide || champ.exemple) && (
        <span className="champ-aide" id={idAide}>
          {aide}
          {aide && champ.exemple && !verrouille ? " " : ""}
          {champ.exemple && !verrouille && <em>Ex. : {champ.exemple}</em>}
        </span>
      )}
    </div>
  );
}

/** Le questionnaire, remonté à chaque changement d'adresse.
 *
 * `Commander` lit le livrable et le projet UNE fois, depuis l'adresse. Revenir
 * par « Commander » dans la barre latérale ne démonte pas la page (même
 * route) : la commande suivante serait partie pour le projet du client
 * précédent. La clé sur la requête de l'adresse force un départ à neuf. */
export function CommanderSelonAdresse() {
  const adresse = useRouterState({ select: (s) => s.location.searchStr });
  return <Commander key={adresse} />;
}

export function Commander() {
  const lectureMoi = useMoi();
  const { data: moi } = lectureMoi;
  const cache = useQueryClient();
  const naviguer = useNavigate();

  // Pré-sélection depuis l'adresse (`/espace/commander?livrable=market_study`).
  //
  // C'est par là qu'arrive quelqu'un qui vient d'acheter UNE étude précise sur
  // `evkha.fr` : lui redemander laquelle, trente secondes après l'avoir payée,
  // c'est lui redemander ce qu'il vient de dire — et lui ouvrir la porte pour
  // se tromper de document.
  //
  // `URLSearchParams` plutôt que `useSearch` du routeur : le paramètre doit
  // être lu même quand la navigation vient de l'extérieur (retour de Stripe),
  // et non d'une transition interne typée.
  const [choisi, setChoisi] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("livrable") || null,
  );
  // Le projet d'un client, quand on commande depuis sa fiche
  // (`/espace/commander?livrable=…&projet=…`). Lu une fois, comme le livrable.
  const [projet] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("projet") || null,
  );
  // Le brouillon est rangé PAR PROJET : sans cela, la saisie laissée pour un
  // client se « restaurait » dans l'étude d'un autre.
  const cleBrouillon = useCallback(
    (type: string) => (projet ? `${projet}.${type}` : type),
    [projet],
  );
  // Repris du brouillon dès l'arrivée par une adresse : démarrer vide faisait
  // EFFACER le brouillon par l'effet qui l'enregistre (une saisie vide le
  // retire). Revenir finir un questionnaire depuis la fiche d'un client
  // perdait donc tout ce qui avait été tapé.
  const [reponses, setReponses] = useState<Record<string, string>>(() =>
    choisi ? lireBrouillon(cleBrouillon(choisi)) : {},
  );
  const [erreur, setErreur] = useState("");
  const [manquants, setManquants] = useState<string[]>([]);
  // Le sens du dernier passage d'une étape à l'autre, pour que l'étape qui
  // arrive glisse du bon côté : depuis la droite quand on avance vers le
  // questionnaire, depuis la gauche quand on revient au choix. Présentation
  // pure — aucune donnée n'en dépend.
  const [sens, setSens] = useState<"avant" | "arriere">("avant");

  const peutCommander = peut(moi, "commander");
  // Le type de compte, et non l'absence d'abonnement : un acheteur à l'unité
  // n'en a pas et n'en aura jamais, ce qui rend `!moi?.abonnement` incapable
  // de les distinguer l'un de l'autre.
  const aLUnite = moi?.organisation.type_de_compte === "a_l_unite";

  const lectureCatalogue = useQuery({
    queryKey: ["espace", "catalogue"],
    queryFn: espaceApi.catalogue,
  });
  const { data: catalogue, isPending } = lectureCatalogue;

  const lectureQuestionnaire = useQuery({
    queryKey: ["espace", "formulaire", choisi],
    queryFn: () => espaceApi.formulaire(choisi!),
    enabled: Boolean(choisi),
  });
  const { data: questionnaire } = lectureQuestionnaire;

  // Ce que l'on a déjà répondu pour ce projet, tous livrables confondus.
  const lectureProjet = useQuery({
    queryKey: ["espace", "projet", projet, "reponses", choisi],
    queryFn: () => espaceApi.reponsesDuProjet(projet!, choisi!),
    enabled: Boolean(projet && choisi),
  });
  const { data: dejaDit } = lectureProjet;
  // « Introuvable » ne se dit que lorsque le SERVEUR le dit (404). Toute
  // erreur le disait : une panne passagère annonçait à l'abonnée que le
  // projet de son client n'existait pas.
  const projetIntrouvable =
    lectureProjet.error instanceof ErreurApi && lectureProjet.error.statut === 404;

  // Le pré-remplissage se pose UNE fois par livrable, sous le brouillon : une
  // saisie en cours l'emporte sur ce que la fiche savait, et une frappe ne
  // doit jamais être écrasée par un rechargement de la requête. Posé pendant
  // le rendu et non dans un effet : React ajuste l'état avant d'afficher,
  // sans un premier rendu vide qui clignoterait.
  const [preRempli, setPreRempli] = useState<string | null>(null);
  if (dejaDit && choisi && preRempli !== choisi) {
    setPreRempli(choisi);
    setReponses((saisie) => {
      const tapees = Object.fromEntries(
        Object.entries(saisie).filter(([, valeur]) => valeur.trim()),
      );
      return { ...dejaDit.reponses, ...tapees, PROJET: dejaDit.projet.nom };
    });
  }
  const repris = dejaDit
    ? Object.keys(dejaDit.reponses).filter((cle) => cle !== "PROJET").length
    : 0;

  // Une saisie en cours vaut 24 réponses de texte long : elle doit survivre à
  // un rechargement, à un clic dans la barre latérale, à un onglet fermé.
  //
  // Ce qui est ENREGISTRÉ et ce qui compte comme « en cours », c'est ce que la
  // personne a tapé — pas ce que la fiche a pré-rempli. Garder le pré-rempli
  // dans le brouillon le faisait passer, au retour, pour une saisie : il
  // l'emportait alors sur une réponse plus récente donnée dans une autre
  // étude, et quitter un questionnaire intact déclenchait l'alerte de départ.
  const propres = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(reponses).filter(
          ([cle, valeur]) =>
            valeur.trim() && valeur !== (dejaDit?.reponses[cle] ?? ""),
        ),
      ),
    [reponses, dejaDit],
  );
  const saisieEnCours = Object.keys(propres).length > 0;
  const brouillonRestaure = useMemo(
    () => (choisi ? dateDuBrouillon(cleBrouillon(choisi)) : null),
    // Ne dépend QUE du type choisi : rafraîchir la date à chaque frappe
    // ferait annoncer « saisie d'il y a une seconde » pendant qu'on écrit.
    [choisi, cleBrouillon],
  );

  useEffect(() => {
    if (choisi) enregistrerBrouillon(cleBrouillon(choisi), propres);
  }, [choisi, propres, cleBrouillon]);

  // Le navigateur ne laisse pas personnaliser ce message, et c'est très bien :
  // ce qui compte est qu'il y en ait un.
  useEffect(() => {
    if (!saisieEnCours) return undefined;
    const avertir = (evenement: BeforeUnloadEvent) => {
      evenement.preventDefault();
    };
    window.addEventListener("beforeunload", avertir);
    return () => window.removeEventListener("beforeunload", avertir);
  }, [saisieEnCours]);

  // Pièces jointes de l'organisation : elles accompagnent la commande. Les
  // questionnaires demandent des tableaux financiers et des études existantes,
  // que le client déposait jusqu'ici en les résumant à la main.
  const lecturePieces = useQuery({
    queryKey: ["espace", "fichiers", "document"],
    queryFn: () => espaceApi.fichiers("document"),
  });
  const { data: pieces } = lecturePieces;

  const depot = useMutation({
    mutationFn: (fichier: File) => espaceApi.deposerFichier(fichier, "document"),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["espace", "fichiers"] });
    },
    onError: (cause) =>
      setErreur(cause instanceof ErreurApi ? cause.message : "Dépôt impossible."),
  });

  const suppression = useMutation({
    mutationFn: (id: string) => espaceApi.supprimerFichier(id),
    onSuccess: () =>
      void cache.invalidateQueries({ queryKey: ["espace", "fichiers"] }),
  });

  const envoi = useMutation({
    mutationFn: () => espaceApi.commander(choisi!, reponses, projet ?? undefined),
    onSuccess: () => {
      // La saisie est partie : la garder en brouillon la ferait « restaurer »
      // à la prochaine commande, et quelqu'un l'enverrait une seconde fois.
      if (choisi) oublierBrouillon(cleBrouillon(choisi));
      void cache.invalidateQueries({ queryKey: ["espace"] });
      // Depuis une fiche, on y revient : c'est là que l'étude s'ajoute à
      // l'historique du client.
      if (dejaDit) {
        void naviguer({
          to: "/espace/clients/$clientId",
          params: { clientId: dejaDit.client.id },
        });
      } else {
        void naviguer({ to: "/espace/livrables" });
      }
    },
  });
  // Le refus du serveur — abonnement inactif (402), solde insuffisant ou
  // questionnaire incomplet (400), démarrage impossible (503) — se lit sur la
  // mutation elle-même, et s'affiche à DEUX endroits : en tête, et contre le
  // bouton. Il n'était rendu qu'en tête d'un questionnaire de vingt-quatre
  // questions : on cliquait « Lancer la génération » tout en bas, le message
  // apparaissait hors écran, et il ne se passait visiblement RIEN (audit du
  // 19/11/2026) — le même défaut que le dépôt de document, plus bas.
  const refusDuLancement = envoi.isError
    ? envoi.error instanceof ErreurApi
      ? envoi.error.message
      : "Le lancement n'a pas abouti. Vérifiez votre connexion et réessayez."
    : "";

  const tousLesChamps = useMemo(
    () => questionnaire?.sections.flatMap((s) => s.champs) ?? [],
    [questionnaire],
  );

  const restants = tousLesChamps.filter(
    (champ) => champ.obligatoire && !(reponses[champ.identifiant] ?? "").trim(),
  );

  function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur("");
    if (restants.length > 0) {
      // On ne laisse pas le serveur être le premier à le dire : l'aller-retour
      // ferait perdre la position dans un formulaire de vingt-quatre questions.
      // Le refus d'un envoi précédent ne vaut plus : celui-ci ne part pas.
      envoi.reset();
      setManquants(restants.map((champ) => champ.identifiant));
      document
        .getElementById(`champ-${restants[0].identifiant}`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    setManquants([]);
    envoi.mutate();
  }

  // ── Choix du document ────────────────────────────────────────────────────

  if (!choisi) {
    if (isPending) return <Squelette lignes={4} />;
    // Rien reçu : on le dit, et on s'arrête là. L'écran lisait `solde ?? 0`
    // et `documents ?? []` : une session expirée affichait « Aucun crédit
    // disponible » — ou « Abonnement à activer » — au-dessus d'une grille
    // vide, à quelqu'un qui a payé (audit du 19/11/2026).
    if (!catalogue) {
      return (
        <ErreurDeChargement
          quoi="le catalogue des documents"
          erreur={lectureCatalogue.error}
        />
      );
    }
    const solde = catalogue.solde;

    return (
      // Une enveloppe par étape, avec sa propre `key` : changer d'étape la
      // remonte, et c'est le remontage qui joue le fondu-glissé.
      <div className={`etape-commande etape-commande-${sens}`} key="choix">
        {lectureCatalogue.isError && (
          <ErreurDeChargement
            quoi="le catalogue des documents"
            erreur={lectureCatalogue.error}
            perimees
          />
        )}
        {lectureMoi.isError && (
          <ErreurDeChargement
            quoi="votre compte"
            erreur={lectureMoi.error}
            perimees={lectureMoi.isRefetchError}
          />
        )}
        {projet && <PourQui projet={projet} />}
        {/* Ce que le rôle permet se lit sur le compte REÇU : sans lui, on ne
            sait pas, et « votre rôle ne permet pas » répondrait à sa place. */}
        {moi && !peutCommander && (
          <Bandeau titre="Votre rôle ne permet pas de commander">
            Demandez à un propriétaire ou à un membre de votre équipe de lancer
            la commande.
          </Bandeau>
        )}
        {/* UN solde à zéro, TROIS situations, trois gestes différents — et une
            seule phrase à afficher.

            Les conditions formaient un chevauchement : « Abonnement à activer »
            et « Aucune étude en attente » testaient toutes deux
            `!moi?.abonnement`, si bien qu'un acheteur à l'unité voyait les
            deux, dont une qui lui demandait d'activer un abonnement qu'il n'a
            pas et ne veut pas.

            Elles sont désormais une PARTITION sur le type de compte : chaque
            client tombe dans un cas et un seul. Ce qui empêche le défaut de
            revenir n'est pas d'avoir corrigé une condition, c'est que les trois
            branches se lisent ensemble et se répondent (règle 4).

            La partition porte sur le COMPTE : sans lui, aucune des trois
            phrases n'est sûre, et la troisième — « Abonnement à activer » —
            s'affichait par défaut à une abonnée dont le compte n'avait
            simplement pas pu être lu. */}
        {moi &&
          solde === 0 &&
          (aLUnite ? (
            <Bandeau ton="echec" titre="Aucune étude en attente">
              Choisissez l'étude que vous voulez produire depuis{" "}
              <Link to="/espace" className="bandeau-lien">
                votre tableau de bord
              </Link>
              . Elle sera disponible ici aussitôt réglée.
            </Bandeau>
          ) : moi.abonnement ? (
            <Bandeau ton="echec" titre="Aucun crédit disponible">
              Aucun découvert n'est possible. Vos prochains crédits arrivent à
              la prochaine échéance, ou{" "}
              <Link to="/espace/abonnement" className="bandeau-lien">
                changez de formule
              </Link>
              .
            </Bandeau>
          ) : (
            <Bandeau ton="echec" titre="Abonnement à activer">
              Vos crédits sont déposés dès le règlement.{" "}
              <Link to="/espace/souscription" className="bandeau-lien">
                Activer mon abonnement
              </Link>
            </Bandeau>
          ))}

        <Carte
          titre="Que souhaitez-vous produire ?"
          note={`Un crédit par document. Solde : ${f.credits(solde)}.`}
        >
          <div className="grille-documents">
            {catalogue.documents.map((doc: DocumentCatalogue) => {
              const indisponible = !doc.couvert || !peutCommander;
              return (
                <button
                  key={doc.type}
                  type="button"
                  className="carte-document"
                  disabled={indisponible}
                  onClick={() => {
                    // `setReponses({})` s'exécutait même en re-sélectionnant
                    // le document DÉJÀ choisi : aller lire la description d'un
                    // autre type puis revenir effaçait 24 réponses en un clic.
                    if (doc.type !== choisi) {
                      setChoisi(doc.type);
                      setReponses(lireBrouillon(cleBrouillon(doc.type)));
                    }
                    setSens("avant");
                    setErreur("");
                    setManquants([]);
                  }}
                >
                  <span className="carte-document-titre">{doc.libelle}</span>
                  <span className="carte-document-texte">{doc.description}</span>
                  <span className="carte-document-pied">
                    {/* Une carte fermée doit DIRE pourquoi. Grisée sans un mot,
                        elle se lit comme une panne — et l'acheteur à l'unité en
                        voit trois d'un coup, celles qu'il n'a pas payées. */}
                    <span
                      className={
                        indisponible && peutCommander
                          ? "pastille pastille-alerte"
                          : "pastille pastille-neutre"
                      }
                    >
                      {indisponible && peutCommander
                        ? "À acheter"
                        : `${doc.cout_credits} crédit`}
                    </span>
                    <span className="carte-note">
                      {doc.questions} questions
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </Carte>
      </div>
    );
  }

  // ── Questionnaire ────────────────────────────────────────────────────────

  // Le questionnaire n'est pas arrivé. S'il a ÉCHOUÉ, on le dit et on rend la
  // main : l'écran restait sous un squelette, indéfiniment, sans un mot et
  // sans issue — y compris pour un type de document inconnu dans l'adresse.
  if (!questionnaire) {
    return lectureQuestionnaire.isError ? (
      <>
        <ErreurDeChargement
          quoi="le questionnaire"
          erreur={lectureQuestionnaire.error}
        />
        <div>
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => {
              setSens("arriere");
              setChoisi(null);
            }}
          >
            Choisir un autre document
          </button>
        </div>
      </>
    ) : (
      <Squelette lignes={6} />
    );
  }

  return (
    <form
      onSubmit={soumettre}
      className={`etape-commande etape-commande-${sens}`}
      key="questionnaire"
    >
      <Carte
        titre={questionnaire.titre}
        note={`${tousLesChamps.length} questions · 1 crédit`}
        action={
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => {
              setSens("arriere");
              setChoisi(null);
            }}
          >
            Changer de document
          </button>
        }
      >
        {/* La note d'introduction vient du serveur : c'est celle des
            questionnaires Tally, mot pour mot. */}
        <p className="questionnaire-note">{questionnaire.note}</p>

        {/* Restaurer en silence ferait envoyer une saisie qu'on croit neuve.
            On le dit, avec sa date, et on laisse la main. */}
        {brouillonRestaure && saisieEnCours && (
          <p className="questionnaire-note" role="status">
            <strong>Brouillon repris</strong> — saisie du{" "}
            {brouillonRestaure.toLocaleDateString("fr-FR", {
              day: "numeric",
              month: "long",
              hour: "2-digit",
              minute: "2-digit",
            })}
            .{" "}
            <button
              type="button"
              className="bouton bouton-discret bouton-sm"
              onClick={() => {
                setReponses({});
                if (choisi) oublierBrouillon(cleBrouillon(choisi));
                // Repartir d'une page blanche garde ce que la fiche savait :
                // c'est la saisie qu'on efface, pas le projet.
                setPreRempli(null);
              }}
            >
              Repartir d'une page blanche
            </button>
          </p>
        )}
      </Carte>

      {lectureMoi.isError && (
        <ErreurDeChargement
          quoi="votre compte"
          erreur={lectureMoi.error}
          perimees={lectureMoi.isRefetchError}
        />
      )}
      {projetIntrouvable && (
        <Bandeau ton="echec" titre="Projet introuvable">
          Ce lien ne correspond à aucun projet de vos clients. Repassez par{" "}
          <Link to="/espace/clients" className="bandeau-lien">
            la liste de vos clients
          </Link>
          .
        </Bandeau>
      )}
      {lectureProjet.isError && !projetIntrouvable && (
        <ErreurDeChargement
          quoi="la fiche de ce projet"
          erreur={lectureProjet.error}
          perimees={lectureProjet.isRefetchError}
        />
      )}
      {dejaDit && (
        <Bandeau
          ton={dejaDit.projet.archive ? "echec" : "succes"}
          titre={`Pour ${dejaDit.client.nom} · ${dejaDit.projet.nom}`}
        >
          {dejaDit.projet.archive
            ? "Ce projet est archivé : il ne reçoit plus d'étude."
            : repris > 0
              ? `${repris} réponse${repris > 1 ? "s" : ""} reprise${repris > 1 ? "s" : ""} de la fiche et des études précédentes. Relisez-les : tout reste modifiable, sauf le nom du projet.`
              : "Le nom du projet est repris de la fiche. Les réponses de cette étude seront proposées aux suivantes."}{" "}
          <Link
            to="/espace/clients/$clientId"
            params={{ clientId: dejaDit.client.id }}
            className="bandeau-lien"
          >
            Revenir à la fiche
          </Link>
        </Bandeau>
      )}
      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
      {refusDuLancement && <Bandeau ton="echec">{refusDuLancement}</Bandeau>}
      {manquants.length > 0 && (
        <Bandeau titre={`${manquants.length} réponse(s) manquante(s)`}>
          Les questions concernées sont signalées ci-dessous.
        </Bandeau>
      )}

      {questionnaire.sections.map((section) => (
        <Carte key={section.titre} titre={section.titre}>
          <div className="questions">
            {section.champs.map((champ) => (
              <Question
                key={champ.identifiant}
                champ={champ}
                valeur={reponses[champ.identifiant] ?? ""}
                manquant={manquants.includes(champ.identifiant)}
                verrouille={
                  dejaDit && champ.identifiant === "PROJET"
                    ? "Repris de la fiche du client : c'est ce nom qui relie les études de ce projet."
                    : undefined
                }
                onChange={(valeur) =>
                  setReponses((precedent) => ({
                    ...precedent,
                    [champ.identifiant]: valeur,
                  }))
                }
              />
            ))}
          </div>
        </Carte>
      ))}

      {/* « Il reste les fichiers de la stratégie » (cliente, 12/08/2026). Ce
          n'est pas un bug de nettoyage : le dépôt appartient à l'ORGANISATION,
          jamais à une commande — un bilan se dépose une fois par an et se
          réutilise. Mais la carte le présentait comme les pièces de CETTE
          commande, et le client pressé ne fait pas la différence. On dit donc
          ce qui est vrai, et la liste porte désormais la date de dépôt. */}
      <Carte
        titre="Vos documents"
        note="Tableaux financiers, études déjà réalisées, présentations. Cette bibliothèque appartient à votre organisation : elle reste d'une commande à l'autre tant que vous ne retirez pas un fichier."
      >
        <ZoneDepot
          libelle="Ajouter un document"
          aide="PDF, Word, Excel, PowerPoint, PNG ou JPEG. 10 Mo maximum."
          accepte=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,image/png,image/jpeg"
          tailleMax={10 * 1024 * 1024}
          enCours={depot.isPending}
          onDeposer={(fichier) => depot.mutate(fichier)}
        />
        {/* L'échec d'un dépôt s'affiche ICI, sous la zone.
            Il ne s'affichait qu'en tête de formulaire, à trente lignes de
            questions au-dessus : on cliquait en bas, le message apparaissait
            hors écran, et il ne se passait visiblement RIEN. C'est ce que la
            cliente décrivait — « il ne s'ajoutait pas » — sans jamais voir la
            raison. Un motif qu'on ne lit pas ne vaut pas mieux qu'un silence
            (règle 2). */}
        {depot.isError && (
          <p className="carte-note" style={{ color: "var(--evkha-echec)" }}>
            {depot.error instanceof ErreurApi
              ? depot.error.message
              : "Dépôt impossible — réessayez, ou vérifiez le format et la taille."}
          </p>
        )}
        {/* La liste se lit sur une réponse REÇUE. Vide par défaut, elle
            écrivait « Aucun fichier déposé. » sur un échec de lecture — juste
            au-dessus de la phrase qui dit que TOUS les documents de la
            bibliothèque seront lus au lancement. */}
        {lecturePieces.isError && (
          <ErreurDeChargement
            quoi="vos documents déposés"
            erreur={lecturePieces.error}
            perimees={lecturePieces.isRefetchError}
          />
        )}
        {pieces && (
          <ListeFichiers
            fichiers={pieces.pieces}
            onSupprimer={(id) => suppression.mutate(id)}
          />
        )}
        {/* Cette note disait « c'est ce résumé que le moteur exploite » — vrai
            jusqu'au 11/09/2026, date à laquelle les documents ont commencé à
            être lus. Elle dit maintenant ce qui est lu, ce qui ne l'est pas, et
            la conséquence du pool partagé : TOUT ce qui est dans la
            bibliothèque est lu pour cette commande. */}
        <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
          Tous les documents de cette bibliothèque sont lus au lancement de
          l'étude : PDF, Word, Excel et PowerPoint. Les images, les PDF
          scannés et les anciens formats (.doc, .xls, .ppt) ne sont pas lus :
          enregistrez-les dans un format récent. Retirez avant de commander un
          document qui ne concerne pas cette étude, et indiquez dans la
          question dédiée ce qu'il faut en retenir en priorité.
        </p>
      </Carte>

      <Carte titre="Récapitulatif">
        <div className="grille-chiffres">
          <div>
            <div className="chiffre-libelle">Document</div>
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              {questionnaire.titre.replace("Questionnaire — ", "")}
            </div>
          </div>
          <div>
            <div className="chiffre-libelle">Coût</div>
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              1 crédit
            </div>
          </div>
          <div>
            <div className="chiffre-libelle">Solde après</div>
            {/* Jamais « 0 crédit » faute de l'avoir lu : un zéro est une
                réponse. */}
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              {moi ? f.credits(Math.max(moi.credits.solde - 1, 0)) : "—"}
            </div>
          </div>
          <div>
            <div className="chiffre-libelle">Réponses complétées</div>
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              {tousLesChamps.length - restants.length} / {tousLesChamps.length}
            </div>
          </div>
        </div>

        {/* QUELLE charte habillera ce document : le serveur en décide, l'écran
            le répète. Cette note écrivait toujours « repris de Ma marque ».
            Or une commande rattachée au projet d'une fiche client porte la
            charte de CETTE fiche — son nom, son logo, ses couleurs —, sans
            repli sur « Ma marque » : une fiche sans charte donne un document
            neutre (`commandes.charte_du_projet`, décidé après la stratégie
            `d319a9e5` partie aux couleurs d'un autre client). Seule la mention
            de confidentialité reste celle de l'abonnée. */}
        <p className="carte-note" style={{ marginTop: "var(--e-5)" }}>
          {projet
            ? `Le nom, le logo et les couleurs de ce document sont ceux de la fiche client${
                dejaDit ? ` « ${dejaDit.client.nom} »` : ""
              }, pas ceux de « Ma marque » : si la fiche n'a ni logo ni couleurs, le document reste neutre. La mention de confidentialité, elle, vient de « Ma marque ».`
            : "Votre logo et vos couleurs sont repris de « Ma marque » — inutile de les ressaisir."}{" "}
          Le crédit est débité au démarrage de la génération, et restitué si
          l'étude échoue définitivement.
        </p>

        {/* Le refus du serveur, CONTRE le bouton qui vient de le provoquer.
            `role="alert"` : il arrive après un geste, et doit être annoncé. */}
        {refusDuLancement && (
          <div role="alert" style={{ marginTop: "var(--e-5)" }}>
            <Bandeau ton="echec" titre="La génération n'a pas été lancée">
              {refusDuLancement}
            </Bandeau>
          </div>
        )}

        <div
          style={{
            display: "flex",
            gap: "var(--e-4)",
            alignItems: "center",
            marginTop: "var(--e-5)",
          }}
        >
          {/* Pendant l'envoi, la pilule est traversée d'un balayage or
              (`.bouton-chargement`) : pas de tourniquet, le texte dit déjà
              « Lancement… ». */}
          <button
            type="submit"
            className={
              envoi.isPending
                ? "bouton bouton-principal bouton-chargement"
                : "bouton bouton-principal"
            }
            disabled={
              envoi.isPending ||
              !peutCommander ||
              Boolean(dejaDit?.projet.archive) ||
              (Boolean(projet) && !dejaDit)
            }
          >
            {envoi.isPending ? "Lancement…" : "Lancer la génération"}
          </button>
          {restants.length > 0 && (
            <span className="carte-note">
              {restants.length} réponse(s) obligatoire(s) restante(s)
            </span>
          )}
        </div>
      </Carte>
    </form>
  );
}

/** Au choix du document, le rappel du client pour qui l'on commande.
 *
 * Le pré-remplissage dépend du livrable, pas le client : on lit donc la fiche
 * par la liste des clients plutôt que d'attendre un choix. */
function PourQui({ projet }: { projet: string }) {
  const { data } = useQuery({
    queryKey: ["espace", "projet", projet, "reponses", "market_study"],
    queryFn: () => espaceApi.reponsesDuProjet(projet, "market_study"),
  });
  if (!data) return null;
  return (
    <Bandeau ton="succes" titre={`Pour ${data.client.nom} · ${data.projet.nom}`}>
      Le questionnaire reprendra ce que vous avez déjà répondu pour ce projet.{" "}
      <Link
        to="/espace/clients/$clientId"
        params={{ clientId: data.client.id }}
        className="bandeau-lien"
      >
        Revenir à la fiche
      </Link>
    </Bandeau>
  );
}

/** Écran affiché quand le catalogue est vide — ne devrait pas arriver. */
export function CommanderVide() {
  return (
    <Vide
      icone="◇"
      titre="Aucun document disponible"
      texte="Contactez EVKHA : votre catalogue est vide."
    />
  );
}
