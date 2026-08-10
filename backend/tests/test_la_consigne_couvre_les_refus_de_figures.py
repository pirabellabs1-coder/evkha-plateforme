"""La consigne doit nommer chaque refus que le rendu applique — sur le prompt ENVOYÉ.

## Ce que la première version de ce fichier vérifiait, et pourquoi c'était vide

Écrite le 08/08/2026 au matin, elle interrogeait `build_system_prompt`. Or ce
prompt **n'atteint pas le moteur qui rend les figures**. `generation/runner.py`
appelle `_produire_avec_reprises` quand le moteur structuré est actif — la
production, `EVKHA_SOCLE_ENABLED=true` — et cette branche ne passe PAS
`system_prompt` ; la chaîne envoie `chapitres/runner._SYSTEME`, qui ne dit rien
des figures.

Le test était donc vert sur une consigne que personne ne reçoit. C'est la règle 1
retournée contre moi : un contrôle qui n'a rien à comparer n'est pas un succès.
Et la règle 6 : il ne pouvait échouer sur aucun code d'avant, puisqu'il ne
regardait pas le chemin où le défaut vit.

Le journal a porté la même erreur : il affirmait que la règle « existe dans la
consigne et n'est pas suivie ». Elle n'existait pas dans la consigne envoyée.
Dix-huit figures abandonnées sur le dossier réel `b561c2d6` — presque toutes
pour « unités hétérogènes », `MEUR, million`, `EUR, MEUR, unite`, `%, MEUR` —
n'étaient pas de la désobéissance. Personne n'avait parlé.

## Ce qu'il vérifie maintenant

`construire_prompt_chapitre`, le prompt réellement transmis, pour chacun des
quatre livrables. Et il vérifie en plus que la NATURE de chaque identifiant y
figure : dire la règle sans donner la matière pour l'appliquer laisserait le
modèle deviner que `unite` est un décompte et `MdEUR` un montant.
"""
from __future__ import annotations

from datetime import date

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.services import bootstrap_generation_job
from generation.socle.schema import (
    DonneeSocle,
    Fiabilite,
    Perimetre,
    Socle,
    Zone,
)
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

#: Les motifs de refus observés sur les deux dossiers réels, et le fragment que
#: la consigne doit porter pour chacun. Fragments volontairement courts : viser
#: une phrase entière ferait tomber ce test à la première reformulation, sans
#: qu'aucune règle ait changé.
MOTIFS_OBSERVES = {
    "radar sans notes (4 refus, 09f32041)": ("radar", "notes"),
    "jauges sans notes (2 refus, 09f32041)": ("jauge", "notes"),
    "radar a moins de 3 axes (1 refus)": ("trois axes",),
    "serie temporelle trouee (1 refus)": ("toutes les periodes",),
    "un seul identifiant (4 refus)": ("DEUX identifiants",),
    "unites heterogenes (18 refus, b561c2d6)": ("MEME NATURE",),
    "deux devises sur un axe": ("devises",),
}

#: Un socle minimal qui mêle exprès les trois natures ayant produit les refus.
DONNEES = (
    ("tam", 1.2, "MdEUR"),
    ("nombre_entreprises", 4200.0, "unite"),
    ("croissance", 3.4, "%"),
    ("delai_moyen", 8.0, "mois"),
    ("note_maturite", 3.5, "note_sur_5"),
)


@pytest.fixture
def socle() -> Socle:
    return Socle(
        secteur="mode",
        zone=Zone(pays="France", region="Île-de-France", ville="Paris"),
        date_socle=date(2026, 8, 8),
        donnees=[
            DonneeSocle(
                id=identifiant,
                libelle=f"Libellé {identifiant}",
                valeur=valeur,
                unite=unite,
                annee=2025,
                perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.OBSERVEE,
                source="Insee, 2025",
            )
            for identifiant, valeur, unite in DONNEES
        ],
    )


def _prompt(livrable: str, socle: Socle) -> str:
    offre = Offer.objects.create(
        name=f"Offre {livrable}", slug=f"offre-{livrable}", deliverable_type=livrable,
    )
    client = Customer.objects.create(email=f"{livrable}@figures.test")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-figures-{livrable}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "mode", "PAYS": "France"},
    )
    job = bootstrap_generation_job(soumission)
    chapitre = job.chapters.order_by("chapter_number").first()
    assert chapitre is not None

    prompt, _ = construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables={"SECTEUR": "mode", "PAYS": "France"},
        document=type_document(livrable),
    )
    return prompt


