# menu/urls.py
from django.urls import path
from . import views

app_name = 'menu' # Define um namespace para as URLs deste app

urlpatterns = [
    path('', views.listar_produtos, name='listar_produtos'),
    path('produto/<int:produto_id>/', views.detalhe_produto, name='detalhe_produto'), # Para ver detalhes e adicionar ao carrinho
    path('carrinho/', views.ver_carrinho, name='ver_carrinho'),
    path('adicionar_ao_carrinho/<int:produto_id>/', views.adicionar_ao_carrinho, name='adicionar_ao_carrinho'),
    path('remover_do_carrinho/<str:item_id_carrinho>/', views.remover_do_carrinho, name='remover_do_carrinho'),
    path('atualizar_carrinho/<str:item_id_carrinho>/', views.atualizar_carrinho, name='atualizar_carrinho'),
    path('finalizar_pedido/', views.finalizar_pedido, name='finalizar_pedido'),
    path('confirmacao_pedido/<uuid:id_pedido_cliente>/', views.confirmacao_pedido, name='confirmacao_pedido'),
    path('esvaziar_carrinho/', views.esvaziar_carrinho, name='esvaziar_carrinho'),
]