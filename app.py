from flask import Flask, render_template, request, jsonify
from database import Session, Produto, Venda, Orcamento, OrcamentoItem, UNIDADES
from datetime import datetime, timedelta

app = Flask(__name__)


# ---------- PÁGINAS (telas) ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/vendas')
def pagina_vendas():
    return render_template('vendas.html')


@app.route('/relatorios')
def pagina_relatorios():
    return render_template('relatorios.html')


@app.route('/orcamentos')
def pagina_orcamentos():
    return render_template('orcamentos.html')


# ---------- VALIDAÇÃO (usada no cadastro e na edição) ----------

def validar_produto(dados):
    """Confere os dados do produto.
    Devolve (mensagem_de_erro, None) se algo estiver errado,
    ou (None, dados_limpos) se estiver tudo certo."""
    nome = str(dados.get('nome', '')).strip()
    categoria = str(dados.get('categoria', '')).strip()
    unidade = str(dados.get('unidade', 'UN')).strip().upper() or 'UN'

    if not nome:
        return 'Digite o nome do produto.', None
    if not categoria:
        return 'Digite a categoria do produto.', None

    # O nome e a categoria precisam ter pelo menos 2 letras
    # (evita nomes como "." ou "-")
    if sum(1 for letra in nome if letra.isalpha()) < 2:
        return 'O nome precisa ter pelo menos 2 letras.', None
    if sum(1 for letra in categoria if letra.isalpha()) < 2:
        return 'A categoria precisa ter pelo menos 2 letras.', None

    try:
        preco = float(dados.get('preco'))
    except (TypeError, ValueError):
        return 'Digite um preço válido.', None

    try:
        quantidade = int(dados.get('quantidade'))
    except (TypeError, ValueError):
        return 'Digite uma quantidade válida (número inteiro).', None

    if preco <= 0:
        return 'O preço precisa ser maior que zero.', None
    if quantidade < 0:
        return 'A quantidade não pode ser negativa.', None

    if unidade not in UNIDADES:
        return 'Escolha uma unidade de medida da lista.', None

    return None, {
        'nome': nome.upper(),
        'preco': preco,
        'quantidade': quantidade,
        'categoria': categoria.upper(),
        'unidade': unidade
    }


# ---------- API DE PRODUTOS ----------

@app.route('/api/unidades')
def lista_unidades():
    return jsonify(UNIDADES)


@app.route('/api/produtos', methods=['GET', 'POST'])
def produtos():
    session = Session()

    # Cadastrar um produto novo
    if request.method == 'POST':
        erro, limpos = validar_produto(request.json)
        if erro:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': erro})

        session.add(Produto(**limpos))
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    # Listar todos os produtos
    todos_produtos = session.query(Produto).order_by(Produto.nome).all()
    resultado = [{
        'id': p.id,
        'nome': p.nome,
        'preco': p.preco,
        'quantidade': p.quantidade,
        'categoria': p.categoria,
        'unidade': p.unidade or 'UN'
    } for p in todos_produtos]
    session.close()
    return jsonify(resultado)


@app.route('/api/produtos/<int:id>', methods=['PUT'])
def editar_produto(id):
    session = Session()
    produto = session.query(Produto).filter_by(id=id).first()

    if not produto:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Produto não encontrado.'})

    erro, limpos = validar_produto(request.json)
    if erro:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': erro})

    produto.nome = limpos['nome']
    produto.preco = limpos['preco']
    produto.quantidade = limpos['quantidade']
    produto.categoria = limpos['categoria']
    produto.unidade = limpos['unidade']
    session.commit()
    session.close()
    return jsonify({'sucesso': True})


@app.route('/api/produtos/<int:id>', methods=['DELETE'])
def deletar_produto(id):
    session = Session()
    produto = session.query(Produto).filter_by(id=id).first()

    if produto:
        session.delete(produto)
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    session.close()
    return jsonify({'sucesso': False})