@pytest.mark.django_db
def test_le_prompt_transmis_est_bien_construit(socle: Socle) -> None:
    """Garde-fou : sans lui, un prompt vide ferait passer tout le reste."""
    prompt = _prompt(DeliverableType.MARKET_STUDY, socle)

    assert "SOCLE VERROUILLÉ" in prompt
    assert "VISUELS" in prompt
    assert len(prompt) > 2000


@pytest.mark.django_db
@pytest.mark.parametrize(("motif", "fragments"), sorted(MOTIFS_OBSERVES.items()))
def test_chaque_motif_de_refus_est_annonce_au_modele(
    motif: str, fragments: tuple[str, ...], socle: Socle
) -> None:
    """Le modèle doit connaître la règle avant qu'on lui reproche de l'enfreindre.

    Sur le prompt ENVOYÉ. C'est toute la différence avec la version d'avant, et
    c'est cette différence qui a coûté dix-huit figures.
    """
    prompt = _prompt(DeliverableType.MARKET_STUDY, socle)
    manquants = [f for f in fragments if f.lower() not in prompt.lower()]

    assert not manquants, (
        f"Le prompt transmis ne dit rien de : {motif}. Absents : {manquants}. "
        "Le rendu refusera pourtant ces figures — voir donnees_graphiques.py."
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "livrable",
    sorted(
        [
            DeliverableType.MARKET_STUDY,
            DeliverableType.BUSINESS_PLAN,
            DeliverableType.BUSINESS_STRATEGY,
            DeliverableType.COMPETITOR_STUDY,
        ]
    ),
)
def test_les_quatre_livrables_recoivent_les_regles(livrable: str, socle: Socle) -> None:
    """Vérifier le seul livrable phare laisserait le trou ouvert sur les trois autres."""
    prompt = _prompt(livrable, socle)

    assert "MEME NATURE" in prompt, livrable
    assert "notes" in prompt.lower(), livrable


@pytest.mark.django_db
def test_chaque_identifiant_porte_sa_nature(socle: Socle) -> None:
    """Dire la règle sans donner la matière laisserait le modèle deviner.

    C'est le complément indispensable du test précédent : « cite des grandeurs
    de même nature » n'est applicable que si la nature de chaque identifiant est
    lisible. Elle l'est désormais entre crochets, avec les mots exacts de
    `famille_de_l_unite` — la fonction qui décide du refus au rendu. Le modèle
    voit le critère auquel il sera jugé, pas une paraphrase (règle 5).
    """
    prompt = _prompt(DeliverableType.MARKET_STUDY, socle)

    # L'unité est montrée TELLE QU'ELLE DOIT APPARAÎTRE dans le document —
    # `Md€`, pas `MdEUR`. Le modèle recopie ce qu'il lit : lui montrer la
    # notation de stockage, c'est la retrouver dans la prose du client
    # (retour cliente du 09/08/2026, « remplacer MEUR par 6,8 Md€ »).
    assert "`tam` = 1.2 Md€ [monetaire]" in prompt
    assert "`nombre_entreprises` = 4200.0  [effectif]" in prompt
    assert "`croissance` = 3.4 % [pourcentage]" in prompt
    assert "`delai_moyen` = 8.0 mois [duree]" in prompt
    assert "`note_maturite` = 3.5 /5 [ratio]" in prompt


@pytest.mark.django_db
def test_une_unite_inconnue_ne_se_tait_pas(socle: Socle) -> None:
    """Contre-épreuve (règle 1) : ne pas confondre « je ne sais pas » et « libre ».

    Une chaîne vide entre les crochets se lirait comme « aucune contrainte » et
    inviterait à mélanger. Le mot « inconnue » se voit.
    """
    socle.donnees.append(
        DonneeSocle(
            id="grandeur_exotique",
            libelle="Unité non répertoriée",
            valeur=42.0,
            unite="parsec",
            annee=2025,
            perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.ESTIMEE,
            source="Estimation interne",
        )
    )

    prompt = _prompt(DeliverableType.MARKET_STUDY, socle)

    assert "`grandeur_exotique` = 42.0 parsec [inconnue]" in prompt
    assert "[]" not in prompt
