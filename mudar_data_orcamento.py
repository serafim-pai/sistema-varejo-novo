"""
FERRAMENTA DE TESTE: muda a data de um orçamento para "X dias atrás".
Serve só para testar as cores da tela de Orçamentos sem esperar vários dias.

Como usar (no terminal, dentro da pasta do projeto):
    python mudar_data_orcamento.py NUMERO_DO_ORCAMENTO DIAS

Exemplo: deixar o orçamento nº 1 como se tivesse sido feito há 5 dias:
    python mudar_data_orcamento.py 1 5
"""
import sqlite3
import sys
from datetime import datetime, timedelta

if len(sys.argv) != 3:
    print("Use assim: python mudar_data_orcamento.py NUMERO_DO_ORCAMENTO DIAS")
    sys.exit()

numero = int(sys.argv[1])
dias = int(sys.argv[2])
nova_data = datetime.now() - timedelta(days=dias)

conexao = sqlite3.connect('varejo.db')
cursor = conexao.execute("UPDATE orcamentos SET data = ? WHERE id = ?",
                         (nova_data.strftime('%Y-%m-%d %H:%M:%S.%f'), numero))
conexao.commit()
conexao.close()

if cursor.rowcount:
    print(f"Pronto! O orçamento nº {numero} agora aparece como feito há {dias} dias.")
else:
    print(f"Não encontrei o orçamento nº {numero}.")
