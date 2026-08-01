/** Briques d'interface de l'espace client.
 *
 * Volontairement sans dépendance : les classes viennent de `theme/espace.css`,
 * qui ne lit que les jetons de `theme/tokens.css`. Aucune couleur en dur nulle
 * part — la charte se corrige en un seul fichier.
 */
import type { ReactNode } from "react";

// ── Cartes ──────────────────────────────────────────────────────────────────

export function Carte({
  titre,
  note,
  action,
  children,
}: {
  titre?: string;
  note?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="carte">
      {(titre || action) && (
        <header className="carte-entete">
          <div>
            {titre && <h2 className="carte-titre">{titre}</h2>}
            {note && <p className="carte-note">{note}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

// ── Chiffre clé ─────────────────────────────────────────────────────────────

export function Chiffre({
  libelle,
  valeur,
  detail,
  accent = false,
}: {
  libelle: string;
  valeur: ReactNode;
  detail?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={accent ? "chiffre accent" : "chiffre"}>
      <span className="chiffre-libelle">{libelle}</span>
      <span className="chiffre-valeur">{valeur}</span>
      {detail && <span className="chiffre-detail">{detail}</span>}
    </div>
  );
}

// ── Pastille de statut ──────────────────────────────────────────────────────

type Ton = "succes" | "alerte" | "echec" | "info" | "neutre";

/** Correspondance statut serveur → ton visuel.
 *
 * Une seule table, ici : la dupliquer dans chaque page la ferait diverger dès
 * qu'un statut est ajouté côté serveur.
 */
const TON_PAR_STATUT: Record<string, Ton> = {
  done: "succes",
  delivered: "succes",
  ready: "succes",
  active: "succes",
  running: "info",
  pending: "neutre",
  processing: "info",
  waiting_intake: "alerte",
  intervention_requise: "alerte",
  suspendue: "alerte",
  failed: "echec",
  cancelled: "neutre",
  expired: "neutre",
};

const LIBELLE_PAR_STATUT: Record<string, string> = {
  done: "Terminé",
  delivered: "Livré",
  ready: "Prêt",
  active: "Active",
  running: "En cours",
  pending: "En attente",
  processing: "En traitement",
  waiting_intake: "Formulaire attendu",
  intervention_requise: "Intervention requise",
  suspendue: "Suspendue",
  failed: "Échec",
  cancelled: "Annulé",
  expired: "Expiré",
};

export function Pastille({ statut, texte }: { statut: string; texte?: string }) {
  const ton = TON_PAR_STATUT[statut] ?? "neutre";
  return (
    <span className={`pastille pastille-${ton}`}>
      {texte ?? LIBELLE_PAR_STATUT[statut] ?? statut}
    </span>
  );
}

// ── État vide ───────────────────────────────────────────────────────────────

export function Vide({
  icone = "◇",
  titre,
  texte,
  action,
}: {
  icone?: string;
  titre: string;
  texte?: string;
  action?: ReactNode;
}) {
  return (
    <div className="vide">
      <div className="vide-icone" aria-hidden="true">
        {icone}
      </div>
      <p className="vide-titre">{titre}</p>
      {texte && <p className="vide-texte">{texte}</p>}
      {action}
    </div>
  );
}

// ── Bandeau ─────────────────────────────────────────────────────────────────

export function Bandeau({
  ton = "alerte",
  titre,
  children,
}: {
  ton?: "alerte" | "echec";
  titre?: string;
  children: ReactNode;
}) {
  return (
    <div className={`bandeau bandeau-${ton}`} role="status">
      <span aria-hidden="true">{ton === "echec" ? "✕" : "!"}</span>
      <div>
        {titre && <strong className="bandeau-titre">{titre}</strong>}
        {children}
      </div>
    </div>
  );
}

// ── Chargement ──────────────────────────────────────────────────────────────

/** Squelette plutôt qu'un tourniquet : la page ne saute pas quand les données
 *  arrivent, parce que la place est déjà prise. */
export function Squelette({ lignes = 3 }: { lignes?: number }) {
  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: "var(--e-3)" }}
      aria-busy="true"
      aria-live="polite"
    >
      <span className="visuellement-cache">Chargement…</span>
      {Array.from({ length: lignes }, (_, index) => (
        <div
          key={index}
          className="squelette"
          style={{ width: `${100 - index * 12}%`, height: "1.25rem" }}
        />
      ))}
    </div>
  );
}

// ── Champ de formulaire ─────────────────────────────────────────────────────

export function Champ({
  libelle,
  aide,
  erreur,
  ...proprietes
}: {
  libelle: string;
  aide?: string;
  erreur?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = proprietes.id ?? `champ-${proprietes.name ?? libelle}`;
  const idAide = aide || erreur ? `${id}-aide` : undefined;
  return (
    <label className="champ" htmlFor={id}>
      <span className="champ-libelle">{libelle}</span>
      <input
        {...proprietes}
        id={id}
        className="champ-saisie"
        aria-invalid={erreur ? true : undefined}
        aria-describedby={idAide}
      />
      {/* Le message d'erreur remplace l'aide : afficher les deux fait lire
          l'utilisateur deux fois pour rien. */}
      {(erreur || aide) && (
        <span
          className="champ-aide"
          id={idAide}
          style={erreur ? { color: "var(--evkha-echec)" } : undefined}
        >
          {erreur ?? aide}
        </span>
      )}
    </label>
  );
}

// ── Aperçu de charte ────────────────────────────────────────────────────────

export function ApercuCharte({
  couleurs,
}: {
  couleurs: (string | undefined)[];
}) {
  const retenues = couleurs.filter((c): c is string => Boolean(c));
  if (retenues.length === 0) {
    return <span className="carte-note">Charte non renseignée</span>;
  }
  return (
    <span className="pastilles-charte">
      {retenues.map((couleur) => (
        <span
          key={couleur}
          className="puce-couleur"
          style={{ background: couleur }}
          title={couleur}
        />
      ))}
      <span className="carte-note">{retenues[0]}</span>
    </span>
  );
}
