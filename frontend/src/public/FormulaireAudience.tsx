/** Les deux formulaires de l'audience : une ressource gratuite contre une
 * adresse, et l'inscription à la lettre.
 *
 * Demande de la cliente du 24/11/2026 : les PDF se téléchargent
 * IMMÉDIATEMENT (elle ne veut plus les envoyer elle-même), et le
 * téléchargement récolte les adresses ; le blog propose la lettre.
 *
 * Le serveur (`audience.vues_publiques`) note l'adresse et rend le lien du
 * PDF ; la page lance aussitôt le téléchargement, et laisse le lien affiché au
 * cas où le navigateur l'aurait bloqué.
 *
 * - La case de la lettre est DÉCOCHÉE par défaut et ne conditionne pas le
 *   téléchargement (règle relevée dans `contenuRessources.FORMULAIRES`).
 * - Le champ `site` est un piège à robots : hors de l'écran, hors du
 *   parcours au clavier, ignoré des lecteurs d'écran.
 * - Le refus du serveur s'affiche sous le champ, relié par
 *   `aria-describedby` ; le succès s'annonce dans une région polie
 *   (`aria-live`, pas `role="status"` : la liste du blog a déjà SA région
 *   d'état, celle du compte, et deux régions d'état sur une page se
 *   confondent pour qui les cherche par leur rôle).
 * - Chaque formulaire renvoie à la politique de confidentialité, qui décrit
 *   déjà la lettre et le désabonnement.
 * - Sur une page PRÉ-RENDUE, le HTML écrit s'affiche plusieurs secondes avant
 *   que React ne monte : ses champs y sont désactivés (`PAGE_ECRITE`), et le
 *   formulaire porte `method="post"` — un envoi natif ne mettra jamais
 *   l'adresse dans l'URL ni dans les journaux.
 */
import { useId, useState, type FormEvent } from "react";

import { CHEMINS } from "./contenuSite";
import { BASE } from "./donnees";
import "./FormulaireAudience.css";

export type NomDeRessource = "checklist" | "lexique";

/** L'hôte du document où `scripts/prerendre.mjs` écrit les pages (son
 *  `JSDOM`, `url`). Le test `les-formulaires-de-l-audience` tient les deux
 *  d'accord. */
export const HOTE_DU_PRERENDU = "prerendu.invalid";

/** Vrai pendant le pré-rendu : le formulaire écrit dans la page n'est pas
 *  encore relié à son script, il ne doit rien laisser saisir. */
function pageEcrite(): boolean {
  return typeof window !== "undefined" && window.location.hostname === HOTE_DU_PRERENDU;
}

type Etat =
  | { etape: "saisie" }
  | { etape: "envoi" }
  | { etape: "refus"; message: string }
  | { etape: "fait"; lien?: string; confirmer?: boolean };

const ECHEC = "L'envoi n'a pas abouti. Réessayez dans un instant.";

async function poster(chemin: string, corps: object): Promise<Record<string, unknown>> {
  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}${chemin}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(corps),
    });
  } catch {
    throw new Error(ECHEC);
  }
  const charge = (await reponse.json().catch(() => ({}))) as Record<string, unknown>;
  if (!reponse.ok) {
    throw new Error(
      typeof charge.erreur === "string" && charge.erreur !== "" ? charge.erreur : ECHEC,
    );
  }
  return charge;
}

/** Un lien de PDF rendu par le serveur, lu avec méfiance : un chemin du site
 *  sous `/ressources/`, jamais une adresse d'ailleurs. */
function lienSur(brut: unknown): string | null {
  return typeof brut === "string" && /^\/ressources\/[a-z0-9-]+\.pdf$/.test(brut) ? brut : null;
}

/** Lance le téléchargement. Un lien `download` du même site, pas un
 *  `window.open` : après un appel réseau, ce n'est plus un geste de la
 *  personne, et les navigateurs bloquent les fenêtres. */
function telecharger(lien: string): void {
  const a = document.createElement("a");
  a.href = lien;
  a.download = "";
  a.hidden = true;
  document.body.append(a);
  a.click();
  a.remove();
}

function Piege({ valeur, changer }: { valeur: string; changer: (v: string) => void }) {
  return (
    <div className="aud-piege" aria-hidden="true">
      <label>
        Site web
        <input
          type="text"
          name="site"
          tabIndex={-1}
          autoComplete="off"
          value={valeur}
          onChange={(e) => changer(e.target.value)}
        />
      </label>
    </div>
  );
}

/** Le champ d'adresse, son libellé, et l'erreur qui s'y rattache. */
function ChampAdresse({
  id,
  valeur,
  changer,
  refus,
}: {
  id: string;
  valeur: string;
  changer: (v: string) => void;
  refus: string | null;
}) {
  return (
    <>
      <label className="aud-libelle" htmlFor={`${id}-email`}>
        Votre adresse e-mail
      </label>
      <input
        id={`${id}-email`}
        className="aud-champ"
        type="email"
        name="email"
        required
        autoComplete="email"
        inputMode="email"
        placeholder="prenom@exemple.fr"
        value={valeur}
        onChange={(e) => changer(e.target.value)}
        aria-invalid={refus ? true : undefined}
        aria-describedby={refus ? `${id}-refus ${id}-mention` : `${id}-mention`}
      />
    </>
  );
}

