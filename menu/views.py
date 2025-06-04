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
import hashlib # Para _gerar_id_item_carrinho


def listar_produtos(request):
    categorias_ordenadas = Categoria.objects.filter(
        produtos__disponivel=True  # Garante que a categoria tem pelo menos um produto disponível
    ).order_by(
        'ordem', 'nome' # Ordena as categorias
    ).distinct().prefetch_related(
        Prefetch('produtos', queryset=Produto.objects.filter(disponivel=True).order_by('nome')) # Pega apenas produtos disponíveis
    )
    context = {
        'categorias': categorias_ordenadas,
    }
    return render(request, 'menu/listar_produtos.html', context)

def detalhe_produto(request, produto_id):
    produto = get_object_or_404(Produto, pk=produto_id) 
    sabores_disponiveis = produto.sabores_disponiveis.all()
    adicionais_disponiveis = produto.adicionais_disponiveis.all()
    categoria_nome = produto.categoria.nome if produto.categoria else None

    context = {
        'produto': produto,
        'sabores_disponiveis': sabores_disponiveis,
        'adicionais_disponiveis': adicionais_disponiveis,
        'categoria_nome': categoria_nome,
    }
    return render(request, 'menu/detalhe_produto.html', context)

def _gerar_id_item_carrinho(produto_id, sabores_com_quantidades, adicionais_com_quantidades, observacao_item):
    # Crie uma tupla ou lista ordenada para garantir a consistência do hash
    sabores_data = sorted([f"{s['id']}-{s['quantidade']}" for s in sabores_com_quantidades])
    adicionais_data = sorted([f"{a['id']}-{a['quantidade']}" for a in adicionais_com_quantidades])
    unique_string = f"{produto_id}-{'_'.join(sabores_data)}-{'_'.join(adicionais_data)}-{observacao_item}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

