"""Le document est-il ecrit en francais, partout ?

Deux defauts releves par la cliente le 18/08/2026, sur deux documents
differents, et de meme nature : le TEXTE lui-meme est abime.

  - Etude de marche `f0064333` : « presence notamment du caractere 「標」, qui
    ne doit evidemment pas apparaitre dans le document final ». U+6A19, au
    milieu d'une phrase, colle au mot precedent :

        …verront probablement l'emergence de標 reperes de prix et de qualite…

  - Business plan `256e63d8` : « beaucoup de texte depourvu d'accents dans le
    chapitre remuneration : Remuneration, annee, securite, coherence, elevee ».
    Trente-trois mots, et la meme zone ecrit « 1500 EUR/mois » la ou le
    document ecrit « € » partout ailleurs.

Aucun controle ne regardait le texte a ce niveau : ils jugeaient sa structure,
ses chiffres, ses sources et sa longueur — jamais ses lettres.

## Calibrage

Les seuils viennent des QUATRE documents reels du 17/08/2026, pas d'une
intuition : le chapitre fautif du business plan porte 33 mots desaccentues, et
le maximum de tous les autres chapitres des quatre documents — chapitres
Sources exclus — est de TROIS.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class Section:
    number: int
    title: str
    body: str


# ── 1. Un caractere d'une autre ecriture ─────────────────────────────────────


def test_l_ideogramme_du_chapitre_4_est_signale() -> None:
    """La phrase EXACTE du document livre.

    Echoue sur le code d'avant : aucun controle ne lisait les caracteres.
    """
    from generation.checks_post_rendu import detecter_caracteres_etrangers

    trouves = detecter_caracteres_etrangers([Section(
        4, "Défis et opportunités",
        "les prochaines années verront probablement l'émergence de標 repères "
        "de prix et de qualité que les premiers entrants pourront fixer.",
    )])
    assert len(trouves) == 1
    assert trouves[0].caractere == "標"
    assert "6A19" in str(trouves[0])
    assert "repères de prix" in str(trouves[0])


@pytest.mark.parametrize("texte", [
    "Le 1ᵉʳ trimestre 2026 ouvre la période, le 4ᵉ la referme.",
    "La marge σ reste stable, le coefficient β est mesuré à 0,4.",
    "Une dose de 5 µg par litre, à 20 °C.",
    "Le marché français pèse 30 000 M€ en 2026, en croissance de 6 % par an.",
])
def test_la_typographie_francaise_legitime_ne_declenche_rien(texte: str) -> None:
    """Contre-epreuve, et elle a servi.

    La premiere version signalait « ᵉ » et « ʳ » — les exposants ordinaux
    francais — parce que leur nom Unicode ne commence pas par LATIN. QUARANTE
    motifs sur la strategie `f8a29b66`, un document correct : le controle ecrit
    pour retirer UN caractere parasite en aurait produit quarante faux le jour
    de sa mise en service (regle 2).
    """
    from generation.checks_post_rendu import detecter_caracteres_etrangers

    assert detecter_caracteres_etrangers([Section(1, "Chapitre", texte)]) == []


@pytest.mark.parametrize("intrus", ["標", "д", "أ", "本"])
def test_les_autres_ecritures_restent_signalees(intrus: str) -> None:
    """Ideogramme, cyrillique, arabe : la regle porte sur la CLASSE."""
    from generation.checks_post_rendu import detecter_caracteres_etrangers

    trouves = detecter_caracteres_etrangers(
        [Section(1, "Chapitre", f"Le marché de{intrus} repères progresse.")]
    )
    assert len(trouves) == 1


# ── 2. Un chapitre produit sans accents ──────────────────────────────────────


REMUNERATION = (
    "| Absence totale de remuneration annee 1 | Fragilise le porteur sans "
    "securiser davantage la tresorerie deja provisionnee | Ecartee |\n"
    "| Remuneration modeste et progressive, indexee sur la montee en charge "
    "du chiffre d'affaires | Coherente avec un chiffre d'affaires en "
    "construction | Retenue |\n"
    "| Arbitrage salaire/dividendes | Premature avant un premier exercice "
    "complet sous statut de societe | A examiner |\n"
    "| Palier 2 | 1 300 EUR/mois | Atteinte d'un rythme proche de 34 "
    "abonnements actifs moyens en annee 2 | Report possible |\n"
    "| Direction, methodologie, qualite, commercial | Fondatrice, aucun "
    "recrutement prevu | Couvert par la remuneration du dirigeant |\n"
    "La securite du modele repose sur une remuneration elevee mais differee, "
    "coherente avec la periode de demarrage et la notoriete acquise.\n"
)

RESTE_DU_DOCUMENT = (
    "La rémunération du dirigeant suit la montée en charge du chiffre "
    "d'affaires. La cohérence de l'année 2 dépend de la sécurité de la "
    "trésorerie, déjà provisionnée. La méthodologie retenue est cohérente "
    "avec la période de démarrage, la société étant prévue début 2027, et "
    "la notoriété acquise reste élevée. Le coût prévisionnel est budgété.\n"
)


def test_le_chapitre_remuneration_est_signale() -> None:
    """Echoue sur le code d'avant : rien ne comparait le document a lui-meme."""
    from generation.checks_post_rendu import detecter_chapitres_desaccentues

    trouves = detecter_chapitres_desaccentues([
        Section(1, "Résumé exécutif", RESTE_DU_DOCUMENT),
        Section(18, "Politique de rémunération", REMUNERATION),
    ])
    assert len(trouves) == 1
    assert trouves[0].chapitre == 18
    assert "annee" in trouves[0].mots
    assert "remuneration" in trouves[0].mots or "Remuneration" in trouves[0].mots