function Mention({ id, texte }: { id: string; texte: string }) {
  return (
    <p className="aud-mention" id={`${id}-mention`}>
      {/[.!?]$/.test(texte) ? texte : `${texte}.`}{" "}
      <a href={CHEMINS.confidentialite}>Politique de confidentialité</a>
    </p>
  );
}

function BoutonDEnvoi({ envoi, libelle }: { envoi: boolean; libelle: string }) {
  return (
    <button className="acc-btn acc-btn-noir aud-bouton" type="submit" disabled={envoi}>
      {envoi ? "Envoi…" : libelle}
      <span className="acc-btn-fleche" aria-hidden="true">
        →
      </span>
    </button>
  );
}

export function FormulaireRessource({
  ressource,
  nom,
  bouton,
  consentement,
  mention,
}: {
  ressource: NomDeRessource;
  /** Le nom de la ressource : distingue deux formulaires d'une page, et
   *  nomme le lien de secours. */
  nom: string;
  bouton: string;
  consentement: string;
  mention: string;
}) {
  const id = useId();
  const [email, setEmail] = useState("");
  const [lettre, setLettre] = useState(false);
  const [piege, setPiege] = useState("");
  const [etat, setEtat] = useState<Etat>({ etape: "saisie" });

  async function envoyer(evenement: FormEvent) {
    evenement.preventDefault();
    setEtat({ etape: "envoi" });
    try {
      const charge = await poster("/api/public/ressources/", {
        email,
        ressource,
        lettre,
        site: piege,
      });
      const lien = lienSur(charge.lien);
      if (!lien) throw new Error("Le document est momentanément indisponible.");
      setEtat({ etape: "fait", lien, confirmer: lettre });
      telecharger(lien);
    } catch (erreur) {
      setEtat({ etape: "refus", message: (erreur as Error).message });
    }
  }

  const refus = etat.etape === "refus" ? etat.message : null;
  return (
    <form className="aud-form" method="post" onSubmit={envoyer} aria-label={`${bouton} : ${nom}`}>
      <fieldset className="aud-cadre" disabled={pageEcrite()}>
      <ChampAdresse id={id} valeur={email} changer={setEmail} refus={refus} />
      <label className="aud-case">
        <input type="checkbox" checked={lettre} onChange={(e) => setLettre(e.target.checked)} />
        <span>{consentement}</span>
      </label>
      <Piege valeur={piege} changer={setPiege} />
      <BoutonDEnvoi envoi={etat.etape === "envoi"} libelle={bouton} />
      </fieldset>
      {refus && (
        <p className="aud-refus" id={`${id}-refus`} role="alert">
          {refus}
        </p>
      )}
      <p className="aud-statut" aria-live="polite" aria-atomic="true">
        {etat.etape === "fait" && etat.lien && (
          <>
            Votre téléchargement a commencé. S'il ne démarre pas :{" "}
            <a href={etat.lien} download>
              télécharger {nom}
            </a>
            .
            {etat.confirmer &&
              " Pour recevoir la newsletter, confirmez votre adresse : un courriel vous arrive dans la minute."}
          </>
        )}
      </p>
      <Mention id={id} texte={mention} />
    </form>
  );
}

export function FormulaireLettre({ bouton, mention }: { bouton: string; mention: string }) {
  const id = useId();
  const [email, setEmail] = useState("");
  const [piege, setPiege] = useState("");
  const [etat, setEtat] = useState<Etat>({ etape: "saisie" });

  async function envoyer(evenement: FormEvent) {
    evenement.preventDefault();
    setEtat({ etape: "envoi" });
    try {
      await poster("/api/public/lettre/", { email, site: piege });
      setEtat({ etape: "fait" });
    } catch (erreur) {
      setEtat({ etape: "refus", message: (erreur as Error).message });
    }
  }

  const refus = etat.etape === "refus" ? etat.message : null;
  return (
    <form
      className="aud-form aud-form-ligne"
      method="post"
      onSubmit={envoyer}
      aria-label="Inscription à la newsletter"
    >
      <fieldset className="aud-cadre" disabled={pageEcrite()}>
      <ChampAdresse id={id} valeur={email} changer={setEmail} refus={refus} />
      <Piege valeur={piege} changer={setPiege} />
      <BoutonDEnvoi envoi={etat.etape === "envoi"} libelle={bouton} />
      </fieldset>
      {refus && (
        <p className="aud-refus" id={`${id}-refus`} role="alert">
          {refus}
        </p>
      )}
      <p className="aud-statut" aria-live="polite" aria-atomic="true">
        {etat.etape === "fait" &&
          "Presque fini : confirmez votre adresse en cliquant sur le lien du courriel qui vous arrive dans la minute."}
      </p>
      <Mention id={id} texte={mention} />
    </form>
  );
}
