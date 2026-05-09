import matplotlib.pyplot as plt
from banco import conectar


def grafico_emprestimos():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, COUNT(*)
        FROM emprestimos
        GROUP BY status
    """)

    dados = cursor.fetchall()

    conn.close()

    if not dados:
        print("Nenhum dado para mostrar.")
        return

    status = [d[0] for d in dados]
    valores = [d[1] for d in dados]

    plt.figure()
    plt.pie(valores, labels=status, autopct='%1.1f%%')
    plt.title("Situação dos Empréstimos")

    plt.show()