# database.py
"""
Gerir base de dados SQLite para histórico de previsões e bilhetes.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

DB_NAME = "footballai.db"

def init_db():
    """Cria as tabelas se não existirem."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_jogo TEXT,
            jogo TEXT,
            mercado TEXT,
            selecao TEXT,
            probabilidade REAL,
            odd REAL,
            pontuacao REAL,
            confianca_jogo REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bilhetes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_bilhete TEXT,
            selecoes TEXT,
            odd_total REAL,
            confianca_media REAL,
            status TEXT DEFAULT 'pendente',
            tipo TEXT DEFAULT 'normal',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Garantir que a coluna 'tipo' existe (compatibilidade)
    cursor.execute("PRAGMA table_info(bilhetes)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'tipo' not in columns:
        cursor.execute("ALTER TABLE bilhetes ADD COLUMN tipo TEXT DEFAULT 'normal'")

    conn.commit()
    conn.close()

def salvar_previsao(data_jogo: str, jogo: str, mercado: str, selecao: str,
                    probabilidade: float, odd: Optional[float], pontuacao: float,
                    confianca_jogo: float):
    """Guarda uma previsão na base de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO previsoes (data_jogo, jogo, mercado, selecao, probabilidade, odd, pontuacao, confianca_jogo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (data_jogo, jogo, mercado, selecao, probabilidade, odd, pontuacao, confianca_jogo))
    conn.commit()
    conn.close()

def salvar_bilhete(data_bilhete: str, selecoes: List[Dict], odd_total: Optional[float],
                   confianca_media: float, status: str = "pendente", tipo: str = "normal"):
    """Guarda um bilhete na base de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    selecoes_json = json.dumps(selecoes, ensure_ascii=False)
    cursor.execute("""
        INSERT INTO bilhetes (data_bilhete, selecoes, odd_total, confianca_media, status, tipo)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data_bilhete, selecoes_json, odd_total, confianca_media, status, tipo))
    conn.commit()
    conn.close()

def listar_previsoes(limit: int = 50) -> List[Dict]:
    """Retorna as últimas previsões guardadas."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM previsoes ORDER BY criado_em DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def listar_bilhetes(limit: int = 20) -> List[Dict]:
    """Retorna os últimos bilhetes guardados."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bilhetes ORDER BY criado_em DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def atualizar_status_bilhete(bilhete_id: int, novo_status: str):
    """Atualiza o status de um bilhete (ex.: 'ganho', 'perdido')."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bilhetes SET status = ? WHERE id = ?", (novo_status, bilhete_id))
    conn.commit()
    conn.close()

# Inicializar a base de dados ao importar
init_db()
