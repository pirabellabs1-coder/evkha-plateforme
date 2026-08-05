"""Le business plan doit suivre les vingt chapitres de son document de référence.

Source : « Systeme EVKHA — Business Plans — V1 FINALE », 133 pages, remis le
05/08/2026. Ses SECTIONS DÉTAILLÉES font foi, pas son sommaire : les deux se
contredisent à partir du chapitre 17 — le sommaire donne 17 Rémunération /
18 Risques, les sections détaillées l'inverse. Écart signalé à la cliente.

Deux écarts corrigés, tous deux vérifiés avant d'y toucher.

1. **Les chapitres 14+15 et 16+17 étaient fusionnés.** Ces fusions dataient
   d'une demande cliente de juillet 2026 ; le document V1 FINALE les redétaille
   comme chapitres distincts. Rien n'a été inventé pour les défaire : les
   sections `bp.14.investissements` et `bp.15.plan_financement` portaient déjà
   leur contenu et redeviennent les chapitres qu'elles étaient.

2. **La Politique de rémunération n'existait nulle part.** Vérifié sur les vingt
   prompts : les trois seules occurrences de « dirigeant » portaient sur son
   parcours, son rôle et son statut social — jamais sur ce qu'il se verse.
   Aucune mention du montant, du calendrier, des charges sociales, de
   l'arbitrage salaire/dividendes ni du maintien de l'ARE. Or une rémunération
   absente du modèle financier rend le prévisionnel incomplet, et c'est
   exactement ce qu'un banquier regarde.

Ces tests échouent sur le code d'avant : le blueprint comptait vingt entrées et
`bp.18.remuneration` n'existait pas.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.blueprints import (
    BUSINESS_PLAN_CHAPTERS,
    SECTION_MAX_WORDS,
    SectionKind,
)
from generation.chapitres.configuration import type_document
from generation.chapitres.fichiers_prompts import chapitres_sans_prompt, charger_prompt
from generation.prompt_library import prompt_instruction

BP = str(DeliverableType.BUSINESS_PLAN)

#: Les vingt chapitres du document, dans l'ordre de ses sections détaillées.
ATTENDUS: dict[int, str] = {
    1: "Résumé exécutif",
    2: "Présentation du porteur de projet",
    3: "Genèse du projet",
    4: "Présentation de l'activité",
    5: "Positionnement et concept",
    6: "Analyse de marché (synthèse)",
    7: "Analyse concurrentielle",
    8: "Offre commerciale",
    9: "Modèle économique et Business Model Canvas",
    10: "Stratégie commerciale et marketing",
    11: "Stratégie de développement",
    12: "Organisation et moyens",
    13: "Structure juridique et réglementaire",
    14: "Investissements et besoins",
    15: "Plan de financement",
    16: "Prévisionnel financier",
    17: "Risques et facteurs de sécurisation",
    18: "Politique de rémunération",
    19: "Conclusion",
    20: "Annexes",
}


def test_le_business_plan_compte_vingt_deux_entrees() -> None:
    """Fiche projet + les vingt chapitres du document + sources."""
    assert len(BUSINESS_PLAN_CHAPTERS) == 22
    numeros = [c.number for c in BUSINESS_PLAN_CHAPTERS]
    assert numeros == list(range(22)), f"numérotation trouée : {numeros}"


def test_chaque_chapitre_du_document_a_sa_place() -> None:
    """Le test qui échoue sur le code d'avant, sur les deux écarts à la fois."""
    par_numero = {c.number: c.title for c in BUSINESS_PLAN_CHAPTERS}
    for numero, titre in ATTENDUS.items():
        assert par_numero.get(numero) == titre, (
            f"chapitre {numero} : « {par_numero.get(numero)} » "
            f"au lieu de « {titre} »"
        )


def test_la_politique_de_remuneration_existe_et_est_complete() -> None:
    """Le chapitre qui manquait, et ce sans quoi il ne servirait à rien.

    Un chapitre déclaré mais vague ne vaut pas mieux que son absence : c'est le
    coût complet, charges comprises, qui rend une rémunération crédible.
    """
    prompt = charger_prompt(BP, 18)
    for attendu in (
        "COUT COMPLET",
        "charges sociales",
        "arbitrage salaire/dividendes",
        "ARE",
        "calendrier",
        "securisation financiere",
    ):
        assert attendu in prompt, f"exigence absente du chapitre 18 : {attendu}"


