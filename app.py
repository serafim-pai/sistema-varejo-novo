from flask import Flask, render_template, request, jsonify
from database import Session, Produto, Venda
from datetime import datetime

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


# ---------- VALIDAÇÃO (usada no cadastro e na edição) ----------

def validar_produto(dados):
    """Confere os dados do produto.
    Devolve (mensagem_de_erro, None) se algo estiver errado,
    ou (None, dados_limpos) se estiver tudo certo."""
    nome = str(dados.get('nome', '')).strip()
    categoria = str(dados.get('categoria', '')).strip()

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

    return None, {
        'nome': nome.upper(),
        'preco': preco,
        'quantidade': quantidade,
        'categoria': categoria.upper()
    }


# ---------- API DE PRODUTOS ----------

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
        'categoria': p.categoria
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
                            'mensagem': f'Estoque insuficiente de {nome}: tem só {disponivel} un.'})
        produtos[produto_id] = produto

    # 2) Tudo certo: dá baixa no estoque e registra as vendas
    agora = datetime.now()
    comprovante = []
    total = 0.0
    ids = []
    for produto_id, quantidade in quantidades.items():
        produto = produtos[produto_id]
        subtotal = quantidade * produto.preco
        produto.quantidade -= quantidade
        venda = Venda(produto_id=produto_id, quantidade=quantidade,
                      valor_total=subtotal, data=agora)
        session.add(venda)
        session.flush()
        ids.append(venda.id)
        comprovante.append({'produto': produto.nome, 'quantidade': quantidade,
                            'preco': produto.preco, 'subtotal': subtotal})
        total += subtotal

    session.commit()
    session.close()
    return jsonify({
        'sucesso': True,
        'numero': min(ids),
        'data': agora.strftime('%d/%m/%Y %H:%M'),
        'itens': comprovante,
        'total': total
    })


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
