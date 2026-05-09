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


def criar_tabelas():
    return