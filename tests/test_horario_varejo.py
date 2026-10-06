"""Testes do horário de Brasília no varejo e da correção única do banco do servidor.
Rodar na pasta do projeto:  python -m unittest discover tests -v
Usam bancos temporários, então os dados reais nunca são tocados."""
import contextlib
import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

_pasta = tempfile.mkdtemp()
os.environ.setdefault('VAREJO_DB', os.path.join(_pasta, 'teste.db'))     # antes de importar o sistema

import database                                  # noqa: E402
import corrigir_horario_utc as correcao          # noqa: E402

UTC = timezone.utc


def utc(ano, mes, dia, hora, minuto=0, segundo=0):
    return datetime(ano, mes, dia, hora, minuto, segundo, tzinfo=UTC)


class AgoraBrasilTest(unittest.TestCase):
    def test_converte_utc_para_brasilia_e_devolve_sem_fuso(self):
        r = database.agora_brasil(agora_utc=utc(2026, 10, 6, 1, 30))
        self.assertEqual(r, datetime(2026, 10, 5, 22, 30))
        self.assertIsNone(r.tzinfo)

    def test_virada_do_dia_acontece_as_3h_utc(self):
        self.assertEqual(database.agora_brasil(agora_utc=utc(2026, 10, 6, 2, 59, 59)), datetime(2026, 10, 5, 23, 59, 59))
        self.assertEqual(database.agora_brasil(agora_utc=utc(2026, 10, 6, 3, 0, 0)), datetime(2026, 10, 6, 0, 0, 0))

    def test_virada_de_ano_e_bissexto(self):
        self.assertEqual(database.agora_brasil(agora_utc=utc(2027, 1, 1, 2, 0)), datetime(2026, 12, 31, 23, 0))
        self.assertEqual(database.agora_brasil(agora_utc=utc(2024, 3, 1, 1, 0)), datetime(2024, 2, 29, 22, 0))

    def test_sem_argumento_usa_o_relogio_de_verdade_com_3_horas_a_menos(self):
        antes = datetime.now(UTC).replace(tzinfo=None)
        r = database.agora_brasil()
        depois = datetime.now(UTC).replace(tzinfo=None)
        self.assertIsNone(r.tzinfo)
        self.assertTrue(antes - timedelta(hours=3, seconds=1) <= r <= depois - timedelta(hours=3) + timedelta(seconds=1), r)

    def test_as_colunas_de_data_gravam_o_horario_de_brasilia(self):
        # o SQLAlchemy usa agora_brasil como valor padrão: confere de ponta a ponta, com o banco de verdade
        sessao = database.Session()
        try:
            cliente = database.Cliente(nome='TESTE HORARIO', telefone='', endereco='', documento='')
            sessao.add(cliente)
            sessao.commit()
            esperado = database.agora_brasil()
            gravado = cliente.criado_em
            sessao.delete(cliente)
            sessao.commit()
        finally:
            sessao.close()
        self.assertLess(abs((esperado - gravado).total_seconds()), 5)

    def test_o_codigo_nao_usa_mais_o_relogio_da_maquina(self):
        pasta_projeto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for nome in ('app.py', 'database.py'):
            with open(os.path.join(pasta_projeto, nome), encoding='utf-8') as arquivo:
                texto = arquivo.read()
            sobras = [linha for linha in texto.splitlines()
                      if 'datetime.now()' in linha and not linha.strip().startswith('#')]
            self.assertEqual(sobras, [], nome)


def criar_banco(caminho, vendas=(), orcamentos=(), clientes=(), usuarios=()):
    """Banco mínimo, com as 4 tabelas que a correção mexe (e uma coluna a mais em cada, para conferir que ela não muda)."""
    banco = sqlite3.connect(caminho)
    banco.execute("CREATE TABLE vendas (id INTEGER PRIMARY KEY, valor_total FLOAT, data DATETIME)")
    banco.execute("CREATE TABLE orcamentos (id INTEGER PRIMARY KEY, cliente TEXT, data DATETIME)")
    banco.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT, criado_em DATETIME)")
    banco.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, criado_em DATETIME)")
    banco.executemany("INSERT INTO vendas (valor_total, data) VALUES (?, ?)", vendas)
    banco.executemany("INSERT INTO orcamentos (cliente, data) VALUES (?, ?)", orcamentos)
    banco.executemany("INSERT INTO clientes (nome, criado_em) VALUES (?, ?)", clientes)
    banco.executemany("INSERT INTO usuarios (nome, criado_em) VALUES (?, ?)", usuarios)
    banco.commit()
    banco.close()


def ler(caminho, consulta):
    banco = sqlite3.connect(caminho)
    try:
        return banco.execute(consulta).fetchall()
    finally:
        banco.close()


