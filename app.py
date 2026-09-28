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


if __name__ == '__main__':
    app.run(debug=True)
