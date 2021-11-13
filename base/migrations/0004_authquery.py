# Generated by Django 3.2.9 on 2021-11-13 03:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_auto_20211111_0801'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthQuery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('handle', models.CharField(max_length=40)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('rating', models.IntegerField(default=1400)),
                ('contest_id', models.IntegerField(default=1400)),
                ('index', models.CharField(max_length=4)),
                ('valid', models.BooleanField(default=False)),
            ],
        ),
    ]
