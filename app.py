from flask import Flask, render_template, request, jsonify, redirect
from flask import session as login          # "login" guarda quem está usando o sistema
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
from database import (Session, Produto, Venda, Orcamento, OrcamentoItem, Usuario, Cliente, UNIDADES,
                      FORMAS_PAGAMENTO, FORMAS_COM_DESCONTO, DESCONTO_MAXIMO_BALCAO)
import re
from datetime import datetime, timedelta
import os
import secrets

app = Flask(__name__)


# ---------- CHAVE SECRETA (protege o login) ----------
# Na primeira vez que o sistema roda, cria o arquivo chave_secreta.txt com uma
# chave aleatória. Esse arquivo NÃO vai para o GitHub (está no .gitignore).
ARQUIVO_CHAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chave_secreta.txt')
if not os.path.exists(ARQUIVO_CHAVE):
    with open(ARQUIVO_CHAVE, 'w') as arquivo:
        arquivo.write(secrets.token_hex(32))
with open(ARQUIVO_CHAVE) as arquivo:
    app.secret_key = arquivo.read().strip()

app.permanent_session_lifetime = timedelta(hours=12)   # login vale por 12 horas

# ---------- PROTEÇÃO CONTRA CSRF ----------
# Protege automaticamente toda rota que muda dados (POST, PUT, PATCH, DELETE).
# O token não expira sozinho (só quando a sessão de 12h expira), para não
# atrapalhar quem deixa a tela aberta o dia todo no balcão.
app.config['WTF_CSRF_TIME_LIMIT'] = None
csrf = CSRFProtect(app)


@app.errorhandler(CSRFError)
def token_csrf_invalido(erro):
    """Pedido sem o token de segurança (ou com um token velho): recusa
    com uma mensagem amigável em vez da página de erro padrão do Flask."""
    if request.path.startswith('/api/'):
        return jsonify({'sucesso': False,
                        'mensagem': 'Sessão expirada ou inválida. Recarregue a página e tente novamente.'}), 400
    return redirect('/login?expirou=1')


# ---------- LOGIN: quem pode entrar e onde ----------

def usuario_logado():
    """Devolve um dicionário com os dados de quem está logado, ou None."""
    return getattr(request, 'usuario', None)


def eh_admin():
    u = usuario_logado()
    return bool(u and u['tipo'] == 'ADMIN')


def so_admin(caminho, metodo):
    """Diz se esta parte do sistema é só para o ADMINISTRADOR MASTER."""
    if caminho.startswith(('/usuarios', '/api/usuarios', '/relatorios', '/api/relatorios')):
        return True
    # Cadastrar, editar, excluir produto e dar entrada no estoque
    if caminho.startswith('/api/produtos') and metodo != 'GET':
        return True
    # Excluir cliente
    if caminho.startswith('/api/clientes/') and metodo == 'DELETE':
        return True
    # Cancelar venda (devolve produto ao estoque)
    if caminho.startswith('/api/vendas/') and metodo == 'DELETE':
        return True
    return False


@app.before_request
def conferir_login():
    """Roda ANTES de toda página: confere se a pessoa entrou com e-mail e senha."""
    request.usuario = None
    caminho = request.path

    if caminho.startswith('/static'):
        return None

    session = Session()
    tem_usuarios = session.query(Usuario).count() > 0

    # Sistema novo, sem nenhum usuário: manda criar o administrador master
    if not tem_usuarios:
        session.close()
        if caminho == '/primeiro-acesso':
            return None
        if caminho.startswith('/api/'):
            return jsonify({'sucesso': False, 'mensagem': 'Crie o administrador primeiro.'}), 401
        return redirect('/primeiro-acesso')

    if caminho in ('/login', '/primeiro-acesso'):
        session.close()
        return None

    # Confere se quem está logado ainda existe e está ativo
    usuario = None
    if login.get('usuario_id'):
        usuario = session.query(Usuario).filter_by(id=login['usuario_id'], ativo=1).first()
    if usuario:
        request.usuario = {'id': usuario.id, 'nome': usuario.nome,
                           'email': usuario.email, 'tipo': usuario.tipo}
    session.close()

    if not usuario:
        login.clear()
        if caminho.startswith('/api/'):
            return jsonify({'sucesso': False, 'mensagem': 'Faça login novamente.'}), 401
        return redirect('/login')

    if so_admin(caminho, request.method) and not eh_admin():
        if caminho.startswith('/api/'):
            return jsonify({'sucesso': False,
                            'mensagem': 'Só o administrador pode fazer isso.'}), 403
        return redirect('/')

    return None


