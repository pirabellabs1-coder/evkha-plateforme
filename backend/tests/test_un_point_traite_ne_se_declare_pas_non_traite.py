"""Un sujet déclaré « non traité » alors que le document le traite.

Cliente, 11/08/2026, sur une étude concurrentielle notée 8,5/10 : « les
canaux d'acquisition sont bien analysés au chapitre 3 puis déclarés "non
traités" au chapitre 8 ; on dirait que ça ne l'a pas pris en compte, et avoir
un point non traité n'est pas très acceptable dans une étude qui dit qu'elle
va le faire ».

Elle a raison sur le fond : un point annoncé puis déclaré non traité est pire
qu'un point absent — il fait douter de tout le reste.

## Pourquoi le contrôle vaut pour les QUATRE livrables

Le chapitre de validation des demandes existe partout : étude concurrentielle
8, stratégie 19, étude de marché 22, business plan 20. Le contrôle des
statuts, lui, ne vivait que dans la strategy EC, et il vérifiait seulement
qu'UN statut existe — jamais qu'il soit vrai. La contradiction est une
classe, pas un cas (règle 4).

## Le soin qui compte

Une ligne « non traitée » livre ses mots PORTEURS — six lettres au moins,
hors vocabulaire commun à toute étude (« marché », « client », « analyse »…).
Il en faut DEUX retrouvés ailleurs pour conclure. Un seuil plus bas ferait
crier le contrôle sur chaque statut, et un contrôle qui crie toujours finit
débranché.
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_demandes_contredites


def test_un_sujet_traite_ailleurs_ne_peut_pas_etre_non_traite() -> None:
    """Le cas exact de la cliente : canaux d'acquisition, chapitre 3 puis 8."""
    sections = [
        (3, "Stratégies commerciales", (
            "Les canaux d'acquisition des onze acteurs se répartissent entre "
            "référencement naturel, publicité payante et partenariats."
        )),
        (8, "Validation des demandes", (
            "- Analyser les canaux d'acquisition des concurrents : non traitée."
        )),
    ]

    defauts = detecter_demandes_contredites(sections)

    assert len(defauts) == 1
    assert defauts[0].chapitre == 8
    assert "acquisition" in defauts[0].detail


def test_un_sujet_reellement_absent_reste_declarable_non_traite() -> None:
    """CONTRE-ÉPREUVE : le statut honnête doit rester possible.

    Sans elle, le contrôle interdirait de dire la vérité — et pousserait à
    déclarer « traité » ce qui ne l'est pas, exactement l'inverse du but.
    """
    sections = [
        (3, "Stratégies commerciales", (
            "Les canaux d'acquisition se répartissent entre référencement et "
            "publicité payante."
        )),
        (8, "Validation des demandes", (
            "- Fournir les bilans comptables consolidés des filiales "
            "luxembourgeoises : non traitée, données non publiées."
        )),
    ]

    assert detecter_demandes_contredites(sections) == []


def test_un_seul_mot_commun_ne_suffit_pas() -> None:
    """CONTRE-ÉPREUVE du seuil : un mot long se croise par hasard.

    « Analyser » ou « comparer » apparaissent dans toute étude. Conclure sur
    un seul mot ferait signaler chaque statut honnête.
    """
    sections = [
        (3, "Analyse", "Le référencement naturel domine les acquisitions."),
        (8, "Validation", "- Fournir les organigrammes détaillés : non traitée."),
    ]

    assert detecter_demandes_contredites(sections) == []


def test_le_vocabulaire_commun_a_toute_etude_est_ignore() -> None:
    """« marché », « client », « concurrents » ne distinguent aucun sujet.

    Les compter ferait de chaque statut une contradiction, puisqu'ils sont
    dans tous les chapitres de toutes les études.
    """
    sections = [
        (2, "Marché", "Le marché français compte de nombreux concurrents."),
        (8, "Validation", (
            "- Étudier le marché des concurrents : non traitée."
        )),
    ]

    assert detecter_demandes_contredites(sections) == []


def test_un_statut_traite_n_est_jamais_signale() -> None:
    """CONTRE-ÉPREUVE : seul « non traité » est jugé."""
    sections = [
        (3, "Canaux", "Les canaux d'acquisition reposent sur le référencement."),
        (8, "Validation", "- Analyser les canaux d'acquisition : traitée au ch. 3."),
    ]

    assert detecter_demandes_contredites(sections) == []


def test_le_gate_execute_le_controle_sur_les_quatre_livrables() -> None:
    """La cause, pas seulement la fonction.

    Elle pourrait exister sans être appelée — défaut mesuré six fois sur ce
    projet. Et elle doit être appelée AVANT le retour anticipé de l'étude de
    marché, sinon elle ne vaudrait que pour trois livrables sur quatre.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "generation" / "gate.py"
    ).read_text(encoding="utf-8")

    appel = source.index("detecter_demandes_contredites(triplets)")
    retour_em = source.index("if is_em:\n        return failures")
    assert appel < retour_em, (
        "le contrôle est appelé après le retour anticipé de l'étude de "
        "marché : il ne vaudrait que pour trois livrables sur quatre"
    )


def test_plusieurs_demandes_sur_une_ligne_ne_se_contaminent_pas() -> None:
    """LA contre-épreuve trouvée par la répétition à blanc, gratuitement.

    La doublure empile trois demandes sur une ligne. Prendre les cent-vingt
    signes qui précèdent « non traitée » ramassait la demande PRÉCÉDENTE — « la
    comparaison tarifaire couvre trois acteurs, voie de complément proposée en
    annexe » — soit quatre mots communs, aucun du sujet jugé. Les quatre
    livrables étaient bloqués à tort.

    Le sujet se coupe donc à la frontière de demande, jamais à un nombre de
    signes.
    """
    sections = [
        (2, "Comparatif", (
            "La comparaison tarifaire couvre trois acteurs. Le complément "
            "figure en annexe."
        )),
        (8, "Validation", (
            "Demande 2 — partiellement traitée : la comparaison tarifaire "
            "couvre trois acteurs sur onze, voie de complément proposée en "
            "annexe. Demande 3 — non traitée : la donnée n'est pas publiée."
        )),
    ]

    assert detecter_demandes_contredites(sections) == []


def test_la_justification_qui_suit_le_statut_n_est_pas_le_sujet() -> None:
    """« non traitée : la donnée n'est pas publiée » — la raison n'est pas le sujet.

    La lire comme tel ferait dépendre le verdict de la façon dont on justifie,
    pas de ce qu'on a traité.
    """
    sections = [
        (4, "Méthode", "La donnée publiée par l'institut sert de référence."),
        (8, "Validation", (
            "Fournir les organigrammes : non traitée, la donnée n'est pas "
            "publiée par les acteurs concernés."
        )),
    ]

    assert detecter_demandes_contredites(sections) == []