def test_les_deux_chapitres_defusionnes_gardent_leur_contenu() -> None:
    """Défusionner ne doit rien perdre : les sections portaient déjà le texte."""
    investissements = charger_prompt(BP, 14)
    financement = charger_prompt(BP, 15)

    assert "besoin en fonds de roulement" in investissements.lower()
    assert "tresorerie de securite" in investissements.lower()
    # Le graphique de répartition des ressources vivait dans la section : il
    # doit survivre à la promotion en chapitre.
    assert "Repartition des ressources de financement" in financement
    assert "apport personnel" in financement.lower()
    assert "emprunt" in financement.lower() or "financements externes" in financement.lower()


def test_les_deux_totaux_financiers_sont_declares_egaux() -> None:
    """Le point de cohérence que le document nomme : besoins 14 = ressources 15.

    Sans cette consigne, les deux chapitres sont écrits séparément et rien
    n'oblige leurs totaux à se rejoindre — le défaut de cohérence transversale
    que le document reproche justement aux business plans générés.
    """
    for numero in (14, 15):
        prompt = charger_prompt(BP, numero)
        assert "coherence a verifier" in prompt.lower(), (
            f"le chapitre {numero} ne déclare aucun point de cohérence"
        )
        assert "chapitre 1" in prompt.lower()


#: Ce que `prompt_instruction` rend quand elle ne connaît pas la clé. Le repli
#: est SILENCIEUX : une clé mal orthographiée produit un chapitre écrit sur une
#: consigne générique d'une ligne, sans que rien ne le signale.
REPLI_GENERIQUE = (
    "Redige ce chapitre selon la methode EVKHA : donnees chiffrees, "
    "sourcees, concretes et exploitables, ton mentor."
)


def test_aucune_cle_ne_renvoie_a_un_chapitre_disparu() -> None:
    """Les dispatchers des fusions doivent partir avec elles (règle 5).

    Les laisser aurait maintenu deux clés vers un chapitre qui n'existe plus,
    et la relecture suivante aurait cru le chapitre encore fusionné.

    On interroge la TABLE et non `prompt_instruction` : celle-ci ne dit jamais
    « je ne connais pas », elle rend un repli générique.
    """
    from generation.prompt_library import BUSINESS_PLAN_PROMPTS

    for morte in (
        "bp.14.besoin_financement",
        "bp.15.previsionnel_tresorerie",
        "bp.17.budget_tresorerie",
        "bp.18.risques_securisation",
    ):
        assert morte not in BUSINESS_PLAN_PROMPTS, f"clé morte encore déclarée : {morte}"


def test_aucun_chapitre_ne_tombe_sur_la_consigne_de_repli() -> None:
    """Le piège que la renumérotation rendait facile à déclencher.

    `prompt_instruction` ne lève pas sur une clé inconnue : elle rend une
    consigne générique d'une ligne. Un `prompt_key` mal renommé produirait donc
    un chapitre entier écrit sans consigne, et le livrable aurait l'air complet
    (règle 1). On vérifie que rien, dans le blueprint, n'y tombe.
    """
    fautifs = [
        f"{c.number} ({c.prompt_key})"
        for c in BUSINESS_PLAN_CHAPTERS
        if prompt_instruction(c.prompt_key) == REPLI_GENERIQUE
    ]
    assert not fautifs, "chapitres sans instruction propre : " + ", ".join(fautifs)


def test_les_sections_declarees_ont_toutes_leur_instruction() -> None:
    """Une section sans texte ferait échouer le chapitre en pleine génération."""
    for chapitre in BUSINESS_PLAN_CHAPTERS:
        for section in chapitre.sections or ():
            assert prompt_instruction(section), (
                f"chapitre {chapitre.number} : section « {section} » sans instruction"
            )
            assert section in SECTION_MAX_WORDS, (
                f"section « {section} » sans budget de mots : elle héritera "
                "de celui du chapitre, qui vaut pour le tout"
            )


def test_chaque_chapitre_declare_a_son_fichier_de_prompt() -> None:
    """Contre-épreuve de la renumérotation : aucun fichier laissé en arrière."""
    assert chapitres_sans_prompt(type_document(BP)) == []


def test_l_ordre_de_lecture_se_termine_par_l_annexe_puis_les_sources() -> None:
    """Le document place les annexes en 20 ; les sources leur succèdent."""
    deux_derniers = BUSINESS_PLAN_CHAPTERS[-2:]
    assert deux_derniers[0].number == 20
    assert deux_derniers[0].section_kind == SectionKind.ANNEXE
    assert deux_derniers[1].number == 21
    assert deux_derniers[1].section_kind == SectionKind.SOURCES
