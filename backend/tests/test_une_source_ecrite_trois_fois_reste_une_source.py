"""« Namastrip », « référence Namastrip », « Namastrip, référence testée » : UNE source.

Étude concurrentielle `e71fa43a`, 26/09/2026, motif du gate : « Le montant
890 € est attribué à 3 sources différentes dans le document ». Les trois
« sources » nommaient le même concurrent — seule la phrase autour changeait.
`sources_divergentes` comparait les chaînes ; il compare désormais l'ORGANISME
qu'elles nomment (règle 4). Un motif faux fait réécrire un chapitre juste, et
c'est payant.

La contre-épreuve garde le vrai défaut : le même montant crédité à l'Insee
ici et à Xerfi là reste une divergence.
"""
from __future__ import annotations

from generation.arithmetique import sources_divergentes


def test_trois_graphies_du_meme_concurrent_ne_divergent_pas() -> None:
    textes = [
        "Le séjour est facturé 890 € (Namastrip, référence testée).",
        "Un tarif de 890 € (référence Namastrip) se retrouve sur le segment premium.",
        "La médiane du segment s'établit à 890 € (Namastrip).",
    ]
    assert sources_divergentes(textes) == []


def test_deux_organismes_pour_le_meme_montant_divergent_toujours() -> None:
    textes = [
        "Le marché pèse 1,2 Md€ (Insee, 2025).",
        "Le marché pèse 1,2 Md€ (Xerfi, 2024).",
    ]
    (divergence,) = sources_divergentes(textes)
    assert divergence.montant.endswith("Md€")
    assert len(divergence.sources) == 2


def test_la_geographie_ne_fait_pas_l_organisme() -> None:
    """« Insee, France » et « Xerfi, France » partagent « France », pas la source."""
    textes = [
        "Le marché pèse 1,2 Md€ (Insee France, 2025).",
        "Le marché pèse 1,2 Md€ (Xerfi France, 2024).",
    ]
    assert len(sources_divergentes(textes)) == 1
