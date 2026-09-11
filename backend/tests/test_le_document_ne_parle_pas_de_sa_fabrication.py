"""Le document livré ne parle jamais de sa propre fabrication.

## D'où vient ce fichier

Retour de la cliente sur la stratégie `f7f2fad9` (11/09/2026) : le document
gardait « une trace de ses propres corrections — "ce que ce chapitre corrige",
"version précédente affirmait que…", une note de mise à jour ». Vérifié sur le
fichier réellement livré (`f7f2fad9`) : un intertitre « CE QUE CE CHAPITRE
CHANGE », et quatre graphiques portant sous eux le brief de leur propre dessin
(« Représente les grandes étapes… », « Illustre l'écart… »).

## Ce que ces tests refusent de laisser revenir

1. Une consigne de réécriture qui parle au modèle de sa « version
   précédente » — c'est elle qui fait écrire « la version précédente
   affirmait ». Vérifié sur le prompt ENVOYÉ par la chaîne Word, celle de la
   production, et non sur une fonction isolée.
2. Un commentaire de graphique imprimé sous la figure alors qu'il est un ordre
   adressé au dessinateur.
3. Un détecteur qui laisse passer les phrases citées par la cliente.
4. Un détecteur qui signale du contenu légitime — la contre-épreuve (règle 6).
   Le client du dossier `f7f2fad9` fait de la maintenance informatique : « mise à jour système » ou
   « la version précédente de Windows » y sont du CONTENU, et un faux motif
   ferait réécrire un chapitre juste, à nos frais (règle 2).

Le texte du document réel n'est PAS recopié ici : ce sont des données d'un
client. Les phrases ci-dessous en reproduisent la forme.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from generation import meta_discours

#: Les fuites CERTAINES : celles qui justifient de réécrire le chapitre.
FUITES_AU_GATE = (
    "Ce que ce chapitre corrige : la marge était surestimée.",
    "CE QUE CE CHAPITRE CHANGE",
    "La version précédente affirmait que le marché était saturé.",
    "Ce chapitre a été corrigé.",
    "Le présent chapitre a été révisé pour intégrer les chiffres de 2025.",
    "La première version de ce chapitre surestimait la marge.",
    "Ce chapitre a été rejeté par le contrôle qualité.",
)

#: Les fuites PROBABLES : signalées en avertissement, jamais réécrites. Chacune
#: a une lecture légitime possible, et la trancher est un travail de lecteur.
FUITES_PROBABLES = (
    "Note de mise à jour : les chiffres du chapitre 4 ont été revus.",
    "Ce chapitre corrige l'estimation du panier moyen.",
    "Par rapport à la version précédente, le seuil a été relevé.",
    "Nous avons corrigé ce chiffre après vérification.",
    "Voici les modifications apportées à ce chapitre.",
    "Modifications apportées au chapitre : le seuil est désormais chiffré.",
    "Dans la version précédente, le marché était estimé à 12 M€.",
    "Contrairement à ce qu'indiquait la version précédente, la cible est locale.",
    "Les montants ont été corrigés par rapport à la version initiale.",
)

#: Du CONTENU, qu'aucun des deux niveaux ne doit signaler.
#:
#: La seconde moitié vient de la relecture du 11/09/2026 : ces phrases avaient
#: déclenché la première version du détecteur. Elles sont réalistes dans les
#: métiers réels des clients — maintenance informatique, offre à paliers,
#: industrie, citation de source — et chacune aurait payé la réécriture d'un
#: chapitre juste en en retirant le passage (règle 2).
CONTENU = (
    "La structuration de l'offre permettra de corriger l'écart entre les formules.",
    "Avant de corriger ce qui ne fonctionne pas, il faut nommer ce qui tient déjà.",
    "Ce qui a été établi au chapitre précédent reste valable.",
    "Le diagnostic confirme un déséquilibre déjà pointé aux chapitres précédents.",
    "Installation antivirus, diagnostic de lenteur, mise à jour système.",
    "Le technicien vérifie que la version précédente de Windows est désinstallée.",
    "Mettre en place un contrôle qualité des interventions à distance.",
    "Ce chapitre analyse les forces structurelles du business.",
    "Ce chapitre change la lecture du marché : la demande est locale.",
    "La version précédente du logiciel ne gérait pas les licences.",
    "Nous avons retenu trois canaux prioritaires.",
    "Cette section présente la feuille de route.",
    "Les tarifs seront mis à jour chaque année.",
    "Le client modifie son abonnement en ligne.",
    # ── Relecture du 11/09/2026 ──
    "Windows 11 24H2 : cette version corrige plusieurs failles de sécurité.",
    "La version précédente posait des problèmes de compatibilité avec les imprimantes.",
    "La version précédente présentait des lenteurs au démarrage.",
    "Consultez la note de version publiée par Microsoft avant la mise à jour.",
    "La note de mise à jour de Windows détaille les correctifs du mois.",
    "Publier un journal des modifications à chaque évolution de l'application.",
    "La formule Premium : cette version remplace l'ancienne offre Pro.",
    "Tout lot rejeté par le contrôle qualité est détruit sous 48 heures.",
    "Nous avons actualisé les données de marché avec l'enquête Insee 2025.",
    "Nous avons révisé les estimations de fréquentation à la baisse.",
    "Selon l'OFCE, ce rapport révise à la baisse la croissance à 0,8 %.",
    "Le nouveau plan local d'urbanisme : ce document modifie le zonage.",
)


@pytest.mark.parametrize("phrase", FUITES_AU_GATE)
def test_une_fuite_certaine_fait_reecrire_le_chapitre(phrase: str) -> None:
    assert meta_discours.trouver_au_gate(phrase), f"fuite non reconnue : {phrase!r}"
    assert meta_discours.trouver(phrase)


@pytest.mark.parametrize("phrase", FUITES_PROBABLES)
def test_une_fuite_probable_avertit_sans_rien_reecrire(phrase: str) -> None:
    """Signalée à la cliente, jamais payée : sa lecture légitime existe."""
    assert meta_discours.trouver(phrase), f"fuite non signalée : {phrase!r}"
    assert meta_discours.trouver_au_gate(phrase) == [], (
        f"une forme ambiguë ferait réécrire un chapitre : {phrase!r}"
    )


@pytest.mark.parametrize("phrase", CONTENU)
def test_le_contenu_legitime_n_est_jamais_signale(phrase: str) -> None:
    """La contre-épreuve, aux deux niveaux."""
    assert meta_discours.trouver(phrase) == [], f"faux positif : {phrase!r}"
    assert meta_discours.trouver_au_gate(phrase) == []


def test_un_bruit_accepte_reste_un_simple_avertissement() -> None:
    """Le prix assumé de l'avertissement : « par rapport à la version
    précédente » se lit aussi dans un document sur Windows. Il avertit, gratis ;
    il ne fait JAMAIS réécrire."""
    phrase = "Par rapport à la version précédente, Windows 11 exige une puce TPM 2.0."
    assert meta_discours.trouver(phrase)
    assert meta_discours.trouver_au_gate(phrase) == []


def test_l_extrait_rendu_est_le_passage_exact() -> None:
    """Un motif doit pouvoir être retrouvé dans le document par qui le lit."""
    texte = "Le marché est porteur. Ce que ce chapitre corrige : la marge."
    assert meta_discours.trouver_au_gate(texte) == ["Ce que ce chapitre corrige"]


# ── Les consignes de dessin ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "commentaire",
    [
        "Représente les grandes étapes attendues entre la situation actuelle et l'objectif.",
        "Illustre l'écart entre le revenu récurrent mensuel actuel et l'objectif.",
        "Positionne le panier moyen actuel et le niveau de marge contributive.",
        "Compare le chiffre d'affaires récurrent actuel au chiffre visé à 24 mois.",
        "Mets en évidence la part des abonnements dans le chiffre d'affaires.",
        "Ce graphique doit montrer l'écart entre les deux formules.",
    ],
)
def test_une_consigne_de_dessin_est_reconnue(commentaire: str) -> None:
    assert meta_discours.est_une_consigne_de_dessin(commentaire)


@pytest.mark.parametrize(
    "commentaire",
    [
        "Source : données du projet, déclarées par le dirigeant.",
        "Le revenu récurrent reste inférieur au seuil de couverture des charges.",
        "Les abonnements pèsent 20 % du chiffre d'affaires.",
        "Comparé à 2024, le panier moyen progresse de 8 %.",
        "Ce graphique montre que le revenu récurrent reste sous le seuil.",
        "Comparer ces deux courbes permet de voir que la marge baisse.",
        # L'infinitif est la forme de la RECOMMANDATION au dirigeant : relevé
        # tel quel dans une vraie stratégie, et légitime sous un graphique.
        "Comparer chaque mois le revenu réel à la trajectoire visée.",
        "Illustrer l'argumentaire par des exemples concrets rencontrés en clientèle.",
        "",
    ],
)
def test_une_legende_de_lecture_n_est_pas_une_consigne(commentaire: str) -> None:
    assert not meta_discours.est_une_consigne_de_dessin(commentaire)


# ── La consigne de réécriture ────────────────────────────────────────────────

#: Ce que la consigne disait au modèle, et qu'il répétait au client.
_MOTS_QUI_PROVOQUENT = ("précédente", "precedente", "refusée", "refusee",
                        "rejetée", "rejetee", "tentative")


def test_la_consigne_de_correction_ne_parle_d_aucune_version_anterieure() -> None:
    consigne = meta_discours.consigne_de_correction(
        ["le tableau 4.2 doit porter le panier moyen", "le seuil doit être chiffré"]
    )
    bas = consigne.lower()
    for mot in _MOTS_QUI_PROVOQUENT:
        assert mot not in bas, f"la consigne dit encore « {mot} »"
    # Les exigences, elles, arrivent à la lettre : sans elles la réécriture ne
    # sert à rien.
    assert "le tableau 4.2 doit porter le panier moyen" in consigne
    assert "le seuil doit être chiffré" in consigne


def test_une_note_deja_en_liste_n_est_pas_prefixee_deux_fois() -> None:
    """La note du gate arrive déjà sous la forme « - motif » ; la consigne la
    préfixait une seconde fois (« - - motif »)."""
    consigne = meta_discours.consigne_de_correction(["- premier point\n- second point"])
    assert "- premier point" in consigne
    assert "- second point" in consigne
    assert "- -" not in consigne


def test_la_chaine_html_emploie_la_meme_consigne() -> None:
    """Une seule source : deux textes écrits séparément avaient produit deux
    fois le même défaut (règle 5)."""
    from generation.prompts import _corrective_footer

    pied = _corrective_footer("le seuil doit être chiffré")
    assert pied.strip() == meta_discours.consigne_de_correction(
        ["le seuil doit être chiffré"]
    ).strip()
    for mot in _MOTS_QUI_PROVOQUENT:
        assert mot not in pied.lower(), f"la chaîne HTML dit encore « {mot} »"


@pytest.fixture
def socle() -> Any:
    from generation.socle.referentiel import Fiabilite, Perimetre
    from generation.socle.schema import DonneeSocle, Socle, Zone

    return Socle(
        secteur="services informatiques aux particuliers",
        zone=Zone(pays="France", region="Nouvelle-Aquitaine", ville="Angoulême"),
        date_socle=date(2026, 9, 1),
        donnees=[
            DonneeSocle(
                id=identifiant, libelle=f"Libellé {identifiant}", valeur=valeur,
                unite=unite, annee=2025, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.OBSERVEE, source="Insee, 2025",
            )
            for identifiant, valeur, unite in (
                ("abonnes", 14.0, "unite"),
                ("panier_moyen", 18.0, "EUR"),
                ("panier_cible", 25.0, "EUR"),
                ("marge", -60.6, "%"),
            )
        ],
    )


@pytest.mark.django_db
def test_le_prompt_envoye_par_la_chaine_word_ne_parle_d_aucune_version(
    socle: Any,
) -> None:
    """Sur le prompt réellement ENVOYÉ en production, pas sur une fonction.

    Il portait « TENTATIVE PRÉCÉDENTE REFUSÉE. Corrige EXACTEMENT ces points ».
    Ce test échoue sur ce code-là (règle 6).
    """
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.chapitres.configuration import type_document
    from generation.chapitres.runner import construire_prompt_chapitre
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    livrable = DeliverableType.BUSINESS_STRATEGY
    offre = Offer.objects.create(
        name="Stratégie", slug="strat-meta", deliverable_type=livrable
    )
    client = Customer.objects.create(email="meta@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-meta", customer=client, offer=offre
    )
    variables = {"SECTEUR": "maintenance informatique", "PAYS": "France"}
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables,
    )
    job = bootstrap_generation_job(soumission)
    chapitre = job.chapters.order_by("chapter_number").first()
    assert chapitre is not None

    prompt, _ = construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables=variables,
        document=type_document(livrable),
        motifs_precedents=["le seuil de rentabilité doit être chiffré"],
    )
    texte = str(prompt).lower()
    assert "le seuil de rentabilité doit être chiffré" in texte
    for mot in ("tentative précédente", "refusée", "version précédente", "rejetée"):
        assert mot not in texte, f"le prompt envoyé dit encore « {mot} »"


# ── Le rendu n'imprime pas une consigne de dessin ────────────────────────────


def test_une_consigne_de_dessin_n_est_pas_imprimee_sous_le_graphique(
    socle: Any,
) -> None:
    """Le commentaire est imprimé à la place de la SOURCE : c'est là que le
    client lisait « Illustre l'écart… ». Retirer la légende ne perd rien ;
    la retirer en silence en perdrait la trace (règle 1)."""
    from generation.chapitres.schema import Graphique, TypeGraphique
    from generation.rendu_word import assemblage, secteurs

    rapport = assemblage.RapportAssemblage()
    demande = Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Panier moyen actuel et visé",
        donnees_ids=["panier_moyen", "panier_cible"],
        commentaire="Illustre l'écart entre le panier moyen et le panier visé.",
    )
    blocs = assemblage._blocs_graphique(
        socle, [demande], secteurs.profil_du_secteur(socle.secteur), rapport, "Ch. 3"
    )

    # Garde-fou : le graphique doit être RENDU, sinon la légende n'est jamais
    # atteinte et le test passerait sans rien vérifier.
    assert rapport.graphiques_rendus == 1, rapport.graphiques_abandonnes
    graphiques = [b for b in blocs if b.get("type") == "graphique"]
    assert graphiques and graphiques[0]["source"] == ""
    assert len(rapport.consignes_de_dessin_retirees) == 1


def test_une_legende_de_lecture_reste_imprimee(socle: Any) -> None:
    """La contre-épreuve : une vraie phrase de lecture n'est pas retirée."""
    from generation.chapitres.schema import Graphique, TypeGraphique
    from generation.rendu_word import assemblage, secteurs

    rapport = assemblage.RapportAssemblage()
    lecture = "Le panier moyen reste inférieur de 7 € au niveau visé."
    blocs = assemblage._blocs_graphique(
        socle,
        [Graphique(
            type_graphique=TypeGraphique.BARRES, titre="Panier moyen actuel et visé",
            donnees_ids=["panier_moyen", "panier_cible"], commentaire=lecture,
        )],
        secteurs.profil_du_secteur(socle.secteur), rapport, "Ch. 3",
    )
    assert rapport.graphiques_rendus == 1, rapport.graphiques_abandonnes
    assert [b["source"] for b in blocs if b.get("type") == "graphique"] == [lecture]
    assert rapport.consignes_de_dessin_retirees == []



