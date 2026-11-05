"""« Il ne reste que quatre concurrents directs nommément identifiés. »

## Pourquoi cette mesure existe

Audit de la cliente du 04/11/2026 sur l'étude SUN TZU, point 7 : « Parmi les
huit concurrents qualifiés de directs, trois ne sont pas des entreprises
identifiées, mais de simples catégories d'acteurs : les importateurs
taïwanais, les vendeurs sur Tmall Global et les distributeurs coréens. […]
Avec la fermeture de City Shop, il ne reste que quatre concurrents directs
nommément identifiés et actifs dans le panel. »

Elle a dû les compter À LA MAIN. Vérifié le 05/11/2026 : ni la fiche du
dossier ni `jobs/<id>/mesure/` n'exposaient la composition du panel. Un défaut
qu'on ne peut pas mesurer se discute au lieu de se corriger — et c'est par ce
trou qu'un panel de quatre entreprises réelles a pu passer pour huit
concurrents directs, en étant parfaitement conforme à la consigne d'alors.

C'est la même raison qui a fait exposer les compteurs de cache le 28/10/2026 :
mesuré, le cache s'est révélé à 96,2 % de lecture là où une note périmée
annonçait « 40 % à récupérer ».

## Ce que la mesure ne fait pas

Elle ne juge pas. Le plancher par territoire CLASSE les territoires et ne
produit aucun motif : la cliente écrit « lorsque le marché le permet », et un
contrôle qui exigerait un nombre ferait inventer des entreprises — exactement
le défaut de l'étude `3a4df56c` d'août 2026, pris par l'autre bout.

Ces tests échouent sur le code d'avant : `mesurer_le_panel` n'existait pas et
`mesure/` ne portait aucune clé `panel`.
"""
from __future__ import annotations

from generation.mesure import PLANCHER_PAR_TERRITOIRE, mesurer_le_panel


class _Acteur:
    """Le strict nécessaire que `mesurer_le_panel` lit d'un concurrent.

    `est_identifie` est recopié de `Concurrent` : la présence d'un domaine web.
    Le reproduire ici plutôt que d'importer le vrai modèle évite de monter une
    base pour compter des entiers — et le critère lui-même est verrouillé chez
    lui, par `test_concurrents_identifies.py`
    (`test_une_entreprise_avec_son_site_est_identifiee` et
    `test_un_profil_type_n_est_pas_identifie`).
    """

    def __init__(self, nom: str, type_: str, site: str, emplacement: str) -> None:
        self.nom = nom
        self.type = type_
        self.site_web = site
        self.emplacement = emplacement

    @property
    def est_identifie(self) -> bool:
        return "." in self.site_web


class _Socle:
    def __init__(self, concurrents: list[_Acteur]) -> None:
        self.concurrents = concurrents


#: Le panel de SUN TZU tel qu'elle le décrit : huit directs, dont trois
#: catégories, répartis sur plusieurs territoires.
#: Les emplacements sont recopiés TELS QUELS du socle de l'étude : de la
#: prose, pas des noms de pays. C'est le point de la normalisation — neuf
#: libellés pour six territoires.
PANEL_SUN_TZU = _Socle([
    _Acteur("City'Super", "direct", "citysuper.com.hk",
            "Hong Kong et Taïwan (plusieurs magasins)"),
    _Acteur("City Shop", "direct", "cityshop.com.cn", "Shanghai, Chine"),
    _Acteur("Kaldi Coffee Farm", "direct", "kaldi.co.jp",
            "Japon (réseau national de magasins)"),
    _Acteur("FairPrice Finest", "direct", "fairprice.com.sg",
            "Singapour (réseau de magasins)"),
    _Acteur("Cold Storage", "direct", "coldstorage.com.sg",
            "Singapour (réseau de magasins)"),
    # Les trois que la cliente refuse : des catégories, sans adresse.
    _Acteur("les importateurs taïwanais", "direct", "", "Taïwan"),
    _Acteur("les vendeurs sur Tmall Global", "direct", "",
            "Chine continentale (vente en ligne transfrontalière)"),
    _Acteur("les distributeurs coréens", "direct", "",
            "Corée du Sud (Séoul notamment)"),
    _Acteur("Carrefour Taiwan", "indirect", "carrefour.com.tw", "Taïwan"),
    _Acteur("SUN TZU ORGANISATION", "projet", "suntzu.fr",
            "Siège France, distribution internationale"),
])


def test_le_compte_qu_elle_a_fait_a_la_main() -> None:
    """Huit directs annoncés, cinq entreprises nommées parmi eux."""
    panel = mesurer_le_panel(PANEL_SUN_TZU)

    assert panel is not None
    # Le projet ne compte pas : ce n'est pas un concurrent de lui-même.
    assert panel["acteurs"] == 9
    assert panel["directs"] == 8
    assert panel["indirects"] == 1
    # LE nombre de son audit : les directs réellement nommés.
    assert panel["directs_identifies"] == 5
    assert panel["categories"] == 3


