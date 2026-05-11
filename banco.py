import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

_pool = None


def iniciar_pool():
    global _pool

    if _pool is None:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise Exception("DATABASE_URL não encontrada no .env")

        _pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url
        )

    return _pool


class ConexaoPool:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if self._conn:
            iniciar_pool().putconn(self._conn)
            self._conn = None


def conectar():
    conn = iniciar_pool().getconn()
    return ConexaoPool(conn)


def caminho_banco():
    return "Supabase PostgreSQL"


def adicionar_coluna_se_nao_existir(cursor, tabela, coluna, tipo):
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
    """, (tabela, coluna))

    existe = cursor.fetchone()[0] > 0

    if not existe:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id BIGSERIAL PRIMARY KEY,
                usuario TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                data_criacao TEXT DEFAULT TO_CHAR(NOW(), 'DD/MM/YYYY HH24:MI:SS')
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                id BIGSERIAL PRIMARY KEY,
                chave TEXT NOT NULL UNIQUE,
                valor TEXT NOT NULL
            )
        """)

        cursor.execute("""
            INSERT INTO configuracoes (chave, valor)
            VALUES ('modo_taxa', 'ambos')
            ON CONFLICT (chave) DO NOTHING
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id BIGSERIAL PRIMARY KEY,
                usuario_id BIGINT,
                nome TEXT NOT NULL,
                telefone TEXT,
                cpf TEXT,
                endereco TEXT,
                data_contratacao TEXT,
                status TEXT DEFAULT 'Aberto',
                data_criacao TEXT DEFAULT TO_CHAR(NOW(), 'DD/MM/YYYY HH24:MI:SS')
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emprestimos (
                id BIGSERIAL PRIMARY KEY,
                usuario_id BIGINT,
                cliente_id BIGINT NOT NULL,
                valor NUMERIC(12,2) DEFAULT 0,
                taxa NUMERIC(12,2) DEFAULT 0,
                juros NUMERIC(12,2) DEFAULT 0,
                total NUMERIC(12,2) DEFAULT 0,
                data_inicio TEXT,
                data_vencimento TEXT,
                status TEXT DEFAULT 'Aberto'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagamentos (
                id BIGSERIAL PRIMARY KEY,
                usuario_id BIGINT,
                emprestimo_id BIGINT NOT NULL,
                valor_pago NUMERIC(12,2) DEFAULT 0,
                tipo TEXT,
                data_pagamento TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendas (
                id BIGSERIAL PRIMARY KEY,
                usuario_id BIGINT,
                produto TEXT NOT NULL,
                cliente TEXT,
                valor_venda NUMERIC(12,2) DEFAULT 0,
                valor_custo NUMERIC(12,2) DEFAULT 0,
                lucro NUMERIC(12,2) DEFAULT 0,
                data_venda TEXT,
                observacao TEXT,
                data_criacao TEXT DEFAULT TO_CHAR(NOW(), 'DD/MM/YYYY HH24:MI:SS')
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id BIGSERIAL PRIMARY KEY,
                usuario TEXT NOT NULL,
                acao TEXT NOT NULL,
                sql_texto TEXT,
                detalhes TEXT,
                data_hora TEXT NOT NULL,
                ip TEXT
            )
        """)

        # Garante que bancos antigos também recebam as novas colunas
        adicionar_coluna_se_nao_existir(cursor, "clientes", "usuario_id", "BIGINT")
        adicionar_coluna_se_nao_existir(cursor, "emprestimos", "usuario_id", "BIGINT")
        adicionar_coluna_se_nao_existir(cursor, "pagamentos", "usuario_id", "BIGINT")
        adicionar_coluna_se_nao_existir(cursor, "vendas", "usuario_id", "BIGINT")

        # Índices para deixar o sistema mais rápido por usuário
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clientes_usuario_id ON clientes(usuario_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emprestimos_usuario_id ON emprestimos(usuario_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagamentos_usuario_id ON pagamentos(usuario_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendas_usuario_id ON vendas(usuario_id)")

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()