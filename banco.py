import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def conectar():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL não encontrada no arquivo .env")

    return psycopg2.connect(database_url)


def caminho_banco():
    return "Supabase PostgreSQL"


def criar_tabelas():
    # As tabelas já foram criadas no Supabase pelo SQL Editor.
    # Então aqui não precisa criar nada.
    return