@app.route('/api/produtos/<int:id>/entrada', methods=['POST'])
def entrada_estoque(id):
    """Repor estoque: soma a quantidade que chegou ao estoque atual."""
    session = Session()
    produto = session.query(Produto).filter_by(id=id).first()

    if not produto:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Produto não encontrado.'})

    try:
        quantidade = int(request.json.get('quantidade'))
    except (TypeError, ValueError):
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Digite uma quantidade válida (número inteiro).'})

    if quantidade <= 0:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'A quantidade de entrada precisa ser maior que zero.'})

    produto.quantidade += quantidade
    novo_total = produto.quantidade
    nome = produto.nome
    session.commit()
    session.close()
    return jsonify({'sucesso': True, 'nome': nome, 'novo_total': novo_total})


# ---------- API DE VENDAS ----------

@app.route('/api/vendas', methods=['GET', 'POST'])
def vendas():
    session = Session()

    # Registrar uma nova venda (e descontar do estoque)
    if request.method == 'POST':
        dados = request.json
        produto_id = int(dados['produto_id'])
        quantidade = int(dados['quantidade'])

        produto = session.query(Produto).filter_by(id=produto_id).first()

        if produto and quantidade > 0 and produto.quantidade >= quantidade:
            produto.quantidade -= quantidade
            nova_venda = Venda(
                produto_id=produto_id,
                quantidade=quantidade,
                valor_total=quantidade * produto.preco
            )
            session.add(nova_venda)
            session.commit()
            session.close()
            return jsonify({'sucesso': True})

        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Estoque insuficiente ou quantidade inválida'})

    # Histórico de vendas (da mais nova para a mais antiga)
    todas_vendas = session.query(Venda).order_by(Venda.data.desc()).all()
    resultado = []
    for v in todas_vendas:
        produto = session.query(Produto).filter_by(id=v.produto_id).first()
        resultado.append({
            'id': v.id,
            'produto': produto.nome if produto else '(produto excluído)',
            'unidade': (produto.unidade if produto else None) or 'UN',
            'quantidade': v.quantidade,
            'valor_total': v.valor_total,
            'data': v.data.strftime('%d/%m/%Y %H:%M')
        })
    session.close()
    return jsonify(resultado)


@app.route('/api/vendas/<int:id>', methods=['DELETE'])
def cancelar_venda(id):
    """Cancelar venda: devolve os produtos ao estoque e apaga a venda."""
    session = Session()
    venda = session.query(Venda).filter_by(id=id).first()

    if not venda:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Venda não encontrada.'})

    produto = session.query(Produto).filter_by(id=venda.produto_id).first()
    if produto:
        produto.quantidade += venda.quantidade

    session.delete(venda)
    session.commit()
    session.close()
    return jsonify({'sucesso': True})


