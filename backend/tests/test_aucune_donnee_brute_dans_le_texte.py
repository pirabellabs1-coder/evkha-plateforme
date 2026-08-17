"""Un format de données n'a rien à faire dans une phrase.

## La demande, et pourquoi elle ne réclame pas d'enquête

Cliente, 09/08/2026 : « du code / CSV brut est visible dans le document ». Puis,
quand j'ai demandé le passage : « tu n'as pas besoin d'avoir le CSV brut, c'est
de faire pour que ça ne figure plus dedans ».

Elle a raison. La cause exacte n'est pas établie et n'a pas besoin de l'être :
c'est la CLASSE qu'on interdit, comme pour le HTML deux jours plus tôt. Un
format de données dans un texte arrive chez le client sous sa forme brute,
quelle que soit la façon dont il y est arrivé (règle 4 — viser la classe, pas
l'exemple).

## Chaque motif est choisi pour ne PAS mordre sur du français

  - trois points-virgules ou plus : une phrase française en porte rarement un,
    jamais trois ;
  - deux barres verticales : c'est une ligne de tableau markdown ;
  - une tabulation : elle ne survit à aucune rédaction normale ;
  - accolade ou crochet suivi d'un guillemet et d'un deux-points : du JSON ;
  - trois accents graves : un bloc de code.

Une énumération française — « le prix, la garantie, la livraison » — emploie des
virgules et traverse intacte. **C'est la contre-épreuve qui compte** : un
correctif qui condamnerait la virgule ferait passer tous les tests ci-dessous et
détruirait la moitié des phrases du document.
"""
from __future__ import annotations

import pytest

from generation.chapitres.schema import (
    BlocEncadre,
    BlocParagraphe,
    BlocTableau,
    ChapitrePayload,
    Encadre,
    Tableau,
    motifs_de_balisage,
)


def _chapitre(*blocs: object) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=list(blocs),  # type: ignore[arg-type]
        resume="Un résumé d'essai suffisamment long pour tenir sa borne.",
    )


@pytest.mark.parametrize(
    ("nom", "texte"),
    [
        ("CSV", "Acteur;Part;CA;Effectif;Note"),
        ("CSV avec valeurs", "Sézane;12%;180 M€;450;4"),
        ("tableau markdown", "| Acteur | Part | CA |"),
        ("tabulation", "Acteur\tPart de marché\tCA"),
        ("JSON", '{"acteur": "Sézane", "part": 12}'),
        ("liste JSON", '[{"nom": "Rouje"}]'),
        ("bloc de code", "```python\nprint(1)\n```"),
    ],
)
def test_un_format_de_donnees_est_refuse(nom: str, texte: str) -> None:
    """Ce sera imprimé tel quel chez le client."""
    motifs = motifs_de_balisage(_chapitre(BlocParagraphe(texte=texte)))

    assert motifs, f"{nom} devrait être refusé"
    assert "imprimé tel quel" in motifs[0]


def test_le_motif_dit_ou_chercher_et_quoi_faire() -> None:
    """Un motif qui ne dit pas quoi corriger ne corrige rien (règle 2)."""
    motifs = motifs_de_balisage(
        _chapitre(BlocParagraphe(texte="Acteur;Part;CA;Effectif"))
    )

    assert "Bloc 0" in motifs[0]
    assert "`texte`" in motifs[0]
    assert "bloc `tableau`" in motifs[0]


def test_les_donnees_brutes_sont_traquees_dans_les_cellules_et_encadres() -> None:
    """Un CSV peut atterrir dans une cellule aussi bien que dans un paragraphe."""
    for payload in (
        _chapitre(
            BlocTableau(
                tableau=Tableau(
                    entetes=["Critère", "Valeur"],
                    lignes=[["Acteurs", "a;b;c;d"]],
                )
            )
        ),
        _chapitre(
            BlocEncadre(
                encadre=Encadre(intitule="À retenir", lignes=["x\ty\tz"])
            )
        ),
    ):
        assert motifs_de_balisage(payload)


