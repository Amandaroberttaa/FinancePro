from banco import conectar
from datetime import datetime, timedelta


def criar_emprestimo(cliente_id, valor):
    conn = conectar()
    cursor = conn.cursor()

    juros = round(valor * 0.30, 2)
    total = round(valor + juros, 2)

    data_inicio = datetime.now()
    vencimento = data_inicio + timedelta(days=30)

    cursor.execute(
        """
        INSERT INTO emprestimos
        (cliente_id, valor, taxa, juros, total, data_inicio, data_vencimento, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            cliente_id,
            valor,
            30,
            juros,
            total,
            data_inicio.strftime("%d/%m/%Y"),
            vencimento.strftime("%d/%m/%Y"),
            "Aberto",
        ),
    )

    conn.commit()
    cursor.close()
    conn.close()


def listar_emprestimos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT clientes.nome,
               emprestimos.valor,
               emprestimos.juros,
               emprestimos.data_vencimento,
               emprestimos.status,
               emprestimos.id
        FROM emprestimos
        JOIN clientes ON emprestimos.cliente_id = clientes.id
        ORDER BY emprestimos.id ASC
        """
    )

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return dados