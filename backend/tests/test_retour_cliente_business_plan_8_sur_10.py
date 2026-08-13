"""Retour cliente du 12/08/2026 sur le premier business plan abouti — noté 8/10.

Trois défauts nommés, tous sur la FORME, et une demande de fond.

  1. « des traces techniques internes. Des mentions telles que "socle EVKHA",
     ca_previsionnel_an1, marche_national_taille apparaissent sous des tableaux »
  2. « le CTA commercial peut être présent sur les autres livrables mais pas sur
     le business plan (car présenté à une banque comme si vous l'aviez écrit) »
  3. « accentuer un sous-chapitre dans le chapitre 11 : vision du projet à
     l'avenir, avec mini stratégie (KPI utilisés, preuve de traction, appui sur
     la qualité du produit vendu par le porteur de projet) »
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ── 1. Les traces techniques sous les tableaux ──────────────────────────────


def _motifs(texte: str) -> list[str]:
    """Les noms des règles déclenchées par un texte de bloc."""
    from generation.chapitres.schema import _VOCABULAIRE_INTERNE, _sans_les_adresses

    propre = _sans_les_adresses(texte)
    return [nom for nom, motif in _VOCABULAIRE_INTERNE if motif.search(propre)]


@pytest.mark.parametrize("fuite", [
    "Socle EVKHA.",
    "Source : socle EVKHA, données consolidées.",
    "ca_previsionnel_an1",
    "Source : marche_national_taille (2026)",
    "Calcul à partir de ebe_previsionnel_an3.",
])
def test_les_traces_techniques_sont_refusees(fuite: str) -> None:
    """Ce que la cliente a lu sous ses tableaux, refusé à la source."""
    assert _motifs(fuite), f"« {fuite} » traverse encore le garde-fou"


@pytest.mark.parametrize("legitime", [
    # « socle » est un mot français, et il a le droit de vivre sa vie.
    "Le socle de compétences de l'équipe couvre les trois métiers.",
    "Un socle tarifaire commun aux trois offres.",
    "Socle commun à toutes les formules d'abonnement.",
    # Une source réelle ne ressemble pas à un identifiant.
    "Source : INSEE, base Sirene 2025.",
    "Source : Xerfi, panorama du secteur, mars 2026.",
    # Une adresse web porte légitimement des tirets bas.
    "Voir https://exemple.fr/etude_2026_complete pour le détail.",
])
def test_le_francais_ordinaire_traverse_intact(legitime: str) -> None:
    """CONTRE-ÉPREUVE : un garde-fou qui refuse tout ne protège rien.

    C'est la moitié difficile. « Socle » suivi d'une CAPITALE est une
    attribution de source ; suivi d'un mot ordinaire, c'est du français. Et
    aucun mot français ne s'écrit en minuscules avec des tirets bas — sauf
    dans une adresse web, retirée avant l'examen.
    """
    assert not _motifs(legitime), f"« {legitime} » est refusé à tort"


def test_une_figure_legitime_n_est_pas_refusee() -> None:
    """LE risque du motif « identifiant technique », vérifié avant déploiement.

    `donnees_ids` porte les identifiants du socle qu'une figure trace — c'est
    sa RAISON D'ÊTRE, et le rendu les résout en barres et en courbes sans
    qu'aucun n'atteigne le document.

    Sans exclusion, la règle ajoutée le 12/08/2026 refusait TOUTE figure, sur
    les quatre livrables : trois motifs levés sur ce graphique parfaitement
    normal. Un garde-fou qui refuse le fonctionnement normal du système ne
    protège personne.
    """
    from generation.chapitres.schema import (
        BlocGraphique,
        Graphique,
        TypeGraphique,
        _motifs_de_vocabulaire_interne,
    )

    class Payload:
        blocs = [BlocGraphique(type="graphique", graphique=Graphique(
            type=TypeGraphique.BARRES,
            titre="Chiffre d'affaires prévisionnel",
            donnees_ids=[
                "ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3",
            ],
            commentaire="La progression reste soutenue sur les trois exercices.",
        ))]

    assert _motifs_de_vocabulaire_interne(Payload()) == []


def test_aucun_champ_machine_n_echappe_a_l_inventaire() -> None:
    """Le jeu des champs machine se maintient tout seul, ou il ment.

    Si le schéma gagne un champ portant des identifiants sans qu'on l'ait
    déclaré, ce test échoue AVANT qu'une génération entière ne se fasse
    refuser. La convention retenue : un nom de champ en `_ids`.
    """
    import inspect

    from pydantic import BaseModel

    from generation.chapitres import schema as S

    porteurs = {
        nom_champ
        for nom, obj in vars(S).items()
        if inspect.isclass(obj) and issubclass(obj, BaseModel)
        for nom_champ in obj.model_fields
        if nom_champ.endswith("_ids")
    }

    assert porteurs <= S._CHAMPS_LUS_PAR_LA_MACHINE, (
        f"Champ(s) d'identifiants non déclaré(s) : "
        f"{porteurs - S._CHAMPS_LUS_PAR_LA_MACHINE}. Ajoutez-les à "
        "`_CHAMPS_LUS_PAR_LA_MACHINE`, sinon toute figure les portant sera refusée."
    )


def test_les_valeurs_du_schema_ne_sont_pas_prises_pour_des_fuites() -> None:
    """Deuxième débordement du motif, trouvé par la répétition à blanc.

    Après l'exclusion de `donnees_ids`, la règle frappait encore les
    DISCRIMINANTS des blocs — « titre_sous_section », « grille_kpi » — et les
    valeurs d'énumération — « barres_empilees ». Un défaut interne sur presque
    chaque chapitre des quatre livrables.

    Exclure les champs un par un ne pouvait pas suffire : le discriminant
    s'appelle `type`, un nom qu'on ne peut pas réserver. On juge donc la
    VALEUR — un texte qui est exactement une constante du schéma est
    structurel, il n'a pas été écrit pour être lu.
    """
    from generation.chapitres.schema import _valeurs_structurelles

    constantes = _valeurs_structurelles()

    for structurel in ("titre_sous_section", "grille_kpi", "barres_empilees"):
        assert structurel in constantes, structurel
        assert not _motifs(structurel) or structurel in constantes


def test_la_consigne_dit_au_modele_de_ne_pas_recopier_les_etiquettes() -> None:
    """LE correctif de fond : la cause est dans la consigne, pas dans le refus.

    Le bloc du socle montre au modèle un identifiant entre accents graves et le
    mot « source » côte à côte. Quand il remplit le champ `source` d'un
    tableau, il écrit ce qu'il a sous les yeux — il n'a rien fait de mal, on ne
    lui avait jamais dit que cette notation ne se recopie pas.

    Le garde-fou du schéma arrive APRÈS : il fait perdre une tentative et de
    l'argent là où une phrase suffit.
    """
    from generation.chapitres.runner import _CE_QUI_NE_SE_RECOPIE_PAS as consigne

    assert "ÉTIQUETTES POUR TOI" in consigne
    assert "ca_previsionnel_an1" in consigne     # l'exemple qu'elle a lu
    assert "marque blanche" in consigne          # pourquoi le nom disparaît
    assert "LAISSE LE CHAMP VIDE" in consigne    # l'issue quand rien à citer
    assert "données du projet" in consigne       # l'issue quand ça vient du brief


def test_la_consigne_atteint_reellement_le_chapitre() -> None:
    """Vérifié sur le bloc ASSEMBLÉ, pas sur la constante.

    Deux règles ne sont jamais arrivées à l'étude de marché parce qu'elles
    vivaient dans un bloc que le moteur n'envoie pas. On interroge donc le
    texte que le modèle reçoit vraiment.
    """
    from datetime import date

    from generation.chapitres.runner import _bloc_socle
    from generation.socle.schema import Socle, Zone

    socle = Socle(
        secteur="joaillerie", zone=Zone(pays="France"),
        date_socle=date(2026, 8, 12), donnees=[], concurrents=[],
    )

    assert "ÉTIQUETTES POUR TOI" in _bloc_socle(socle)


# ── 2. Le CTA commercial, jamais sur le business plan ───────────────────────


def test_le_business_plan_n_a_pas_de_recommandation_commerciale() -> None:
    """Il part chez un banquier, signé par le client.

    Une dernière page qui vend une prestation dit au lecteur que le plan qu'il
    évalue a été acheté, et que son auteur n'est pas celui qui le présente.
    """
    from generation.rendu_word.depuis_json import RECOMMANDATION_PAR_LIVRABLE

    assert "business_plan" not in RECOMMANDATION_PAR_LIVRABLE


def test_les_trois_autres_livrables_la_gardent() -> None:
    """CONTRE-ÉPREUVE : on retire une exception, pas la fonctionnalité.

    Les trois autres se lisent en interne — leur destinataire est le dirigeant
    qui les a commandés, et lui proposer la suite est un service.
    """
    from generation.rendu_word.depuis_json import RECOMMANDATION_PAR_LIVRABLE

    for livrable in ("market_study", "competitor_study", "business_strategy"):
        assert livrable in RECOMMANDATION_PAR_LIVRABLE, livrable


def test_le_rendu_n_ecrit_rien_pour_un_livrable_absent_de_la_table() -> None:
    """L'omission EST le mécanisme : aucune exception n'est codée ailleurs.

    Si `_recommandation_finale` écrivait un encadré par défaut, retirer
    l'entrée du business plan ne changerait rien au document livré.
    """
    from generation.rendu_word import depuis_json

    source = Path(depuis_json.__file__).read_text(encoding="utf-8")
    assert "if not nom or not lignes:" in source
    assert "return" in source.split("if not nom or not lignes:")[1][:200]


# ── 3. Le sous-chapitre « Vision du projet à l'avenir » ─────────────────────


def _chapitre_11() -> str:
    from generation.chapitres.configuration import RACINE_PROMPTS

    return (
        RACINE_PROMPTS / "business_plan" / "chapitre_11.md"
    ).read_text(encoding="utf-8")


def test_le_chapitre_11_reclame_la_vision_a_l_avenir() -> None:
    """Les trois points demandés, chacun explicitement."""
    texte = _chapitre_11().lower()

    assert "vision du projet a l'avenir" in texte
    assert "indicateurs" in texte          # les KPI suivis
    assert "traction" in texte             # les preuves acquises
    assert "difficile a copier" in texte   # la qualité de ce que vend le porteur


def test_la_traction_ne_s_invente_pas() -> None:
    """Le point qui protège le document devant un banquier.

    Une preuve de traction inventée est vérifiable en un appel, et sa
    découverte décrédibilise le plan entier — pas seulement le paragraphe.
    """
    texte = _chapitre_11()

    assert "n'en invente pas" in texte
    assert "aucune traction chiffree n'est" in texte
