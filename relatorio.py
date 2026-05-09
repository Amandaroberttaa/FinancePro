from pathlib import Path
from datetime import datetime
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie

from banco import conectar


def moeda(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_pdf(valor):
    if not valor:
        return "-"

    valor = str(valor).strip()

    try:
        if len(valor) >= 10 and valor[2] == "/" and valor[5] == "/":
            return valor[:10]
    except Exception:
        pass

    try:
        if len(valor) >= 10 and valor[4] == "-" and valor[7] == "-":
            data = datetime.strptime(valor[:10], "%Y-%m-%d")
            return data.strftime("%d/%m/%Y")
    except Exception:
        pass

    try:
        data = datetime.fromisoformat(valor)
        return data.strftime("%d/%m/%Y")
    except Exception:
        return valor[:10]


def caminho_pdf_temporario(nome_base):
    pasta_temp = Path(tempfile.gettempdir())
    nome_arquivo = f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.pdf"
    return pasta_temp / nome_arquivo


def buscar_dados_gerais():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT SUM(valor) FROM emprestimos")
    total_emprestado = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(valor_pago) FROM pagamentos")
    total_recebido = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(total)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
    """)
    total_em_aberto = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(total)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'quitado'
    """)
    total_quitado = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(total)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
          AND date(
                substr(data_vencimento, 7, 4) || '-' ||
                substr(data_vencimento, 4, 2) || '-' ||
                substr(data_vencimento, 1, 2)
              ) < date('now')
    """)
    total_atraso = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT c.id,
               c.nome,
               c.telefone,
               c.cpf,
               c.endereco,
               COUNT(e.id) as qtd,
               COALESCE(SUM(e.valor), 0) as total_emprestado,
               COALESCE(SUM(CASE WHEN LOWER(TRIM(e.status)) = 'aberto' THEN e.total ELSE 0 END), 0) as saldo_aberto,
               COALESCE(SUM(CASE WHEN LOWER(TRIM(e.status)) = 'quitado' THEN e.total ELSE 0 END), 0) as total_quitado
        FROM clientes c
        LEFT JOIN emprestimos e ON e.cliente_id = c.id
        GROUP BY c.id, c.nome, c.telefone, c.cpf, c.endereco
        ORDER BY total_emprestado DESC, qtd DESC, c.nome ASC
    """)
    ranking_volume = cursor.fetchall()

    cursor.execute("""
        SELECT c.nome,
               COUNT(p.id) as qtd_pagamentos,
               COALESCE(SUM(p.valor_pago), 0) as total_pago
        FROM clientes c
        LEFT JOIN emprestimos e ON e.cliente_id = c.id
        LEFT JOIN pagamentos p ON p.emprestimo_id = e.id
        GROUP BY c.id, c.nome
        ORDER BY total_pago DESC, qtd_pagamentos DESC, c.nome ASC
    """)
    ranking_pagadores = cursor.fetchall()

    cursor.execute("""
        SELECT c.nome,
               COUNT(e.id) as qtd_atrasos,
               COALESCE(SUM(e.total), 0) as total_atrasado
        FROM clientes c
        JOIN emprestimos e ON e.cliente_id = c.id
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND date(
                substr(e.data_vencimento, 7, 4) || '-' ||
                substr(e.data_vencimento, 4, 2) || '-' ||
                substr(e.data_vencimento, 1, 2)
              ) < date('now')
        GROUP BY c.id, c.nome
        ORDER BY total_atrasado DESC, qtd_atrasos DESC, c.nome ASC
    """)
    ranking_atrasados = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) FROM emprestimos WHERE LOWER(TRIM(status)) = 'quitado'
    """)
    qtd_quitados = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*) FROM emprestimos WHERE LOWER(TRIM(status)) = 'aberto'
    """)
    qtd_abertos = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "total_emprestado": total_emprestado,
        "total_recebido": total_recebido,
        "total_em_aberto": total_em_aberto,
        "total_quitado": total_quitado,
        "total_atraso": total_atraso,
        "ranking_volume": ranking_volume,
        "ranking_pagadores": ranking_pagadores,
        "ranking_atrasados": ranking_atrasados,
        "quitados": qtd_quitados,
        "abertos": qtd_abertos
    }


