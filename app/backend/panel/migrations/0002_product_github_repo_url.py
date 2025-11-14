# Generated migration for adding github_repo_url to Product

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='github_repo_url',
            field=models.CharField(blank=True, help_text='URL del repositorio GitHub del código base', max_length=500),
        ),
    ]
