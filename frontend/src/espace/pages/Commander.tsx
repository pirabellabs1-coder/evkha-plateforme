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
import { useMemo, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
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
import { Bandeau, Carte, Squelette, Vide } from "../composants/Interface";
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
}: {
  champ: ChampFormulaire;
  valeur: string;
  onChange: (valeur: string) => void;
  manquant: boolean;
}) {
  const id = `champ-${champ.identifiant}`;
  const idAide = champ.aide || champ.exemple ? `${id}-aide` : undefined;
  const commun = {
    id,
    name: champ.identifiant,
    className: "champ-saisie",
    value: valeur,
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
      {(champ.aide || champ.exemple) && (
        <span className="champ-aide" id={idAide}>
          {champ.aide}
          {champ.aide && champ.exemple ? " " : ""}
          {champ.exemple && <em>Ex. : {champ.exemple}</em>}
        </span>
      )}
    </div>
  );
}

export function Commander() {
  const { data: moi } = useMoi();
  const cache = useQueryClient();
  const naviguer = useNavigate();

  const [choisi, setChoisi] = useState<string | null>(null);
  const [reponses, setReponses] = useState<Record<string, string>>({});
  const [erreur, setErreur] = useState("");
  const [manquants, setManquants] = useState<string[]>([]);

  const peutCommander = peut(moi, "commander");

  // Une saisie en cours vaut 24 réponses de texte long : elle doit survivre à
  // un rechargement, à un clic dans la barre latérale, à un onglet fermé.
  const saisieEnCours = Object.values(reponses).some((v) => v.trim());
  const brouillonRestaure = useMemo(
    () => (choisi ? dateDuBrouillon(choisi) : null),
    // Ne dépend QUE du type choisi : rafraîchir la date à chaque frappe
    // ferait annoncer « saisie d'il y a une seconde » pendant qu'on écrit.
    [choisi],
  );

  useEffect(() => {
    if (choisi) enregistrerBrouillon(choisi, reponses);
  }, [choisi, reponses]);

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

  const { data: catalogue, isPending } = useQuery({
    queryKey: ["espace", "catalogue"],
    queryFn: espaceApi.catalogue,
  });

  const { data: questionnaire } = useQuery({
    queryKey: ["espace", "formulaire", choisi],
    queryFn: () => espaceApi.formulaire(choisi!),
    enabled: Boolean(choisi),
  });

  // Pièces jointes de l'organisation : elles accompagnent la commande. Les
  // questionnaires demandent des tableaux financiers et des études existantes,
  // que le client déposait jusqu'ici en les résumant à la main.
  const { data: pieces } = useQuery({
    queryKey: ["espace", "fichiers", "document"],
    queryFn: () => espaceApi.fichiers("document"),
  });

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
    mutationFn: () => espaceApi.commander(choisi!, reponses),
    onSuccess: () => {
      // La saisie est partie : la garder en brouillon la ferait « restaurer »
      // à la prochaine commande, et quelqu'un l'enverrait une seconde fois.
      if (choisi) oublierBrouillon(choisi);
      void cache.invalidateQueries({ queryKey: ["espace"] });
      void naviguer({ to: "/espace/livrables" });
    },
    onError: (cause) =>
      setErreur(
        cause instanceof ErreurApi ? cause.message : "Lancement impossible.",
      ),
  });

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
    const solde = catalogue?.solde ?? 0;

    return (
      <>
        {!peutCommander && (
          <Bandeau titre="Votre rôle ne permet pas de commander">
            Demandez à un propriétaire ou à un membre de votre équipe de lancer
            la commande.
          </Bandeau>
        )}
        {/* Deux situations distinctes derrière un même solde à zéro, et deux
            gestes différents. Le bandeau disait « Rendez-vous dans Abonnement
            pour DEMANDER des crédits » dans les deux cas : il envoyait
            attendre un appel quelqu'un dont l'abonnement se règle en un clic. */}
        {solde === 0 && !moi?.abonnement && (
          <Bandeau ton="echec" titre="Abonnement à activer">
            Vos crédits sont déposés dès le règlement.{" "}
            <Link to="/espace/souscription" className="bandeau-lien">
              Activer mon abonnement
            </Link>
          </Bandeau>
        )}
        {solde === 0 && moi?.abonnement && (
          <Bandeau ton="echec" titre="Aucun crédit disponible">
            Aucun découvert n'est possible. Vos prochains crédits arrivent à la
            prochaine échéance, ou{" "}
            <Link to="/espace/abonnement" className="bandeau-lien">
              changez de formule
            </Link>
            .
          </Bandeau>
        )}

        <Carte
          titre="Que souhaitez-vous produire ?"
          note={`Un crédit par document. Solde : ${f.credits(solde)}.`}
        >
          <div className="grille-documents">
            {(catalogue?.documents ?? []).map((doc: DocumentCatalogue) => {
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
                      setReponses(lireBrouillon(doc.type));
                    }
                    setErreur("");
                    setManquants([]);
                  }}
                >
                  <span className="carte-document-titre">{doc.libelle}</span>
                  <span className="carte-document-texte">{doc.description}</span>
                  <span className="carte-document-pied">
                    <span className="pastille pastille-neutre">
                      {doc.cout_credits} crédit
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
      </>
    );
  }

  // ── Questionnaire ────────────────────────────────────────────────────────

  if (!questionnaire) return <Squelette lignes={6} />;

  return (
    <form onSubmit={soumettre}>
      <Carte
        titre={questionnaire.titre}
        note={`${tousLesChamps.length} questions · 1 crédit`}
        action={
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => setChoisi(null)}
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
                if (choisi) oublierBrouillon(choisi);
              }}
            >
              Repartir d'une page blanche
            </button>
          </p>
        )}
      </Carte>

      {erreur && <Bandeau ton="echec">{erreur}</Bandeau>}
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
        <ListeFichiers
          fichiers={pieces?.pieces ?? []}
          onSupprimer={(id) => suppression.mutate(id)}
        />
        <p className="carte-note" style={{ marginTop: "var(--e-4)" }}>
          Résumez tout de même l'essentiel dans la question dédiée : c'est ce
          résumé que le moteur exploite pour rédiger.
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
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              {f.credits(Math.max((moi?.credits.solde ?? 0) - 1, 0))}
            </div>
          </div>
          <div>
            <div className="chiffre-libelle">Réponses complétées</div>
            <div style={{ fontWeight: 600, marginTop: "var(--e-1)" }}>
              {tousLesChamps.length - restants.length} / {tousLesChamps.length}
            </div>
          </div>
        </div>

        <p className="carte-note" style={{ marginTop: "var(--e-5)" }}>
          Votre logo et vos couleurs sont repris de « Ma marque » — inutile de
          les ressaisir. Le crédit est débité au démarrage de la génération, et
          restitué si l'étude échoue définitivement.
        </p>

        <div
          style={{
            display: "flex",
            gap: "var(--e-4)",
            alignItems: "center",
            marginTop: "var(--e-5)",
          }}
        >
          <button
            type="submit"
            className="bouton bouton-principal"
            disabled={envoi.isPending || !peutCommander}
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
