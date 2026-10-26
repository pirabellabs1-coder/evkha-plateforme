"""Le lien d'un organisme ne mène pas chez un autre organisme.

26/10/2026, étude de marché à l'export relevée par la cliente : « le lien d'un
organisme pointe vers le domaine d'un autre organisme ». Le lecteur qui clique
arrive ailleurs, et le chiffre perd sa source.

`_cles_de_source` traite le nom ET l'adresse comme deux clés du MÊME acteur —
c'est ce qui permet de reconnaître « lettredujardin » derrière
« lettredujardin.substack.com ». Aucun contrôle ne se demandait si les deux
désignaient le même organisme : la question n'était posée nulle part (règle 9).
"""
from __future__ import annotations

from generation.relecture import Document, Reference, Section
from generation.relecture.sources import controler

ENTIER = Reference(livrable="market_study", document_entier=True)


def _document(*lignes: str) -> Document:
    """Un document dont le dernier chapitre est la liste des sources."""
    corps = Section(
        numero="ch. 2", titre="Le marché", chapitre=2,
        paragraphes=["Le marché national pèse 1,2 Md€ (Insee, 2025)."],
    )
    sources = Section(
        numero="ch. 20", titre="Sources et méthodologie", chapitre=20,
        paragraphes=list(lignes),
    )
    return Document(sections=[corps, sources])


def _motifs(document: Document) -> list[str]:
    return [c.detail for c in controler(document, ENTIER)]


def test_le_defaut_mesure_est_attrape() -> None:
    """« Initiative France » cité avec l'adresse de LegalPlace."""
    document = _document(
        "Insee — Enquête emploi 2025 — https://www.insee.fr/fr/statistiques/1234",
        "Initiative France — Baromètre 2025 — https://www.legalplace.fr/guides/barometre",
        "LegalPlace — Guide de la création 2025 — https://www.legalplace.fr/guides/creation",
    )
    motifs = [m for m in _motifs(document) if "mène chez" in m]
    assert len(motifs) == 1, _motifs(document)
    assert "Initiative France" in motifs[0]
    assert "LegalPlace" in motifs[0]
    # Le motif doit dire quoi faire, des deux côtés (règle 2).
    assert "attribue" in motifs[0]


def test_une_source_qui_renvoie_chez_elle_passe() -> None:
    """Contre-épreuve : chaque organisme sur son propre domaine."""
    document = _document(
        "Insee — Enquête emploi 2025 — https://www.insee.fr/fr/statistiques/1234",
        "Initiative France — Baromètre 2025 — https://www.initiative-france.fr/barometre",
        "LegalPlace — Guide de la création 2025 — https://www.legalplace.fr/guides/creation",
    )
    assert [m for m in _motifs(document) if "mène chez" in m] == []


def test_un_portail_partage_n_est_pas_une_erreur() -> None:
    """Contre-épreuve : un rapport de l'Insee déposé sur data.gouv.fr reste de l'Insee.

    Sans cette exception, le contrôle crierait faux sur une citation juste —
    et ce dépôt a mesuré ce que coûte un motif faux (règle 2).
    """
    document = _document(
        "Insee — Base Sirene 2025 — https://www.data.gouv.fr/fr/datasets/sirene",
        "Data — Portail ouvert — https://www.data.gouv.fr/fr/a-propos",
    )
    assert [m for m in _motifs(document) if "mène chez" in m] == []


def test_un_domaine_inconnu_du_document_ne_dit_rien() -> None:
    """Contre-épreuve : on ne juge que ce qu'on sait rattacher.

    Un sigle sur un domaine qui ne ressemble pas à son nom — « BPI » sur
    `bpifrance.fr` — n'est pas une attribution fausse : c'est une attribution
    qu'on ne sait pas trancher.
    """
    document = _document(
        "BPI — Rapport annuel 2025 — https://www.bpifrance.fr/rapport",
        "Insee — Enquête emploi 2025 — https://www.insee.fr/fr/statistiques/1234",
    )
    assert [m for m in _motifs(document) if "mène chez" in m] == []


def test_un_document_sans_chapitre_de_sources_ne_plante_pas() -> None:
    """Contre-épreuve : sans liste, il n'y a rien à rapprocher (règle 1)."""
    document = Document(sections=[
        Section(numero="ch. 2", titre="Le marché", chapitre=2, paragraphes=["Texte."]),
    ])
    assert [m for m in _motifs(document) if "mène chez" in m] == []