def test_un_document_correctement_accentue_ne_declenche_rien() -> None:
    """Contre-epreuve : mesuree sur trois des quatre livrables reels."""
    from generation.checks_post_rendu import detecter_chapitres_desaccentues

    assert detecter_chapitres_desaccentues([
        Section(1, "Résumé exécutif", RESTE_DU_DOCUMENT),
        Section(2, "Genèse du projet", RESTE_DU_DOCUMENT),
    ]) == []


def test_les_participes_ne_comptent_pas_pour_des_fautes() -> None:
    """Contre-epreuve : « adresse » et « adressé » sont deux mots francais.

    Sans cette distinction le controle relevait 75 « fautes » sur le business
    plan et 36 sur une etude de marche saine — du bruit, pas un signal. Le
    discriminant est la POSITION de l'accent : interne, jamais finale.
    """
    from generation.checks_post_rendu import detecter_chapitres_desaccentues

    prose = (
        "Le chiffre adressé au comité est chiffré et daté. La limite limitée "
        "au périmètre reste une limite. Les postes classés se classent par "
        "ordre. Le montant constitué constitue la base, et la base cible les "
        "segments ciblés, notés et mesurés. Le dossier phasé se phase en "
        "trois. Les acteurs activés restent actifs.\n"
    ) * 3
    assert detecter_chapitres_desaccentues([
        Section(1, "Chapitre", prose),
        Section(2, "Chapitre", prose),
    ]) == []


def test_un_chapitre_de_sources_n_est_pas_juge() -> None:
    """Contre-epreuve : les sources portent titres anglais, noms propres, URL.

    Mesure reelle : le chapitre « Sources et methodologie » de l'etude de
    marche du 17/08 en porte treize, sans qu'aucun accent manque a la prose.
    """
    from generation.checks_post_rendu import detecter_chapitres_desaccentues

    assert detecter_chapitres_desaccentues([
        Section(1, "Résumé exécutif", RESTE_DU_DOCUMENT),
        Section(21, "Sources et méthodologie", REMUNERATION),
    ]) == []


def test_les_deux_motifs_sont_reparables_par_la_boucle() -> None:
    """Un motif que la boucle ne sait pas traiter part tel quel chez le client.

    Echoue sur le code d'avant : ces deux checks n'existaient pas, donc ne
    figuraient pas dans la liste des defauts regenerables.
    """
    from generation.correction import _CHAPTER_LEVEL_CHECKS, _CHECK_LABELS

    for check in ("caractere_etranger", "chapitre_desaccentue"):
        assert check in _CHAPTER_LEVEL_CHECKS
        assert check in _CHECK_LABELS
