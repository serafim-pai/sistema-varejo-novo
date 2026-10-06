"""Testes de segurança do varejo: trava de login, números inválidos, logout, cookie e cabeçalhos.
Usam banco temporário; os dados reais nunca são tocados."""
import os
import re
import tempfile
import unittest

_pasta = tempfile.mkdtemp()
os.environ.setdefault('VAREJO_DB', os.path.join(_pasta, 'teste.db'))

from werkzeug.security import generate_password_hash   # noqa: E402
import app as sistema                                    # noqa: E402
from database import Session, Usuario, Produto, TentativaLogin   # noqa: E402

SENHA = 'senha123'
HASH = generate_password_hash(SENHA, method='pbkdf2:sha256')


def token_do_formulario(c):
    html = c.get('/login').get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


class SegurancaTest(unittest.TestCase):
    def setUp(self):
        sistema.app.config['TESTING'] = True
        s = Session()
        for modelo in (TentativaLogin, Produto, Usuario):
            s.query(modelo).delete()
        s.add(Usuario(nome='ADM', email='adm@t.com', tipo='ADMIN', senha_hash=HASH))
        s.add(Usuario(nome='BAL', email='bal@t.com', tipo='SIMPLES', senha_hash=HASH))
        s.add(Produto(nome='CIMENTO', preco=35.0, quantidade=100, categoria='CIMENTO', unidade='UN'))
        s.commit()
        self.produto_id = s.query(Produto).first().id
        s.close()

    def tentar(self, email, senha, c=None):
        c = c or sistema.app.test_client()
        return c.post('/login', data={'acesso': email, 'chave': senha, 'csrf_token': token_do_formulario(c)}), c

    def entrar(self, email='adm@t.com'):
        r, c = self.tentar(email, SENHA)
        self.assertEqual(r.status_code, 302)
        tk = re.search(r'name="csrf-token" content="([^"]+)"', c.get('/').get_data(as_text=True)).group(1)
        return c, tk

    # ---- trava de tentativas ----
    def test_depois_de_5_erros_nem_a_senha_certa_entra(self):
        for _ in range(sistema.MAX_ERROS_LOGIN):
            r, _c = self.tentar('adm@t.com', 'errada')
            self.assertEqual(r.status_code, 200)
        r, _c = self.tentar('adm@t.com', SENHA)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Muitas tentativas', r.get_data(as_text=True))

    def test_menos_de_5_erros_nao_trava_e_acerto_zera_a_contagem(self):
        for _ in range(sistema.MAX_ERROS_LOGIN - 1):
            self.tentar('adm@t.com', 'errada')
        r, _c = self.tentar('adm@t.com', SENHA)
        self.assertEqual(r.status_code, 302)
        for _ in range(sistema.MAX_ERROS_LOGIN - 1):
            self.tentar('adm@t.com', 'errada')
        r, _c = self.tentar('adm@t.com', SENHA)
        self.assertEqual(r.status_code, 302)

    def test_trava_de_um_email_nao_atrapalha_outro(self):
        for _ in range(sistema.MAX_ERROS_LOGIN):
            self.tentar('adm@t.com', 'errada')
        r, _c = self.tentar('bal@t.com', SENHA)
        self.assertEqual(r.status_code, 302)

    def test_erros_antigos_deixam_de_valer(self):
        from datetime import timedelta
        s = Session()
        antigo = sistema.agora_brasil() - timedelta(minutes=sistema.MINUTOS_BLOQUEIO_LOGIN + 1)
        for _ in range(sistema.MAX_ERROS_LOGIN):
            s.add(TentativaLogin(email='adm@t.com', quando=antigo))
        s.commit(); s.close()
        r, _c = self.tentar('adm@t.com', SENHA)
        self.assertEqual(r.status_code, 302)

    # ---- números inválidos ----
    def test_preco_nan_e_infinito_sao_recusados(self):
        c, tk = self.entrar()
        for ruim in ('nan', 'inf', '-inf', 'Infinity'):
            r = c.post('/api/produtos', json={'nome': 'TIJOLO', 'preco': ruim, 'quantidade': 1,
                                              'categoria': 'BASE', 'unidade': 'UN'}, headers={'X-CSRFToken': tk})
            self.assertFalse(r.get_json()['sucesso'], ruim)
        r = c.post('/api/produtos', json={'nome': 'TIJOLO', 'preco': 5, 'quantidade': 1, 'categoria': 'BASE',
                                          'unidade': 'UN', 'preco_compra': 'nan', 'margem': 'inf'},
                   headers={'X-CSRFToken': tk})
        self.assertFalse(r.get_json()['sucesso'])
        s = Session(); self.assertEqual(s.query(Produto).count(), 1); s.close()

    def test_desconto_e_valor_recebido_nan_sao_recusados(self):
        c, tk = self.entrar('bal@t.com')
        for campo in ('desconto_percentual', 'valor_recebido'):
            r = c.post('/api/pedidos', json={'itens': [{'produto_id': self.produto_id, 'quantidade': 1}],
                                             'forma_pagamento': 'DINHEIRO', campo: 'nan'},
                       headers={'X-CSRFToken': tk})
            self.assertEqual(r.status_code, 200, campo)
            self.assertFalse(r.get_json()['sucesso'], campo)

    # ---- logout, cookie, cabeçalhos ----
    def test_sair_so_por_post(self):
        c, tk = self.entrar()
        self.assertEqual(c.get('/sair').status_code, 405)
        self.assertEqual(c.get('/').status_code, 200)             # continua logado
        r = c.post('/sair', data={'csrf_token': tk})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get('/').status_code, 302)             # agora foi para o login

    def test_cookie_com_samesite_httponly(self):
        r = sistema.app.test_client().get('/login')
        cookie = ' '.join(r.headers.get_all('Set-Cookie'))
        self.assertIn('SameSite=Lax', cookie)
        self.assertIn('HttpOnly', cookie)

    def test_cabecalhos_de_seguranca(self):
        c, _tk = self.entrar()
        for caminho in ('/login', '/', '/api/produtos'):
            r = c.get(caminho)
            self.assertEqual(r.headers.get('X-Frame-Options'), 'DENY', caminho)
            self.assertEqual(r.headers.get('X-Content-Type-Options'), 'nosniff', caminho)
            self.assertEqual(r.headers.get('Referrer-Policy'), 'same-origin', caminho)

    def test_menu_tem_botao_sair_em_formulario(self):
        c, _tk = self.entrar()
        html = c.get('/').get_data(as_text=True)
        self.assertIn('action="/sair"', html)
        self.assertNotIn('href="/sair"', html)


if __name__ == '__main__':
    unittest.main()
