"""« Dix risques majeurs » au-dessus de six lignes : l'encadré avait le dernier mot.

Étude de marché à l'export, cliente, 26/10/2026 : « dix risques annoncés, six
présentés » ; « cinq repères annoncés, huit présentés ». Les lignes d'un
encadré partaient à plat dans les paragraphes, et son compte avec : l'intitulé
n'avait rien contre quoi se juger (règle 1), et le contrôle des comptes écartait
explicitement les encadrés (règle 9).
"""
from __future__ import annotations

from generation.relecture import Document, Reference, document_du_chapitre, relire
from generation.relecture.comptages import _comptes_contre_les_encadres


def _document(
    intitule: str, lignes: list[str], *, paragraphe: str = "Du texte.",
) -> Document:
    return document_du_chapitre({
        "chapitre": 12,
        "titre": "Risques",
        "blocs": [
            {"type": "paragraphe", "texte": paragraphe},
            {"type": "encadre", "encadre": {"intitule": intitule, "lignes": lignes}},
        ],
    })


def test_l_encadre_garde_ses_lignes_ensemble() -> None:
    """Sans cela, il n'y a rien à comparer."""
    document = _document("À retenir", ["Opportunité — …", "Limite — …"])
    [encadre] = [e for s in document.sections for e in s.encadres]
    assert encadre.intitule == "À retenir"
    assert encadre.lignes == ("Opportunité — …", "Limite — …")
    # Les lignes restent lisibles par les contrôles de texte.
    assert "Limite — …" in document.texte()


def test_dix_risques_pour_six_lignes_est_signale() -> None:
    [constat] = _comptes_contre_les_encadres(
        _document("Dix risques majeurs", [f"Risque {n}" for n in range(6)])
    )
    assert constat.classe == "comptage"
    assert "10" in constat.detail
    assert "6 ligne" in constat.detail
    # Règle 2 : le lecteur doit retrouver le passage dans le document.
    assert constat.extrait == "Dix risques majeurs"
    # JAMAIS grave : voir `test_un_intitule_correct_ne_commande_rien`.
    assert constat.grave is False


def test_cinq_reperes_pour_trois_lignes_est_signale() -> None:
    [constat] = _comptes_contre_les_encadres(
        _document("Trois repères du lancement", ["a", "b", "c", "d", "e"])
    )
    assert constat.grave is False
    assert "5 ligne" in constat.detail


def test_un_intitule_correct_ne_commande_rien() -> None:
    """Le constat ne doit JAMAIS faire reprendre un chapitre (revue du 27/10/2026).

    Mesuré sur des intitulés corrects : « Les 27 États membres : ce qui
    change » au-dessus de quatre lignes recevait un constat GRAVE dont le
    détail ORDONNAIT d'écrire « quatre ». Le modèle aurait obéi — un motif
    faux qui envoie corriger ce qui était juste, c'est la règle 2 dans sa forme
    la plus coûteuse.

    Aucune règle de surface ne sépare un compte de LIGNES d'un compte du MONDE.
    Le contrôle reste donc un filet, et un filet ne commande pas ; la cause du
    défaut de la cliente est fermée ailleurs, par le plafond déclaré au modèle.
    """
    corrects = [
        ("Les 27 Etats membres : ce qui change", 4),
        ("Les dix pays du panel", 3),
        ("Les 150 distributeurs recenses", 3),
        ("Les 5 forces de Porter appliquees au marche", 6),
    ]
    for intitule, lignes in corrects:
        for constat in _comptes_contre_les_encadres(
            _document(intitule, [f"l{n}" for n in range(lignes)])
        ):
            assert constat.grave is False, f"« {intitule} » ferait reprendre le chapitre"
        # Et son détail ne dicte aucun chiffre à écrire.
        for constat in _comptes_contre_les_encadres(
            _document(intitule, [f"l{n}" for n in range(lignes)])
        ):
            assert "écrire «" not in constat.detail, constat.detail


def test_un_compte_juste_ne_dit_rien() -> None:
    """Contre-épreuve."""
    assert _comptes_contre_les_encadres(
        _document("Trois risques", ["Risque A", "Risque B", "Risque C"])
    ) == []


def test_un_intitule_sans_compte_ne_dit_rien() -> None:
    """Contre-épreuve : l'intitulé courant du document de référence."""
    assert _comptes_contre_les_encadres(
        _document("Opportunité / Limite / Décision", ["a", "b", "c", "d"])
    ) == []


def test_un_nom_qui_ne_se_compte_pas_ne_dit_rien() -> None:
    """Contre-épreuve : « trois ans », « deux fois » ne comptent pas des items."""
    assert _comptes_contre_les_encadres(
        _document("Trois ans pour décider", ["a", "b"])
    ) == []


def test_le_constat_remonte_par_la_relecture() -> None:
    """Le contrôle doit être BRANCHÉ, pas seulement écrit (le défaut de Gamma)."""
    constats = relire(
        _document("Dix risques majeurs", [f"Risque {n}" for n in range(6)]),
        Reference(),
    )
    assert any(
        c.classe == "comptage" and c.extrait == "Dix risques majeurs" for c in constats
    ), [c.motif() for c in constats]