# ---------- LEITURA SEGURA DO JSON ----------

def dados_requisicao():
    """Lê o JSON do corpo do pedido com segurança.
    Devolve o dicionário de dados, ou None se o corpo estiver ausente,
    vazio ou mal formatado (evita que a rota quebre com erro 500)."""
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else None


MENSAGEM_JSON_INVALIDO = 'Não foi possível ler os dados enviados. Recarregue a página e tente novamente.'


@app.context_processor
def dados_para_as_telas():
    """Deixa o usuário logado disponível em todas as telas (menu, botões)."""
    return {'usuario': usuario_logado(), 'admin': eh_admin()}


@app.route('/login', methods=['GET', 'POST'])
def pagina_login():
    erro = 'Sua sessão expirou. Tente entrar de novo.' if request.args.get('expirou') else None
    email = ''
    if request.method == 'POST':
        email = request.form.get('acesso', '').strip().lower()
        senha = request.form.get('chave', '')
        session = Session()
        usuario = session.query(Usuario).filter_by(email=email).first()
        if not usuario or not check_password_hash(usuario.senha_hash, senha):
            erro = 'E-mail ou senha errados.'
        elif not usuario.ativo:
            erro = 'Este usuário está bloqueado. Fale com o administrador.'
        else:
            login.clear()
            login.permanent = True
            login['usuario_id'] = usuario.id
            session.close()
            return redirect('/')
        session.close()
    return render_template('login.html', modo='login', erro=erro, email=email)


@app.route('/primeiro-acesso', methods=['GET', 'POST'])
def primeiro_acesso():
    """Só funciona quando ainda não existe nenhum usuário:
    cria o ADMINISTRADOR MASTER."""
    session = Session()
    if session.query(Usuario).count() > 0:
        session.close()
        return redirect('/login')

    erro = None
    dados = {'nome': '', 'email': ''}
    if request.method == 'POST':
        dados = {'nome': request.form.get('nome', ''), 'email': request.form.get('acesso', ''),
                 'senha': request.form.get('chave', ''), 'tipo': 'ADMIN'}
        if request.form.get('chave', '') != request.form.get('chave2', ''):
            erro = 'As duas senhas não são iguais.'
        else:
            erro, limpos = validar_usuario(session, dados)
            if not erro:
                usuario = Usuario(**limpos)
                session.add(usuario)
                session.commit()
                login.clear()
                login.permanent = True
                login['usuario_id'] = usuario.id
                session.close()
                return redirect('/')
    session.close()
    return render_template('login.html', modo='primeiro', erro=erro,
                           nome=dados.get('nome', ''), email=dados.get('email', ''))


@app.route('/sair')
def sair():
    login.clear()
    return redirect('/login')


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


@app.route('/usuarios')
def pagina_usuarios():
    return render_template('usuarios.html')


@app.route('/clientes')
def pagina_clientes():
    return render_template('clientes.html')


# ---------- CLIENTES (balcão cadastra e edita; só o administrador exclui) ----------

def validar_cliente(dados):
    """Confere os dados do cliente. Devolve (erro, None) ou (None, dados_limpos)."""
    nome = str(dados.get('nome', '')).strip().upper()
    telefone = str(dados.get('telefone', '')).strip().upper()
    endereco = str(dados.get('endereco', '')).strip().upper()
    documento = str(dados.get('documento', '')).strip().upper()

    if sum(1 for letra in nome if letra.isalpha()) < 2:
        return 'Digite o nome do cliente.', None
    if not telefone_valido(telefone):
        return MENSAGEM_TELEFONE, None
    if documento:
        numeros = ''.join(c for c in documento if c.isdigit())
        if len(numeros) not in (11, 14):
            return 'O CPF precisa ter 11 números (ou o CNPJ, 14 números).', None
    return None, {'nome': nome, 'telefone': telefone, 'endereco': endereco, 'documento': documento}