CORTE = datetime(2026, 10, 10, 12, 0, 0)       # "agora" da correção, nos testes


class CorrecaoUnicaTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.banco = os.path.join(self.pasta, 'varejo.db')
        self.addCleanup(shutil.rmtree, self.pasta, True)

    def test_atrasa_3_horas_so_das_linhas_antigas_nas_4_tabelas(self):
        criar_banco(self.banco,
                    vendas=[(100.0, '2026-10-02 22:10:05.123456')],
                    orcamentos=[('MARIA', '2026-10-03 09:00:00.000001')],
                    clientes=[('JOAO', '2026-09-30 15:45:10.500000')],
                    usuarios=[('DONO', '2026-09-20 03:00:00.000000')])
        r = correcao.corrigir(self.banco, corte=CORTE)
        self.assertTrue(r['aplicado'])
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas"), [('2026-10-02 19:10:05.123456',)])
        self.assertEqual(ler(self.banco, "SELECT data FROM orcamentos"), [('2026-10-03 06:00:00.000001',)])
        self.assertEqual(ler(self.banco, "SELECT criado_em FROM clientes"), [('2026-09-30 12:45:10.500000',)])
        self.assertEqual(ler(self.banco, "SELECT criado_em FROM usuarios"), [('2026-09-20 00:00:00.000000',)])

    def test_atravessa_a_meia_noite_para_o_dia_anterior(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-06 01:00:00.000000'), (2.0, '2027-01-01 02:30:00.000000')])
        correcao.corrigir(self.banco, corte=datetime(2027, 6, 1))
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas ORDER BY id"),
                         [('2026-10-05 22:00:00.000000',), ('2026-12-31 23:30:00.000000',)])

    def test_aceita_data_com_e_sem_microssegundos(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05'), (2.0, '2026-10-02 22:10:05.250000')])
        correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas ORDER BY id"),
                         [('2026-10-02 19:10:05.000000',), ('2026-10-02 19:10:05.250000',)])

    def test_itens_da_mesma_venda_continuam_com_a_mesma_hora(self):
        # um carrinho grava vários itens com exatamente a mesma data: a relatório conta 1 venda por data
        criar_banco(self.banco, vendas=[(10.0, '2026-10-02 22:10:05.123456'), (20.0, '2026-10-02 22:10:05.123456'),
                                        (30.0, '2026-10-02 22:10:05.999999')])
        correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT COUNT(DISTINCT data) FROM vendas"), [(2,)])
        datas = [d for (d,) in ler(self.banco, "SELECT data FROM vendas ORDER BY id")]
        self.assertEqual(datas[0], datas[1])
        self.assertNotEqual(datas[1], datas[2])

    def test_linha_depois_do_corte_nao_e_mexida_e_e_informada(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-09 10:00:00.000000'),
                                        (2.0, '2026-10-10 12:00:00.000000'),       # exatamente no corte: não mexe
                                        (3.0, '2026-10-10 12:00:01.000000')])      # depois do corte: não mexe
        r = correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual([d for (d,) in ler(self.banco, "SELECT data FROM vendas ORDER BY id")],
                         ['2026-10-09 07:00:00.000000', '2026-10-10 12:00:00.000000', '2026-10-10 12:00:01.000000'])
        self.assertEqual(r['resumo']['vendas.data']['corrigidas'], 1)
        self.assertEqual(r['resumo']['vendas.data']['depois_do_corte'], 2)

    def test_data_vazia_nao_e_mexida(self):
        criar_banco(self.banco, vendas=[(1.0, None), (2.0, '2026-10-02 22:10:05.000000')])
        correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas ORDER BY id"),
                         [(None,), ('2026-10-02 19:10:05.000000',)])

    def test_outras_colunas_nao_mudam(self):
        criar_banco(self.banco, vendas=[(123.45, '2026-10-02 22:10:05.000000')], orcamentos=[('MARIA DA SILVA', '2026-10-02 22:10:05.000000')])
        correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT valor_total FROM vendas"), [(123.45,)])
        self.assertEqual(ler(self.banco, "SELECT cliente FROM orcamentos"), [('MARIA DA SILVA',)])

    def test_so_roda_uma_vez(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05.000000')])
        correcao.corrigir(self.banco, corte=CORTE)
        r = correcao.corrigir(self.banco, corte=datetime(2027, 1, 1))              # segunda chamada, corte bem depois
        self.assertFalse(r['aplicado'])
        self.assertIn('já foi aplicado', r['motivo'])
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas"), [('2026-10-02 19:10:05.000000',)])   # não atrasou 6 horas
        self.assertEqual(ler(self.banco, "SELECT COUNT(*) FROM ajustes_unicos"), [(1,)])

    def test_anota_que_ja_rodou(self):
        criar_banco(self.banco)
        correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT nome FROM ajustes_unicos"), [(correcao.AJUSTE,)])

    def test_simulacao_nao_altera_nada_e_nao_anota(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05.000000')])
        r = correcao.corrigir(self.banco, corte=CORTE, simular=True)
        self.assertTrue(r['simulacao'])
        self.assertEqual(r['resumo']['vendas.data']['corrigidas'], 1)
        self.assertEqual(r['resumo']['vendas.data']['exemplo'], ('2026-10-02 22:10:05.000000', '2026-10-02 19:10:05.000000'))
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas"), [('2026-10-02 22:10:05.000000',)])
        self.assertEqual(ler(self.banco, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'ajustes_unicos'"), [(0,)])
        self.assertEqual(os.listdir(self.pasta), ['varejo.db'])                        # nem cópia de segurança
        r2 = correcao.corrigir(self.banco, corte=CORTE)                                # e depois ainda dá para aplicar de verdade
        self.assertTrue(r2['aplicado'])

    def test_guarda_uma_copia_do_banco_antes_de_alterar(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05.000000')], usuarios=[('DONO', '2026-09-20 03:00:00.000000')])
        r = correcao.corrigir(self.banco, corte=CORTE)
        self.assertTrue(os.path.exists(r['backup']))
        self.assertEqual(os.path.dirname(r['backup']), self.pasta)
        self.assertIn('antes-do-horario', os.path.basename(r['backup']))
        self.assertEqual(ler(r['backup'], "SELECT data FROM vendas"), [('2026-10-02 22:10:05.000000',)])       # como era
        self.assertEqual(ler(r['backup'], "SELECT criado_em FROM usuarios"), [('2026-09-20 03:00:00.000000',)])
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas"), [('2026-10-02 19:10:05.000000',)])         # como ficou

    def test_se_der_erro_no_meio_nada_e_alterado(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05.000000')])
        banco = sqlite3.connect(self.banco)
        banco.execute("DROP TABLE usuarios")                                          # a última tabela da lista vai falhar
        banco.commit()
        banco.close()
        with self.assertRaises(sqlite3.OperationalError):
            correcao.corrigir(self.banco, corte=CORTE)
        self.assertEqual(ler(self.banco, "SELECT data FROM vendas"), [('2026-10-02 22:10:05.000000',)])
        self.assertEqual(ler(self.banco, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'ajustes_unicos'"), [(0,)])

    def test_o_sistema_consegue_ler_de_volta_o_que_a_correcao_gravou(self):
        # banco de verdade, criado pelo próprio sistema (SQLAlchemy), corrigido e relido pelo sistema
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        motor = create_engine('sqlite:///' + self.banco)
        database.Base.metadata.create_all(motor)
        Sessao = sessionmaker(bind=motor)
        s = Sessao()
        s.add(database.Venda(produto_id=1, quantidade=2, valor_total=50.0, data=datetime(2026, 10, 2, 22, 10, 5, 123456)))
        s.add(database.Orcamento(cliente='MARIA', data=datetime(2026, 10, 6, 1, 0, 0), validade_dias=7))
        s.commit()
        s.close()
        motor.dispose()
        correcao.corrigir(self.banco, corte=CORTE)
        motor = create_engine('sqlite:///' + self.banco)
        s = sessionmaker(bind=motor)()
        self.assertEqual(s.query(database.Venda).one().data, datetime(2026, 10, 2, 19, 10, 5, 123456))
        self.assertEqual(s.query(database.Orcamento).one().data, datetime(2026, 10, 5, 22, 0, 0))
        s.close()
        motor.dispose()

    def test_as_tabelas_e_colunas_da_correcao_existem_no_sistema(self):
        for tabela, coluna in correcao.COLUNAS:
            modelo = database.Base.metadata.tables[tabela]
            self.assertIn(coluna, modelo.columns, (tabela, coluna))

    def test_o_texto_na_tela_explica_o_que_aconteceu(self):
        criar_banco(self.banco, vendas=[(1.0, '2026-10-02 22:10:05.000000')])
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            correcao.mostrar(correcao.corrigir(self.banco, corte=CORTE))
            correcao.mostrar(correcao.corrigir(self.banco, corte=CORTE))
        texto = saida.getvalue()
        self.assertIn('CORREÇÃO APLICADA', texto)
        self.assertIn('vendas.data: 1 corrigidas', texto)
        self.assertIn('Cópia do banco guardada em', texto)
        self.assertIn('já foi aplicado antes', texto)


if __name__ == '__main__':
    unittest.main()
