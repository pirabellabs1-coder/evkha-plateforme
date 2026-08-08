"""L'annexe des réponses essentielles, rétablie d'après le manuel (§8, pp. 33-34).

Elle avait été supprimée du blueprint EM sur la foi de la version PRÉCÉDENTE du
manuel, au motif que les CHECKs inter-blocs suffisaient à garantir que « toutes
les demandes du client aient une réponse identifiable dans l'étude ».

Le raisonnement était juste et la conclusion fausse. Un CHECK vérifie que la
réponse EXISTE quelque part dans soixante pages ; l'annexe la rend TROUVABLE en
une minute. Ce n'est pas la même promesse — et le manuel de juillet 2026 la
réinstaure explicitement, jusqu'à inscrire sa présence dans son CHECK FINAL.

Ces tests échouent sur le code d'avant : `MARKET_STUDY_CHAPTERS` s'arrêtait au
chapitre 21 et `prompts/etude_marche/chapitre_22.md` n'existait pas.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.blueprints import MARKET_STUDY_CHAPTERS, SectionKind, get_blueprint

NUMERO_ANNEXE = 22


def test_l_etude_de_marche_se_termine_par_l_annexe() -> None:
    """Le test qui échoue sur le code d'avant : le blueprint s'arrêtait à 21."""
    dernier = MARKET_STUDY_CHAPTERS[-1]
    assert dernier.number == NUMERO_ANNEXE, (
        f"le dernier chapitre est le {dernier.number} : l'annexe manque"
    )
    assert dernier.section_kind == SectionKind.ANNEXE
    assert "coup d'œil" in dernier.title


def test_l_annexe_vient_apres_les_sources() -> None:
    """Le manuel : « Après le chapitre 21, ajouter une annexe ».

    L'ordre n'est pas cosmétique : les sources ferment la démonstration,
    l'annexe rouvre sur la décision.
    """
    numeros = [c.number for c in MARKET_STUDY_CHAPTERS]
    assert numeros == sorted(numeros), "chapitres dans le désordre"
    assert numeros[-2:] == [21, NUMERO_ANNEXE]


def test_l_annexe_a_un_prompt_et_il_porte_les_questions_du_manuel() -> None:
    """Un chapitre déclaré sans prompt échouerait à la génération, pas ici."""
    from generation.chapitres.fichiers_prompts import charger_prompt

    prompt = charger_prompt(str(DeliverableType.MARKET_STUDY), NUMERO_ANNEXE)
    assert prompt.strip()

    # Les sept questions que le manuel impose de reprendre, plus la reprise
    # des demandes ecrites du client.
    for attendu in (
        "Le marche est-il suffisamment porteur",
        "La zone choisie est-elle pertinente",
        "Qui sont les cibles prioritaires",
        "Quels produits ou services sont les plus recherches",
        "Quelles obligations peuvent bloquer",
        "trois risques les plus importants",
        "Le projet parait-il viable",
        "actions prioritaires a engager",
    ):
        assert attendu in prompt, f"question absente de l'annexe : {attendu}"


def test_l_annexe_interdit_toute_donnee_nouvelle() -> None:
    """La règle qui empêche l'annexe de devenir une seconde étude.

    Le manuel : « Aucune donnée, conclusion ou recommandation nouvelle ne doit
    apparaître uniquement dans l'annexe. » Sans cette consigne, le modèle
    comblerait les trous qu'il perçoit en résumant — donc en inventant.
    """
    from generation.chapitres.fichiers_prompts import charger_prompt

    prompt = charger_prompt(str(DeliverableType.MARKET_STUDY), NUMERO_ANNEXE)
    assert "aucune nouveaute" in prompt.lower()
    assert "n'invente pas la reponse ici" in prompt


def test_l_annexe_renvoie_vers_des_chapitres_qui_existent() -> None:
    """Un renvoi « Ch. 23 » enverrait le lecteur nulle part.

    L'erreur serait muette : le tableau aurait l'air complet.
    """
    import re

    from generation.chapitres.fichiers_prompts import charger_prompt

    prompt = charger_prompt(str(DeliverableType.MARKET_STUDY), NUMERO_ANNEXE)
    connus = {c.number for c in MARKET_STUDY_CHAPTERS}
    cites = {int(n) for n in re.findall(r"\bch\. ?(\d+)", prompt, re.IGNORECASE)}
    cites |= {int(n) for n in re.findall(r"chapitre (\d+)", prompt)}
    assert cites, "aucun renvoi de chapitre dans l'annexe"
    assert not (cites - connus), f"renvois vers des chapitres inexistants : {cites - connus}"


def test_le_controle_final_couvre_l_annexe() -> None:
    """Le manuel inscrit l'annexe dans son CHECK FINAL.

    Sans cela, une étude livrée sans annexe passait le contrôle : le bloc J ne
    regardait que le chapitre 21.
    """
    from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT

    final = BLOCS_PAR_IDENTIFIANT["J"]
    assert NUMERO_ANNEXE in final.chapitres
    questions = " ".join(final.questions).lower()
    assert "annexe" in questions
    # Les trois autres items ajoutes par le manuel a son controle final.
    assert "35 a 60" in questions
    assert "2024-2026" in questions
    assert "2026-2030" in questions


def test_l_annexe_recoit_la_base_chiffree_consolidee() -> None:
    """Elle doit reprendre les chiffres à l'identique : il lui faut la référence.

    C'est le chapitre qui en a le plus besoin — il lui est interdit d'introduire
    le moindre chiffre nouveau, donc tout ce qu'il écrit doit être vérifiable
    contre la base.
    """
    from generation.strategies.em import _CHAPITRES_CIBLES

    assert NUMERO_ANNEXE in _CHAPITRES_CIBLES


def test_le_blueprint_de_l_annexe_est_resolvable() -> None:
    """Contre-épreuve : un chapitre déclaré doit être retrouvable par le runner."""
    blueprint = get_blueprint(str(DeliverableType.MARKET_STUDY), NUMERO_ANNEXE)
    assert blueprint is not None
    assert blueprint.prompt_key == "em.22.annexe_reponses"
    assert blueprint.max_words, "sans cible de mots, l'annexe peut faire dix pages"