@require_POST
def adicionar_ao_carrinho(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, disponivel=True)
    carrinho = request.session.get('carrinho', {})

    # Para bebidas direto no carrinho, pega a quantidade_bebida
    if produto.categoria.nome == 'Bebidas':
        quantidade_input = int(request.POST.get('quantidade_bebida', 1))
    else:
        # Para outros produtos, pega a quantidade principal (se houver)
        quantidade_input = int(request.POST.get('quantidade', 0))

    sabores_com_quantidades_input = []
    sabores_selecionados_para_db = []
    sabores_info_para_sessao = [] # Detalhes para exibição no carrinho

    preco_total_sabores_extras = Decimal('0.00')

    if hasattr(produto, 'sabores_disponiveis') and produto.sabores_disponiveis.exists():
        sabores_disponiveis_objs = produto.sabores_disponiveis.all()
        for sabor_obj in sabores_disponiveis_objs:
            sabor_id_str = str(sabor_obj.id)
            # Verifica se o sabor foi selecionado (checkbox marcado)
            if sabor_id_str in request.POST.getlist('sabores'):
                sabor_quantidade_str = request.POST.get(f'sabores_quantities_{sabor_obj.id}', '0')
                sabor_quantidade = int(sabor_quantidade_str) if sabor_quantidade_str.isdigit() else 0
                
                # Para Açaí, a quantidade do sabor é sempre 1 no detalhe do sabor. A quantidade final é a do produto principal.
                if produto.categoria.nome == 'Açaí':
                    sabor_quantidade = 1 # Garante que a quantidade do sabor é 1 para Açaí
                
                if sabor_quantidade > 0:
                    sabores_com_quantidades_input.append({'id': sabor_obj.id, 'quantidade': sabor_quantidade})
                    sabores_selecionados_para_db.append(sabor_obj.id)
                    
                    sabor_preco_individual = getattr(sabor_obj, 'preco', Decimal('0.00'))
                    subtotal_sabor_extra = sabor_preco_individual * sabor_quantidade
                    preco_total_sabores_extras += subtotal_sabor_extra
                    
                    sabores_info_para_sessao.append({
                        'nome': sabor_obj.nome,
                        'quantidade': sabor_quantidade,
                        'preco_unitario_extra': str(sabor_preco_individual),
                        'subtotal_extra': str(subtotal_sabor_extra)
                    })

    adicionais_com_quantidades_input = []
    adicionais_selecionados_para_db = []
    adicionais_info_para_sessao = [] # Detalhes para exibição no carrinho
    preco_total_adicionais = Decimal('0.00')

    if hasattr(produto, 'adicionais_disponiveis') and produto.adicionais_disponiveis.exists():
        adicionais_disponiveis_objs = produto.adicionais_disponiveis.all()
        adicionais_obj_map = {ad.id: ad for ad in adicionais_disponiveis_objs}
        for adicional_id_str in request.POST.getlist('adicionais'):
            adicional_id = int(adicional_id_str)
            adicional_obj = adicionais_obj_map.get(adicional_id)
            if adicional_obj:
                adicional_quantidade_str = request.POST.get(f'adicionais_quantities_{adicional_id}', '1')
                adicional_quantidade = int(adicional_quantidade_str) if adicional_quantidade_str.isdigit() and int(adicional_quantidade_str) > 0 else 1
                
                # Para Açaí, a quantidade do adicional é sempre 1.
                if produto.categoria.nome == 'Açaí':
                    adicional_quantidade = 1 # Garante que a quantidade do adicional é 1 para Açaí

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
    # Para Picolés e Potes, a quantidade final do item é a soma das quantidades dos sabores selecionados.
    # Para Açaí, a quantidade principal é a que vem do input 'quantidade'.
    # Para Bebidas, a quantidade é a que vem do input 'quantidade_bebida'.

    quantidade_final_para_item_carrinho = 0
    if produto.categoria.nome == 'Picolés' or produto.categoria.nome == 'Potes (Massa)':
        quantidade_final_para_item_carrinho = sum(s_info['quantidade'] for s_info in sabores_com_quantidades_input)
        if quantidade_final_para_item_carrinho == 0:
            messages.error(request, f"Por favor, selecione pelo menos um sabor para '{produto.nome}'.")
            return redirect(request.POST.get('next', reverse('menu:detalhe_produto', kwargs={'produto_id': produto.id})))
    elif produto.categoria.nome == 'Bebidas':
        quantidade_final_para_item_carrinho = quantidade_input
    else: # Açaí e outros produtos que usam a quantidade principal
        quantidade_final_para_item_carrinho = quantidade_input
        if quantidade_final_para_item_carrinho <= 0:
            messages.error(request, f"Por favor, defina uma quantidade para '{produto.nome}'.")
            return redirect(request.POST.get('next', reverse('menu:detalhe_produto', kwargs={'produto_id': produto.id})))


    preco_final_unitario_do_produto = produto.preco_base + preco_total_sabores_extras + preco_total_adicionais
    observacao_item = request.POST.get('observacao_item', '')

    item_id_carrinho = _gerar_id_item_carrinho(
        produto.id,
        sabores_com_quantidades_input,
        adicionais_com_quantidades_input,
        observacao_item
    )

    if item_id_carrinho in carrinho:
        carrinho[item_id_carrinho]['quantidade'] += quantidade_final_para_item_carrinho
    else:
        carrinho[item_id_carrinho] = {
            'produto_id': produto.id,
            'nome': produto.nome,
            'quantidade': quantidade_final_para_item_carrinho,
            'preco_unitario_base': str(produto.preco_base),
            
            # --- Chaves corretas para o template do carrinho ---
            'sabores_detalhados': sabores_info_para_sessao,
            'adicionais_detalhados': adicionais_info_para_sessao,
            # --- Fim das chaves corretas ---

            'sabores_ids_para_db': sabores_selecionados_para_db, 
            'adicionais_ids_para_db': adicionais_selecionados_para_db,

            'subtotal_sabores_extras': str(preco_total_sabores_extras),
            'subtotal_adicionais': str(preco_total_adicionais),
            'preco_final_unitario': str(preco_final_unitario_do_produto),
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

    # Para garantir que o valor total do carrinho seja calculado corretamente,
    # mesmo se a sessão 'valor_total_carrinho' não existir ou estiver desatualizada.
    # Essa sessão é mais para otimização ou exibição rápida, o cálculo real
    # deve vir dos itens.
    for item_id_carrinho, item_data in carrinho_session.items():
        preco_unitario_base = Decimal(item_data.get('preco_unitario_base', '0.00'))
        # Garante que preco_final_unitario é Decimal
        preco_final_unitario = Decimal(item_data.get('preco_final_unitario', str(preco_unitario_base))) 
        quantidade = item_data.get('quantidade', 1)

        subtotal_item = preco_final_unitario * quantidade
        valor_total_carrinho += subtotal_item

        itens_carrinho_formatados.append({
            'item_id_carrinho': item_id_carrinho,
            'produto_id': item_data.get('produto_id'),
            'nome': item_data.get('nome'),
            'quantidade': quantidade,
            'preco_unitario_base': preco_unitario_base,
            'preco_final_unitario': preco_final_unitario,
            
            # Garante que esses campos existam na sessão e sejam passados para o template
            'sabores_detalhados': item_data.get('sabores_detalhados', []),
            'adicionais_detalhados': item_data.get('adicionais_detalhados', []),
            
            'observacao_item': item_data.get('observacao_item', ''),
            'imagem_url': item_data.get('imagem_url'),
            'subtotal': subtotal_item,
        })
    
    # Atualiza o valor total na sessão para uso posterior (opcional, mas bom ter)
    request.session['valor_total_carrinho'] = str(valor_total_carrinho)


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
        elif nova_quantidade == 0:
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
    carrinho_session = request.session.get('carrinho', {})
    if not carrinho_session:
        messages.warning(request, "Seu carrinho está vazio.")
        return redirect('menu:listar_produtos')

    # O valor_total_carrinho deve ser recalculado ou pego de forma segura
    # já na view ver_carrinho antes de vir para cá, ou recalculado aqui.
    # Vamos pegar o valor da sessão que já foi atualizado por ver_carrinho
    valor_total_carrinho_str = request.session.get('valor_total_carrinho', '0.00')
    valor_total_carrinho = Decimal(valor_total_carrinho_str)


    if request.method == 'POST':
        nome_cliente = request.POST.get('nome_cliente', 'Cliente')
        sobrenome_cliente = request.POST.get('sobrenome_cliente', '')
        endereco_cliente = request.POST.get('endereco_cliente', '')
        telefone_cliente = request.POST.get('telefone_cliente', '')
        cpf_cliente = request.POST.get('cpf_cliente', '') # Opcional
        observacoes_gerais = request.POST.get('observacoes_gerais', '')
        forma_pagamento = request.POST.get('forma_pagamento', '')
        troco_para = request.POST.get('troco_para', '0.00')
        
        # Validar troco_para
        try:
            troco_para = Decimal(troco_para.replace(',', '.')) if troco_para else Decimal('0.00')
        except:
            troco_para = Decimal('0.00') # Reseta se for inválido

        # 1. Salvar o Pedido no Banco de Dados
        try:
            novo_pedido = Pedido.objects.create(
                nome_cliente=f"{nome_cliente} {sobrenome_cliente}".strip(),
                observacoes=observacoes_gerais,
                valor_total=valor_total_carrinho, # Usamos o valor já calculado no carrinho
                endereco_cliente=endereco_cliente, # Novo campo
                telefone_cliente=telefone_cliente, # Novo campo
                cpf_cliente=cpf_cliente,           # Novo campo
                forma_pagamento=forma_pagamento,   # Novo campo
                troco_para=troco_para              # Novo campo
            )
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao criar o pedido: {e}. Por favor, tente novamente.')
            return redirect('menu:ver_carrinho')

        texto_pedido_whatsapp_itens = []
        valor_total_calculado_servidor = Decimal('0.00') # Recalcula para segurança

        for item_id_carrinho, item_data in carrinho_session.items():
            produto_obj = get_object_or_404(Produto, id=item_data['produto_id'])

            # Recalcular subtotal dos adicionais no servidor
            adicionais_obj_pedido = Adicional.objects.filter(id__in=item_data.get('adicionais_ids_para_db', []))
            # O cálculo de subtotal_adicionais_servidor deve considerar a quantidade de cada adicional
            subtotal_adicionais_servidor = sum(
                Decimal(ad['preco_unitario']) * ad['quantidade']
                for ad in item_data.get('adicionais_detalhados', [])
            )
            
            # Recalcular preco_total_sabores_extras no servidor (se aplicável, para produtos como Picolé/Pote)
            preco_total_sabores_extras_servidor = sum(
                Decimal(sabor['preco_unitario_extra']) * sabor['quantidade']
                for sabor in item_data.get('sabores_detalhados', [])
            )

            # Recalcular preço final unitário no servidor (base + custo de sabores + custo de adicionais)
            preco_final_unitario_servidor = produto_obj.preco_base + preco_total_sabores_extras_servidor + subtotal_adicionais_servidor
            
            # Subtotal do item (preço final unitário * quantidade do item)
            subtotal_item_servidor = preco_final_unitario_servidor * int(item_data['quantidade'])
            valor_total_calculado_servidor += subtotal_item_servidor

            item_pedido = ItemPedido.objects.create(
                pedido=novo_pedido,
                produto=produto_obj,
                quantidade=item_data['quantidade'],
                preco_unitario=produto_obj.preco_base, # Preço base do produto no momento da compra
                subtotal_adicionais=subtotal_adicionais_servidor,
                subtotal_item=subtotal_item_servidor,
            )

            if item_data.get('sabores_ids_para_db'):
                item_pedido.sabores_selecionados.set(Sabor.objects.filter(id__in=item_data['sabores_ids_para_db']))
            if item_data.get('adicionais_ids_para_db'):
                item_pedido.adicionais_selecionados.set(Adicional.objects.filter(id__in=item_data['adicionais_ids_para_db']))

            # Formatação do texto para WhatsApp
            item_txt = f"{item_data['quantidade']}x {produto_obj.nome}"
            
            sabores_txt_lista = []
            if item_data.get('sabores_detalhados'):
                for s_det in item_data['sabores_detalhados']:
                    if produto.categoria.nome == 'Açaí': # Açaí: só o nome do sabor (quantidade implícita na qtde do produto)
                        sabores_txt_lista.append(s_det['nome'])
                    else: # Picolé/Pote: nome e quantidade do sabor
                        sabores_txt_lista.append(f"{s_det['nome']} ({s_det['quantidade']}x)")
            if sabores_txt_lista:
                item_txt += f" (Sabores: {', '.join(sabores_txt_lista)})"

            adicionais_txt_lista = []
            if item_data.get('adicionais_detalhados'):
                for ad_det in item_data['adicionais_detalhados']:
                    adicionais_txt_lista.append(f"{ad_det['nome']} ({ad_det['quantidade']}x)")
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
            messages.error(request, "Número de WhatsApp da loja não configurado. Não foi possível gerar o link de envio.")
            novo_pedido.delete()
            return redirect('menu:ver_carrinho')

        mensagem_whatsapp = f"Olá, Black Açaí e Sorveteria! 👋\n\n"
        mensagem_whatsapp += f"Gostaria de fazer o seguinte pedido (ID: {novo_pedido.id_pedido_cliente.hex[:8]}):\n" # Usar parte do UUID

        if nome_cliente and nome_cliente.lower() != 'cliente':
            mensagem_whatsapp += f"Nome: {nome_cliente} {sobrenome_cliente}\n"
        if telefone_cliente:
            mensagem_whatsapp += f"Telefone: {telefone_cliente}\n"
        if endereco_cliente:
            mensagem_whatsapp += f"Endereço: {endereco_cliente}\n"
        if cpf_cliente: # Opcional
            mensagem_whatsapp += f"CPF: {cpf_cliente}\n"
        
        mensagem_whatsapp += "\n*Itens do Pedido:*\n"
        for linha_item in texto_pedido_whatsapp_itens:
            mensagem_whatsapp += f"- {linha_item}\n"

        mensagem_whatsapp += f"\n*Total do Pedido: R$ {novo_pedido.valor_total:.2f}*\n"
        
        mensagem_whatsapp += f"\n*Forma de Pagamento: {forma_pagamento.capitalize()}*\n"
        if forma_pagamento == 'dinheiro' and troco_para > 0:
            mensagem_whatsapp += f"Precisa de troco para: R$ {troco_para:.2f}\n"

        if observacoes_gerais:
            mensagem_whatsapp += f"\nObservações Gerais: {observacoes_gerais}\n"

        mensagem_whatsapp += "\nAguardo a confirmação e informações sobre pagamento/retirada/entrega. Obrigado!"

        # 3. Limpar o carrinho da sessão
        request.session['carrinho'] = {}
        request.session.pop('valor_total_carrinho', None)
        request.session.modified = True
        messages.success(request, "Seu pedido foi finalizado com sucesso!")

        # 4. Marcar pedido como enviado
        novo_pedido.enviado_whatsapp = True
        novo_pedido.save(update_fields=['enviado_whatsapp'])

        link_whatsapp = f"https://wa.me/{numero_whatsapp_loja}?text={urllib.parse.quote(mensagem_whatsapp)}"

        return redirect(reverse('menu:confirmacao_pedido', kwargs={'id_pedido_cliente': novo_pedido.id_pedido_cliente}) + f"?whatsapp_link={urllib.parse.quote(link_whatsapp)}")

    context = {
        'carrinho': carrinho_session,
        'valor_total_carrinho': valor_total_carrinho,
    }
    return render(request, 'menu/finalizar_pedido.html', context)


def confirmacao_pedido(request, id_pedido_cliente):
    pedido = get_object_or_404(Pedido, id_pedido_cliente=id_pedido_cliente)
    link_whatsapp = request.GET.get('whatsapp_link')
    context = {
        'pedido': pedido,
        'link_whatsapp': link_whatsapp,
    }
    return render(request, 'menu/confirmacao_pedido.html', context)