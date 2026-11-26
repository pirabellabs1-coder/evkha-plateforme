"""Un premier modèle, pour que l'onglet « Modèles » montre d'emblée la mise
en page d'une newsletter EVKHA (demande du 26/11/2026 : « on doit voir le
modèle »). Créé seulement si aucun modèle n'existe ; la gérante le modifie
ou le supprime comme les autres."""
from django.db import migrations

CORPS = (
    "<h1>Les nouvelles d'EVKHA</h1>"
    "<p>Bonjour,</p>"
    "<p>Voici ce qui a bougé ce mois-ci chez EVKHA, et ce qui peut vous servir "
    "pour avancer sur votre projet.</p>"
    "<h2>À la une</h2>"
    "<p>Présentez ici la nouveauté du mois : une étude, une formation, un "
    "conseil. Deux ou trois phrases suffisent.</p>"
    "<h2>Le portrait du mois</h2>"
    "<p>Un porteur de projet que vous accompagnez : son projet, sa difficulté, "
    "ce qui l'a fait avancer.</p>"
    '<blockquote style="margin:16px 0;padding:4px 16px;border-left:3px solid #c8a24a;'
    'color:#555555"><p>Une phrase de lui, entre guillemets.</p></blockquote>'
    '<p><a href="https://evkha.fr/blog" target="_blank" rel="noopener noreferrer">'
    "Lire les portraits sur le blog</a></p>"
    '<hr style="border:0;border-top:1px solid #e6e6e6;margin:24px 0">'
    "<p>À très vite,<br>Evangéline</p>"
)


def creer(apps, schema_editor):  # type: ignore[no-untyped-def]
    # HTML figé, déjà conforme au nettoyage : une migration ne doit pas
    # dépendre du code du jour (rejouée sur une base vide dans un an).
    Modele = apps.get_model("lettre", "Modele")
    if Modele.objects.exists():
        return
    Modele.objects.create(
        nom="Modèle EVKHA",
        objet="Les nouvelles d'EVKHA",
        apercu="Ce qui a bougé ce mois-ci, et ce qui peut vous servir.",
        corps_html=CORPS,
    )


class Migration(migrations.Migration):
    dependencies = [("lettre", "0001_initial")]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
