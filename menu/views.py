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
from django.db.models import Prefetch
from decimal import Decimal
import hashlib # Para _gerar_id_item_carrinho
import json    # Para _gerar_id_item_carrinho


def listar_produtos(request):
    # Buscamos categorias que tenham produtos disponíveis,
    # ordenamos pela nossa nova coluna 'ordem' e depois por 'nome' como desempate.
    # Usamos Prefetch para otimizar a busca dos produtos já filtrados por disponibilidade.
    
    categorias_ordenadas = Categoria.objects.filter(
        produtos__disponivel=True  # Garante que a categoria tem pelo menos um produto disponível
    ).order_by(
        'ordem', 'nome' # Ordena as categorias
    ).distinct().prefetch_related(
        Prefetch('produtos', queryset=Produto.objects.filter(disponivel=True).order_by('nome')) # Pega apenas produtos disponíveis
    )

    # Debug (opcional, remover depois)
    # print("--- Categorias Ordenadas para o Template ---")
    # for cat in categorias_ordenadas:
    #     print(f"Ordem: {cat.ordem}, Nome: {cat.nome}")
    #     for prod in cat.produtos.all(): # produtos aqui já estarão filtrados pelo prefetch
    #          print(f"  - Produto: {prod.nome}")


    context = {
        'categorias': categorias_ordenadas,
    }
    return render(request, 'menu/listar_produtos.html', context)

def detalhe_produto(request, produto_id):
    # Carregando o produto e seus sabores/adicionais relacionados
    produto = get_object_or_404(
        Produto.objects.prefetch_related('sabores_disponiveis', 'adicionais_disponiveis'),
        pk=produto_id
    )

    context = {
        'produto': produto,
        'sabores_disponiveis': produto.sabores_disponiveis.all(), # Pegar os sabores específicos deste produto
        'adicionais_disponiveis': produto.adicionais_disponiveis.all(), # Pegar os adicionais específicos deste produto
    }
    return render(request, 'menu/detalhe_produto.html', context)

# Lógica do Carrinho (usando sessões do Django)
# O carrinho será um dicionário na sessão.
# Chave: um ID único para o item no carrinho (pode ser produto_id ou produto_id + hash_de_configuracoes)
# Valor: {'produto_id': X, 'nome': 'Nome', 'quantidade': Y, 'preco_unitario': Z, 'sabores': [id1, id2], 'adicionais': [id1, id2], 'observacao_item': 'Texto'}

def _gerar_id_item_carrinho(produto_id, sabores_com_quantidades, adicionais_com_quantidades, observacao_item):
    # Crie uma tupla ou lista ordenada para garantir a consistência do hash
    # para sabores e adicionais com quantidades
    sabores_data = sorted([f"{s['id']}-{s['quantidade']}" for s in sabores_com_quantidades])
    adicionais_data = sorted([f"{a['id']}-{a['quantidade']}" for a in adicionais_com_quantidades])

    # Concatena todos os elementos relevantes em uma string para hashing
    unique_string = f"{produto_id}-{'_'.join(sabores_data)}-{'_'.join(adicionais_data)}-{observacao_item}"
    
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()


