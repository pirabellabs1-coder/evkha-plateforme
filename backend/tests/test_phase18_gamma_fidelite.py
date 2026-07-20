"""Phase 18 — Gamma reecrit le document : on verifie sa sortie.

Le gate valide le markdown produit par Claude. Puis Gamma refait le document,
et RIEN ne controlait son resultat. Mesure sur le premier vrai BP SYNAPSES
(juillet 2026), avec le parametrage d'alors :

    source pipeline : 38 752 mots, 20 chapitres
    PDF Gamma       :  3 835 mots, 10 cartes (chapitres fusionnes)

90 % du document perdu, et 5 verticales sur 10 EFFACEES — dont le
self-stockage, l'hebergement de serveurs et les activites sportives douces,
exactement les trois que la cliente signalait comme disparues. Le gate les
avait validees : elles etaient bien dans le markdown. Gamma les a supprimees
APRES, en silence.

Active tel quel, Gamma aggravait le probleme qu'on corrigeait.
"""
from __future__ import annotations

from delivery.gamma_fidelite import controler_fidelite

VERTICALES = (
    "coworking",
    "boxes de stockage",
    "hebergement de serveurs",
    "activites sportives douces",
)


def test_gamma_qui_efface_des_verticales_est_refuse() -> None:
    """Le cas SYNAPSES reel : Gamma garde le coworking, jette le reste."""
    source = " ".join(
        ["Le tiers-lieu propose du coworking, des boxes de stockage, "
         "de l'hebergement de serveurs et des activites sportives douces."] * 60
    )
    pdf = " ".join(["Le tiers-lieu propose du coworking moderne."] * 60)

    rapport = controler_fidelite(
        texte_pdf=pdf, markdown_source=source, verticales=VERTICALES
    )

    assert rapport.fidele is False
    assert "boxes de stockage" in rapport.verticales_perdues
    assert "hebergement de serveurs" in rapport.verticales_perdues
    assert "activites sportives douces" in rapport.verticales_perdues
    assert "coworking" not in rapport.verticales_perdues


def test_gamma_qui_resume_le_document_est_refuse() -> None:
    """38 752 mots -> 3 835 : ce n'est plus une mise en page, c'est un resume.

    Meme si toutes les verticales survivaient, un document ampute de 90 % de
    son texte n'est pas livrable a une banque.
    """
    source = " ".join(["coworking boxes de stockage hebergement de serveurs "
                       "activites sportives douces phrase de remplissage"] * 200)
    pdf = " ".join(["coworking boxes de stockage hebergement de serveurs "
                    "activites sportives douces"] * 10)

    rapport = controler_fidelite(
        texte_pdf=pdf, markdown_source=source, verticales=VERTICALES
    )

    assert rapport.fidele is False
    assert rapport.verticales_perdues == ()  # les verticales sont la...
    assert "resume" in rapport.motif  # ...mais le texte a disparu
    assert rapport.ratio < 0.60


def test_gamma_fidele_est_accepte() -> None:
    """Contre-epreuve : une vraie mise en page ne doit pas etre refusee.

    Gamma reformate legitimement : il retire le markdown, reorganise les
    titres. Une perte de quelques pourcents est normale et ne doit rien
    bloquer — sinon on refuserait tous les rendus.
    """
    phrase = ("Le tiers-lieu propose du coworking, des boxes de stockage, de "
              "l'hebergement de serveurs et des activites sportives douces. ")
    source = "## Titre\n\n" + (phrase * 50)
    pdf = phrase * 48  # ~96 % du texte, sans le markdown

    rapport = controler_fidelite(
        texte_pdf=pdf, markdown_source=source, verticales=VERTICALES
    )

    assert rapport.fidele is True
    assert rapport.verticales_perdues == ()


def test_verticale_nommee_autrement_n_est_pas_comptee_perdue() -> None:
    """Meme regle que le gate : les mots porteurs, pas le libelle litteral.

    Le gate a deja bloque un livrable correct en exigeant « domiciliation
    d'entreprises » mot pour mot. Ne pas refaire l'erreur ici : deux modules,
    deux verites, c'est le defaut de fond de ce projet.
    """
    source = "La domiciliation commerciale est proposee aux entreprises. " * 20
    pdf = "La domiciliation commerciale est proposee aux entreprises. " * 19

    rapport = controler_fidelite(
        texte_pdf=pdf,
        markdown_source=source,
        verticales=("domiciliation d'entreprises",),
    )

    assert rapport.fidele is True


def test_pdf_illisible_ne_bloque_pas_la_livraison() -> None:
    """Ne pas savoir n'autorise pas a bloquer un livrable par ailleurs valide.

    Mais le silence non plus : le motif le dit.
    """
    rapport = controler_fidelite(
        texte_pdf="", markdown_source="du texte source", verticales=VERTICALES
    )

    assert rapport.fidele is True
    assert "non effectue" in rapport.motif
