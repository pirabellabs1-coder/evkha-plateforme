"""La mémoire d'une étude, assemblée : faits, décisions, et ce que le rédacteur en lit.

Construite une fois, au démarrage de la rédaction, depuis le socle verrouillé et
les réponses du questionnaire ; puis donnée à CHAQUE chapitre sous la même
forme. Déterministe : le même socle et le même brief donnent la même mémoire,
ce qui permet de re-rendre un chapitre sans le réécrire.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from generation.socle.schema import Socle

from .decisions import decisions_de_l_etude
from .faits import Fait, faits_de_l_etude
from .regles import Decision
from .reperes import valeur_affichee


@dataclass
class MemoireEtude:
    faits: dict[str, Fait]
    decisions: list[Decision] = field(default_factory=list)

    @classmethod
    def construire(cls, socle: Socle, variables: Mapping[str, object]) -> MemoireEtude:
        faits = faits_de_l_etude(socle)
        return cls(faits=faits, decisions=decisions_de_l_etude(socle, variables, faits))

    def en_dict(self) -> dict[str, object]:
        """La forme stockée et exposée au rapport interne."""
        return {
            "faits": {
                f.id: {
                    "valeur": f.valeur, "unite": f.unite, "annee": f.annee,
                    "libelle": f.libelle, "origine": f.origine, "formule": f.formule,
                    "depuis": list(f.depuis), "definition": f.definition,
                }
                for f in self.faits.values()
            },
            "decisions": [
                {"sujet": d.sujet, "valeur": d.valeur, "annee": d.annee,
                 "justification": d.justification, "source": d.source}
                for d in self.decisions
            ],
        }

    def bloc_pour_le_redacteur(self) -> str:
        """Ce que chaque chapitre reçoit : les faits à citer, les décisions à tenir."""
        lignes = [
            "MÉMOIRE DE L'ÉTUDE — source unique des chiffres et des décisions.",
            "",
            "CHIFFRES : tout chiffre du projet s'écrit par son repère, jamais en clair : "
            "{{identifiant}}. Le rendu écrit la valeur exacte au bon format. N'effectue "
            "AUCUN calcul toi-même : chaque écart, évolution, part ou moyenne mensuelle "
            "dont tu as besoin est dans la liste. Si un chiffre te manque, ne l'écris pas.",
        ]
        for fait in self.faits.values():
            formule = f" = {fait.formule}" if fait.formule else ""
            definition = f" — {fait.definition}" if fait.definition else ""
            lignes.append(
                f"- {{{{{fait.id}}}}} : {valeur_affichee(fait)} — {fait.libelle}"
                f"{formule}{definition}"
            )
        if self.decisions:
            lignes += [
                "",
                "DÉCISIONS DU DOSSIER — à reprendre telles quelles, jamais contredites ni "
                "reformulées (une date, un statut, un compte se citent à l'identique) :",
            ]
            for decision in self.decisions:
                annee = f" [{decision.annee}]" if decision.annee else ""
                lignes.append(
                    f"- {decision.sujet}{annee} : {decision.valeur} ({decision.justification})"
                )
        return "\n".join(lignes)