@app.route('/api/pedidos', methods=['POST'])
def finalizar_pedido():
    """Venda com vários itens (carrinho): confere o estoque de todos,
    dá baixa em tudo de uma vez e devolve os dados do comprovante."""
    session = Session()
    itens = (request.json or {}).get('itens', [])
    orcamento_id = (request.json or {}).get('orcamento_id')

    if not itens:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'O carrinho está vazio.'})

    # Junta itens repetidos do mesmo produto
    quantidades = {}
    for item in itens:
        try:
            produto_id = int(item['produto_id'])
            quantidade = int(item['quantidade'])
        except (KeyError, TypeError, ValueError):
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Item inválido no carrinho.'})
        if quantidade <= 0:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Quantidade inválida no carrinho.'})
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade

    # 1) Confere o estoque de TODOS os itens antes de vender
    produtos = {}
    for produto_id, quantidade in quantidades.items():
        produto = session.query(Produto).filter_by(id=produto_id).first()
        if not produto:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Produto não encontrado.'})
        if produto.quantidade < quantidade:
            nome, disponivel = produto.nome, produto.quantidade
            session.close()
            return jsonify({'sucesso': False,
                            'mensagem': f'Estoque insuficiente de {nome}: tem só {disponivel}.'})
        produtos[produto_id] = produto

    # Se a venda veio de um orçamento, usa os preços combinados no orçamento
    orcamento = None
    precos_orcamento = {}
    if orcamento_id:
        orcamento = session.query(Orcamento).filter_by(id=int(orcamento_id)).first()
        if not orcamento:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Orçamento não encontrado.'})
        situacao, _, _ = situacao_orcamento(orcamento)
        if situacao != 'ABERTO' and situacao != 'VENCENDO':
            session.close()
            return jsonify({'sucesso': False,
                            'mensagem': f'Este orçamento não pode virar venda (situação: {situacao}).'})
        for item in session.query(OrcamentoItem).filter_by(orcamento_id=orcamento.id).all():
            precos_orcamento[item.produto_id] = item.preco

    # 2) Tudo certo: dá baixa no estoque e registra as vendas
    agora = datetime.now()
    comprovante = []
    total = 0.0
    ids = []
    for produto_id, quantidade in quantidades.items():
        produto = produtos[produto_id]
        preco = precos_orcamento.get(produto_id, produto.preco)
        subtotal = quantidade * preco
        produto.quantidade -= quantidade
        venda = Venda(produto_id=produto_id, quantidade=quantidade,
                      valor_total=subtotal, data=agora)
        session.add(venda)
        session.flush()
        ids.append(venda.id)
        comprovante.append({'produto': produto.nome, 'quantidade': quantidade,
                            'unidade': produto.unidade or 'UN',
                            'preco': preco, 'subtotal': subtotal})
        total += subtotal

    if orcamento:
        orcamento.situacao = 'VIROU VENDA'
        orcamento.venda_numero = min(ids)

    session.commit()
    session.close()
    return jsonify({
        'sucesso': True,
        'numero': min(ids),
        'data': agora.strftime('%d/%m/%Y %H:%M'),
        'itens': comprovante,
        'total': total
    })


# ---------- ORÇAMENTOS ----------

def situacao_orcamento(orcamento):
    """Calcula a situação do orçamento pela idade dele.
    Devolve (situacao, dias_desde_que_foi_feito, dias_que_faltam_para_vencer)."""
    dias = (datetime.now().date() - orcamento.data.date()).days
    faltam = orcamento.validade_dias - dias
    if orcamento.situacao in ('VIROU VENDA', 'CANCELADO'):
        return orcamento.situacao, dias, faltam
    if faltam < 0:
        return 'VENCIDO', dias, faltam
    if dias >= 5 or faltam <= 2:
        return 'VENCENDO', dias, faltam
    return 'ABERTO', dias, faltam


def orcamento_para_json(session, orcamento):
    itens = session.query(OrcamentoItem).filter_by(orcamento_id=orcamento.id).all()
    situacao, dias, faltam = situacao_orcamento(orcamento)
    lista = [{'produto_id': i.produto_id, 'produto': i.produto_nome, 'unidade': i.unidade,
              'quantidade': i.quantidade, 'preco': i.preco, 'subtotal': i.quantidade * i.preco}
             for i in itens]
    return {
        'id': orcamento.id,
        'cliente': orcamento.cliente,
        'telefone': orcamento.telefone or '',
        'data': orcamento.data.strftime('%d/%m/%Y %H:%M'),
        'validade_dias': orcamento.validade_dias,
        'valido_ate': (orcamento.data + timedelta(days=orcamento.validade_dias)).strftime('%d/%m/%Y'),
        'dias': dias,
        'faltam': faltam,
        'situacao': situacao,
        'venda_numero': orcamento.venda_numero,
        'itens': lista,
        'total': sum(i['subtotal'] for i in lista)
    }


