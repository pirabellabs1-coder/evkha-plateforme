"""Quatre mots de trop ne doivent pas détruire une étude.

La seconde génération réelle est morte au **chapitre 5**, après quatre
chapitres écrits et payés (0,277 €), sur ce motif :

    Le résumé fait 254 mots ; attendu entre 150 et 250. Il est relu par tous
    les chapitres suivants : trop court il perd des chiffres, trop long il
    sature leur contexte.

Le motif dit lui-même à quoi sert la borne. **Raccourcir atteint exactement ce
but** ; refuser le chapitre ne l'atteint pas — il le détruit, et l'étude avec,
puisque le runner de production ne réessaie pas.

C'est le troisième défaut de la même famille sur ce dossier : une déviation
dimensionnelle, réparable, traitée comme une rupture de contrat. La différence
entre les deux, c'est qu'une réparation est possible et qu'elle rend le
résultat conforme au but poursuivi.

Ce qui n'est PAS réparé : un résumé trop COURT. On ne peut pas inventer le
contenu manquant, et prétendre le contraire serait faire taire un contrôle sans
rien corriger (règle 1).
"""
from __future__ import annotations

from generation.chapitres.schema import raccourcir_le_resume, valider_chapitre


class _Payload:
    """Porteur minimal, avec les seuls champs que les deux fonctions lisent.

    Construire un `ChapitrePayload` complet demanderait des blocs, des données
    et des graphiques qui n'ont aucun rapport avec ce qu'on vérifie ici — et
    le test échouerait sur le décor plutôt que sur son objet (règle 2).
    """

    def __init__(self, resume: str, *, chapitre: int = 1) -> None:
        self.resume = resume
        self.chapitre = chapitre
        self.donnees_utilisees: list[str] = []
        self.sous_titres: list[object] = []


def _mots(nombre: int) -> str:
    return " ".join(f"mot{i}" for i in range(nombre))


# ── Ce qui est réparé ────────────────────────────────────────────────────────


def test_un_resume_de_quatre_mots_trop_long_est_raccourci() -> None:
    """Le cas exact qui a tué l'étude : 254 mots pour 250."""
    payload = _Payload(_mots(254))

    mention = raccourcir_le_resume(payload, maximum=250)

    assert mention, "aucune mention : la reparation serait silencieuse"
    assert len(payload.resume.split()) <= 250


def test_la_reparation_est_dite_et_non_silencieuse() -> None:
    """Une réparation muette laisserait croire que le modèle respecte la borne.

    Le prompt continuerait alors de produire des résumés hors borne sans que
    personne ne le sache — et la mesure de la dérive serait perdue.
    """
    payload = _Payload(_mots(300))

    mention = raccourcir_le_resume(payload, maximum=250)

    assert "300" in mention and "250" in mention


def test_la_coupe_cherche_une_frontiere_de_phrase() -> None:
    """Le résumé est LU par les chapitres suivants.

    Couper au mot près rendrait un texte qui s'interrompt au milieu d'une
    idée, et cette idée tronquée serait relue vingt fois.
    """
    phrase = "Le marché parisien pèse deux milliards. " * 40
    payload = _Payload(phrase)

    raccourcir_le_resume(payload, maximum=100)

    assert payload.resume.endswith("."), payload.resume[-60:]


def test_une_coupe_de_phrase_trop_gourmande_est_refusee() -> None:
    """Contre-épreuve : mieux vaut un mot coupé qu'un résumé amputé de moitié.

    Si la dernière frontière de phrase se trouve très tôt, s'y arrêter
    sacrifierait les chiffres que ce résumé doit transmettre — ce que la borne
    cherche justement à préserver.
    """
    payload = _Payload("Court. " + _mots(400))

    raccourcir_le_resume(payload, maximum=250)

    assert len(payload.resume.split()) > 125, (
        "la coupe a la phrase a sacrifie la moitie du resume"
    )


# ── Ce qui n'est PAS réparé ──────────────────────────────────────────────────


def test_un_resume_dans_la_borne_n_est_pas_touche() -> None:
    """Contre-épreuve : on ne réécrit pas ce qui va bien."""
    original = _mots(200)
    payload = _Payload(original)

    assert raccourcir_le_resume(payload, maximum=250) == ""
    assert payload.resume == original


def test_un_resume_trop_court_reste_un_motif_de_rejet() -> None:
    """On ne peut pas inventer le contenu manquant.

    Le faire taire serait exactement le défaut de la règle 1 : une réparation
    qui ne répare rien mais éteint le contrôle.
    """
    payload = _Payload(_mots(80))

    raccourcir_le_resume(payload, maximum=250)
    motifs = valider_chapitre(
        payload,
        numero_attendu=1,
        identifiants_socle=frozenset(),
        resume_mots_min=150,
        resume_mots_max=250,
    )

    assert any("résumé" in m.lower() for m in motifs), (
        "un resume trop court doit rester un motif : rien ne peut le reparer"
    )


def test_le_runner_repare_avant_de_juger() -> None:
    """La propriété structurelle : l'ordre des deux gestes EST le correctif.

    Réparer après la validation ne servirait à rien — le chapitre serait déjà
    refusé. Vérifier la fonction isolément ne dirait rien de cet ordre
    (règle 7).
    """
    import inspect

    from generation.chapitres import runner

    source = inspect.getsource(runner.generer_chapitre)

    assert source.index("raccourcir_le_resume") < source.index("valider_chapitre("), (
        "la reparation intervient APRES le jugement : elle ne sert a rien"
    )
