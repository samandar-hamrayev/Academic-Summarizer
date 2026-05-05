import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('summarizer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='summary',
            name='language',
            field=models.CharField(
                choices=[('en', 'English'), ('ru', 'Russian'), ('uz', 'Uzbek')],
                default='en',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='summary',
            name='citations',
            field=models.TextField(blank=True, help_text='Stored as JSON list of citation strings'),
        ),
        migrations.CreateModel(
            name='ShareLink',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token',        models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('expires_at',   models.DateTimeField(blank=True, null=True)),
                ('access_count', models.PositiveIntegerField(default=0)),
                ('is_active',    models.BooleanField(default=True)),
                ('summary',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='share_links',
                    to='summarizer.summary',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