def test_neuf_libelles_de_prose_donnent_six_territoires() -> None:
    """LE point de la normalisation.

    Avant elle, chaque libellé comptait pour un territoire : « Shanghai,
    Chine » et « Chine continentale (vente en ligne transfrontalière) » en
    faisaient deux, et le panel paraissait deux fois plus dispersé qu'il ne
    l'est. Ce test échoue sur le code d'avant.
    """
    panel = mesurer_le_panel(PANEL_SUN_TZU)
    assert panel is not None

    territoires = set(panel["par_territoire"])  # type: ignore[call-overload]

    assert territoires == {
        "chine", "coree du sud", "hong kong", "japon", "singapour", "taiwan",
    }


def test_un_acteur_present_sur_deux_territoires_compte_dans_les_deux() -> None:
    """« Hong Kong et Taïwan » dit quelque chose des DEUX marchés."""
    panel = mesurer_le_panel(PANEL_SUN_TZU)
    assert panel is not None

    assert panel["par_territoire"]["hong kong"]["identifies"] == 1  # type: ignore[index]
    # Taïwan : City'Super (nommé) + Carrefour Taiwan (nommé) + la catégorie.
    assert panel["par_territoire"]["taiwan"] == {  # type: ignore[index]
        "acteurs": 3, "identifies": 2,
    }


def test_les_territoires_les_plus_pauvres_viennent_en_premier() -> None:
    """Classer, c'est dire où chercher — pas condamner."""
    panel = mesurer_le_panel(PANEL_SUN_TZU)
    assert panel is not None

    territoires = list(panel["par_territoire"])  # type: ignore[call-overload]

    # La Corée du Sud ne porte qu'une catégorie : elle vient devant Singapour,
    # qui porte deux enseignes nommées.
    assert territoires.index("coree du sud") < territoires.index("singapour")
    assert panel["par_territoire"]["singapour"] == {  # type: ignore[index]
        "acteurs": 2, "identifies": 2,
    }
    assert panel["par_territoire"]["coree du sud"] == {  # type: ignore[index]
        "acteurs": 1, "identifies": 0,
    }


def test_les_territoires_sous_le_plancher_sont_nommes() -> None:
    """Son critère : trois à cinq acteurs concrets par territoire."""
    panel = mesurer_le_panel(PANEL_SUN_TZU)
    assert panel is not None

    sous = panel["territoires_sous_le_plancher"]

    assert "coree du sud" in sous  # type: ignore[operator]
    # Singapour n'a que deux nommés : il y est aussi, et c'est voulu — deux,
    # ce n'est pas trois.
    assert "singapour" in sous  # type: ignore[operator]
    assert panel["plancher_par_territoire"] == PLANCHER_PAR_TERRITOIRE


def test_un_emplacement_qui_ne_nomme_aucun_pays_est_compte_a_part() -> None:
    """« Siège international, distribution en Asie » n'est pas un territoire.

    C'est une portée. L'inventer en territoire ferait un marché de plus dans
    la mesure ; le taire ferait disparaître l'acteur. On le dit (règle 1).
    """
    panel = mesurer_le_panel(_Socle([
        _Acteur("Groupe X", "direct", "x.com",
                "Siège international, distribution en Asie"),
        _Acteur("Maison Y", "direct", "y.fr", "Japon"),
    ]))
    assert panel is not None

    assert panel["sans_territoire"] == 1
    assert set(panel["par_territoire"]) == {"japon"}  # type: ignore[call-overload]
    # L'acteur n'a pas disparu du total.
    assert panel["acteurs"] == 2


# ---------------------------------------------------------------------------
# Contre-épreuves
# ---------------------------------------------------------------------------


def test_sans_socle_la_mesure_rend_None_et_pas_des_zeros() -> None:
    """Ne pas pouvoir mesurer n'est pas mesurer zéro (règle 1).

    Un panel à zéro acteur se lirait comme une étude sans concurrents ; un
    `null` dit qu'il n'y avait rien à lire.
    """
    assert mesurer_le_panel(_Socle([])) is None
    assert mesurer_le_panel(object()) is None


def test_un_panel_entierement_nomme_n_a_aucun_territoire_pauvre() -> None:
    """CONTRE-ÉPREUVE : la mesure doit savoir dire « rien à signaler »."""
    bon = _Socle([
        _Acteur(f"Maison {i}", "direct", f"maison{i}.fr", "France")
        for i in range(4)
    ])

    panel = mesurer_le_panel(bon)

    assert panel is not None
    assert panel["categories"] == 0
    assert panel["directs_identifies"] == 4
    assert panel["territoires_sous_le_plancher"] == []


def test_un_acteur_sans_emplacement_est_range_sans_mentir() -> None:
    """« non précisé » plutôt qu'un territoire inventé ou une clé vide."""
    panel = mesurer_le_panel(_Socle([
        _Acteur("Maison A", "direct", "a.fr", ""),
    ]))

    assert panel is not None
    assert panel["sans_territoire"] == 1
    assert panel["par_territoire"] == {}
