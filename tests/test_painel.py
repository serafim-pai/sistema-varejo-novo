"""Testes do Painel. Rodar na pasta do projeto:  python -m unittest discover tests -v
Usam um banco temporário, então os dados reais nunca são tocados."""
import os
import tempfile
import unittest
from datetime import date, datetime

_pasta = tempfile.mkdtemp()
os.environ['VAREJO_DB'] = os.path.join(_pasta, 'teste.db')   # tem que vir ANTES de importar o sistema

from werkzeug.security import generate_password_hash   # noqa: E402
import app as sistema                                   # noqa: E402
from database import Base, engine, Session, Produto, Venda, Usuario   # noqa: E402

HOJE = date(2026, 10, 15)   # quinta-feira


def dia(d, hora=10, minuto=0):
    return datetime(2026, 10, d, hora, minuto)


class PainelTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        sistema.app.config['TESTING'] = True
        sistema.app.config['WTF_CSRF_ENABLED'] = False
        self.s = Session()
        self.s.add_all([
            Usuario(nome='ADMIN TESTE', email='admin@teste.com', tipo='ADMIN',
                    senha_hash=generate_password_hash('123456', method='pbkdf2:sha256')),
            Usuario(nome='BALCAO TESTE', email='balcao@teste.com', tipo='SIMPLES',
                    senha_hash=generate_password_hash('123456', method='pbkdf2:sha256')),
        ])
        self.s.commit()

    def tearDown(self):
        self.s.close()

    def entrar(self, email):
        cliente = sistema.app.test_client()
        r = cliente.post('/login', data={'acesso': email, 'chave': '123456'})
        self.assertEqual(r.status_code, 302)
        return cliente

    def produto(self, nome, qtd, preco=100.0, compra=None):
        p = Produto(nome=nome, preco=preco, quantidade=qtd, categoria='TESTE', unidade='UN',
                    preco_compra=compra)
        self.s.add(p)
        self.s.commit()
        return p

    def venda(self, produto, quantidade, valor, quando, forma='PIX', custo=None):
        self.s.add(Venda(produto_id=produto.id, quantidade=quantidade, valor_total=valor,
                         custo_total=custo, data=quando, forma_pagamento=forma))
        self.s.commit()

    # ---------- permissões ----------

    def test_sem_login_vai_para_o_login(self):
        c = sistema.app.test_client()
        self.assertEqual(c.get('/painel').headers['Location'], '/login')
        self.assertEqual(c.get('/api/painel').status_code, 401)

    def test_balcao_nao_acessa(self):
        c = self.entrar('balcao@teste.com')
        self.assertEqual(c.get('/painel').headers['Location'], '/')
        self.assertEqual(c.get('/api/painel').status_code, 403)

    def test_admin_acessa_pagina_e_dados(self):
        c = self.entrar('admin@teste.com')
        pagina = c.get('/painel')
        self.assertEqual(pagina.status_code, 200)
        self.assertIn('Painel'.encode(), pagina.data)
        r = c.get('/api/painel')
        self.assertEqual(r.status_code, 200)
        self.assertIn('grafico', r.get_json())

    def test_menu_mostra_painel_so_para_admin(self):
        self.assertIn(b'/painel', self.entrar('admin@teste.com').get('/').data)
        self.assertNotIn(b'/painel', self.entrar('balcao@teste.com').get('/').data)

    # ---------- números ----------

    def test_banco_vazio(self):
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['hoje'], {'valor': 0, 'vendas': 0, 'lucro': 0, 'itens_sem_custo': 0})
        self.assertEqual(len(d['grafico']), 7)
        self.assertEqual(d['top_produtos'], [])
        self.assertEqual(d['por_pagamento'], [])
        self.assertEqual(d['estoque_baixo']['total'], 0)

    def test_hoje_mes_e_lucro(self):
        tinta = self.produto('TINTA', 50, compra=60.0)
        self.venda(tinta, 2, 200.0, dia(15), custo=120.0)                  # hoje: lucro 80
        self.venda(tinta, 1, 100.0, dia(15, 11), custo=60.0)               # hoje, outra venda: lucro 40
        self.venda(tinta, 1, 100.0, dia(3), custo=60.0)                    # mês: lucro 40
        self.venda(tinta, 1, 999.0, datetime(2026, 9, 28, 10))             # mês passado: fora
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['hoje'], {'valor': 300.0, 'vendas': 2, 'lucro': 120.0, 'itens_sem_custo': 0})
        self.assertEqual(d['mes']['valor'], 400.0)
        self.assertEqual(d['mes']['vendas'], 3)
        self.assertEqual(d['mes']['lucro'], 160.0)

    def test_carrinho_com_varios_itens_conta_uma_venda(self):
        a, b = self.produto('A', 50), self.produto('B', 50)
        momento = dia(15, 9, 30)
        self.venda(a, 1, 10.0, momento)
        self.venda(b, 1, 20.0, momento)
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['hoje']['vendas'], 1)
        self.assertEqual(d['hoje']['valor'], 30.0)

    def test_venda_sem_custo_fica_fora_do_lucro_e_avisa(self):
        sem_compra = self.produto('CIMENTO', 50, compra=None)
        self.venda(sem_compra, 2, 70.0, dia(15))
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['hoje']['valor'], 70.0)
        self.assertEqual(d['hoje']['lucro'], 0)
        self.assertEqual(d['hoje']['itens_sem_custo'], 1)

    def test_venda_antiga_usa_preco_de_compra_atual(self):
        p = self.produto('AREIA', 50, compra=30.0)
        self.venda(p, 2, 100.0, dia(15), custo=None)   # lucro = 100 - 2*30 = 40
        self.assertEqual(sistema.dados_do_painel(self.s, HOJE)['hoje']['lucro'], 40.0)

    def test_grafico_tem_7_dias_terminando_hoje(self):
        p = self.produto('P', 50)
        self.venda(p, 1, 50.0, dia(9))      # 6 dias atrás: primeira barra
        self.venda(p, 1, 80.0, dia(15))     # hoje: última barra
        self.venda(p, 1, 70.0, dia(8))      # 7 dias atrás: fora do gráfico
        g = sistema.dados_do_painel(self.s, HOJE)['grafico']
        self.assertEqual([x['dia'] for x in g][0], '09/10')
        self.assertEqual(g[-1]['dia'], '15/10')
        self.assertTrue(g[-1]['hoje'])
        self.assertEqual([x['valor'] for x in g], [50.0, 0, 0, 0, 0, 0, 80.0])

    def test_pagamento_e_top_produtos(self):
        a, b = self.produto('A', 50), self.produto('B', 50)
        self.venda(a, 1, 300.0, dia(14), forma='PIX')
        self.venda(b, 5, 100.0, dia(14, 12), forma='DINHEIRO')
        self.venda(b, 1, 50.0, dia(14, 13), forma='PIX')
        self.venda(a, 1, 10.0, datetime(2026, 8, 1), forma='PIX')   # fora dos 30 dias
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['por_pagamento'][0], {'forma': 'PIX', 'valor': 350.0})
        self.assertEqual([p['produto'] for p in d['top_produtos']], ['A', 'B'])
        self.assertEqual(d['top_produtos'][1]['quantidade'], 6)

    def test_top_limitado_a_cinco(self):
        for i in range(7):
            self.venda(self.produto(f'P{i}', 50), 1, 10.0 + i, dia(14))
        self.assertEqual(len(sistema.dados_do_painel(self.s, HOJE)['top_produtos']), 5)

    def test_estoque_baixo_ordenado_do_mais_critico(self):
        self.produto('OK', 10)
        self.produto('BAIXO', 4)
        self.produto('ZERADO', 0)
        e = sistema.dados_do_painel(self.s, HOJE)['estoque_baixo']
        self.assertEqual(e['total'], 2)
        self.assertEqual([p['nome'] for p in e['produtos']], ['ZERADO', 'BAIXO'])

    def test_produto_excluido_nao_quebra(self):
        self.s.add(Venda(produto_id=999, quantidade=1, valor_total=10.0, data=dia(14), custo_total=None))
        self.s.commit()
        d = sistema.dados_do_painel(self.s, HOJE)
        self.assertEqual(d['top_produtos'][0]['produto'], '(produto excluído)')


if __name__ == '__main__':
    unittest.main()