def gerar_grafico_pizza(abertos, quitados):
    drawing = Drawing(400, 220)

    pie = Pie()
    pie.x = 140
    pie.y = 20
    pie.width = 140
    pie.height = 140
    pie.data = [abertos, quitados] if (abertos + quitados) > 0 else [1, 0]
    pie.labels = ["Abertos", "Quitados"]
    pie.slices.strokeWidth = 0.5
    pie.slices[0].fillColor = colors.HexColor("#4F81BD")
    pie.slices[1].fillColor = colors.HexColor("#9BBB59")

    drawing.add(pie)
    drawing.add(String(120, 180, "Distribuição dos empréstimos", fontSize=12))

    return drawing


def estilo_tabela(tabela, font_size=8, padding=6):
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), padding),
    ]))


def gerar_relatorio():
    dados = buscar_dados_gerais()
    arquivo = caminho_pdf_temporario("relatorio_emprestimos_bonito")

    doc = SimpleDocTemplate(
        str(arquivo),
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloRelatorio",
        fontSize=22,
        leading=26,
        alignment=TA_LEFT,
        spaceAfter=10,
        textColor=colors.HexColor("#111111"),
    ))

    styles.add(ParagraphStyle(
        name="SubInfo",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#666666"),
    ))

    styles.add(ParagraphStyle(
        name="Secao",
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=10,
        textColor=colors.HexColor("#222222"),
    ))

    elementos = []

    elementos.append(Paragraph("Relatório Geral de Empréstimos", styles["TituloRelatorio"]))
    elementos.append(
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles["SubInfo"]
        )
    )
    elementos.append(Spacer(1, 18))

    resumo_data = [
        ["Indicador", "Valor"],
        ["Total emprestado", moeda(dados["total_emprestado"])],
        ["Total recebido", moeda(dados["total_recebido"])],
        ["Total em aberto", moeda(dados["total_em_aberto"])],
        ["Total quitado", moeda(dados["total_quitado"])],
        ["Total em atraso", moeda(dados["total_atraso"])],
    ]

    tabela_resumo = Table(resumo_data, colWidths=[230, 150])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("Visão geral", styles["Secao"]))
    elementos.append(gerar_grafico_pizza(dados["abertos"], dados["quitados"]))
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("Ranking por volume de empréstimos", styles["Secao"]))
    ranking_volume_data = [[
        "Posição", "Cliente", "Qtd.", "Total emprestado", "Quitado", "Em aberto"
    ]]

    for i, c in enumerate(dados["ranking_volume"], start=1):
        ranking_volume_data.append([
            str(i),
            c[1] or "-",
            str(c[5] or 0),
            moeda(c[6]),
            moeda(c[8]),
            moeda(c[7]),
        ])

    tabela_volume = Table(ranking_volume_data, colWidths=[45, 120, 45, 95, 85, 85])
    estilo_tabela(tabela_volume, 8, 6)
    elementos.append(tabela_volume)
    elementos.append(Spacer(1, 18))

    elementos.append(Paragraph("Ranking dos melhores pagadores", styles["Secao"]))
    ranking_pagadores_data = [[
        "Posição", "Cliente", "Qtd. pagamentos", "Total pago"
    ]]

    for i, c in enumerate(dados["ranking_pagadores"], start=1):
        ranking_pagadores_data.append([
            str(i),
            c[0] or "-",
            str(c[1] or 0),
            moeda(c[2]),
        ])

    tabela_pagadores = Table(ranking_pagadores_data, colWidths=[45, 180, 100, 110])
    estilo_tabela(tabela_pagadores, 8, 6)
    elementos.append(tabela_pagadores)
    elementos.append(Spacer(1, 18))

    elementos.append(Paragraph("Ranking dos mais atrasados", styles["Secao"]))
    ranking_atrasados_data = [[
        "Posição", "Cliente", "Qtd. atrasos", "Total atrasado"
    ]]

    if dados["ranking_atrasados"]:
        for i, c in enumerate(dados["ranking_atrasados"], start=1):
            ranking_atrasados_data.append([
                str(i),
                c[0] or "-",
                str(c[1] or 0),
                moeda(c[2]),
            ])
    else:
        ranking_atrasados_data.append(["-", "Nenhum cliente em atraso", "-", moeda(0)])

    tabela_atrasados = Table(ranking_atrasados_data, colWidths=[45, 180, 100, 110])
    estilo_tabela(tabela_atrasados, 8, 6)
    elementos.append(tabela_atrasados)

    doc.build(elementos)
    return str(arquivo)