def cliente_para_json(c):
    return {'id': c.id, 'nome': c.nome, 'telefone': c.telefone or '',
            'endereco': c.endereco or '', 'documento': c.documento or '',
            'criado_em': c.criado_em.strftime('%d/%m/%Y') if c.criado_em else ''}


@app.route('/api/clientes', methods=['GET', 'POST'])
def clientes():
    session = Session()

    if request.method == 'POST':
        dados = dados_requisicao()
        if dados is None:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
        erro, limpos = validar_cliente(dados)
        if erro:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': erro})
        # Evita cadastrar o mesmo cliente duas vezes (mesmo nome e mesmo telefone)
        repetido = session.query(Cliente).filter_by(nome=limpos['nome'], telefone=limpos['telefone']).first()
        if repetido:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Este cliente já está cadastrado.'})
        cliente = Cliente(**limpos)
        session.add(cliente)
        session.commit()
        resultado = cliente_para_json(cliente)
        session.close()
        return jsonify({'sucesso': True, 'cliente': resultado})

    todos = session.query(Cliente).order_by(Cliente.nome).all()
    resultado = [cliente_para_json(c) for c in todos]
    session.close()
    return jsonify(resultado)


@app.route('/api/clientes/<int:id>', methods=['PUT', 'DELETE'])
def alterar_cliente(id):
    session = Session()
    cliente = session.query(Cliente).filter_by(id=id).first()
    if not cliente:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Cliente não encontrado.'})

    if request.method == 'DELETE':
        session.delete(cliente)
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    dados = dados_requisicao()
    if dados is None:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
    erro, limpos = validar_cliente(dados)
    if erro:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': erro})
    cliente.nome = limpos['nome']
    cliente.telefone = limpos['telefone']
    cliente.endereco = limpos['endereco']
    cliente.documento = limpos['documento']
    session.commit()
    session.close()
    return jsonify({'sucesso': True})


# ---------- USUÁRIOS (só o administrador master) ----------

def validar_usuario(session, dados, id_atual=None, senha_obrigatoria=True):
    """Confere os dados de um usuário. Devolve (erro, None) ou (None, dados_limpos)."""
    nome = str(dados.get('nome', '')).strip().upper()
    email = str(dados.get('email', '')).strip().lower()
    senha = str(dados.get('senha', ''))
    tipo = str(dados.get('tipo', 'SIMPLES')).strip().upper()

    if sum(1 for letra in nome if letra.isalpha()) < 2:
        return 'Digite o nome do usuário.', None
    if '@' not in email or '.' not in email.split('@')[-1] or ' ' in email:
        return 'Digite um e-mail válido.', None
    if tipo not in ('ADMIN', 'SIMPLES'):
        return 'Escolha o tipo: Administrador ou Simples.', None

    repetido = session.query(Usuario).filter_by(email=email).first()
    if repetido and repetido.id != id_atual:
        return 'Já existe um usuário com este e-mail.', None

    limpos = {'nome': nome, 'email': email, 'tipo': tipo}
    if senha or senha_obrigatoria:
        if len(senha) < 6:
            return 'A senha precisa ter pelo menos 6 caracteres.', None
        limpos['senha_hash'] = generate_password_hash(senha, method='pbkdf2:sha256')
    return None, limpos


def admins_ativos(session):
    return session.query(Usuario).filter_by(tipo='ADMIN', ativo=1).count()


@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    session = Session()

    if request.method == 'POST':
        dados = dados_requisicao()
        if dados is None:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
        erro, limpos = validar_usuario(session, dados)
        if erro:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': erro})
        session.add(Usuario(**limpos))
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    todos = session.query(Usuario).order_by(Usuario.nome).all()
    resultado = [{
        'id': u.id, 'nome': u.nome, 'email': u.email, 'tipo': u.tipo,
        'ativo': bool(u.ativo), 'eu': u.id == usuario_logado()['id'],
        'criado_em': u.criado_em.strftime('%d/%m/%Y') if u.criado_em else ''
    } for u in todos]
    session.close()
    return jsonify(resultado)