@require_POST
def adicionar_ao_carrinho(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, disponivel=True)
    carrinho = request.session.get('carrinho', {})

    quantidade_principal_produto_input = int(request.POST.get('quantidade', 0)) # Default 0 para facilitar lógica abaixo

    # --- SABORES ---
    sabores_com_quantidades_input = [] # Lista de {'id': X, 'quantidade': Y} para ID do carrinho
    sabores_selecionados_para_db = []  # Lista de IDs para ItemPedido.sabores_selecionados
    sabores_info_para_sessao = []      # Lista de {'nome': ..., 'quantidade': ..., 'preco_unitario_extra': ..., 'subtotal_extra': ...}
    
    preco_total_sabores_extras = Decimal('0.00') # Custo ADICIONAL dos sabores

    # Verifica se o produto tem sabores_disponiveis antes de tentar iterar
    if hasattr(produto, 'sabores_disponiveis') and produto.sabores_disponiveis.exists():
        sabores_disponiveis_objs = produto.sabores_disponiveis.all()
        for sabor_obj in sabores_disponiveis_objs:
            sabor_quantidade_str = request.POST.get(f'sabores_quantities_{sabor_obj.id}', '0')
            sabor_quantidade = int(sabor_quantidade_str) if sabor_quantidade_str.isdigit() else 0
            
            if sabor_quantidade > 0:
                sabores_com_quantidades_input.append({'id': sabor_obj.id, 'quantidade': sabor_quantidade})
                sabores_selecionados_para_db.append(sabor_obj.id)
                
                sabor_preco_individual = getattr(sabor_obj, 'preco', Decimal('0.00')) # Pega Sabor.preco, default 0
                subtotal_sabor_extra = sabor_preco_individual * sabor_quantidade
                preco_total_sabores_extras += subtotal_sabor_extra
                
                sabores_info_para_sessao.append({
                    'nome': sabor_obj.nome,
                    'quantidade': sabor_quantidade,
                    'preco_unitario_extra': str(sabor_preco_individual),
                    'subtotal_extra': str(subtotal_sabor_extra)
                })

    # --- ADICIONAIS --- (lógica existente, mas garantindo que adicionais_disponiveis existe)
    adicionais_com_quantidades_input = []
    adicionais_selecionados_para_db = []
    adicionais_info_para_sessao = []
    preco_total_adicionais = Decimal('0.00')

    if hasattr(produto, 'adicionais_disponiveis') and produto.adicionais_disponiveis.exists():
        adicionais_disponiveis_objs = produto.adicionais_disponiveis.all()
        adicionais_obj_map = {ad.id: ad for ad in adicionais_disponiveis_objs}
        for adicional_id_str in request.POST.getlist('adicionais'): # Nome do checkbox
            adicional_id = int(adicional_id_str)
            adicional_obj = adicionais_obj_map.get(adicional_id)
            if adicional_obj:
                adicional_quantidade_str = request.POST.get(f'adicionais_quantities_{adicional_id}', '1')
                adicional_quantidade = int(adicional_quantidade_str) if adicional_quantidade_str.isdigit() and int(adicional_quantidade_str) > 0 else 1
                
                adicionais_com_quantidades_input.append({'id': adicional_obj.id, 'quantidade': adicional_quantidade})
                adicionais_selecionados_para_db.append(adicional_obj.id)
                subtotal_adicional = adicional_obj.preco * adicional_quantidade
                preco_total_adicionais += subtotal_adicional
                adicionais_info_para_sessao.append({
                    'nome': adicional_obj.nome,
                    'quantidade': adicional_quantidade,
                    'preco_unitario': str(adicional_obj.preco),
                    'subtotal': str(subtotal_adicional)
                })

    # --- DETERMINAR QUANTIDADE FINAL PARA O ITEM NO CARRINHO ---
    soma_quantidades_sabores = sum(s_info['quantidade'] for s_info in sabores_com_quantidades_input)
    
    quantidade_final_para_item_carrinho = 0

    if soma_quantidades_sabores > 0:
        quantidade_final_para_item_carrinho = soma_quantidades_sabores
        # Opcional: Avisar se a quantidade principal foi ignorada
        # if quantidade_principal_produto_input > 0 and quantidade_principal_produto_input != soma_quantidades_sabores:
        # messages.info(request, f"A quantidade de '{produto.nome}' foi definida pela soma dos sabores ({soma_quantidades_sabores}).")
    elif quantidade_principal_produto_input > 0:
        quantidade_final_para_item_carrinho = quantidade_principal_produto_input
    
    if quantidade_final_para_item_carrinho <= 0:
        messages.error(request, f"Por favor, defina uma quantidade para '{produto.nome}' ou para seus sabores.")
        return redirect(request.POST.get('next', reverse('menu:detalhe_produto', kwargs={'produto_id': produto.id})))

    # --- PREÇO FINAL UNITÁRIO DO PRODUTO (preço de UMA unidade base + custos extras de opções) ---
    # Para picolés, se Sabor.preco = 0, preco_total_sabores_extras será 0.
    # O preco_final_unitario_do_produto será então produto.preco_base (ex: R$1.10).
    # E a quantidade_final_para_item_carrinho (ex: 10 picolés) multiplicará este valor.
    preco_final_unitario_do_produto = produto.preco_base + preco_total_sabores_extras + preco_total_adicionais
    observacao_item = request.POST.get('observacao_item', '')

    item_id_carrinho = _gerar_id_item_carrinho(
        produto.id,
        sabores_com_quantidades_input,
        adicionais_com_quantidades_input,
        observacao_item
    )

    if item_id_carrinho in carrinho:
        # Item já existe, somar a nova quantidade (que já foi determinada acima)
        carrinho[item_id_carrinho]['quantidade'] += quantidade_final_para_item_carrinho
        # Se precisar concatenar observações ou algo assim, adicione lógica aqui.
        # carrinho[item_id_carrinho]['observacao_item'] += f"; {observacao_item}" # Exemplo
    else:
        carrinho[item_id_carrinho] = {
            'produto_id': produto.id,
            'nome': produto.nome,
            'quantidade': quantidade_final_para_item_carrinho, # Quantidade total do item
            'preco_unitario_base': str(produto.preco_base), # Preço base do produto
            
            'sabores_detalhados': sabores_info_para_sessao,    # Detalhes dos sabores selecionados
            'sabores_ids_para_db': sabores_selecionados_para_db, # IDs para salvar M2M

            'adicionais_detalhados': adicionais_info_para_sessao, # Detalhes dos adicionais
            'adicionais_ids_para_db': adicionais_selecionados_para_db,

            'subtotal_sabores_extras': str(preco_total_sabores_extras), # Custo extra total SÓ dos sabores
            'subtotal_adicionais': str(preco_total_adicionais),     # Custo extra total SÓ dos adicionais
            'preco_final_unitario': str(preco_final_unitario_do_produto), # Preço de UMA unidade (base + todas opções)
            'observacao_item': observacao_item,
            'imagem_url': produto.imagem.url if produto.imagem else None
        }

    request.session['carrinho'] = carrinho
    request.session.modified = True

    messages.success(request, f"'{produto.nome}' (x{quantidade_final_para_item_carrinho}) adicionado ao carrinho!")
    return redirect(request.POST.get('next', reverse('menu:listar_produtos')))


