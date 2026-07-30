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
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  ErreurApi,
  espaceApi,
  type ChampFormulaire,
  type DocumentCatalogue,
} from "../api";
import * as f from "../format";
import { peut, useMoi } from "../useMoi";
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
        {solde === 0 && (
          <Bandeau ton="echec" titre="Aucun crédit disponible">
            Une commande est bloquée si le solde ne la couvre pas — aucun
            découvert n'est possible. Rendez-vous dans Abonnement pour demander
            des crédits.
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
                    setChoisi(doc.type);
                    setReponses({});
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

      <Carte
        titre="Documents complémentaires"
        note="Tableaux financiers, études déjà réalisées, présentations."
      >
        <ZoneDepot
          libelle="Ajouter un document"
          aide="PDF, Word, Excel, PowerPoint, PNG ou JPEG. 10 Mo maximum."
          accepte=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,image/png,image/jpeg"
          tailleMax={10 * 1024 * 1024}
          enCours={depot.isPending}
          onDeposer={(fichier) => depot.mutate(fichier)}
        />
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