@app.route('/api/usuarios/<int:id>', methods=['PUT', 'DELETE'])
def alterar_usuario(id):
    session = Session()
    usuario = session.query(Usuario).filter_by(id=id).first()
    if not usuario:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Usuário não encontrado.'})

    sou_eu = usuario.id == usuario_logado()['id']

    # Excluir usuário
    if request.method == 'DELETE':
        if sou_eu:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Você não pode excluir o seu próprio usuário.'})
        session.delete(usuario)
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    # Editar usuário (a senha só muda se for digitada uma nova)
    dados = dados_requisicao()
    if dados is None:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
    erro, limpos = validar_usuario(session, dados, id_atual=id, senha_obrigatoria=False)
    if erro:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': erro})

    ativo = 1 if dados.get('ativo', True) else 0
    if sou_eu and (limpos['tipo'] != 'ADMIN' or not ativo):
        session.close()
        return jsonify({'sucesso': False,
                        'mensagem': 'Você não pode tirar o seu próprio acesso de administrador.'})

    usuario.nome = limpos['nome']
    usuario.email = limpos['email']
    usuario.tipo = limpos['tipo']
    usuario.ativo = ativo
    if 'senha_hash' in limpos:
        usuario.senha_hash = limpos['senha_hash']
    session.commit()
    session.close()
    return jsonify({'sucesso': True})


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

    # Preço de compra e porcentagem: não são obrigatórios (podem ficar em branco)
    preco_compra = None
    margem = None
    texto_compra = str(dados.get('preco_compra') or '').strip().replace(',', '.')
    texto_margem = str(dados.get('margem') or '').strip().replace(',', '.')
    if texto_compra:
        try:
            preco_compra = float(texto_compra)
        except ValueError:
            return 'Digite um preço de compra válido.', None
        if preco_compra < 0:
            return 'O preço de compra não pode ser negativo.', None
    if texto_margem:
        try:
            margem = float(texto_margem)
        except ValueError:
            return 'Digite uma porcentagem válida.', None

    return None, {
        'nome': nome.upper(),
        'preco': preco,
        'quantidade': quantidade,
        'categoria': categoria.upper(),
        'unidade': unidade,
        'preco_compra': preco_compra,
        'margem': margem
    }


# ---------- API DE PRODUTOS ----------

@app.route('/api/formas-pagamento')
def lista_formas_pagamento():
    return jsonify(FORMAS_PAGAMENTO)


@app.route('/api/unidades')
def lista_unidades():
    return jsonify(UNIDADES)


@app.route('/api/produtos', methods=['GET', 'POST'])
def produtos():
    session = Session()

    # Cadastrar um produto novo
    if request.method == 'POST':
        dados = dados_requisicao()
        if dados is None:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
        erro, limpos = validar_produto(dados)
        if erro:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': erro})

        session.add(Produto(**limpos))
        session.commit()
        session.close()
        return jsonify({'sucesso': True})

    # Listar todos os produtos
    todos_produtos = session.query(Produto).order_by(Produto.nome).all()
    resultado = []
    for p in todos_produtos:
        item = {
            'id': p.id,
            'nome': p.nome,
            'preco': p.preco,
            'quantidade': p.quantidade,
            'categoria': p.categoria,
            'unidade': p.unidade or 'UN'
        }
        # Preço de compra e porcentagem: só vão para a tela do ADMINISTRADOR.
        # O terminal do balcão nem recebe esses números.
        if eh_admin():
            item['preco_compra'] = p.preco_compra
            item['margem'] = p.margem
        resultado.append(item)
    session.close()
    return jsonify(resultado)


@app.route('/api/produtos/<int:id>', methods=['PUT'])
def editar_produto(id):
    session = Session()
    produto = session.query(Produto).filter_by(id=id).first()

    if not produto:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Produto não encontrado.'})

    dados = dados_requisicao()
    if dados is None:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
    erro, limpos = validar_produto(dados)
    if erro:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': erro})

    produto.nome = limpos['nome']
    produto.preco = limpos['preco']
    produto.quantidade = limpos['quantidade']
    produto.categoria = limpos['categoria']
    produto.unidade = limpos['unidade']
    produto.preco_compra = limpos['preco_compra']
    produto.margem = limpos['margem']
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

    dados = dados_requisicao()
    if dados is None:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
    try:
        quantidade = int(dados.get('quantidade'))
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

