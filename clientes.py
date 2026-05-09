from banco import conectar


def cadastrar_cliente(nome, telefone):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO clientes (nome, telefone) VALUES (%s, %s)",
        (nome, telefone),
    )

    conn.commit()
    cursor.close()
    conn.close()


def listar_clientes():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nome FROM clientes ORDER BY id ASC")

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return dados