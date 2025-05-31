# menu/admin.py
from django.contrib import admin
from .models import Categoria, Sabor, Adicional, Produto, Pedido, ItemPedido

class ItemPedidoInline(admin.TabularInline): # Ou admin.StackedInline
    model = ItemPedido
    extra = 0 # Não mostrar itens vazios para adicionar por padrão
    readonly_fields = ('preco_unitario', 'subtotal_adicionais', 'subtotal_item') # Campos calculados
    # raw_id_fields = ['produto'] # Para buscar produto por ID se a lista for muito grande

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id_pedido_cliente', 'nome_cliente', 'valor_total', 'data_pedido', 'enviado_whatsapp')
    list_filter = ('data_pedido', 'enviado_whatsapp')
    search_fields = ('id_pedido_cliente', 'nome_cliente')
    inlines = [ItemPedidoInline]
    readonly_fields = ('id_pedido_cliente', 'data_pedido', 'valor_total') # Campos que não devem ser editados manualmente aqui

    def save_model(self, request, obj, form, change):
        # Recalcular valor total do pedido se necessário, embora seja melhor fazer isso via ItemPedido.save()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Após salvar os itens do pedido, recalcular e salvar o valor total do pedido
        pedido = form.instance
        total_pedido = 0
        for item in pedido.itens.all():
            total_pedido += item.subtotal_item
        pedido.valor_total = total_pedido
        pedido.save(update_fields=['valor_total'])


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao')
    search_fields = ('nome',)

@admin.register(Sabor)
class SaborAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(Adicional)
class AdicionalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'preco')
    search_fields = ('nome',)
    list_filter = ('preco',)

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'preco_base', 'disponivel')
    list_filter = ('categoria', 'disponivel')
    search_fields = ('nome', 'descricao', 'categoria__nome')
    filter_horizontal = ('sabores_disponiveis', 'adicionais_disponiveis') # Melhor interface para ManyToMany
    # Se você adicionar 'tamanhos' ou 'variações', pode listá-los aqui também

# Não precisa registrar ItemPedido separadamente se ele está como inline no PedidoAdmin
# admin.site.register(ItemPedido)