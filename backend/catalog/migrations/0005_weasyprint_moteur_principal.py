"""WeasyPrint devient le moteur de mise en page ; Gamma est desactive.

Decision prise APRES mesure, pas par principe. La migration precedente
(0004) activait Gamma partout : c'etait la bonne chose a faire pour le tester,
puisqu'il n'avait jamais tourne une seule fois. On l'a teste, et voici ce que
le premier vrai dossier a montre.

CE QUE GAMMA FAIT AU DOCUMENT
Gamma borne une carte a ~500 mots. Le decoupage produit une carte par
chapitre. Sa capacite est donc `nb_chapitres x 500 mots` — et AUCUN livrable
EVKHA n'y rentre :

    livrable            cible mots   capacite Gamma
    business_plan           25 900           10 000
    market_study            32 400           11 500
    business_strategy       26 400           10 000
    competitor_study        16 600            5 000

Mesure sur le BP SYNAPSES reel : 38 707 mots en entree, 10 121 en sortie
(26 %). Avec le reglage d'origine (cardSplit=auto), c'etait pire : 3 835 mots
et CINQ verticales sur dix effacees — dont le self-stockage et l'hebergement
de serveurs, exactement les trois que la cliente signalait comme disparues.
Active tel quel, Gamma aggravait le probleme qu'on corrigeait.

POURQUOI WEASYPRINT
Ce n'est pas un repli faute de mieux :
- il ne tronque rien : il rend exactement le markdown valide par le gate ;
- il implemente DEJA la charte du Bloc 6 des Consignes (or #C9A227, noir
  #1A1A1A, creme #FBF8EF, Carlito/Calibri, encadres mentor, pagination) ;
- il gere le SOMMAIRE PAGINE (`target-counter`), exige par les Consignes. Les
  alternatives testees ne le font pas : wkhtmltopdf est archive depuis
  janvier 2023, et PlutoPrint (teste ici) renvoie 0 comme numero de page ;
- ses bibliotheques systeme sont deja dans le Dockerfile, police Carlito
  comprise.

Une presentation en cartes et un dossier bancaire de 80 pages ne sont pas le
meme objet. Gamma est un bon outil pour le mauvais livrable.

CE QUI RESTE
Le client Gamma, le controle de fidelite et le flag `gamma_enabled` restent
en place : une offre courte et visuelle pourra le reactiver offre par offre.
Le controle de fidelite a d'ailleurs fait son travail — il a refuse de livrer
le document ampute a 26 %.
"""
from django.db import migrations, models


def desactiver_gamma(apps, schema_editor):
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.update(gamma_enabled=False)


def reactiver_gamma(apps, schema_editor):
    """Retour arriere : reactive Gamma partout (etat de la migration 0004)."""
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.update(gamma_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_activer_gamma_partout"),
    ]

    operations = [
        # Le defaut du champ aussi : sans cela, une offre creee demain
        # reactiverait Gamma sans que personne ne l'ait decide.
        migrations.AlterField(
            model_name="offer",
            name="gamma_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(desactiver_gamma, reactiver_gamma),
    ]