def ver_carrinho(request):
    carrinho_session = request.session.get('carrinho', {})
    itens_carrinho_formatados = []
    valor_total_carrinho = Decimal('0.00')

    for item_id_carrinho, item_data in carrinho_session.items():
        preco_unitario_base = Decimal(item_data.get('preco_unitario_base', '0.00'))
        preco_final_unitario = Decimal(item_data.get('preco_final_unitario', '0.00'))
        quantidade = item_data.get('quantidade', 1)

        subtotal_item = preco_final_unitario * quantidade
        valor_total_carrinho += subtotal_item

        itens_carrinho_formatados.append({
            'item_id_carrinho': item_id_carrinho,
            'produto_id': item_data.get('produto_id'),
            'nome': item_data.get('nome'),
            'quantidade': quantidade,
            'preco_unitario_base': preco_unitario_base,
            'preco_final_unitario': preco_final_unitario, # Preço unitário já com adicionais
            
            # NOVO: Use 'sabores_com_quantidades'
            'sabores_com_quantidades': item_data.get('sabores_com_quantidades', []),
            
            'adicionais_com_quantidades': item_data.get('adicionais_com_quantidades', []),
            'observacao_item': item_data.get('observacao_item', ''),
            'imagem_url': item_data.get('imagem_url'),
            'subtotal': subtotal_item, # Subtotal calculado para este item
        })

    context = {
        'itens_carrinho': itens_carrinho_formatados,
        'valor_total_carrinho': valor_total_carrinho,
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
    carrinho_session = request.session.get('carrinho', {}) # Renomeado para consistência com o exemplo
    if not carrinho_session:
        messages.warning(request, "Seu carrinho está vazio.")
        return redirect('menu:listar_produtos')

    valor_total_carrinho_str = request.session.get('valor_total_carrinho', '0.00')
    valor_total_carrinho = Decimal(valor_total_carrinho_str)

    if request.method == 'POST':
        nome_cliente = request.POST.get('nome_cliente', 'Cliente') # Pode ser opcional ou pedir no form
        observacoes_gerais = request.POST.get('observacoes_gerais', '')

        # 1. Salvar o Pedido no Banco de Dados
        # Use try-except para capturar possíveis erros na criação do Pedido
        try:
            novo_pedido = Pedido.objects.create(
                nome_cliente=nome_cliente,
                observacoes=observacoes_gerais,
                valor_total=valor_total_carrinho # Inicial, será recalculado e confirmado abaixo
            )
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao criar o pedido: {e}. Por favor, tente novamente.')
            return redirect('menu:ver_carrinho') # Redireciona para o carrinho em caso de erro

        texto_pedido_whatsapp_itens = []
        valor_total_calculado_servidor = Decimal('0.00')

        # Adiciona os Itens do Pedido (AQUI ESTÃO AS PRINCIPAIS ALTERAÇÕES DO MEU EXEMPLO)
        for item_id_carrinho, item_data in carrinho_session.items(): # Renomeado para consistência
            produto_obj = get_object_or_404(Produto, id=item_data['produto_id'])

            # RECALCULAR NO SERVIDOR:
            # Recalcular subtotal dos adicionais no servidor para segurança
            adicionais_obj_pedido = Adicional.objects.filter(id__in=item_data.get('adicionais_ids_para_db', [])) # Use o novo nome e fallback para lista vazia
            subtotal_adicionais_servidor = sum(ad.preco for ad in adicionais_obj_pedido)

            # Recalcular preço final unitário no servidor
            preco_final_unitario_servidor = produto_obj.preco_base + subtotal_adicionais_servidor
            subtotal_item_servidor = preco_final_unitario_servidor * int(item_data['quantidade'])
            valor_total_calculado_servidor += subtotal_item_servidor

            # CRIAÇÃO DO ITEMPEDIDO COM OS VALORES CALCULADOS NO SERVIDOR:
            item_pedido = ItemPedido.objects.create(
                pedido=novo_pedido,
                produto=produto_obj,
                quantidade=item_data['quantidade'],
                preco_unitario=produto_obj.preco_base, # Preço base do produto (como estava na sua original)
                subtotal_adicionais=subtotal_adicionais_servidor, # Usa o valor calculado no servidor
                subtotal_item=subtotal_item_servidor,             # Usa o valor calculado no servidor
            )

            # Adiciona os ManyToManyFields (COM OS NOVOS NOMES DE CAMPO DA SESSÃO):
            if item_data.get('sabores_ids_para_db'): # Usando o novo nome do campo da sessão
                item_pedido.sabores_selecionados.set(Sabor.objects.filter(id__in=item_data['sabores_ids_para_db']))

            if item_data.get('adicionais_ids_para_db'): # Usando o novo nome do campo da sessão
                item_pedido.adicionais_selecionados.set(Adicional.objects.filter(id__in=item_data['adicionais_ids_para_db']))

            # item_pedido.save() # Já é chamado no create, não precisa chamar novamente.

            # Texto para WhatsApp (adaptado para usar os campos da sessão e nomes corretos)
            item_txt = f"{item_data['quantidade']}x {produto_obj.nome}"
            if item_data.get('sabores_nomes'): # Use .get() para evitar KeyError se não existir
                item_txt += f" (Sabores: {', '.join(item_data['sabores_nomes'])})"

            adicionais_txt_lista = []
            if item_data.get('adicionais_nomes_precos'): # Use .get()
                for ad in item_data['adicionais_nomes_precos']:
                    adicionais_txt_lista.append(f"{ad['nome']}")
            if adicionais_txt_lista:
                item_txt += f" (Adicionais: {', '.join(adicionais_txt_lista)})"

            if item_data.get('observacao_item'): # Use .get()
                item_txt += f" (Obs: {item_data['observacao_item']})"

            item_txt += f" - R$ {subtotal_item_servidor:.2f}"
            texto_pedido_whatsapp_itens.append(item_txt)

        # Atualizar o valor total do pedido com o valor calculado no servidor (mais seguro)
        novo_pedido.valor_total = valor_total_calculado_servidor
        novo_pedido.save(update_fields=['valor_total'])

        # 2. Preparar mensagem para WhatsApp
        numero_whatsapp_loja = config('WHATSAPP_NUMBER')
        if not numero_whatsapp_loja:
            messages.error(request, "Número de WhatsApp da loja não configurado. Não foi possível gerar o link de envio.")
            # Você pode escolher o que fazer aqui:
            # 1. Deletar o pedido recém-criado: novo_pedido.delete()
            # 2. Marcar o pedido com um status de erro de envio: novo_pedido.status = 'erro_whatsapp'; novo_pedido.save()
            # 3. Simplesmente não gerar o link e permitir que o cliente veja o pedido sem a opção de WhatsApp.
            # No seu original, você deleta. Mantenho essa lógica.
            novo_pedido.delete()
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
        request.session.pop('valor_total_carrinho', None)
        request.session.modified = True
        messages.success(request, "Seu pedido foi finalizado com sucesso!") # Adicionei aqui para ser mais claro

        # 4. Marcar pedido como enviado (ou tentar enviar)
        novo_pedido.enviado_whatsapp = True
        novo_pedido.save(update_fields=['enviado_whatsapp'])

        link_whatsapp = f"https://wa.me/{numero_whatsapp_loja}?text={urllib.parse.quote(mensagem_whatsapp)}"

        # Redirecionar para uma página de confirmação com o link do WhatsApp
        return redirect(reverse('menu:confirmacao_pedido', kwargs={'id_pedido_cliente': novo_pedido.id_pedido_cliente}) + f"?whatsapp_link={urllib.parse.quote(link_whatsapp)}")

    # Se for GET, apenas exibe o formulário de finalização (nome, observações)
    context = {
        'carrinho': carrinho_session, # Use o nome atualizado
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