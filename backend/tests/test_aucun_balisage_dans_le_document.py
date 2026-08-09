"""Un document livré ne contient jamais de balise imprimée en toutes lettres.

**Trouvé par la cliente**, le 08/08/2026, sur les DEUX livrables qu'elle venait
de valider. Vérifié ensuite en ouvrant les fichiers :

    b561c2d6  etude de marche  : 10 balises HTML dans le corps du texte
    09f32041  business plan    : 44 balises HTML dans le corps du texte

Le lecteur voyait, en pleine page :

    <table style="border-collapse:collapse;width:100%;margin:4mm 0;…"><thead>…

## D'où cela venait

Les fichiers d'instruction des chapitres montrent des exemples de tableaux
écrits en HTML. Ils datent du moteur HÉRITÉ, qui produisait du HTML : ces
exemples y étaient justes. Le moteur STRUCTURÉ les reçoit toujours, et le
modèle fait ce qu'on lui montre — il recopie le motif dans un bloc de texte, où
il ne veut plus rien dire.

Aucun contrôle ne regardait cela. Le gate lit le markdown, la conformité juge
les volumes et les formes, la validation croise les identifiants du socle :
personne ne se demandait si le TEXTE contenait du balisage. C'est la règle 9 —
ce que le contrôle ne regarde pas est exactement là où le défaut vit.

## Deux correctifs, et ce test couvre les deux

La CAUSE est traitée dans la consigne (`_SYSTEME` le dit désormais en toutes
lettres). Le GARDE-FOU est ici : même si le modèle recommence, le chapitre est
refusé et rejoué. Une consigne sans contrainte est un vœu — ce projet l'a déjà
mesuré sur les budgets de mots.

## La contre-épreuve compte plus que l'épreuve

Un plan d'affaires est PLEIN de comparaisons légitimes : « panier moyen < 220 €
», « conversion < 2 % », « solde < 2 mois de charges ». Un correctif qui
condamnerait le chevron ferait passer le premier test et mutilerait tous les
seuils d'alerte du document. C'est le défaut de la règle 2, en pire : un remède
qui frappe ce qui n'était pas malade.
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

TABLEAU_HTML = (
    '<table style="border-collapse:collapse;width:100%;margin:4mm 0;'
    'font-size:9pt"><thead><tr><th style="background:#1A1A1A;color:#fff">'
    "Question du client</th></tr></thead></table>"
)


def _chapitre(*blocs: object) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=list(blocs),  # type: ignore[arg-type]
        resume="Un résumé d'essai suffisamment long pour tenir sa borne.",
    )


def test_un_tableau_html_dans_un_paragraphe_est_refuse() -> None:
    """Le défaut exact des deux livrables du 08/08/2026."""
    payload = _chapitre(BlocParagraphe(texte=f"Voici la synthèse. {TABLEAU_HTML}"))

    motifs = motifs_de_balisage(payload)

    assert len(motifs) == 1
    assert "balisage HTML" in motifs[0]
    # Le motif doit permettre de RETROUVER le passage (règle 2).
    assert "table" in motifs[0]


def test_le_motif_nomme_le_bloc_et_le_champ() -> None:
    """Un motif qui ne dit pas où chercher ne fait pas corriger (règle 2)."""
    payload = _chapitre(
        BlocParagraphe(texte="Un paragraphe sain."),
        BlocParagraphe(texte=TABLEAU_HTML),
    )

    motifs = motifs_de_balisage(payload)

    assert "Bloc 1" in motifs[0]
    assert "`texte`" in motifs[0]


def test_le_balisage_est_traque_jusque_dans_les_cellules() -> None:
    """Une balise peut atterrir dans une cellule comme dans un paragraphe.

    Ne regarder que les paragraphes traiterait l'instance et non la classe
    (règle 4) — et laisserait passer le cas le plus probable, puisque c'est
    précisément un TABLEAU que le modèle essayait de produire.
    """
    payload = _chapitre(
        BlocTableau(
            tableau=Tableau(
                entetes=["Poste", "Montant"],
                lignes=[["Loyer", "12 kEUR"], ["Charges", TABLEAU_HTML]],
            )
        )
    )

    assert motifs_de_balisage(payload)


def test_le_balisage_est_traque_dans_les_encadres() -> None:
    payload = _chapitre(
        BlocEncadre(encadre=Encadre(intitule="Point clé", lignes=["Une ligne saine", TABLEAU_HTML]))
    )

    assert motifs_de_balisage(payload)


@pytest.mark.parametrize(
    "texte",
    [
        "Panier moyen < 220 € ou taux de conversion < 2 % sur deux trimestres",
        "Solde de trésorerie < 2 mois de charges fixes",
        "Réachat < 20 % en fin d'an 1 ; remises > 10 % du CA",
        "La marge est > 35 % et le délai < 30 jours",
        "Formule : si CA < seuil alors alerte",
        "Comparatif 2025 > 2026 sur le segment premium",
    ],
)
def test_une_comparaison_legitime_traverse_intacte(texte: str) -> None:
    """LA contre-épreuve : ces phrases viennent des documents réels.

    Elles abondent dans un plan d'affaires — seuils d'alerte, conditions de
    déclenchement. Un correctif qui condamnerait le chevron les détruirait
    toutes, et il passerait pourtant les tests ci-dessus.
    """
    assert motifs_de_balisage(_chapitre(BlocParagraphe(texte=texte))) == []


@pytest.mark.parametrize(
    "texte",
    [
        "Le marché <b>croît</b> de 3 %.",
        "Segment premium<br>Segment accessible",
        '<div class="encadre">Attention</div>',
        "<p>Un paragraphe balisé</p>",
        "<span style='color:red'>Alerte</span>",
    ],
)
def test_les_autres_balises_sont_refusees_aussi(texte: str) -> None:
    """La règle vise le balisage, pas le seul `<table>` observé (règle 4)."""
    assert motifs_de_balisage(_chapitre(BlocParagraphe(texte=texte)))


def test_un_chapitre_sain_ne_produit_aucun_motif() -> None:
    payload = _chapitre(
        BlocParagraphe(texte="Le marché progresse de 3,4 % par an depuis 2022."),
        BlocTableau(tableau=Tableau(entetes=["Poste", "Montant"], lignes=[["Loyer", "12 kEUR"]])),
        BlocEncadre(encadre=Encadre(intitule="À retenir", lignes=["Croissance soutenue"])),
    )

    assert motifs_de_balisage(payload) == []


def test_la_consigne_interdit_explicitement_le_balisage() -> None:
    """La cause, et non seulement le garde-fou.

    Sans cette phrase, le modèle continuerait d'imiter les exemples HTML de ses
    instructions, et chaque chapitre coûterait une reprise. Le garde-fou ne
    doit pas devenir la façon normale de fonctionner.
    """
    from generation.chapitres.runner import _SYSTEME

    assert "AUCUN BALISAGE" in _SYSTEME
    assert "<table" in _SYSTEME
    assert "`tableau`" in _SYSTEME
