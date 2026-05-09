from banco import conectar
from datetime import datetime, timedelta


def pagar_juros(emprestimo_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT valor FROM emprestimos WHERE id = %s",
        (emprestimo_id,)
    )

    linha = cursor.fetchone()

    if not linha:
        cursor.close()
        conn.close()
        return False

    valor = float(linha[0])
    juros = round(valor * 0.30, 2)

    nova_data = datetime.now() + timedelta(days=30)

    cursor.execute(
        """
        UPDATE emprestimos
        SET juros = %s, data_vencimento = %s
        WHERE id = %s
        """,
        (juros, nova_data.strftime("%d/%m/%Y"), emprestimo_id),
    )

    conn.commit()
    cursor.close()
    conn.close()

    return True