"""Une adresse en prose devient le NOM du site, gratuitement.

## La fonction existait, elle n'était pas appliquée à la prose

`rendu_word.composants.source_lisible` remplace une adresse par son domaine
depuis le 09/08/2026, après une demande de la cliente : « il vaut mieux
utiliser des noms de source propres ». Elle garde la source et ne touche que
l'adresse.

Elle n'était appelée qu'à DEUX endroits : la note sous une figure, et la ligne
d'attribution d'un tableau. **Jamais sur la prose.** Mesuré sur l'étude de la
concurrence `e150aade`, sections 5.4 et 6.4 :

    Sources : FEVS, bilan 2025, via Pleinchamp
    (https://www.pleinchamp.com/actualite/en-2025-les-exportations-de-vins)

## Pourquoi réparer plutôt que refuser

Le critère de `chapitres.typographie` : une classe sans AUCUNE exception
légitime. Le cahier des charges de l'étude de la concurrence écrit « ne jamais
intégrer les sources au milieu du texte » depuis le 18/05/2026 — il n'y a donc
pas d'exception, et la réparation ne perd rien puisque le nom du site reste.

Refuser coûterait une reprise payée par chapitre concerné. La répétition à
blanc du 28/10/2026 l'avait chiffré : deux tentatives brûlées sur un chapitre
dont le modèle réécrivait la même ligne.

Ces tests échouent sur le code d'avant : `_raccourcir_les_adresses` n'existait
pas et `reparer_typographie` ne voyait aucune adresse.
"""
from __future__ import annotations

from generation.chapitres.schema import BlocParagraphe, ChapitrePayload
from generation.chapitres.typographie import reparer_typographie

EN_PROSE = (
    "Sources : FEVS, bilan 2025, via Pleinchamp "
    "(https://www.pleinchamp.com/actualite/en-2025-les-exportations-de-vins)."
)


def _payload(titre: str, *paragraphes: str, **extra: object) -> ChapitrePayload:
    return ChapitrePayload.model_validate({
        "chapitre": 6,
        "titre": titre,
        "accroche": "Trois acteurs se détachent du panel.",
        "blocs": [{"type": "paragraphe", "texte": p} for p in paragraphes],
        "resume": "Le chapitre compare les onze acteurs du panel et leurs prix.",
        **extra,
    })


def _prose(payload: ChapitrePayload) -> list[str]:
    return [b.texte for b in payload.blocs if isinstance(b, BlocParagraphe)]


def test_l_adresse_devient_le_nom_du_site() -> None:
    payload = _payload("Estimation des chiffres d'affaires", EN_PROSE)
    reparer_typographie(payload)
    [texte] = _prose(payload)

    assert "https://" not in texte
    # La SOURCE reste : c'est tout l'intérêt, et c'est ce qu'elle a demandé.
    assert "FEVS, bilan 2025" in texte
    assert "pleinchamp.com" in texte


def test_le_chapitre_des_sources_garde_ses_adresses() -> None:
    """Contre-épreuve : le cahier des charges y veut « nom + URL »."""
    payload = _payload("Sources et méthodologie", EN_PROSE)
    reparer_typographie(payload)

    assert "https://www.pleinchamp.com" in _prose(payload)[0]


def test_l_annexe_des_chiffres_garde_ses_adresses() -> None:
    """Contre-épreuve : son titre ne contient pas « source », et c'est pourtant cela."""
    from generation.rendu_word.annexe_chiffres import TITRE

    payload = _payload(TITRE, EN_PROSE)
    reparer_typographie(payload)

    assert "https://www.pleinchamp.com" in _prose(payload)[0]


def test_une_sous_section_d_annexe_garde_ses_adresses() -> None:
    """Contre-épreuve trouvée par la répétition à blanc : « B — Sources par acteur »."""
    payload = ChapitrePayload.model_validate({
        "chapitre": 4,
        "titre": "Positionnement et annexes",
        "accroche": "Les annexes rassemblent la matière brute.",
        "blocs": [
            {"type": "titre_sous_section", "numero": "Annexe",
             "intitule": "B — Sources par acteur"},
            {"type": "paragraphe", "texte": EN_PROSE},
        ],
        "resume": "Les annexes rassemblent la grille tarifaire et les sources.",
    })
    reparer_typographie(payload)

    assert "https://www.pleinchamp.com" in _prose(payload)[0]


def test_un_chapitre_sans_adresse_n_est_pas_touche() -> None:
    """Contre-épreuve : la forme NORMALE d'une source nommée."""
    propre = "Sources : FEVS, bilan 2025 ; Team France Export, 2025."
    payload = _payload("Estimation", propre)
    reparer_typographie(payload)

    # La passe pose la fine insécable avant « : » et « ; » — c'est son travail
    # depuis bien avant, et ce n'est pas une adresse. On compare les LETTRES.
    assert _prose(payload)[0].replace(" ", " ") == propre


def test_la_reparation_est_idempotente() -> None:
    payload = _payload("Estimation", EN_PROSE)
    reparer_typographie(payload)
    une = _prose(payload)[0]
    reparer_typographie(payload)

    assert _prose(payload)[0] == une


def test_la_relecture_ne_trouve_plus_rien_apres_la_reparation() -> None:
    """Le point de tout l'exercice : plus de reprise payée pour cette classe.

    La réparation tourne AVANT le contrôle (`chapitres.runner`), donc le
    contrôle ne doit plus avoir de quoi faire reprendre le chapitre.
    """
    from generation.relecture import Reference, document_du_chapitre, relire

    payload = _payload("Estimation des chiffres d'affaires", EN_PROSE)
    reparer_typographie(payload)
    constats = relire(document_du_chapitre(payload), Reference())

    assert not [c for c in constats if c.classe == "source" and c.grave], [
        c.motif() for c in constats
    ]
