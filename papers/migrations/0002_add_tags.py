from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id',    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name',  models.CharField(max_length=50, unique=True)),
                ('slug',  models.SlugField(blank=True, unique=True)),
                ('color', models.CharField(default='#4361ee', max_length=7)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='paper',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='papers', to='papers.tag'),
        ),
    ]
