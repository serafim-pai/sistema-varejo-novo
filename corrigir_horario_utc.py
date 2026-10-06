"""CORREÇÃO ÚNICA do horário do banco do servidor online.

Por que existe: até agora o sistema gravava a hora do relógio da máquina. No servidor online isso é UTC
(3 horas à frente de Brasília), então as vendas, orçamentos, clientes e usuários antigos estão com a hora
adiantada em 3 horas. A partir de agora o sistema grava o horário de Brasília (ver database.agora_brasil).
Este script atrasa em 3 horas só as linhas ANTIGAS, para o histórico ficar certo.

Como usar, no console do servidor, dentro da pasta do projeto:
    python corrigir_horario_utc.py --ver    (só mostra o que mudaria, não altera nada)
    python corrigir_horario_utc.py          (corrige de verdade)

Trava de segurança: o script anota que já rodou (tabela ajustes_unicos) e, se for chamado de novo, não faz
nada. Assim ninguém atrasa as horas duas vezes. Antes de alterar, ele guarda uma cópia do banco ao lado.

NÃO rode no computador de casa: lá as horas já foram gravadas no horário de Brasília.
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

AJUSTE = "horario_utc_para_brasilia"
COLUNAS = [("vendas", "data"), ("orcamentos", "data"), ("clientes", "criado_em"), ("usuarios", "criado_em")]
HORAS = 3
FORMATO = "%Y-%m-%d %H:%M:%S.%f"       # o mesmo jeito que o SQLAlchemy guarda


def _ler(texto):
    return datetime.fromisoformat(texto)


def corrigir(caminho, corte=None, simular=False, fazer_backup=True):
    """Atrasa em 3 horas as datas anteriores a 'corte' (por padrão, agora em UTC).
    Devolve um dicionário com o que foi (ou seria) feito."""
    corte = corte or datetime.now(timezone.utc).replace(tzinfo=None)
    banco = sqlite3.connect(caminho)
    try:
        ja_aplicado = False
        existe = banco.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ajustes_unicos'").fetchone()
        if existe:
            ja_aplicado = banco.execute("SELECT 1 FROM ajustes_unicos WHERE nome = ?", (AJUSTE,)).fetchone() is not None
        if ja_aplicado:
            return {"aplicado": False, "motivo": "já foi aplicado antes: nada foi alterado", "corte": corte}

        # Primeiro lê tudo e calcula (nada é escrito ainda)
        plano = {}
        for tabela, coluna in COLUNAS:
            linhas = banco.execute(f"SELECT id, {coluna} FROM {tabela} WHERE {coluna} IS NOT NULL ORDER BY id").fetchall()
            mudar, depois_do_corte = [], []
            for id_, texto in linhas:
                momento = _ler(texto)
                if momento < corte:
                    mudar.append((id_, texto, (momento - timedelta(hours=HORAS)).strftime(FORMATO)))
                else:
                    depois_do_corte.append(id_)
            plano[(tabela, coluna)] = {"mudar": mudar, "depois_do_corte": depois_do_corte}

        resumo = {f"{t}.{c}": {"corrigidas": len(p["mudar"]), "depois_do_corte": len(p["depois_do_corte"]),
                               "exemplo": (p["mudar"][0][1], p["mudar"][0][2]) if p["mudar"] else None}
                  for (t, c), p in plano.items()}
        resultado = {"aplicado": not simular, "simulacao": simular, "corte": corte, "resumo": resumo, "backup": None}
        if simular:
            return resultado

        if fazer_backup:
            copia = f"{caminho}.antes-do-horario-{corte:%Y%m%d-%H%M%S}"
            destino = sqlite3.connect(copia)
            try:
                banco.backup(destino)
            finally:
                destino.close()
            resultado["backup"] = copia

        # Depois escreve tudo de uma vez: ou corrige tudo, ou não corrige nada
        try:
            for (tabela, coluna), p in plano.items():
                for id_, _antes, novo in p["mudar"]:
                    banco.execute(f"UPDATE {tabela} SET {coluna} = ? WHERE id = ?", (novo, id_))
            banco.execute("CREATE TABLE IF NOT EXISTS ajustes_unicos (nome TEXT PRIMARY KEY, feito_em TEXT NOT NULL)")
            banco.execute("INSERT INTO ajustes_unicos (nome, feito_em) VALUES (?, ?)", (AJUSTE, corte.strftime(FORMATO)))
            banco.commit()
        except Exception:
            banco.rollback()
            raise
        return resultado
    finally:
        banco.close()


def mostrar(resultado):
    if resultado.get("motivo"):
        print(resultado["motivo"])
        return
    print("SIMULAÇÃO (nada foi alterado)" if resultado["simulacao"] else "CORREÇÃO APLICADA")
    print("Corte (UTC):", resultado["corte"])
    for coluna, r in resultado["resumo"].items():
        exemplo = f"  ex.: {r['exemplo'][0]}  ->  {r['exemplo'][1]}" if r["exemplo"] else ""
        print(f"  {coluna}: {r['corrigidas']} corrigidas, {r['depois_do_corte']} depois do corte{exemplo}")
    if resultado.get("backup"):
        print("Cópia do banco guardada em:", resultado["backup"])


if __name__ == "__main__":
    caminho = os.environ.get("VAREJO_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "varejo.db")
    if not os.path.exists(caminho):
        sys.exit(f"Não achei o banco em {caminho}")
    mostrar(corrigir(caminho, simular="--ver" in sys.argv))