def gerar_relatorio_cliente(cliente_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nome, telefone, cpf, endereco
        FROM clientes
        WHERE id = ?
    """, (cliente_id,))
    cliente = cursor.fetchone()

    if not cliente:
        conn.close()
        raise Exception("Cliente não encontrado.")

    cursor.execute("""
        SELECT id, valor, taxa, juros, total, data_inicio, data_vencimento, status
        FROM emprestimos
        WHERE cliente_id = ?
        ORDER BY id ASC
    """, (cliente_id,))
    emprestimos = cursor.fetchall()

    cursor.execute("""
        SELECT p.emprestimo_id, p.valor_pago, p.tipo, p.data_pagamento
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE e.cliente_id = ?
        ORDER BY p.id ASC
    """, (cliente_id,))
    pagamentos = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(p.valor_pago), 0)
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE e.cliente_id = ?
    """, (cliente_id,))
    total_pago = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM emprestimos
        WHERE cliente_id = ?
          AND LOWER(TRIM(status)) = 'aberto'
    """, (cliente_id,))
    total_em_aberto = cursor.fetchone()[0] or 0

    conn.close()

    arquivo = caminho_pdf_temporario(f"cliente_{cliente_id}_relatorio")

    doc = SimpleDocTemplate(
        str(arquivo),
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SecaoCliente",
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=8,
        textColor=colors.HexColor("#222222"),
    ))

    elementos = []

    elementos.append(Paragraph(f"Relatório do Cliente: {cliente[0]}", styles["Title"]))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"<b>Telefone:</b> {cliente[1] or '-'}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>CPF:</b> {cliente[2] or '-'}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Endereço:</b> {cliente[3] or '-'}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    resumo_cliente = [
        ["Indicador", "Valor"],
        ["Total pago", moeda(total_pago)],
        ["Total em aberto", moeda(total_em_aberto)],
        ["Qtd. empréstimos", str(len(emprestimos))],
        ["Qtd. pagamentos", str(len(pagamentos))],
    ]
    tabela_resumo = Table(resumo_cliente, colWidths=[180, 130])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 18))

    elementos.append(Paragraph("Empréstimos do cliente", styles["SecaoCliente"]))

    dados_tabela = [[
        "ID", "Valor", "Taxa", "Juros", "Total", "Início", "Vencimento", "Status"
    ]]

    for e in emprestimos:
        dados_tabela.append([
            str(e[0]),
            moeda(e[1]),
            f"{e[2]}%",
            moeda(e[3]),
            moeda(e[4]),
            formatar_data_pdf(e[5]),
            formatar_data_pdf(e[6]),
            e[7] or "-"
        ])

    tabela_emprestimos = Table(
        dados_tabela,
        colWidths=[30, 60, 40, 55, 60, 65, 65, 55]
    )
    estilo_tabela(tabela_emprestimos, 7.5, 5)
    elementos.append(tabela_emprestimos)
    elementos.append(Spacer(1, 18))

    elementos.append(Paragraph("Histórico de pagamentos", styles["SecaoCliente"]))

    pagamentos_data = [[
        "Empréstimo", "Valor pago", "Tipo", "Data pagamento"
    ]]

    if pagamentos:
        for p in pagamentos:
            tipo_formatado = "Juros" if str(p[2]).lower() == "juros" else "Quitação total"
            pagamentos_data.append([
                str(p[0]),
                moeda(p[1]),
                tipo_formatado,
                formatar_data_pdf(p[3]),
            ])
    else:
        pagamentos_data.append(["-", moeda(0), "Nenhum pagamento", "-"])

    tabela_pagamentos = Table(
        pagamentos_data,
        colWidths=[80, 100, 140, 100]
    )
    estilo_tabela(tabela_pagamentos, 8, 6)
    elementos.append(tabela_pagamentos)

    doc.build(elementos)
    return str(arquivo)