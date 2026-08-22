/** La fenêtre d'annonce, affichée à la connexion.
 *
 * EVKHA rédige un message depuis son administration ; il part par courriel ET
 * s'affiche ici. Les deux canaux servent des gens différents : le courriel
 * touche ceux qui ne se connectent pas, cette fenêtre touche ceux qui ne
 * lisent pas leurs courriels.
 *
 * ## Elle ne revient pas
 *
 * La fermeture est enregistrée EN BASE, pas dans le navigateur. Rangée côté
 * client, la fenêtre reviendrait sur un autre appareil et disparaîtrait au
 * premier vidage de cache — deux façons de mentir sur ce que la personne a lu.
 *
 * ## Une seule à la fois
 *
 * Quand plusieurs annonces attendent, la plus récente est montrée seule. Trois
 * fenêtres empilées à la connexion se ferment sans être lues ; la suivante
 * apparaît dès que celle-ci est fermée.
 */
import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { espaceApi } from "../api";

export function FenetreAnnonce() {
  const cache = useQueryClient();
  const { data } = useQuery({
    queryKey: ["espace", "annonces"],
    queryFn: espaceApi.mesAnnonces,
    // Une annonce arrive rarement : la redemander à chaque navigation dans
    // l'espace ferait beaucoup de requêtes pour une nouvelle par mois.
    staleTime: 5 * 60 * 1000,
  });
  const fermeture = useRef<HTMLButtonElement>(null);

  const annonce = data?.annonces?.[0];

  const fermer = useMutation({
    mutationFn: (id: string) => espaceApi.fermerUneAnnonce(id),
    onSettled: () => {
      // `onSettled` et non `onSuccess` : si l'enregistrement échoue, la
      // fenêtre doit tout de même se fermer. Rester bloqué sur une annonce
      // qu'on a lue serait pire que la revoir demain.
      void cache.invalidateQueries({ queryKey: ["espace", "annonces"] });
    },
  });

  // Le focus va sur la fermeture à l'ouverture : la fenêtre s'impose devant le
  // contenu, et il faut pouvoir en sortir au clavier sans chercher.
  useEffect(() => {
    if (annonce) fermeture.current?.focus();
  }, [annonce]);

  useEffect(() => {
    if (!annonce) return;
    const auClavier = (evenement: KeyboardEvent) => {
      if (evenement.key === "Escape") fermer.mutate(annonce.id);
    };
    window.addEventListener("keydown", auClavier);
    return () => window.removeEventListener("keydown", auClavier);
  }, [annonce, fermer]);

  if (!annonce) return null;

  const paragraphes = annonce.message
    .split(/\n\s*\n/)
    .filter((paragraphe) => paragraphe.trim());

  return (
    <div className="annonce-voile" role="presentation">
      <div
        className="annonce-fenetre"
        role="dialog"
        aria-modal="true"
        aria-labelledby="annonce-titre"
      >
        <button
          ref={fermeture}
          type="button"
          className="annonce-fermer"
          aria-label="Fermer l'annonce"
          onClick={() => fermer.mutate(annonce.id)}
        >
          ✕
        </button>

        <p className="annonce-eyebrow">Information EVKHA</p>
        <h2 id="annonce-titre">{annonce.titre}</h2>

        {paragraphes.map((paragraphe) => (
          <p key={paragraphe.slice(0, 40)} className="annonce-texte">
            {paragraphe}
          </p>
        ))}

        <div className="annonce-actions">
          {annonce.lien_libelle && annonce.lien_cible && (
            <a
              className="bouton"
              href={annonce.lien_cible}
              onClick={() => fermer.mutate(annonce.id)}
            >
              {annonce.lien_libelle}
            </a>
          )}
          <button
            type="button"
            className="bouton bouton-discret"
            onClick={() => fermer.mutate(annonce.id)}
          >
            {/* « J'ai compris » et non « Fermer » : le second laisse croire
                qu'on pourra la rouvrir. */}
            J'ai compris
          </button>
        </div>
      </div>
    </div>
  );
}
