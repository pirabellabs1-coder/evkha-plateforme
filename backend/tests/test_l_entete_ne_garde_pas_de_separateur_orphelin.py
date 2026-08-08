"""Un champ optionnel laissé vide ne doit pas laisser sa ponctuation derrière lui.

**Trouvé sur le dossier réel `b561c2d6`**, l'étude de marché validée par la
cliente le 08/08/2026. Son en-tête portait « ` /  Étude de marché` » — une barre
oblique sans rien à sa gauche, répétée sur **soixante-dix pages**. Aucune suite
de tests ne l'avait vu ; il a fallu ouvrir le `.docx` et lire `word/header1.xml`
(règle 7).

## Pourquoi le garde-fou existant n'a rien gardé

`rendre_etude` écrivait `marque.get("nom", "—")`. Ce repli **n'a jamais pu se
déclencher** : `marque_du_job` pose toujours la clé `nom`, avec `""` quand le
client n'a pas rempli `NOM_ENTREPRISE` — champ optionnel, `extract_branding` le
confirme. Or `dict.get` ne regarde que l'ABSENCE d'une clé, jamais le vide de sa
valeur. Une valeur par défaut qui ne se déclenche jamais est pire qu'absente :
elle donne à la lecture l'impression que le cas est traité.

## La classe, pas le cas

La correction ne teste pas `nom` (règle 4) : **tout repère vide emporte le
séparateur qui le borde**, des deux côtés. Le jour où le gabarit portera
`{{ client }}  /  {{ titre }}  /  {{ date }}`, aucune ligne n'est à écrire.

Et la contre-épreuve compte autant que l'épreuve (règle 6) : un titre qui
contient LUI-MÊME une barre oblique doit traverser intact. Une correction qui
supprimerait toutes les barres obliques ferait passer le premier test et
mutilerait un document correct.
"""
from __future__ import annotations

import pytest

from generation.rendu_word.depuis_json import substituer_reperes
from generation.rendu_word.gabarit import charger_gabarit

GABARIT_ENTETE = "{{ client }}  /  {{ titre_document }}"


def test_un_nom_vide_emporte_sa_barre_oblique() -> None:
    """Le défaut exact du dossier `b561c2d6`."""
    rendu = substituer_reperes(
        GABARIT_ENTETE, {"{{ client }}": "", "{{ titre_document }}": "Étude de marché"}
    )

    assert rendu == "Étude de marché"
    assert "/" not in rendu


def test_le_cote_droit_vide_emporte_aussi_sa_barre() -> None:
    """La règle vaut des deux côtés, sinon elle ne vaut que pour l'exemple vu."""
    rendu = substituer_reperes(
        GABARIT_ENTETE, {"{{ client }}": "Maison Lorel", "{{ titre_document }}": ""}
    )

    assert rendu == "Maison Lorel"


def test_deux_champs_vides_ne_laissent_rien() -> None:
    rendu = substituer_reperes(
        GABARIT_ENTETE, {"{{ client }}": "", "{{ titre_document }}": ""}
    )

    assert rendu == ""


def test_les_deux_champs_remplis_gardent_le_separateur() -> None:
    """Contre-épreuve : le correctif ne doit pas casser le cas nominal."""
    rendu = substituer_reperes(
        GABARIT_ENTETE,
        {"{{ client }}": "Maison Lorel", "{{ titre_document }}": "Étude de marché"},
    )

    assert rendu == "Maison Lorel  /  Étude de marché"


@pytest.mark.parametrize(
    "titre",
    ["Étude B2B/B2C", "Marché 2026/2027", "Prêt-à-porter / accessoires"],
)
def test_une_barre_oblique_DANS_une_valeur_survit(titre: str) -> None:
    """Contre-épreuve, la plus importante : ne pas mutiler un document correct.

    Un correctif qui découperait bêtement sur « / » passerait les tests
    précédents et abîmerait celui-ci. C'est la règle 2 : un remède pire que le
    mal parce qu'il agit sur ce qui n'était pas malade.
    """
    rendu = substituer_reperes(
        GABARIT_ENTETE, {"{{ client }}": "Maison Lorel", "{{ titre_document }}": titre}
    )

    assert rendu == f"Maison Lorel  /  {titre}"


def test_une_valeur_vide_ne_mange_pas_la_barre_d_une_autre_valeur() -> None:
    """Le nettoyage ne doit toucher qu'AUTOUR du repère vide."""
    rendu = substituer_reperes(
        GABARIT_ENTETE, {"{{ client }}": "", "{{ titre_document }}": "Étude B2B/B2C"}
    )

    assert rendu == "Étude B2B/B2C"


def test_le_gabarit_livre_porte_bien_ces_reperes() -> None:
    """Sans ce test, une renommée du repère laisserait les autres verts.

    Ils opèrent sur une chaîne écrite à la main ; celui-ci les rattache au
    fichier `.docx` réellement embarqué — le seul que le client reçoive.
    """
    document = charger_gabarit()
    entetes = [
        paragraphe.text
        for section in document.sections
        for paragraphe in section.header.paragraphs
    ]

    assert any("{{ client }}" in texte for texte in entetes), entetes
    assert any("{{ titre_document }}" in texte for texte in entetes), entetes
