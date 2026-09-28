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


# ---------- API DE PRODUTOS ----------

@app.route('/api/produtos', methods=['GET', 'POST'])
def produtos():
    session = Session()

    if request.method == 'POST':
        dados = request.json
        novo_produto = Produto(
            nome=dados['nome'],
            preco=float(dados['preco']),
            quantidade=int(dados['quantidade']),
            categoria=dados['categoria']
        )
        session.add(novo_produto)
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

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
