/** Les études de boutique achetées.
 *
 * Page distincte de « Livrables », et ce n'est pas un détail de rangement :
 * une étude sur mesure a un questionnaire, une progression et des contrôles ;
 * une étude de boutique est un fichier acheté une fois. Les mêler ferait une
 * liste où « en cours de production » côtoie « téléchargé », sans qu'on sache
 * lequel attend quoi.
 *
 * Des cartes avec couverture, et non des lignes. Ce bloc est une bibliothèque,
 * pas un tableau de suivi : on y revient pour retrouver une étude parmi
 * d'autres, et une couverture se reconnaît plus vite qu'un titre lu.
 *
 * ## C'est ici qu'on donne son avis
 *
 * Le courriel envoyé deux jours après l'achat mène à cette page. Le formulaire
 * vit donc sous l'étude concernée, et non sur une page dédiée : la personne
 * arrive en sachant de quelle étude elle veut parler, et la voir sous les yeux
 * évite d'écrire sur la mauvaise.
 *
 * ## Aucune étude n'est PROPOSÉE ici
 *
 * La page affichait « Le reste du catalogue » avec un bouton d'achat par
 * étude. C'était une suggestion, et une suggestion suppose qu'on connaisse le
 * besoin de la personne — on ne le connaît pas. Qui cherche une autre étude va
 * au catalogue, où il les voit toutes, filtrées par thème, avec leur fiche.
 * Ne reste ici qu'un lien vers cette boutique.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { espaceApi, type AchatDeBoutique } from "../api";
import * as f from "../format";
import { Bandeau, Carte, Squelette, Vide } from "../composants/Interface";

/** L'initiale du titre, pour les études sans couverture. L'article est retiré,
 *  sans quoi toutes les études du catalogue donneraient « L ». */
function initiale(titre: string): string {
  const mot = titre.replace(/^(le|la|les|l'|un|une|du|de|des)\s+/i, "").trim();
  return (mot[0] ?? "?").toUpperCase();
}

function Couverture({ image, titre }: { image: string; titre: string }) {
  return (
    <div className="achat-couverture">
      {image ? (
        <img src={image} alt="" loading="lazy" />
      ) : (
        <span aria-hidden="true">{initiale(titre)}</span>
      )}
    </div>
  );
}

/** Le choix de la note, en étoiles cliquables.
 *
 *  Un groupe de boutons radio et non une liste déroulante : cinq valeurs se
 *  choisissent d'un geste, et la note est ce qu'on donne en premier. */
function ChoixDeNote({
  note,
  onChange,
}: {
  note: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="avis-notes" role="radiogroup" aria-label="Votre note">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={note === n}
          aria-label={`${n} sur 5`}
          className={`avis-etoile ${n <= note ? "avis-etoile-pleine" : ""}`}
          onClick={() => onChange(n)}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function DonnerSonAvis({ achat }: { achat: AchatDeBoutique }) {
  const cache = useQueryClient();
  const [ouvert, setOuvert] = useState(false);
  const [note, setNote] = useState(5);
  const [texte, setTexte] = useState("");
  const [qualite, setQualite] = useState("");
  const [erreur, setErreur] = useState("");

  const envoi = useMutation({
    mutationFn: () =>
      espaceApi.deposerUnAvis(achat.id, { note, texte: texte.trim(), qualite }),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["espace", "achats"] });
    },
    onError: (cause: unknown) =>
      setErreur(
        cause instanceof Error
          ? cause.message
          : "Votre avis n'a pas pu être enregistré.",
      ),
  });

  // Déjà donné : on le rappelle, on ne le redemande pas. L'état de relecture
  // est dit franchement — sinon la personne cherche son texte sur la fiche
  // publique et croit qu'il s'est perdu.
  if (achat.avis) {
    return (
      <p className="avis-donne">
        <span className="avis-donne-etoiles" aria-label={`${achat.avis.note} sur 5`}>
          {"★".repeat(achat.avis.note)}
          {"☆".repeat(5 - achat.avis.note)}
        </span>
        {achat.avis.publie
          ? "Votre avis est en ligne sur la fiche de l'étude. Merci."
          : "Votre avis est enregistré, il sera publié après relecture."}
      </p>
    );
  }

  if (!ouvert) {
    return (
      <button
        type="button"
        className="bouton bouton-discret bouton-sm"
        onClick={() => setOuvert(true)}
      >
        Donner mon avis
      </button>
    );
  }

  return (
    <form
      className="avis-formulaire"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        if (!texte.trim()) {
          setErreur(
            "Écrivez une phrase : une note seule n'apprend rien à celle qui hésite.",
          );
          return;
        }
        envoi.mutate();
      }}
    >
      <p className="avis-titre">Votre avis sur cette étude</p>
      <ChoixDeNote note={note} onChange={setNote} />
      <textarea
        rows={3}
        value={texte}
        onChange={(e) => setTexte(e.currentTarget.value)}
        placeholder="Ce que vous en avez retiré, en une ou deux phrases."
        aria-label="Votre avis"
      />
      <input
        value={qualite}
        onChange={(e) => setQualite(e.currentTarget.value)}
        placeholder="Votre métier ou votre ville (facultatif)"
        aria-label="Votre qualité"
      />
      {erreur && <p className="avis-erreur">{erreur}</p>}
      <p className="avis-mention">
        Publié sous votre nom, jamais votre adresse e-mail, et après relecture.
      </p>
      <div className="avis-boutons">
        <button type="submit" className="bouton bouton-sm" disabled={envoi.isPending}>
          {envoi.isPending ? "Envoi…" : "Envoyer mon avis"}
        </button>
        <button
          type="button"
          className="bouton bouton-discret bouton-sm"
          onClick={() => setOuvert(false)}
        >
          Annuler
        </button>
      </div>
    </form>
  );
}

