# Generated by Django 5.2.1 on 2025-06-05 14:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0003_pedido_cpf_cliente_pedido_endereco_cliente_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pedido',
            name='cpf_cliente',
        ),
        migrations.AlterField(
            model_name='pedido',
            name='nome_cliente',
            field=models.CharField(default='Cliente Antigo', max_length=150, verbose_name='Nome Completo do Cliente'),
            preserve_default=False,
        ),
    ]
