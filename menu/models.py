# menu/models.py
from django.db import models
from django.core.validators import MinValueValidator
import uuid # Para IDs de pedido únicos

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Categoria")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

class Sabor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Sabor")
    # Se sabores podem pertencer a categorias específicas de produto (ex: sabor de sorvete, sabor de açaí)
    # categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="sabores_categoria")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Sabor"
        verbose_name_plural = "Sabores"

class Adicional(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Adicional")
    preco = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0.0)], verbose_name="Preço")
    # Se adicionais podem ser específicos para categorias
    # categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="adicionais_categoria")

    def __str__(self):
        return f"{self.nome} (R$ {self.preco})"

    class Meta:
        verbose_name = "Adicional"
        verbose_name_plural = "Adicionais"

class Produto(models.Model):
    nome = models.CharField(max_length=200, verbose_name="Nome do Produto")
    descricao = models.TextField(verbose_name="Descrição Detalhada")
    preco_base = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.0)], verbose_name="Preço Base")
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name="produtos", verbose_name="Categoria")
    imagem = models.ImageField(upload_to='produtos_imagens/', blank=True, null=True, verbose_name="Imagem do Produto")
    disponivel = models.BooleanField(default=True, verbose_name="Disponível")

    # Relacionamentos (se um produto pode ter vários sabores/adicionais para escolha)
    sabores_disponiveis = models.ManyToManyField(Sabor, blank=True, verbose_name="Sabores Disponíveis")
    adicionais_disponiveis = models.ManyToManyField(Adicional, blank=True, verbose_name="Adicionais Disponíveis")

    # Para produtos como açaí que podem ter tamanhos diferentes com preços diferentes
    # Ex: P, M, G. Você pode criar um modelo 'Tamanho' ou simplificar aqui se os preços variam muito
    # Se o preço varia apenas por tamanho, pode ser melhor ter produtos separados (Açaí P, Açaí M)
    # ou um modelo mais complexo de 'VariacaoProduto'. Por ora, manteremos simples.

    def __str__(self):
        return f"{self.nome} - {self.categoria.nome}"

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"


# Modelos para o Pedido
class Pedido(models.Model):
    id_pedido_cliente = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="ID do Pedido (Cliente)")
    nome_cliente = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nome do Cliente") # Opcional, pode pegar no WhatsApp
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Valor Total")
    data_pedido = models.DateTimeField(auto_now_add=True, verbose_name="Data do Pedido")
    enviado_whatsapp = models.BooleanField(default=False, verbose_name="Enviado para WhatsApp")
    # Poderia adicionar status: PENDENTE, PREPARANDO, PRONTO, ENTREGUE, CANCELADO

    def __str__(self):
        return f"Pedido {self.id_pedido_cliente} - R$ {self.valor_total}"

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-data_pedido']

class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='itens', on_delete=models.CASCADE, verbose_name="Pedido")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, verbose_name="Produto")
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Quantidade")
    preco_unitario = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Preço Unitário no Momento da Compra") # Preço do produto base
    sabores_selecionados = models.ManyToManyField(Sabor, blank=True, verbose_name="Sabores Selecionados")
    adicionais_selecionados = models.ManyToManyField(Adicional, blank=True, verbose_name="Adicionais Selecionados")
    subtotal_adicionais = models.DecimalField(max_digits=8, decimal_places=2, default=0.0, verbose_name="Subtotal Adicionais")
    subtotal_item = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal do Item") # (preco_unitario + subtotal_adicionais) * quantidade

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} (Pedido {self.pedido.id_pedido_cliente})"

    def calcular_subtotal_adicionais(self):
        total = 0
        for adicional in self.adicionais_selecionados.all():
            total += adicional.preco
        return total

    def calcular_subtotal_item(self):
        preco_base_item = self.preco_unitario
        subtotal_adicionais_calc = self.calcular_subtotal_adicionais()
        self.subtotal_adicionais = subtotal_adicionais_calc # Atualiza o campo
        return (preco_base_item + subtotal_adicionais_calc) * self.quantidade

    def save(self, *args, **kwargs):
        # Atualiza o preço unitário para o preço do produto no momento da criação do item
        if not self.pk: # Se é um novo item
             self.preco_unitario = self.produto.preco_base
        # Recalcula antes de salvar. Os manytomany precisam ser salvos primeiro.
        # Isso é um pouco complexo aqui, idealmente o cálculo final é feito na view antes de salvar.
        # Por simplicidade, vamos assumir que os adicionais já estão associados.
        # Uma abordagem mais robusta seria calcular na view ou usar signals.
        self.subtotal_adicionais = self.calcular_subtotal_adicionais()
        self.subtotal_item = (self.preco_unitario + self.subtotal_adicionais) * self.quantidade
        super().save(*args, **kwargs)


    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"