# ── Les branchements : le chemin payant et la décision « jamais bloquant » ───


def _job_avec_un_chapitre(contenu: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Stratégie", slug=f"strat-{abs(hash(contenu)) % 10**8}",
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    client = Customer.objects.create(email=f"c{abs(hash(contenu)) % 10**8}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-{abs(hash(contenu)) % 10**8}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "maintenance informatique", "PAYS": "France"},
    )
    job = bootstrap_generation_job(soumission)
    ChapterGeneration.objects.update_or_create(
        job=job, chapter_number=3,
        defaults={"chapter_title": "Chapitre 3", "prompt_key": "chapitre_03",
                  "status": ChapterStatus.DONE, "content": contenu},
    )
    return job


@pytest.mark.django_db
def test_une_fuite_certaine_fait_echouer_le_gate_sur_son_chapitre() -> None:
    from generation.gate import _check_meta_discours

    job = _job_avec_un_chapitre(
        "## Lecture\n\nCe que ce chapitre change : la cible devient locale."
    )
    echecs = _check_meta_discours(job)

    assert [e.check for e in echecs] == ["meta_discours"]
    assert echecs[0].chapter_number == 3
    assert "Ce que ce chapitre change" in echecs[0].detail


@pytest.mark.django_db
def test_un_chapitre_de_contenu_ne_fait_rien_echouer() -> None:
    """La contre-épreuve sur le chemin payant, avec le métier réel du client."""
    from generation.gate import _check_meta_discours

    job = _job_avec_un_chapitre(
        "Windows 11 24H2 : cette version corrige plusieurs failles. La version "
        "précédente posait des problèmes de compatibilité. Par rapport à la "
        "version précédente, Windows 11 exige une puce TPM 2.0."
    )
    assert _check_meta_discours(job) == []


def test_la_boucle_sait_reparer_ce_motif_et_le_nomme_juste() -> None:
    from generation.correction import _CHECK_LABELS, _is_regenerable

    assert _is_regenerable("meta_discours")
    libelle = _CHECK_LABELS["meta_discours"].lower()
    # Il ne se fait plus passer pour un « marqueur technique interne ».
    assert "marqueur technique" not in libelle
    assert "reformuler" in libelle


def test_le_controle_final_avertit_et_ne_bloque_jamais() -> None:
    """Décision cliente du 13/08/2026 : le document part sans action de sa part."""
    from pathlib import Path

    from generation.verification import controles
    from generation.verification.lecture import DocumentLu
    from generation.verification.rapport import Gravite, RapportControle

    document = DocumentLu(
        chemin=Path("livrable.docx"),
        paragraphes=[
            "CE QUE CE CHAPITRE CHANGE",
            "Par rapport à la version précédente, le seuil a été relevé.",
        ],
    )
    anomalies = controles.controler_meta_discours(document)

    assert len(anomalies) == 2
    assert all(a.gravite is Gravite.AVERTISSEMENT for a in anomalies)
    rapport = RapportControle()
    rapport.ajouter(*anomalies)
    assert rapport.livrable, "une fuite ne doit jamais retenir le document"


def test_le_controle_final_tourne_aussi_sans_socle() -> None:
    from pathlib import Path

    from generation.verification.lecture import DocumentLu
    from generation.verification.services import verifier_document_sans_socle

    rapport = verifier_document_sans_socle(
        DocumentLu(chemin=Path("livrable.docx"), paragraphes=["Un paragraphe."])
    )
    assert "meta_discours" in rapport.controles_executes


def test_le_schema_envoye_au_modele_ne_montre_ni_l_intitule_ni_le_dossier() -> None:
    """Une docstring de modèle Pydantic part dans la consigne du modèle.

    Le premier correctif y racontait l'incident : il montrait au modèle, pour
    chaque chapitre de chaque client, l'intitulé exact à ne pas écrire, et le
    nom du client concerné (relecture du 11/09/2026).
    """
    import json

    from generation.chapitres.schema import ChapitrePayload
    from generation.couverture import RapportDuModele

    for modele in (ChapitrePayload, RapportDuModele):
        schema = json.dumps(modele.model_json_schema(), ensure_ascii=False)
        assert "ce que ce chapitre" not in schema.lower()
        assert "lecture du chapitre" not in schema.lower()
        assert "f7f2fad9" not in schema
