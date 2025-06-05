# menu/models.py
from django.db import models
from django.core.validators import MinValueValidator
import uuid 


class Categoria(models.Model): 
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Categoria") 
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição") 
    ordem = models.PositiveIntegerField( 
        default=0, 
        verbose_name="Ordem de Exibição", 
        help_text="Defina a ordem (ex: 0, 1, 2...). Categorias com números menores aparecem primeiro." 
    ) 

    def __str__(self): 
        return self.nome 

    class Meta: 
        verbose_name = "Categoria" 
        verbose_name_plural = "Categorias" # Corrected
        ordering = ['ordem', 'nome'] 

class Sabor(models.Model): 
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Sabor") 

    def __str__(self): 
        return self.nome 

    class Meta: 
        verbose_name = "Sabor" 
        verbose_name_plural = "Sabores" # Corrected

class Adicional(models.Model): 
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Adicional") 
    preco = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0.0)], verbose_name="Preço") 

    def __str__(self): 
        return f"{self.nome} (R$ {self.preco})" 

    class Meta: 
        verbose_name = "Adicional" 
        verbose_name_plural = "Adicionais" # Corrected

class Produto(models.Model): 
    nome = models.CharField(max_length=200, verbose_name="Nome do Produto") 
    descricao = models.TextField(verbose_name="Descrição Detalhada") 
    preco_base = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.0)], verbose_name="Preço Base") 
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name="produtos", verbose_name="Categoria") 
    imagem = models.ImageField(upload_to='produtos_imagens/', blank=True, null=True, verbose_name="Imagem do Produto") 
    disponivel = models.BooleanField(default=True, verbose_name="Disponível") 

    sabores_disponiveis = models.ManyToManyField(Sabor, blank=True, verbose_name="Sabores Disponíveis") 
    adicionais_disponiveis = models.ManyToManyField(Adicional, blank=True, verbose_name="Adicionais Disponíveis") 

    def __str__(self): 
        return f"{self.nome} - {self.categoria.nome}" 

    class Meta: 
        verbose_name = "Produto" 
        verbose_name_plural = "Produtos" # Corrected


class Pedido(models.Model): 
    id_pedido_cliente = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="ID do Pedido (Cliente)") 
    nome_cliente = models.CharField(max_length=150, verbose_name="Nome Completo do Cliente") # Campo único para nome completo
    endereco_cliente = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço de Entrega") 
    telefone_cliente = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone do Cliente") 
    
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações Gerais do Pedido") 
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Valor Total") 
    data_pedido = models.DateTimeField(auto_now_add=True, verbose_name="Data do Pedido") 
    enviado_whatsapp = models.BooleanField(default=False, verbose_name="Enviado para WhatsApp") 
    
    FORMA_PAGAMENTO_CHOICES = [ 
        ('pix', 'Pix'), 
        ('cartao', 'Cartão (Débito/Crédito)'), 
        ('dinheiro', 'Dinheiro'), 
    ] 
    forma_pagamento = models.CharField( 
        max_length=10, 
        choices=FORMA_PAGAMENTO_CHOICES, 
        default='dinheiro', 
        verbose_name="Forma de Pagamento" 
    ) 
    troco_para = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Precisa de troco para") 

    def __str__(self): 
        return f"Pedido {self.id_pedido_cliente.hex[:8]} - R$ {self.valor_total}" 

    class Meta: 
        verbose_name = "Pedido" 
        verbose_name_plural = "Pedidos" # Corrected
        ordering = ['-data_pedido'] 

class ItemPedido(models.Model): 
    pedido = models.ForeignKey(Pedido, related_name='itens', on_delete=models.CASCADE, verbose_name="Pedido") 
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, verbose_name="Produto") 
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Quantidade") 
    preco_unitario = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Preço Unitário no Momento da Compra") 
    sabores_selecionados = models.ManyToManyField(Sabor, blank=True, verbose_name="Sabores Selecionados") 
    adicionais_selecionados = models.ManyToManyField(Adicional, blank=True, verbose_name="Adicionais Selecionados") 
    subtotal_adicionais = models.DecimalField(max_digits=8, decimal_places=2, default=0.0, verbose_name="Subtotal Adicionais") 
    subtotal_item = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal do Item") 

    def __str__(self): 
        return f"{self.quantidade}x {self.produto.nome} (Pedido {self.pedido.id_pedido_cliente.hex[:8]})"

    def calcular_subtotal_adicionais(self): 
        total = 0 
        for adicional in self.adicionais_selecionados.all(): 
            total += adicional.preco 
        return total 

    def calcular_subtotal_item(self): 
        preco_base_item = self.preco_unitario 
        subtotal_adicionais_calc = self.calcular_subtotal_adicionais() 
        self.subtotal_adicionais = subtotal_adicionais_calc 
        return (preco_base_item + subtotal_adicionais_calc) * self.quantidade 

    def save(self, *args, **kwargs): 
        if not self.pk: 
            self.preco_unitario = self.produto.preco_base 
        super().save(*args, **kwargs) 


    class Meta: 
        verbose_name = "Item do Pedido" 
        verbose_name_plural = "Itens do Pedido" # Corrected