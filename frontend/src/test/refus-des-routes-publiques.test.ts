/** Le client lit-il la clé que le serveur envoie vraiment ?
 *
 * ## Le défaut que ces tests verrouillent
 *
 * `backend/organisations/vues_publiques.py::_refus` rend
 * `{"erreur": …, "code": …}` — clé **française**. Deux fonctions de
 * `donnees.ts` lisaient `charge.error`, clé anglaise que ce serveur n'envoie
 * jamais. Elle valait donc toujours `undefined`, et le repli générique
 * s'affichait à la place du message précis : « Impossible de définir le mot de
 * passe (400) » au lieu de « Ce lien n'est plus valable… ».
 *
 * Le défaut ne se voyait nulle part. Rien ne plantait, aucun test ne tombait,
 * et l'écran affichait une phrase plausible — seulement pas la bonne. C'est
 * exactement le cas de la règle 2 du dépôt : un motif d'échec doit rester
 * trouvable par la personne qui le lit.
 *
 * ## Conséquence en cascade
 *
 * `MotDePasse.tsx` proposait « Demander un nouveau lien » en cherchant
 * « plus valable » dans le message. Comme le message n'arrivait jamais, la
 * sortie de secours de quelqu'un dont le lien a expiré n'était **jamais**
 * offerte. Ce n'est plus le texte qui décide mais le `code`, ce que le
 * commentaire de `RefusInscription` réclamait depuis le début : « un texte que
 * l'on compare finit toujours par être reformulé ».
 *
 * ## Pourquoi une charge écrite à la main
 *
 * Les charges ci-dessous reproduisent la forme EXACTE du serveur. Les dériver
 * du code client reviendrait à comparer le client à lui-même — et c'est
 * précisément ce que le défaut d'origine faisait passer pour correct (règle 9).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  RefusInscription,
  confirmerLAdresse,
  definirLeMotDePasse,
  demanderUnLien,
} from "../public/donnees";

/** Forme réelle d'un refus des vues publiques, recopiée du serveur. */
function refusDuServeur(erreur: string, code: string, statut = 400): Response {
  return {
    ok: false,
    status: statut,
    json: async () => ({ erreur, code }),
  } as unknown as Response;
}

describe("les refus des routes publiques arrivent entiers jusqu'à l'écran", () => {
  const origine = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = origine;
  });

  it("definirLeMotDePasse rend le message du serveur, pas un repli", async () => {
    globalThis.fetch = vi.fn(async () =>
      refusDuServeur(
        "Ce lien n'est plus valable. Il expire au bout de trois jours.",
        "lien_invalide",
      ),
    ) as unknown as typeof fetch;

    await expect(
      definirLeMotDePasse({ id: "x", jeton: "y", mot_de_passe: "z" }),
    ).rejects.toThrow(/plus valable/);
  });

  it("definirLeMotDePasse rend AUSSI le code, sans quoi rien ne distingue les refus", async () => {
    globalThis.fetch = vi.fn(async () =>
      refusDuServeur("Ce lien n'est plus valable.", "lien_invalide"),
    ) as unknown as typeof fetch;

    const refus = await definirLeMotDePasse({
      id: "x",
      jeton: "y",
      mot_de_passe: "z",
    }).catch((cause: unknown) => cause);

    expect(refus).toBeInstanceOf(RefusInscription);
    expect((refus as RefusInscription).code).toBe("lien_invalide");
  });

  it("un mot de passe faible ne se confond pas avec un lien périmé", async () => {
    globalThis.fetch = vi.fn(async () =>
      refusDuServeur("Ce mot de passe est trop court.", "mot_de_passe_faible"),
    ) as unknown as typeof fetch;

    const refus = (await definirLeMotDePasse({
      id: "x",
      jeton: "y",
      mot_de_passe: "abc",
    }).catch((cause: unknown) => cause)) as RefusInscription;

    // C'est CE code que `MotDePasse.tsx` compare pour décider d'offrir ou non
    // « Demander un nouveau lien ». Le proposer ici enverrait redemander un
    // lien parfaitement valable.
    expect(refus.code).toBe("mot_de_passe_faible");
    expect(refus.message).toContain("trop court");
  });

  it("demanderUnLien rend le message du serveur", async () => {
    globalThis.fetch = vi.fn(async () =>
      refusDuServeur("Trop de demandes. Réessayez dans une heure.", "trop_de_demandes", 429),
    ) as unknown as typeof fetch;

    await expect(demanderUnLien("qui@exemple.fr")).rejects.toThrow(
      /Trop de demandes/,
    );
  });

  it("confirmerLAdresse rend le message du serveur", async () => {
    globalThis.fetch = vi.fn(async () =>
      refusDuServeur("Cette adresse est déjà utilisée par un compte.", "adresse_refusee", 409),
    ) as unknown as typeof fetch;

    await expect(confirmerLAdresse("un-jeton")).rejects.toThrow(
      /déjà utilisée/,
    );
  });

  it("le repli générique ne sert QUE si le serveur n'a rien dit", async () => {
    // Contre-épreuve : le correctif ne doit pas faire disparaître le repli.
    // Une passerelle en panne rend du HTML, pas du JSON — il faut alors une
    // phrase, et le code reste vide pour ne rien laisser croire à l'écran.
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("pas du JSON");
      },
    })) as unknown as typeof fetch;

    const refus = (await definirLeMotDePasse({
      id: "x",
      jeton: "y",
      mot_de_passe: "z",
    }).catch((cause: unknown) => cause)) as RefusInscription;

    expect(refus.message).toContain("502");
    expect(refus.code).toBe("");
  });
});
