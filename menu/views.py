# menu/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from .models import Produto, Categoria, Pedido, ItemPedido, Sabor, Adicional
from django.contrib import messages # Para feedback ao usuário
from decimal import Decimal
import json # Para lidar com dados JSON do frontend se necessário
from decouple import config # Para pegar o número do WhatsApp
import urllib.parse # Para formatar a mensagem do WhatsApp


def listar_produtos(request):
    categorias = Categoria.objects.prefetch_related('produtos').filter(produtos__disponivel=True).distinct()
    # Se quiser listar produtos sem categoria também:
    # produtos_sem_categoria = Produto.objects.filter(categoria__isnull=True, disponivel=True)
    context = {
        'categorias': categorias,
    }
    return render(request, 'menu/listar_produtos.html', context)

def detalhe_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, disponivel=True)
    context = {
        'produto': produto,
    }
    return render(request, 'menu/detalhe_produto.html', context)

# Lógica do Carrinho (usando sessões do Django)
# O carrinho será um dicionário na sessão.
# Chave: um ID único para o item no carrinho (pode ser produto_id ou produto_id + hash_de_configuracoes)
# Valor: {'produto_id': X, 'nome': 'Nome', 'quantidade': Y, 'preco_unitario': Z, 'sabores': [id1, id2], 'adicionais': [id1, id2], 'observacao_item': 'Texto'}

def _gerar_id_item_carrinho(produto_id, sabores_ids=None, adicionais_ids=None, observacao_item=""):
    """Gera um ID único para um item no carrinho baseado em suas configurações."""
    sabores_str = "_s" + "".join(sorted(map(str, sabores_ids))) if sabores_ids else ""
    adicionais_str = "_a" + "".join(sorted(map(str, adicionais_ids))) if adicionais_ids else ""
    observacao_hash = "_o" + str(hash(observacao_item)) if observacao_item else ""
    return f"item_{produto_id}{sabores_str}{adicionais_str}{observacao_hash}"


@require_POST # Garante que esta view só aceita requisições POST
def adicionar_ao_carrinho(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, disponivel=True)
    carrinho = request.session.get('carrinho', {})

    quantidade = int(request.POST.get('quantidade', 1))
    if quantidade < 1:
        messages.error(request, "Quantidade inválida.")
        return redirect('menu:detalhe_produto', produto_id=produto.id)

    sabores_selecionados_ids = request.POST.getlist('sabores') # Vem como lista de strings
    adicionais_selecionados_ids = request.POST.getlist('adicionais') # Vem como lista de strings
    observacao_item = request.POST.get('observacao_item', '')

    # Validar sabores e adicionais (se eles realmente pertencem ao produto, etc.) - Opcional aqui para simplificar
    # Mas é uma boa prática.

    sabores_obj = list(Sabor.objects.filter(id__in=sabores_selecionados_ids))
    adicionais_obj = list(Adicional.objects.filter(id__in=adicionais_selecionados_ids))

    preco_total_adicionais = sum(ad.preco for ad in adicionais_obj)
    preco_final_unitario = produto.preco_base + preco_total_adicionais

    item_id_carrinho = _gerar_id_item_carrinho(produto.id, sabores_selecionados_ids, adicionais_selecionados_ids, observacao_item)

    if item_id_carrinho in carrinho:
        carrinho[item_id_carrinho]['quantidade'] += quantidade
    else:
        carrinho[item_id_carrinho] = {
            'produto_id': produto.id,
            'nome': produto.nome,
            'quantidade': quantidade,
            'preco_unitario_base': str(produto.preco_base), # Armazenar como string para Decimal
            'sabores_ids': sabores_selecionados_ids,
            'sabores_nomes': [s.nome for s in sabores_obj],
            'adicionais_ids': adicionais_selecionados_ids,
            'adicionais_nomes_precos': [{'nome': a.nome, 'preco': str(a.preco)} for a in adicionais_obj],
            'subtotal_adicionais': str(preco_total_adicionais),
            'preco_final_unitario': str(preco_final_unitario), # Preço com adicionais
            'observacao_item': observacao_item,
            'imagem_url': produto.imagem.url if produto.imagem else None
        }

    request.session['carrinho'] = carrinho
    request.session.modified = True # Importante para salvar a sessão

    messages.success(request, f"{produto.nome} adicionado ao carrinho!")
    return redirect(request.POST.get('next', reverse('menu:listar_produtos')))


