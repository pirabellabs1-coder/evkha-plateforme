"""Une garantie nommée mais introuvable ne protège personne.

Ce dépôt cite abondamment ses tests dans les commentaires — « X interdit la
combinaison des deux », « voir Y ». C'est une bonne pratique : elle relie une
décision à ce qui la verrouille. Elle ne vaut que si la citation est trouvable.

Deux ne l'étaient pas, découvertes le 08/08/2026 en balayant le dépôt :

- `referentiel.py` renvoyait à un `test_repetition_a_blanc_bp_et_str` qui n'a
  **jamais existé**. Une répétition à blanc est une manipulation, pas un test :
  la citer comme un test faisait croire à une garantie rejouable ;
- `runner.py` citait `test_blueprints_code_execution`. Le test existe et
  protège, mais sous le nom
  `test_aucun_blueprint_ne_combine_sections_et_execution_de_code` — introuvable
  pour qui cherche le nom cité.

Les deux se vérifient en une commande, et personne ne l'avait lancée. C'est la
classe du défaut que ce test ferme, plutôt que ses deux instances (règle 4).
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_DES_TESTS = Path(__file__).resolve().parent

#: Citations qui désignent volontairement un test ABSENT, avec la raison.
#:
#: Chaque entrée documente le sort d'un test disparu — c'est précisément sa
#: valeur, et la supprimer perdrait la réponse à « pourquoi ceci n'est-il plus
#: vérifié ? ». La liste ne peut que rétrécir : le troisième test de ce module
#: échoue si l'un de ces noms redevient réel, ce qui force à retirer la ligne au
#: lieu de la laisser mentir.
#:
#: Ne PAS couper un nom cité sur deux lignes : le contrôle lit le texte, pas
#: l'intention, et une moitié de nom lui est introuvable. C'est ce fichier
#: lui-même qui l'a appris, à son premier lancement.
ABSENCES_ASSUMEES = {
    # Retirés le 08/08/2026 : ils exigeaient du charter des règles supprimées
    # le 24/07/2026 avec l'adoption du manuel Evangeline. Cités dans les
    # docstrings de tête qui conservent leur motif.
    "test_charter_impose_hierarchie_des_sources",
    "test_charter_regles_acronymes_et_tcac_retenu",
    "test_charter_mentionne_le_marqueur_action",
    "test_charter_em_dash_exception_titres",
    "test_charter_impose_source_recente",
    "test_charter_mentionne_les_marqueurs_parseables",
    "test_charter_interdit_la_genericite",
    # Verrouillait l'invariant INVERSE avant la bascule du 06/08/2026 ; remplacé
    # par `test_les_quatre_livrables_sont_couverts`.
    "test_rien_n_a_bascule",
    # N'a jamais existé — voir la docstring de ce module.
    "test_repetition_a_blanc_bp_et_str",
    # Nom fautif corrigé dans `runner.py` le 08/08/2026, et cité là-bas pour
    # expliquer la correction. Le vrai nom est
    # test_aucun_blueprint_ne_combine_sections_et_execution_de_code.
    "test_blueprints_code_execution",
}

#: Dossiers à ne pas balayer. `.claude/worktrees` contient des copies de travail
#: d'autres sessions : y trouver une citation périmée ne dit rien de CE dépôt,
#: et ferait échouer le test sur le travail en cours de quelqu'un d'autre.
IGNORES = (".venv", "__pycache__", ".claude", "node_modules", "staticfiles")


def _noms_de_tests_connus() -> set[str]:
    """Modules et fonctions de test réellement présents."""
    connus = {p.stem for p in DOSSIER_DES_TESTS.glob("test_*.py")}
    for fichier in DOSSIER_DES_TESTS.glob("test_*.py"):
        source = fichier.read_text(encoding="utf-8-sig")
        connus |= set(re.findall(r"^def (test_\w+)", source, re.M))
    return connus


def _citation_trouvable(citation: str, connus: set[str]) -> bool:
    """Un PRÉFIXE suffit.

    Une citation coupée par un backtick — `test_phase46_` — reste parfaitement
    trouvable. Exiger l'égalité stricte produirait une dizaine de faux positifs
    sur des citations correctes, et un contrôle qui crie à tort finit ignoré.
    """
    return any(nom == citation or nom.startswith(citation) for nom in connus)


def _citations_du_depot() -> dict[str, str]:
    """Rend chaque `test_...` cité entre backticks, et où il l'est."""
    citations: dict[str, str] = {}
    for fichier in RACINE.rglob("*.py"):
        if any(part in IGNORES for part in fichier.parts):
            continue
        try:
            source = fichier.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        for citation in re.findall(r"`(test_\w+)", source):
            citations.setdefault(citation, str(fichier.relative_to(RACINE)))
    return citations


def test_le_balayage_trouve_bien_des_citations() -> None:
    """Garde-fou : sans lui, les deux suivants passeraient sur un dict vide.

    Si le motif cessait de correspondre — changement de convention, encodage —
    le contrôle ne dirait plus rien et serait pris pour un succès (règle 1).
    """
    citations = _citations_du_depot()

    assert len(citations) > 20, f"seulement {len(citations)} citations trouvees"
    assert len(_noms_de_tests_connus()) > 100


def test_toute_garantie_citee_est_trouvable() -> None:
    """Le contrôle qui compte."""
    connus = _noms_de_tests_connus()
    introuvables = {
        citation: ou
        for citation, ou in _citations_du_depot().items()
        if citation not in ABSENCES_ASSUMEES and not _citation_trouvable(citation, connus)
    }

    assert not introuvables, (
        "Ces commentaires citent un test qui n'existe pas. Une garantie qu'on "
        "ne peut pas retrouver ne protege personne :\n  "
        + "\n  ".join(f"{c} — cite dans {ou}" for c, ou in sorted(introuvables.items()))
        + "\n\nCorriger le nom, ou ajouter le test a ABSENCES_ASSUMEES avec sa raison."
    )


def test_une_absence_assumee_est_vraiment_absente() -> None:
    """La liste des tolérances ne doit pas survivre à ce qu'elle tolère.

    Sans ce test, un nom réintroduit resterait tolére pour toujours, et la
    prochaine faute de frappe sur ce nom passerait inaperçue. C'est la même
    exigence que pour les prohibitions : une tolérance sans provenance vivante
    est du bruit.
    """
    connus = _noms_de_tests_connus()
    devenus_reels = sorted(n for n in ABSENCES_ASSUMEES if n in connus)

    assert not devenus_reels, (
        f"Ces noms sont redevenus de vrais tests : {devenus_reels}. Les retirer "
        "de ABSENCES_ASSUMEES, sinon la liste ment."
    )
