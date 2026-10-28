"""« 24 802 € » et « 99 € par jour ouvré » sont le même seuil de rentabilité.

## Le motif faux

Business plan `ad6bb533` (28/10/2026), gate :

    « Valeurs divergentes pour un même libellé : seuil_rentabilite :
      24 802 € (ch. 3, 4, 9, 10, 11, 16, 17, 18, 19) ; 99 € (ch. 9) »

Et la phrase du chapitre 9 :

    « Ramené au calendrier, le point mort représente 99 € de CA PAR JOUR
      OUVRÉ en 2027, 172 € en … »

24 802 ÷ 250 jours ouvrés ≈ 99. Ce n'est pas une valeur concurrente, c'est la
même, ramenée à la journée — et la phrase le dit explicitement.

`_MOTS_DE_RUPTURE` ne pouvait pas le voir : il regarde ENTRE le libellé et le
montant, et le qualificatif est APRÈS.

## Pourquoi « par an » reste collecté

L'exemption porte sur « par <base>, SAUF l'année ». « 24 802 € par an » EST la
valeur du seuil : l'exempter ferait disparaître la mention de référence, et
plus aucune divergence ne serait détectée contre elle (règle 1 — un contrôle
qui n'a rien à comparer est un échec).

## Ce que le garde-fou change, mesuré

Comparé avec et sans, sur les mêmes quatre phrases, avant d'écrire ce
fichier :

    par an seul        AUCUNE  ->  AUCUNE   (déjà écarté avant, pas par moi)
    sans qualificatif  24 802  ->  24 802   (inchangé)
    par jour ouvré     99      ->  AUCUNE   (la correction)
    par mois           AUCUNE  ->  AUCUNE   (déjà écarté avant)

Une seule ligne de comportement change. C'est ce qu'on demande à un correctif
qui touche un contrôle bloquant.
"""
from __future__ import annotations

from generation.checks_evangeline import collecter_mentions, detecter_divergences

FINE = " "
EURO = "€"


def _euros(montant: str) -> str:
    return f"{montant}{FINE}{EURO}"


#: Recopiées du business plan `ad6bb533`.
CANONIQUE = f"Le seuil de rentabilité est de {_euros('24 802')} en 2027."
PAR_JOUR = (
    "Ramené au calendrier, le point mort représente "
    f"{_euros('99')} de CA par jour ouvré en 2027."
)
VRAIE_DIVERGENCE = f"Le seuil de rentabilité est de {_euros('31 000')} en 2027."


def _divergences(*phrases: str) -> list[str]:
    mentions = []
    for numero, phrase in enumerate(phrases, 1):
        mentions.extend(collecter_mentions(numero, phrase))
    return [d.resume for d in detecter_divergences(mentions)]


def test_le_meme_seuil_ramene_a_la_journee_ne_diverge_pas() -> None:
    """Le cas de `ad6bb533`. Échoue sur le code d'avant, qui rendait 99 € ≠ 24 802 €."""
    assert _divergences(CANONIQUE, PAR_JOUR) == []


def test_un_montant_par_jour_n_est_pas_une_valeur_de_reference() -> None:
    """Seul, il ne doit pas non plus devenir la valeur du libellé.

    Sans cela, un document qui ne donnerait que la valeur journalière ferait
    du 99 € sa référence, et toute mention annuelle divergerait contre elle.
    """
    assert collecter_mentions(9, PAR_JOUR) == []


#: Business plan `81192cb7` (28/10/2026) : la MÊME classe, dite autrement —
#: par un ADJECTIF de période et par l'opération ÉCRITE, sans « par ». Le
#: premier correctif ne lisait que « par <base> », et ce livrable est resté
#: bloqué pour cette seule raison. L'instance au lieu de la classe (règle 4).
CANONIQUE_CAF = f"La CAF 2027 est de {_euros('662')}."
MENSUELLE = (
    "| Capacité de prélèvement mensuelle (CAF ÷ 12) | "
    f"{_euros('55,17')} |"
)


def test_le_meme_montant_dit_mensuel_ne_diverge_pas() -> None:
    """662 ÷ 12 = 55,17. Échoue sur le premier correctif, qui exigeait « par »."""
    assert _divergences(CANONIQUE_CAF, MENSUELLE) == []


def test_une_vraie_divergence_de_caf_est_toujours_vue() -> None:
    """CONTRE-ÉPREUVE sur le même libellé : deux CAF annuelles différentes."""
    divergences = _divergences(CANONIQUE_CAF, f"La CAF 2027 est de {_euros('800')}.")

    assert len(divergences) == 1
    assert "662" in divergences[0]


def test_une_vraie_divergence_est_toujours_vue() -> None:
    """CONTRE-ÉPREUVE : c'est le défaut SYNAPSES — trois seuils concurrents.

    Sans ce test, le correctif aurait pu neutraliser le contrôle au lieu de le
    rendre juste.
    """
    divergences = _divergences(CANONIQUE, VRAIE_DIVERGENCE)

    assert len(divergences) == 1
    assert "24 802" in divergences[0]


def test_la_valeur_sans_qualificatif_reste_la_reference() -> None:
    """CONTRE-ÉPREUVE : le garde-fou ne doit pas avaler la mention canonique."""
    mentions = collecter_mentions(3, CANONIQUE)

    assert len(mentions) == 1
    assert "24 802" in mentions[0].montant_lu
