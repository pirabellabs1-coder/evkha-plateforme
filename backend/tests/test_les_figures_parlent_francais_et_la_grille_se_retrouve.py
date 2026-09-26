"""« 1.5e+06 » sur une marche d'entonnoir, « 45 » sans %, « MEUR » dans un tableau.

Audit des figures du 26/09/2026. Les VALEURS résolues depuis le socle étaient
justes — c'est leur ÉCRITURE qui restait anglaise ou technique :

- `_valeur_lisible` formatait en `:g` (« 1.5e+06 », point décimal) ;
- `_suffixe("%")` rendait la chaîne vide : les barres de pourcentages
  affichaient « 45 » là où le repli promettait « 45 % » ;
- les axes de courbes et de barres groupées portaient le code de stockage
  (« MdEUR », « note_sur_5 ») ; le tableau de repli imprimait « MEUR » et
  ses milliers avec une espace sécable.

Et la grille de notation : ses codes sont NORMALISÉS à la validation (lot 85c),
mais `Socle.critere` et `Concurrent.note_sur` comparaient à l'identique. Une
figure citant « Prix » — un autre appel du modèle — était abandonnée pour
« identifiants absents ».

Enfin le convertisseur PDF tenait pour un document tout fichier présent avec
un code retour 0 : un PDF vide passait (règle 1).
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from generation.rendu_word.assemblage import _tableau_de_repli
from generation.rendu_word.donnees_graphiques import _suffixe, _valeur_lisible
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    Concurrent,
    Critere,
    DonneeSocle,
    NoteConcurrent,
    Socle,
    Zone,
    nombre_francais,
)
from integrations.docx_pdf import ConversionPdfError, LibreOfficeConvertisseurDocx

# ── L'écriture des figures ───────────────────────────────────────────────────


def test_une_marche_d_entonnoir_s_ecrit_a_son_echelle_en_francais() -> None:
    assert _valeur_lisible(1_500_000.0, "EUR") == "1,5 M€"
    assert _valeur_lisible(600_000.0, "EUR") == "600 k€"
    assert "e+" not in _valeur_lisible(16_500_000_000.0, "EUR")


def test_un_pourcentage_garde_son_signe() -> None:
    assert _suffixe("%") == " %"
    assert _valeur_lisible(45.0, "%") == "45 %"


def test_le_formateur_des_figures_est_celui_du_document() -> None:
    assert nombre_francais(1_200_000.0) == "1 200 000"
    assert nombre_francais(0.6) == "0,6"


def _socle_avec(*donnees: DonneeSocle, **extra: Any) -> Socle:
    return Socle(
        secteur="test", zone=Zone(pays="France"), date_socle=date(2026, 8, 8),
        donnees=list(donnees), **extra,
    )


def test_le_tableau_de_repli_ecrit_pour_le_lecteur() -> None:
    socle = _socle_avec(DonneeSocle(
        id="tam", libelle="Marché total", valeur=1_250_000.0, unite="EUR", annee=2025,
        perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.OBSERVEE, source="Insee, 2025",
    ))
    demande = SimpleNamespace(donnees_ids=["tam"], titre="Une figure refusée")

    tableau = _tableau_de_repli(socle, demande)  # type: ignore[arg-type]

    assert tableau is not None
    ligne = tableau["lignes"][0]
    assert ligne[1] == "1 250 000"
    assert ligne[2] == "€"


# ── La grille se retrouve quelle que soit la graphie ─────────────────────────


def _socle_note() -> Socle:
    return _socle_avec(
        grille_notation=[Critere(code="Prix", intitule="Prix", note_1="cher", note_5="bon marché")],
        concurrents=[Concurrent(
            nom="Acteur A", type="direct", site_web="acteur-a.fr",
            notes=[NoteConcurrent(critere="Prix", note=4)],
        )],
    )


def test_un_code_de_grille_se_retrouve_sous_sa_graphie_d_origine() -> None:
    socle = _socle_note()
    assert socle.grille_notation[0].code == "prix"
    assert socle.critere("Prix") is not None
    assert socle.critere("prix") is not None
    assert socle.concurrents[0].note_sur("Prix") == 4
    assert socle.concurrents[0].note_sur("PRIX ") == 4


def test_un_code_inconnu_reste_inconnu() -> None:
    """Contre-épreuve : normaliser n'est pas deviner."""
    socle = _socle_note()
    assert socle.critere("qualite") is None
    assert socle.concurrents[0].note_sur("qualite") is None


# ── Un PDF vide n'est pas un PDF ─────────────────────────────────────────────


def test_un_pdf_vide_est_un_echec_de_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "etude.docx"
    source.write_bytes(b"PK\x03\x04 faux docx")

    def _faux_soffice(commande: list[str], **_: Any) -> Any:
        dossier = Path(commande[commande.index("--outdir") + 1])
        (dossier / "etude.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(subprocess, "run", _faux_soffice)
    convertisseur = LibreOfficeConvertisseurDocx("soffice")

    with pytest.raises(ConversionPdfError, match="vide ou illisible"):
        convertisseur.convertir(source, tmp_path / "sortie.pdf")
    assert not (tmp_path / "sortie.pdf").exists()
