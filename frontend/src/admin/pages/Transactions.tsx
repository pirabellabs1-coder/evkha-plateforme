/** Suivi des paiements : aboutis, en cours, abandonnés.
 *
 * Une session de paiement ne laissait aucune trace. On demandait une adresse à
 * Stripe, on la donnait au client, et s'il abandonnait, personne ne le savait
 * jamais. Un panier abandonné est pourtant l'information commerciale la plus
 * utile de la plateforme : quelqu'un a voulu payer et s'est arrêté en chemin.
 *
 * L'écran ne décide de rien. Il montre, et il donne un bouton pour écrire —
 * c'est la cliente qui juge s'il faut relancer, et quand. Une relance
 * automatique serait vite ressentie comme du harcèlement, et le nombre d'envois
 * déjà faits est affiché précisément pour qu'on ne l'oublie pas.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, type TransactionSupervision } from "../api";
import { Icone } from "../icones";
import * as f from "../../espace/format";
import {
  Bandeau,
  Carte,
  Chiffre,
  ErreurDeChargement,
  Squelette,
  Vide,
} from "../../espace/composants/Interface";

/** Les filtres proposés. « Tout » d'abord : on vient souvent chercher une
 *  transaction précise, pas une catégorie. */
const FILTRES = [
  { cle: "", libelle: "Tout" },
  { cle: "abandonnee", libelle: "Abandonnés" },
  { cle: "ouverte", libelle: "En cours" },
  { cle: "payee", libelle: "Payés" },
] as const;

const ETIQUETTES: Record<TransactionSupervision["etat"], string> = {
  ouverte: "En attente de paiement",
  abandonnee: "Abandonné",
  payee: "Payé",
};

/** Le ton de chaque état, pris dans les pastilles déjà définies par le thème.
 *  En inventer de nouvelles ferait deux vocabulaires visuels pour la même
 *  notion de statut, d'un écran d'administration à l'autre. */
const TONS: Record<TransactionSupervision["etat"], string> = {
  ouverte: "pastille-alerte",
  abandonnee: "pastille-echec",
  payee: "pastille-succes",
};

