from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()
engine = create_engine('sqlite:///varejo.db')
Session = sessionmaker(bind=engine)

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


class Venda(Base):
    __tablename__ = 'vendas'

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, nullable=False)
    quantidade = Column(Integer, nullable=False)
    valor_total = Column(Float, nullable=False)
    data = Column(DateTime, default=datetime.now)


class Orcamento(Base):
    """Orçamento: proposta de preço para o cliente. NÃO mexe no estoque."""
    __tablename__ = 'orcamentos'

    id = Column(Integer, primary_key=True)
    cliente = Column(String(100), nullable=False)
    telefone = Column(String(30), nullable=True)
    data = Column(DateTime, default=datetime.now)
    validade_dias = Column(Integer, nullable=False, default=7)
    situacao = Column(String(20), nullable=False, default='ABERTO')   # ABERTO, VIROU VENDA, CANCELADO
    venda_numero = Column(Integer, nullable=True)                      # nº da venda, quando virar venda


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