def telefone_valido(telefone):
    """Telefone no formato (DDD) + 9 números. Ex.: (11) 98888-7777. Vazio também vale."""
    return not telefone or re.fullmatch(r'\(\d{2}\) \d{5}-\d{4}', telefone) is not None


MENSAGEM_TELEFONE = 'Telefone inválido. Use o DDD entre parênteses e 9 números. Ex.: (11) 98888-7777'


def dados_do_cliente(session, dados):
    """Lê o cliente da venda (tudo opcional). Se o nome for de um cliente cadastrado,
    liga a venda a ele. Devolve (nome, telefone, endereco, cliente_id)."""
    nome = str(dados.get('cliente') or '').strip().upper() or None
    telefone = str(dados.get('telefone') or '').strip() or None
    endereco = str(dados.get('endereco') or '').strip().upper() or None
    cliente_id = None
    if nome:
        cadastrado = session.query(Cliente).filter_by(nome=nome).first()
        if cadastrado:
            cliente_id = cadastrado.id
    return nome, telefone, endereco, cliente_id


def custo_da_venda(produto, quantidade):
    """Quanto a loja pagou pelos itens vendidos (usa o preço de compra de hoje).
    Se o produto não tem preço de compra, devolve None (lucro desconhecido)."""
    if produto.preco_compra is None:
        return None
    return quantidade * produto.preco_compra