@app.route('/api/orcamentos', methods=['GET', 'POST'])
def orcamentos():
    session = Session()

    # Criar um orçamento novo (NÃO mexe no estoque)
    if request.method == 'POST':
        dados = request.json or {}
        cliente = str(dados.get('cliente', '')).strip().upper()
        telefone = str(dados.get('telefone', '')).strip()
        itens = dados.get('itens', [])

        # Data de validade escolhida pelo vendedor (formato AAAA-MM-DD)
        try:
            validade = datetime.strptime(str(dados.get('validade', '')), '%Y-%m-%d').date()
        except ValueError:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Escolha a data de validade do orçamento.'})
        validade_dias = (validade - datetime.now().date()).days
        if validade_dias < 0:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'A data de validade não pode ser antes de hoje.'})

        if sum(1 for letra in cliente if letra.isalpha()) < 2:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Digite o nome do cliente.'})
        if not itens:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'O carrinho está vazio.'})

        orcamento = Orcamento(cliente=cliente, telefone=telefone, data=datetime.now(),
                              validade_dias=validade_dias)
        session.add(orcamento)
        session.flush()

        for item in itens:
            try:
                produto_id = int(item['produto_id'])
                quantidade = int(item['quantidade'])
            except (KeyError, TypeError, ValueError):
                session.rollback()
                session.close()
                return jsonify({'sucesso': False, 'mensagem': 'Item inválido no carrinho.'})
            produto = session.query(Produto).filter_by(id=produto_id).first()
            if not produto or quantidade <= 0:
                session.rollback()
                session.close()
                return jsonify({'sucesso': False, 'mensagem': 'Item inválido no carrinho.'})
            session.add(OrcamentoItem(orcamento_id=orcamento.id, produto_id=produto.id,
                                      produto_nome=produto.nome, unidade=produto.unidade or 'UN',
                                      quantidade=quantidade, preco=produto.preco))

        session.commit()
        resultado = orcamento_para_json(session, orcamento)
        session.close()
        return jsonify({'sucesso': True, 'orcamento': resultado})

    # Listar todos os orçamentos (do mais novo para o mais antigo)
    todos = session.query(Orcamento).order_by(Orcamento.id.desc()).all()
    resultado = [orcamento_para_json(session, o) for o in todos]
    session.close()
    return jsonify(resultado)


@app.route('/api/orcamentos/<int:id>')
def ver_orcamento(id):
    session = Session()
    orcamento = session.query(Orcamento).filter_by(id=id).first()
    if not orcamento:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Orçamento não encontrado.'})
    resultado = orcamento_para_json(session, orcamento)
    session.close()
    return jsonify({'sucesso': True, 'orcamento': resultado})


@app.route('/api/orcamentos/<int:id>/cancelar', methods=['POST'])
def cancelar_orcamento(id):
    session = Session()
    orcamento = session.query(Orcamento).filter_by(id=id).first()
    if not orcamento:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Orçamento não encontrado.'})
    if orcamento.situacao == 'VIROU VENDA':
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Este orçamento já virou venda.'})
    orcamento.situacao = 'CANCELADO'
    session.commit()
    session.close()
    return jsonify({'sucesso': True})


# ---------- RELATÓRIO: PRODUTOS MAIS VENDIDOS ----------

@app.route('/api/relatorios/mais-vendidos')
def mais_vendidos():
    session = Session()
    todas_vendas = session.query(Venda).all()

    # Soma as vendas de cada produto
    resumo = {}
    for v in todas_vendas:
        if v.produto_id not in resumo:
            produto = session.query(Produto).filter_by(id=v.produto_id).first()
            resumo[v.produto_id] = {
                'produto': produto.nome if produto else '(produto excluído)',
                'unidade': (produto.unidade if produto else None) or 'UN',
                'quantidade_vendida': 0,
                'numero_vendas': 0,
                'valor_vendido': 0.0
            }
        resumo[v.produto_id]['quantidade_vendida'] += v.quantidade
        resumo[v.produto_id]['numero_vendas'] += 1
        resumo[v.produto_id]['valor_vendido'] += v.valor_total

    # Ordena do que mais vendeu para o que menos vendeu
    ranking = sorted(resumo.values(), key=lambda item: item['quantidade_vendida'], reverse=True)

    session.close()
    return jsonify({
        'ranking': ranking,
        'total_vendas': len(todas_vendas),
        'valor_vendido': sum(v.valor_total for v in todas_vendas)
    })


if __name__ == '__main__':
    app.run(debug=True)