export function MesAchats() {
  const { data, isPending } = useQuery({
    queryKey: ["espace", "achats"],
    queryFn: espaceApi.mesAchats,
  });
  if (isPending) return <Squelette lignes={3} />;

  const achats = data?.achats ?? [];
  const catalogue = data?.catalogue ?? [];
  const attendus = achats.filter((a) => !a.avis).length;

  return (
    <>
      {attendus > 0 && (
        <Bandeau ton="alerte" titre="Votre avis compte">
          {attendus === 1
            ? "Une de vos études attend votre avis. Une note et une phrase suffisent."
            : `${attendus} de vos études attendent votre avis. Une note et une phrase suffisent.`}
        </Bandeau>
      )}

      <Carte
        titre="Mes études"
        note={
          achats.length > 0
            ? "Téléchargeables à tout moment, autant de fois que vous le souhaitez."
            : undefined
        }
      >
        {achats.length === 0 ? (
          <Vide
            titre="Aucune étude achetée"
            texte="Les études que vous achetez dans la boutique apparaissent ici, et y restent."
          />
        ) : (
          <ul className="achats-grille">
            {achats.map((a) => (
              <li key={a.id} className="achat-carte">
                <Couverture image={a.image} titre={a.titre} />
                <div className="achat-corps">
                  <p className="achat-titre">{a.titre}</p>
                  <p className="carte-note">
                    Acheté le {f.date(a.achete_le)}
                  </p>
                  <div className="achat-liens">
                    {a.telechargement && (
                      <a
                        className="bouton bouton-contour bouton-sm"
                        href={a.telechargement}
                      >
                        Télécharger le PDF
                      </a>
                    )}
                    {a.editable && (
                      <a className="bouton bouton-discret bouton-sm" href={a.editable}>
                        Word
                      </a>
                    )}
                  </div>
                  <div className="achat-avis">
                    <DonnerSonAvis achat={a} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Carte>

      {catalogue.length > 0 && (
        <Carte titre="Le catalogue">
          <p className="carte-note">
            {catalogue.length} autre{catalogue.length > 1 ? "s" : ""} étude
            {catalogue.length > 1 ? "s" : ""} en téléchargement immédiat.
          </p>
          <p className="achat-vers-boutique">
            <a className="bouton bouton-contour bouton-sm" href="/boutique">
              Ouvrir la boutique
            </a>
          </p>
        </Carte>
      )}
    </>
  );
}