@app.route('/api/vendas', methods=['GET', 'POST'])
def vendas():
    session = Session()

    # Registrar uma nova venda (e descontar do estoque)
    if request.method == 'POST':
        dados = dados_requisicao()
        if dados is None:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
        try:
            produto_id = int(dados['produto_id'])
            quantidade = int(dados['quantidade'])
        except (KeyError, TypeError, ValueError):
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Dados de venda inválidos.'}), 400

        produto = session.query(Produto).filter_by(id=produto_id).first()

        if produto and quantidade > 0 and produto.quantidade >= quantidade:
            produto.quantidade -= quantidade
            nova_venda = Venda(
                produto_id=produto_id,
                quantidade=quantidade,
                valor_total=quantidade * produto.preco,
                custo_total=custo_da_venda(produto, quantidade),
                vendedor_id=usuario_logado()['id'],
                vendedor=usuario_logado()['nome']
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
            'data': v.data.strftime('%d/%m/%Y %H:%M'),
            'cliente': v.cliente or '',
            'endereco_entrega': v.endereco_entrega or '',
            'forma_pagamento': v.forma_pagamento or '',
            'desconto': v.desconto or 0,
            'vendedor': v.vendedor or ''
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
    dados = dados_requisicao()
    if dados is None:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
    itens = dados.get('itens', [])
    orcamento_id = dados.get('orcamento_id')
    cliente_nome, cliente_telefone, cliente_endereco, cliente_id = dados_do_cliente(session, dados)

    if not telefone_valido(cliente_telefone):
        session.close()
        return jsonify({'sucesso': False, 'mensagem': MENSAGEM_TELEFONE})

    # Forma de pagamento (obrigatória)
    forma_pagamento = str(dados.get('forma_pagamento') or '').strip().upper()
    if forma_pagamento not in FORMAS_PAGAMENTO:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Escolha a forma de pagamento.'})
    valor_recebido = None
    texto_recebido = str(dados.get('valor_recebido') or '').strip().replace(',', '.')
    if forma_pagamento == 'DINHEIRO' and texto_recebido:
        try:
            valor_recebido = float(texto_recebido)
        except ValueError:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Digite um valor recebido válido.'})

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
        try:
            orcamento_id = int(orcamento_id)
        except (TypeError, ValueError):
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'Orçamento inválido.'}), 400
        orcamento = session.query(Orcamento).filter_by(id=orcamento_id).first()
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

    # Desconto (em %): só no DINHEIRO ou PIX; balcão até 5%
    texto_desconto = str(dados.get('desconto_percentual') or '').strip().replace(',', '.')
    try:
        desconto_percentual = float(texto_desconto) if texto_desconto else 0.0
    except ValueError:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Digite um desconto válido.'})
    if desconto_percentual < 0:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'O desconto não pode ser negativo.'})
    if desconto_percentual > 0 and forma_pagamento not in FORMAS_COM_DESCONTO:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'Desconto só no pagamento em DINHEIRO ou PIX.'})
    if not eh_admin() and desconto_percentual > DESCONTO_MAXIMO_BALCAO + 0.001:
        session.close()
        return jsonify({'sucesso': False,
                        'mensagem': f'O desconto máximo no balcão é {DESCONTO_MAXIMO_BALCAO:.0f}%. Acima disso, chame o administrador.'})
    if desconto_percentual >= 100:
        session.close()
        return jsonify({'sucesso': False, 'mensagem': 'O desconto precisa ser menor que 100%.'})

    total_bruto = sum(q * precos_orcamento.get(pid, produtos[pid].preco) for pid, q in quantidades.items())
    desconto_valor = round(total_bruto * desconto_percentual / 100, 2)
    total_previsto = total_bruto - desconto_valor

    # Confere se o dinheiro recebido dá para pagar (antes de mexer no estoque)
    if valor_recebido is not None:
        if valor_recebido + 0.001 < total_previsto:
            session.close()
            return jsonify({'sucesso': False,
                            'mensagem': f'Valor recebido (R$ {valor_recebido:.2f}) é menor que o total (R$ {total_previsto:.2f}).'})

    # 2) Tudo certo: dá baixa no estoque e registra as vendas
    agora = datetime.now()
    comprovante = []
    ids = []
    for produto_id, quantidade in quantidades.items():
        produto = produtos[produto_id]
        preco = precos_orcamento.get(produto_id, produto.preco)
        subtotal = quantidade * preco
        # O desconto é dividido entre os itens, na mesma proporção
        desconto_item = subtotal * desconto_percentual / 100
        produto.quantidade -= quantidade
        venda = Venda(produto_id=produto_id, quantidade=quantidade,
                      valor_total=subtotal - desconto_item, desconto=desconto_item, data=agora,
                      custo_total=custo_da_venda(produto, quantidade),
                      cliente_id=cliente_id, cliente=cliente_nome,
                      telefone=cliente_telefone, endereco_entrega=cliente_endereco,
                      forma_pagamento=forma_pagamento,
                      vendedor_id=usuario_logado()['id'], vendedor=usuario_logado()['nome'])
        session.add(venda)
        session.flush()
        ids.append(venda.id)
        comprovante.append({'produto': produto.nome, 'quantidade': quantidade,
                            'unidade': produto.unidade or 'UN',
                            'preco': preco, 'subtotal': subtotal})

    total = total_previsto

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
        'subtotal': total_bruto,
        'desconto': desconto_valor,
        'desconto_percentual': desconto_percentual,
        'total': total,
        'cliente': cliente_nome or '',
        'telefone': cliente_telefone or '',
        'endereco': cliente_endereco or '',
        'forma_pagamento': forma_pagamento,
        'vendedor': usuario_logado()['nome'],
        'valor_recebido': valor_recebido,
        'troco': (valor_recebido - total) if valor_recebido is not None else None
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
        'endereco': orcamento.endereco or '',
        'data': orcamento.data.strftime('%d/%m/%Y %H:%M'),
        'validade_dias': orcamento.validade_dias,
        'valido_ate': (orcamento.data + timedelta(days=orcamento.validade_dias)).strftime('%d/%m/%Y'),
        'dias': dias,
        'faltam': faltam,
        'situacao': situacao,
        'venda_numero': orcamento.venda_numero,
        'vendedor': orcamento.vendedor or '',
        'itens': lista,
        'total': sum(i['subtotal'] for i in lista)
    }