def ver_carrinho(request):
    carrinho = request.session.get('carrinho', {})
    itens_carrinho = []
    valor_total_carrinho = Decimal('0.00')

    for item_id, item_data in carrinho.items():
        subtotal_item = Decimal(item_data['preco_final_unitario']) * item_data['quantidade']
        itens_carrinho.append({
            'item_id_carrinho': item_id,
            'produto_id': item_data['produto_id'],
            'nome': item_data['nome'],
            'quantidade': item_data['quantidade'],
            'preco_final_unitario': Decimal(item_data['preco_final_unitario']),
            'sabores_nomes': item_data.get('sabores_nomes', []),
            'adicionais_nomes_precos': item_data.get('adicionais_nomes_precos', []),
            'observacao_item': item_data.get('observacao_item', ''),
            'imagem_url': item_data.get('imagem_url'),
            'subtotal': subtotal_item
        })
        valor_total_carrinho += subtotal_item

    # Salvar o total na sessão para usar no checkout
    request.session['valor_total_carrinho'] = str(valor_total_carrinho)

    context = {
        'itens_carrinho': itens_carrinho,
        'valor_total_carrinho': valor_total_carrinho,
        'whatsapp_number': config('WHATSAPP_NUMBER', default='')
    }
    return render(request, 'menu/ver_carrinho.html', context)


@require_POST
def remover_do_carrinho(request, item_id_carrinho):
    carrinho = request.session.get('carrinho', {})
    if item_id_carrinho in carrinho:
        del carrinho[item_id_carrinho]
        request.session['carrinho'] = carrinho
        request.session.modified = True
        messages.success(request, "Item removido do carrinho.")
    else:
        messages.error(request, "Item não encontrado no carrinho.")
    return redirect('menu:ver_carrinho')

@require_POST
def atualizar_carrinho(request, item_id_carrinho):
    carrinho = request.session.get('carrinho', {})
    nova_quantidade = int(request.POST.get('quantidade', 0))

    if item_id_carrinho in carrinho:
        if nova_quantidade > 0:
            carrinho[item_id_carrinho]['quantidade'] = nova_quantidade
            messages.success(request, "Quantidade atualizada.")
        elif nova_quantidade == 0: # Permitir zerar para remover
            del carrinho[item_id_carrinho]
            messages.success(request, "Item removido do carrinho.")
        else:
            messages.error(request, "Quantidade inválida.")

        request.session['carrinho'] = carrinho
        request.session.modified = True
    else:
        messages.error(request, "Item não encontrado no carrinho.")
    return redirect('menu:ver_carrinho')