export function TransactionsAdmin() {
  const [filtre, setFiltre] = useState<string>("");
  const [erreur, setErreur] = useState("");
  const cache = useQueryClient();

  const { data, isPending, isError, isRefetchError, error } = useQuery({
    queryKey: ["admin", "transactions", filtre],
    queryFn: () => adminApi.transactions(filtre),
  });

  const relance = useMutation({
    mutationFn: (id: string) => adminApi.relancerLaTransaction(id),
    onSuccess: () => {
      setErreur("");
      void cache.invalidateQueries({ queryKey: ["admin", "transactions"] });
    },
    onError: (cause: unknown) =>
      setErreur(
        cause instanceof Error ? cause.message : "Relance impossible.",
      ),
  });

  if (isPending) return <Squelette lignes={5} />;

  const resume = data?.resume;
  const lignes = data?.transactions ?? [];

  return (
    <>
      {/* Sans ce bandeau, un échec se lisait « 0 panier abandonné », « 0 €
          encaissé » et « Aucune transaction » : l'information commerciale la
          plus utile de la plateforme, remplacée par un zéro (audit du
          19/11/2026, règle 1). */}
      {isError && (
        <ErreurDeChargement quoi="les transactions" erreur={error} perimees={isRefetchError} />
      )}

      {resume && (
        <div className="grille-chiffres">
          <Chiffre
            libelle="Paniers abandonnés"
            valeur={f.nombre(resume.abandonnees)}
            detail={`${f.montant(resume.manque_a_gagner_cents)} de manque à gagner`}
            accent
          />
          <Chiffre
            libelle="Paiements en cours"
            valeur={f.nombre(resume.en_cours)}
            detail="Ouverts depuis moins de 24 h"
          />
          <Chiffre
            libelle="Paiements aboutis"
            valeur={f.nombre(resume.payees)}
            detail={`${f.montant(resume.encaisse_cents)} encaissés`}
          />
        </div>
      )}

      {erreur && (
        <Bandeau ton="echec" titre="Relance impossible">
          {erreur}
        </Bandeau>
      )}

      <div className="console-segments" role="group" aria-label="Filtrer les transactions par état">
        {FILTRES.map((choix) => (
          <button
            key={choix.cle}
            type="button"
            className={
              choix.cle === filtre
                ? "bouton bouton-sm"
                : "bouton bouton-contour bouton-sm"
            }
            aria-pressed={choix.cle === filtre}
            onClick={() => setFiltre(choix.cle)}
          >
            {choix.libelle}
          </button>
        ))}
      </div>

      <Carte
        titre="Transactions"
        note="Un paiement ouvert reste « en cours » 24 h, puis devient un panier abandonné : c'est la durée de vie d'une session Stripe."
      >
        {lignes.length === 0 ? (
          // « Aucune transaction » ne se dit que sur une liste REÇUE et à jour.
          data &&
          !isError && (
            <Vide
              icone={<Icone nom="transactions" />}
              titre="Aucune transaction"
              texte="Les paiements apparaîtront ici dès qu'un abonné ouvrira une souscription ou un achat de crédits."
            />
          )
        ) : (
          <div className="tableau-cadre tableau-defile">
            <table className="tableau">
              <thead>
                <tr>
                  <th scope="col">Ouverte le</th>
                  <th scope="col">Organisation</th>
                  <th scope="col">Objet</th>
                  <th scope="col" className="nombre">
                    Montant
                  </th>
                  <th scope="col">État</th>
                  <th scope="col">Relances</th>
                  <th scope="col">
                    <span className="visuellement-cache">Relancer</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {lignes.map((ligne) => (
                  <tr key={ligne.id}>
                    <td className="console-tabulaire">{f.date(ligne.ouverte_le)}</td>
                    <td>
                      <strong>{ligne.organisation}</strong>
                      {/* Un achat de boutique ouvert depuis la page publique
                          n'a pas encore d'organisation — le compte naît de
                          l'encaissement. Il ne porte qu'une adresse, et c'est
                          elle qui sert à relancer. */}
                      <div className="carte-note">{ligne.contact || "—"}</div>
                    </td>
                    <td>
                      {ligne.objet_libelle}
                      {/* L'étude visée : « quelqu'un a abandonné » vaut moins
                          que « quelqu'un a abandonné LAQUELLE » — c'est ce qui
                          permet d'écrire une relance qui parle du bon
                          document. */}
                      {ligne.produit && (
                        <div className="carte-note">{ligne.produit}</div>
                      )}
                      {/* Même raison pour une formation, dont le panier est
                          celui qui vaut le plus d'être relancé : sans son
                          titre, la ligne dirait « Achat d'une formation »
                          sans dire laquelle. */}
                      {ligne.formation && (
                        <div className="carte-note">{ligne.formation}</div>
                      )}
                      {ligne.formule && (
                        <div className="carte-note">{ligne.formule}</div>
                      )}
                      {ligne.quantite > 0 && (
                        <div className="carte-note">
                          {ligne.quantite} crédit{ligne.quantite > 1 ? "s" : ""}
                        </div>
                      )}
                    </td>
                    <td className="nombre">{f.montant(ligne.montant_cents, ligne.devise)}</td>
                    <td>
                      <span className={`pastille ${TONS[ligne.etat]}`}>
                        {ETIQUETTES[ligne.etat]}
                      </span>
                    </td>
                    <td className="console-tabulaire">
                      {ligne.relances === 0
                        ? "—"
                        : `${ligne.relances} · ${f.date(ligne.relancee_le)}`}
                    </td>
                    <td>
                      {ligne.etat !== "payee" && ligne.contact && (
                        <button
                          type="button"
                          className="bouton bouton-contour bouton-sm"
                          disabled={relance.isPending}
                          onClick={() => {
                            setErreur("");
                            relance.mutate(ligne.id);
                          }}
                        >
                          {relance.isPending ? "Envoi…" : "Relancer"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Carte>
    </>
  );
}