@app.route('/api/orcamentos', methods=['GET', 'POST'])
def orcamentos():
    session = Session()

    # Criar um orçamento novo (NÃO mexe no estoque)
    if request.method == 'POST':
        dados = dados_requisicao()
        if dados is None:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_JSON_INVALIDO}), 400
        cliente = str(dados.get('cliente', '')).strip().upper()
        telefone = str(dados.get('telefone', '')).strip()
        endereco = str(dados.get('endereco', '') or '').strip().upper()
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
        if not telefone_valido(telefone):
            session.close()
            return jsonify({'sucesso': False, 'mensagem': MENSAGEM_TELEFONE})
        if not itens:
            session.close()
            return jsonify({'sucesso': False, 'mensagem': 'O carrinho está vazio.'})

        orcamento = Orcamento(cliente=cliente, telefone=telefone, endereco=endereco,
                              data=datetime.now(), validade_dias=validade_dias,
                              vendedor_id=usuario_logado()['id'], vendedor=usuario_logado()['nome'])
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
    produtos = {}
    for v in todas_vendas:
        if v.produto_id not in resumo:
            produto = session.query(Produto).filter_by(id=v.produto_id).first()
            produtos[v.produto_id] = produto
            resumo[v.produto_id] = {
                'produto': produto.nome if produto else '(produto excluído)',
                'unidade': (produto.unidade if produto else None) or 'UN',
                'quantidade_vendida': 0,
                'numero_vendas': 0,
                'valor_vendido': 0.0,
                'custo': 0.0,
                'valor_com_custo': 0.0,   # parte das vendas em que o custo é conhecido
                'sem_custo': 0            # vendas sem preço de compra (lucro desconhecido)
            }
        item = resumo[v.produto_id]
        item['quantidade_vendida'] += v.quantidade
        item['numero_vendas'] += 1
        item['valor_vendido'] += v.valor_total

        # Custo desta venda: o que foi guardado na hora da venda.
        # Vendas antigas (de antes do preço de compra existir) usam o preço de compra atual.
        custo = v.custo_total
        produto = produtos[v.produto_id]
        if custo is None and produto and produto.preco_compra is not None:
            custo = v.quantidade * produto.preco_compra
        if custo is None:
            item['sem_custo'] += 1
        else:
            item['custo'] += custo
            item['valor_com_custo'] += v.valor_total

    # Lucro de cada produto (só da parte em que o custo é conhecido)
    for item in resumo.values():
        if item['sem_custo'] == item['numero_vendas']:
            item['lucro'] = None
            item['margem'] = None
        else:
            item['lucro'] = item['valor_com_custo'] - item['custo']
            item['margem'] = (item['lucro'] / item['custo'] * 100) if item['custo'] > 0 else None

    # Ordena do que mais vendeu para o que menos vendeu
    ranking = sorted(resumo.values(), key=lambda item: item['quantidade_vendida'], reverse=True)

    # Total vendido por forma de pagamento
    por_pagamento = {}
    for v in todas_vendas:
        forma = v.forma_pagamento or 'NÃO INFORMADO'
        por_pagamento[forma] = por_pagamento.get(forma, 0.0) + v.valor_total

    # Quanto cada vendedor vendeu (vendas com vários itens contam como 1 venda)
    por_vendedor = {}
    for v in todas_vendas:
        nome = v.vendedor or 'NÃO INFORMADO'
        item = por_vendedor.setdefault(nome, {'vendedor': nome, 'valor': 0.0, 'vendas': set(), 'desconto': 0.0})
        item['valor'] += v.valor_total
        item['desconto'] += v.desconto or 0
        item['vendas'].add(v.data)
    lista_vendedores = sorted(
        [{'vendedor': i['vendedor'], 'valor': i['valor'], 'desconto': i['desconto'],
          'numero_vendas': len(i['vendas'])} for i in por_vendedor.values()],
        key=lambda x: -x['valor'])

    custo_total = sum(i['custo'] for i in ranking)
    lucro_total = sum(i['lucro'] for i in ranking if i['lucro'] is not None)

    session.close()
    return jsonify({
        'ranking': ranking,
        'total_vendas': len(todas_vendas),
        'valor_vendido': sum(v.valor_total for v in todas_vendas),
        'custo_total': custo_total,
        'lucro_total': lucro_total,
        'vendas_sem_custo': sum(i['sem_custo'] for i in ranking),
        'por_vendedor': lista_vendedores,
        'por_pagamento': [{'forma': f, 'valor': v}
                          for f, v in sorted(por_pagamento.items(), key=lambda x: -x[1])]
    })


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG') == '1'
    # O reiniciador automático (reinicia sozinho quando um arquivo é salvo) fica
    # sempre ligado, mesmo sem o modo debug — assim uma alteração no código nunca
    # fica "no ar" à toa. O depurador interativo (o que é perigoso deixar ligado)
    # só liga de verdade com FLASK_DEBUG=1.
    app.run(debug=debug, use_reloader=True)
