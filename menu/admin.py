# menu/admin.py
from django.contrib import admin
from .models import Categoria, Sabor, Adicional, Produto, Pedido, ItemPedido

class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ('preco_unitario', 'subtotal_adicionais', 'subtotal_item')

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id_pedido_cliente', 'nome_cliente', 'valor_total', 'data_pedido', 'enviado_whatsapp')
    list_filter = ('data_pedido', 'enviado_whatsapp')
    search_fields = ('id_pedido_cliente__hex', 'nome_cliente') # Corrigido para buscar UUID
    inlines = [ItemPedidoInline]
    readonly_fields = ('id_pedido_cliente', 'data_pedido', 'valor_total')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        pedido = form.instance
        total_pedido = sum(item.subtotal_item for item in pedido.itens.all())
        pedido.valor_total = total_pedido
        pedido.save(update_fields=['valor_total'])

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem', 'descricao')
    search_fields = ('nome',)
    list_editable = ('ordem',)

@admin.register(Sabor)
class SaborAdmin(admin.ModelAdmin):
    # { ATUALIZADO }
    list_display = ('nome', 'preco')
    search_fields = ('nome',)
    list_editable = ('preco',)

@admin.register(Adicional)
class AdicionalAdmin(admin.ModelAdmin):
    # { ATUALIZADO }
    list_display = ('nome', 'preco', 'tipo')
    search_fields = ('nome',)
    list_filter = ('tipo', 'preco')
    list_editable = ('preco', 'tipo')

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'preco_base', 'disponivel')
    list_filter = ('categoria', 'disponivel')
    search_fields = ('nome', 'descricao', 'categoria__nome')
    filter_horizontal = ('sabores_disponiveis', 'adicionais_disponiveis')