# ── LA contre-épreuve : le français normal traverse intact ───────────────────

@pytest.mark.parametrize(
    "texte",
    [
        # LA phrase qui a tué la génération cliente `cc0dfe14` (10/08/2026,
        # 89 minutes de blocage, chapitre 0 en échec). Une énumération à trois
        # points-virgules est la forme NORMALE d'une cellule de tableau ; mes
        # contre-épreuves n'en testaient aucune.
        "Taille du marché français 2026 et part réalisée en ligne ; évolution "
        "et perspectives à 3-5 ans du e-commerce animalier ; segments les plus "
        "porteurs ; barrières à l'entrée identifiées",
        "Le prix ; la garantie ; la livraison ; le service après-vente",
        "Concentrer l'offre sur l'alimentation récurrente et le conseil ; "
        "éviter le catalogue large ; viser l'abonnement dès le lancement",
        "Le prix, la garantie et la livraison pèsent le plus dans la décision.",
        "Trois acteurs dominent : Sézane, Rouje et Ba&sh.",
        "Le marché progresse de 3,4 % ; la part en ligne, elle, double.",
        "Deux segments se dégagent ; un troisième reste marginal.",
        "L'étude retient un panier moyen de 68 € (source : Fevad, 2025).",
        "Les critères sont : notoriété, prix, qualité de service, logistique.",
        "Voir le rapport 2025 de la Fevad, page 12, pour le détail des canaux.",
    ],
)
def test_une_phrase_francaise_normale_survit(texte: str) -> None:
    """Un correctif qui condamnerait la virgule ou le point-virgule isolé
    ferait passer tous les tests ci-dessus et détruirait le document.

    C'est le défaut de la règle 2 — un remède qui frappe ce qui n'était pas
    malade — et c'est exactement ce qui est arrivé ce matin avec une liste de
    mots trop large : elle a tué un chapitre parfaitement juste.
    """
    assert motifs_de_balisage(_chapitre(BlocParagraphe(texte=texte))) == []


# ── Un seul motif par passage, et aucune brèche ──────────────────────────────

_STYLE_HTML = (
    '<table style="border-collapse:collapse;width:100%;margin:4mm 0;'
    'font-size:9pt"><tr><td>Sézane</td></tr></table>'
)


def test_du_html_ne_produit_pas_aussi_un_motif_de_csv() -> None:
    """Une feuille de style porte des points-virgules — ce n'est pas un CSV.

    Le second motif enverrait corriger un fichier de données qui n'existe pas,
    alors que le vrai défaut est le balisage (règle 2 — un motif doit être
    trouvable tel qu'il est écrit).
    """
    motifs = motifs_de_balisage(_chapitre(BlocParagraphe(texte=_STYLE_HTML)))

    assert len(motifs) == 1
    assert "balisage HTML" in motifs[0]


def test_le_html_et_le_csv_ensemble_restent_refuses() -> None:
    """CONTRE-ÉPREUVE du correctif ci-dessus.

    Ignorer les données brutes dans un texte balisé ne doit rien laisser
    passer : le chapitre est rejeté de toute façon, et il est rejoué. Ce test
    échouerait si le `continue` devenait un `return`.
    """
    payload = _chapitre(
        BlocParagraphe(texte=_STYLE_HTML),
        BlocParagraphe(texte="Sézane;12%;180 M€;450"),
    )

    motifs = motifs_de_balisage(payload)

    assert len(motifs) == 2
    assert any("imprimé tel quel" in m and "Bloc 1" in m for m in motifs)


def test_la_consigne_interdit_les_donnees_brutes() -> None:
    """La cause, pas seulement le garde-fou.

    Le contrôle ne doit pas devenir la façon normale de fonctionner : chaque
    refus coûte une reprise.
    """
    from generation.chapitres.runner import _SYSTEME

    assert "AUCUN FORMAT DE DONNÉES" in _SYSTEME
    assert "points-virgules" in _SYSTEME
    assert "JSON" in _SYSTEME