def finalizar_pedido(request):
    carrinho = request.session.get('carrinho', {})
    if not carrinho:
        messages.warning(request, "Seu carrinho está vazio.")
        return redirect('menu:listar_produtos')

    valor_total_carrinho_str = request.session.get('valor_total_carrinho', '0.00')
    valor_total_carrinho = Decimal(valor_total_carrinho_str)

    if request.method == 'POST':
        nome_cliente = request.POST.get('nome_cliente', 'Cliente') # Pode ser opcional ou pedir no form
        observacoes_gerais = request.POST.get('observacoes_gerais', '')

        # 1. Salvar o Pedido no Banco de Dados
        novo_pedido = Pedido.objects.create(
            nome_cliente=nome_cliente,
            observacoes=observacoes_gerais,
            valor_total=valor_total_carrinho # Inicial, será recalculado e confirmado abaixo
        )

        texto_pedido_whatsapp_itens = []
        valor_total_calculado_servidor = Decimal('0.00')

        for item_id, item_data in carrinho.items():
            produto_obj = get_object_or_404(Produto, id=item_data['produto_id'])

            # Recalcular subtotal dos adicionais no servidor para segurança
            adicionais_obj_pedido = Adicional.objects.filter(id__in=item_data['adicionais_ids'])
            subtotal_adicionais_servidor = sum(ad.preco for ad in adicionais_obj_pedido)

            # Recalcular preço final unitário no servidor
            preco_final_unitario_servidor = produto_obj.preco_base + subtotal_adicionais_servidor
            subtotal_item_servidor = preco_final_unitario_servidor * int(item_data['quantidade'])
            valor_total_calculado_servidor += subtotal_item_servidor

            item_pedido = ItemPedido.objects.create(
                pedido=novo_pedido,
                produto=produto_obj,
                quantidade=item_data['quantidade'],
                preco_unitario=produto_obj.preco_base, # Preço base do produto
                subtotal_adicionais=subtotal_adicionais_servidor,
                subtotal_item=subtotal_item_servidor,
            )
            # Adicionar sabores e adicionais selecionados ao ItemPedido
            sabores_obj_pedido = Sabor.objects.filter(id__in=item_data['sabores_ids'])
            item_pedido.sabores_selecionados.set(sabores_obj_pedido)
            item_pedido.adicionais_selecionados.set(adicionais_obj_pedido)
            # item_pedido.save() # save() já é chamado no create, e o subtotal é recalculado no save do ItemPedido

            # Texto para WhatsApp
            item_txt = f"{item_data['quantidade']}x {produto_obj.nome}"
            if item_data['sabores_nomes']:
                item_txt += f" (Sabores: {', '.join(item_data['sabores_nomes'])})"

            adicionais_txt_lista = []
            if item_data['adicionais_nomes_precos']:
                for ad in item_data['adicionais_nomes_precos']:
                     adicionais_txt_lista.append(f"{ad['nome']}") # Não mostrar preço aqui, já está no total
            if adicionais_txt_lista:
                item_txt += f" (Adicionais: {', '.join(adicionais_txt_lista)})"

            if item_data.get('observacao_item'):
                item_txt += f" (Obs: {item_data['observacao_item']})"

            item_txt += f" - R$ {subtotal_item_servidor:.2f}"
            texto_pedido_whatsapp_itens.append(item_txt)

        # Atualizar o valor total do pedido com o valor calculado no servidor (mais seguro)
        novo_pedido.valor_total = valor_total_calculado_servidor
        novo_pedido.save(update_fields=['valor_total'])


        # 2. Preparar mensagem para WhatsApp
        numero_whatsapp_loja = config('WHATSAPP_NUMBER')
        if not numero_whatsapp_loja:
            messages.error(request, "Número de WhatsApp da loja não configurado.")
            # Poderia deletar o pedido ou marcar como 'erro_envio'
            novo_pedido.delete() # Ou marcar com um status de erro
            return redirect('menu:ver_carrinho')

        mensagem_whatsapp = f"Olá, Black Açaí e Sorveteria! 👋\n\n"
        mensagem_whatsapp += f"Gostaria de fazer o seguinte pedido (ID: {novo_pedido.id_pedido_cliente}):\n"
        if nome_cliente and nome_cliente.lower() != 'cliente':
            mensagem_whatsapp += f"Nome: {nome_cliente}\n\n"

        for linha_item in texto_pedido_whatsapp_itens:
            mensagem_whatsapp += f"- {linha_item}\n"

        mensagem_whatsapp += f"\n*Total do Pedido: R$ {novo_pedido.valor_total:.2f}*\n"
        if observacoes_gerais:
            mensagem_whatsapp += f"\nObservações Gerais: {observacoes_gerais}\n"

        mensagem_whatsapp += "\nAguardo a confirmação e informações sobre pagamento/retirada/entrega. Obrigado!"

        # 3. Limpar o carrinho da sessão
        request.session['carrinho'] = {}
        request.session.pop('valor_total_carrinho', None) # Remove o total da sessão
        request.session.modified = True

        # 4. Marcar pedido como enviado (ou tentar enviar)
        # Aqui você pode integrar com alguma API de WhatsApp se quiser automatizar o envio.
        # Por enquanto, vamos gerar o link para o cliente enviar.
        novo_pedido.enviado_whatsapp = True # Assume que o cliente vai clicar no link
        novo_pedido.save(update_fields=['enviado_whatsapp'])

        link_whatsapp = f"https://wa.me/{numero_whatsapp_loja}?text={urllib.parse.quote(mensagem_whatsapp)}"

        # Redirecionar para uma página de confirmação com o link do WhatsApp
        return redirect(reverse('menu:confirmacao_pedido', kwargs={'id_pedido_cliente': novo_pedido.id_pedido_cliente}) + f"?whatsapp_link={urllib.parse.quote(link_whatsapp)}")

    # Se for GET, apenas exibe o formulário de finalização (nome, observações)
    context = {
        'carrinho': carrinho, # Para exibir um resumo se quiser
        'valor_total_carrinho': valor_total_carrinho,
    }
    return render(request, 'menu/finalizar_pedido.html', context)


def confirmacao_pedido(request, id_pedido_cliente):
    pedido = get_object_or_404(Pedido, id_pedido_cliente=id_pedido_cliente)
    link_whatsapp = request.GET.get('whatsapp_link') # Pega o link da URL
    context = {
        'pedido': pedido,
        'link_whatsapp': link_whatsapp,
    }
    return render(request, 'menu/confirmacao_pedido.html', context)