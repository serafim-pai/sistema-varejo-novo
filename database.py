from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()
# O banco fica sempre ao lado deste arquivo, não importa de onde o sistema é ligado
# (necessário na hospedagem online, onde a pasta de trabalho é outra).
# (A variável VAREJO_DB permite usar outro banco, por exemplo nos testes.)
CAMINHO_BANCO = os.environ.get('VAREJO_DB') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'varejo.db')
engine = create_engine('sqlite:///' + CAMINHO_BANCO)
Session = sessionmaker(bind=engine)

# Formas de pagamento aceitas (sem fiado)
FORMAS_PAGAMENTO = ['DINHEIRO', 'PIX', 'CARTÃO DE DÉBITO', 'CARTÃO DE CRÉDITO']

# Desconto: só no DINHEIRO ou PIX. O balcão pode dar até 5%; o administrador, mais.
FORMAS_COM_DESCONTO = ['DINHEIRO', 'PIX']
DESCONTO_MAXIMO_BALCAO = 5.0

# Unidades de medida que o sistema aceita
UNIDADES = ['UN', 'SACO', 'M³', 'M²', 'M', 'KG', 'MILHEIRO', 'LATA', 'CAIXA', 'BARRA', 'ROLO', 'LITRO']


class Produto(Base):
    __tablename__ = 'produtos'

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    preco = Column(Float, nullable=False)
    quantidade = Column(Integer, nullable=False)
    categoria = Column(String(50), nullable=False)
    unidade = Column(String(20), nullable=False, default='UN')
    preco_compra = Column(Float, nullable=True)   # quanto a loja pagou (só o administrador vê)
    margem = Column(Float, nullable=True)         # porcentagem de lucro em cima do preço de compra


class Usuario(Base):
    """Pessoa que entra no sistema com e-mail e senha.
    tipo = 'ADMIN' (administrador master: pode tudo) ou 'SIMPLES' (balcão: vende e orça)."""
    __tablename__ = 'usuarios'

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, unique=True)
    senha_hash = Column(String(255), nullable=False)   # a senha nunca é guardada "aberta"
    tipo = Column(String(10), nullable=False, default='SIMPLES')
    ativo = Column(Integer, nullable=False, default=1)  # 1 = pode entrar, 0 = bloqueado
    criado_em = Column(DateTime, default=datetime.now)


class Cliente(Base):
    """Cliente da loja (usado nos orçamentos, nas vendas e no fiado)."""
    __tablename__ = 'clientes'

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    telefone = Column(String(30), nullable=True)
    endereco = Column(String(200), nullable=True)
    documento = Column(String(20), nullable=True)   # CPF ou CNPJ (opcional)
    criado_em = Column(DateTime, default=datetime.now)


class Venda(Base):
    __tablename__ = 'vendas'

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, nullable=False)
    quantidade = Column(Integer, nullable=False)
    valor_total = Column(Float, nullable=False)
    custo_total = Column(Float, nullable=True)   # quanto a loja pagou por esses itens (preço de compra do dia)
    data = Column(DateTime, default=datetime.now)
    # Cliente da venda (opcional) e endereço de entrega
    cliente_id = Column(Integer, nullable=True)
    cliente = Column(String(100), nullable=True)
    telefone = Column(String(30), nullable=True)
    endereco_entrega = Column(String(200), nullable=True)
    forma_pagamento = Column(String(30), nullable=True)   # DINHEIRO, PIX, CARTÃO DE DÉBITO, CARTÃO DE CRÉDITO
    desconto = Column(Float, nullable=True)                # desconto em R$ dado neste item (valor_total já vem descontado)
    vendedor_id = Column(Integer, nullable=True)           # usuário que fez a venda
    vendedor = Column(String(100), nullable=True)          # nome do usuário (fica guardado mesmo se ele for excluído)


class Orcamento(Base):
    """Orçamento: proposta de preço para o cliente. NÃO mexe no estoque."""
    __tablename__ = 'orcamentos'

    id = Column(Integer, primary_key=True)
    cliente = Column(String(100), nullable=False)
    telefone = Column(String(30), nullable=True)
    endereco = Column(String(200), nullable=True)                      # endereço de entrega
    data = Column(DateTime, default=datetime.now)
    validade_dias = Column(Integer, nullable=False, default=7)
    situacao = Column(String(20), nullable=False, default='ABERTO')   # ABERTO, VIROU VENDA, CANCELADO
    venda_numero = Column(Integer, nullable=True)                      # nº da venda, quando virar venda
    vendedor_id = Column(Integer, nullable=True)                       # usuário que fez o orçamento
    vendedor = Column(String(100), nullable=True)


class OrcamentoItem(Base):
    """Cada produto de um orçamento, com o preço do dia em que foi feito."""
    __tablename__ = 'orcamento_itens'

    id = Column(Integer, primary_key=True)
    orcamento_id = Column(Integer, nullable=False)
    produto_id = Column(Integer, nullable=False)
    produto_nome = Column(String(100), nullable=False)
    unidade = Column(String(20), nullable=False, default='UN')
    quantidade = Column(Integer, nullable=False)
    preco = Column(Float, nullable=False)


Base.metadata.create_all(engine)

# Atualização do banco: se a tabela de produtos ainda não tem a coluna "unidade",
# ela é criada aqui, e os produtos antigos ficam com "UN".
colunas = [c['name'] for c in inspect(engine).get_columns('produtos')]
if 'unidade' not in colunas:
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE produtos ADD COLUMN unidade VARCHAR(20) NOT NULL DEFAULT 'UN'"))

# Mesma ideia para o preço de compra e a porcentagem (produtos antigos ficam em branco)
if 'preco_compra' not in colunas:
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE produtos ADD COLUMN preco_compra FLOAT"))
if 'margem' not in colunas:
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE produtos ADD COLUMN margem FLOAT"))

# Vendas: guarda o custo (preço de compra) no momento da venda, para calcular o lucro
colunas_vendas = [c['name'] for c in inspect(engine).get_columns('vendas')]
if 'custo_total' not in colunas_vendas:
    with engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE vendas ADD COLUMN custo_total FLOAT"))

# Vendas e orçamentos: cliente e endereço de entrega
novas_colunas = [
    ('vendas', 'cliente_id', 'INTEGER'),
    ('vendas', 'cliente', 'VARCHAR(100)'),
    ('vendas', 'telefone', 'VARCHAR(30)'),
    ('vendas', 'endereco_entrega', 'VARCHAR(200)'),
    ('vendas', 'forma_pagamento', 'VARCHAR(30)'),
    ('vendas', 'desconto', 'FLOAT'),
    ('vendas', 'vendedor_id', 'INTEGER'),
    ('vendas', 'vendedor', 'VARCHAR(100)'),
    ('orcamentos', 'vendedor_id', 'INTEGER'),
    ('orcamentos', 'vendedor', 'VARCHAR(100)'),
    ('orcamentos', 'endereco', 'VARCHAR(200)'),
]
for tabela, coluna, tipo in novas_colunas:
    existentes = [c['name'] for c in inspect(engine).get_columns(tabela)]
    if coluna not in existentes:
        with engine.begin() as conexao:
            conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"))
