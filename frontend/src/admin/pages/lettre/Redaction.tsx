/** Ce que partagent une newsletter, un modèle et un message d'automatisation :
 * les trois champs du contenu, l'APERÇU EN DIRECT du courriel à côté de
 * l'éditeur, et l'essai à soi-même.
 *
 * L'aperçu est celui du serveur (`lettre.gabarit`, après nettoyage) : la
 * gérante voit le modèle de courriel — en-tête, cadre, pied de désinscription
 * — EN MÊME TEMPS qu'elle écrit (demande du 26/11/2026), et ce qu'elle voit
 * est ce que l'abonné recevra, pas une imitation côté navigateur. */
import { lazy, Suspense, useEffect, useId, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { adminApi, type ContenuDeLettre } from "../../api";
import { Squelette } from "../../../espace/composants/Interface";
import { message } from "./outils";

const EditeurEnrichi = lazy(() => import("./EditeurEnrichi"));

/** Le temps d'une pause dans la frappe, avant de redemander l'aperçu. */
const PAUSE_MS = 500;

function useApresUnePause<T>(valeur: T): T {
  const [retenue, setRetenue] = useState(valeur);
  useEffect(() => {
    const minuterie = window.setTimeout(() => setRetenue(valeur), PAUSE_MS);
    return () => window.clearTimeout(minuterie);
  }, [valeur]);
  return retenue;
}

/** Un HTML montré sans qu'il puisse rien exécuter : `sandbox` vide interdit
 *  scripts, formulaires et navigation de la page. */
function CadreIsole({
  html,
  titre,
  classe,
  horsClavier = false,
}: {
  html: string;
  titre: string;
  classe?: string;
  horsClavier?: boolean;
}) {
  return (
    <iframe
      className={classe ?? "lt-cadre"}
      title={titre}
      sandbox=""
      srcDoc={html}
      tabIndex={horsClavier ? -1 : undefined}
    />
  );
}

export function ApercuEnDirect({ contenu }: { contenu: ContenuDeLettre }) {
  const stable = useApresUnePause(contenu);
  const apercu = useQuery({
    queryKey: ["admin", "lettre", "apercu", stable.objet, stable.apercu, stable.corps_html],
    queryFn: () => adminApi.apercuDeLettre(stable),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
  return (
    <section className="lt-direct" aria-label="Aperçu du courriel">
      <p className="lt-direct-titre">
        Aperçu du courriel{apercu.isFetching ? " — mise à jour…" : ""}
      </p>
      {apercu.isError ? (
        <p className="lt-statut-echec">
          {message(apercu.error, "L'aperçu n'a pas pu être préparé.")}
        </p>
      ) : apercu.data ? (
        <CadreIsole html={apercu.data.html} titre="Aperçu du courriel" />
      ) : (
        <Squelette lignes={6} />
      )}
    </section>
  );
}

/** Une vignette de modèle : le courriel en réduction, sans interaction. */
export function Vignette({ contenu, nom }: { contenu: ContenuDeLettre; nom: string }) {
  const apercu = useQuery({
    queryKey: ["admin", "lettre", "apercu", contenu.objet, contenu.apercu, contenu.corps_html],
    queryFn: () => adminApi.apercuDeLettre(contenu),
    staleTime: 60_000,
  });
  return (
    <div className="lt-vignette" aria-hidden="true">
      {apercu.data && (
        <CadreIsole
          html={apercu.data.html}
          titre={`Aperçu du modèle ${nom}`}
          classe="lt-vignette-cadre"
          horsClavier
        />
      )}
    </div>
  );
}

export function ChampsDuContenu({
  contenu,
  changer,
  lectureSeule = false,
  objetObligatoire = true,
  apercuEnDirect = true,
}: {
  contenu: ContenuDeLettre;
  changer: (contenu: ContenuDeLettre) => void;
  lectureSeule?: boolean;
  objetObligatoire?: boolean;
  /** Faux pour les messages d'une automatisation : vingt aperçus montés
   *  d'un coup feraient vingt requêtes ; chacun s'ouvre à la demande. */
  apercuEnDirect?: boolean;
}) {
  const id = useId();
  const [ouvert, setOuvert] = useState(apercuEnDirect);
  return (
    <div className="lt-composition">
      <div className="lt-champs">
        <label className="champ" htmlFor={`${id}-objet`}>
          <span className="champ-libelle">Objet{objetObligatoire ? "" : " (facultatif)"}</span>
          <input
            id={`${id}-objet`}
            className="champ-saisie"
            value={contenu.objet}
            maxLength={200}
            required={objetObligatoire}
            readOnly={lectureSeule}
            onChange={(e) => changer({ ...contenu, objet: e.target.value })}
          />
        </label>
        <label className="champ" htmlFor={`${id}-apercu`}>
          <span className="champ-libelle">Texte d'aperçu (facultatif)</span>
          <input
            id={`${id}-apercu`}
            className="champ-saisie"
            value={contenu.apercu}
            maxLength={200}
            readOnly={lectureSeule}
            aria-describedby={`${id}-apercu-aide`}
            onChange={(e) => changer({ ...contenu, apercu: e.target.value })}
          />
          <span className="champ-aide" id={`${id}-apercu-aide`}>
            La ligne grise que les messageries affichent à côté de l'objet.
          </span>
        </label>
        {!lectureSeule && (
          <div className="lt-editeur">
            <span className="champ-libelle">Texte</span>
            <Suspense fallback={<Squelette lignes={6} />}>
              <EditeurEnrichi
                valeur={contenu.corps_html}
                changer={(corps_html) => changer({ ...contenu, corps_html })}
                libelle="Texte de la newsletter"
              />
            </Suspense>
          </div>
        )}
      </div>
      {ouvert ? (
        <ApercuEnDirect contenu={contenu} />
      ) : (
        <div className="lt-direct">
          <button
            type="button"
            className="bouton bouton-contour bouton-sm"
            onClick={() => setOuvert(true)}
          >
            Voir le courriel
          </button>
        </div>
      )}
    </div>
  );
}

export function Relecture({ contenu }: { contenu: ContenuDeLettre }) {
  const id = useId();
  const [adresse, setAdresse] = useState("");
  const [retour, setRetour] = useState<{ ton: "succes" | "echec"; texte: string } | null>(null);

  const essai = useMutation({
    mutationFn: () => adminApi.essaiDeLettre(contenu, adresse),
    onSuccess: (r) =>
      setRetour({
        ton: "succes",
        texte: `Exemplaire d'essai envoyé à ${r.adresse}. Il arrive en général en moins d'une minute.`,
      }),
    onError: (cause) =>
      setRetour({ ton: "echec", texte: message(cause, "L'essai n'est pas parti. Réessayez.") }),
  });

  return (
    <div className="lt-relecture">
      <form
        className="lt-essai"
        onSubmit={(e) => {
          e.preventDefault();
          setRetour(null);
          essai.mutate();
        }}
      >
        <label className="champ" htmlFor={`${id}-essai`}>
          <span className="champ-libelle">S'envoyer un essai</span>
          <input
            id={`${id}-essai`}
            className="champ-saisie"
            type="email"
            autoComplete="email"
            placeholder="votre@adresse.fr"
            value={adresse}
            onChange={(e) => setAdresse(e.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          className="bouton bouton-contour bouton-sm"
          disabled={essai.isPending || !contenu.objet.trim()}
        >
          {essai.isPending ? "Envoi…" : "Envoyer l'essai"}
        </button>
      </form>
      <p className="lt-statut" aria-live="polite">
        {retour && <span className={`lt-statut-${retour.ton}`}>{retour.texte}</span>}
      </p>
    </div>
  );
}
