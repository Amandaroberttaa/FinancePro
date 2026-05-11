
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from flask import Flask, render_template, request, jsonify, send_file, session

from banco import conectar, criar_tabelas, caminho_banco

try:
    from relatorio import gerar_relatorio, gerar_relatorio_cliente
except Exception:
    gerar_relatorio = None
    gerar_relatorio_cliente = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except Exception:
    A4 = None


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static")
)

app.secret_key = os.environ.get("FINANCEPRO_SECRET_KEY", "financepro_secret_2026_admin")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("VERCEL") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

criar_tabelas()

ADMIN_USUARIO = "ADM"
ADMIN_SENHA = "A1D2M3"


# ---------------- UTILITÁRIOS ----------------

def formatar_data_texto(valor):
    if not valor:
        return ""

    valor = str(valor).strip()

    if len(valor) >= 10 and valor[2] == "/" and valor[5] == "/":
        return valor[:10]

    if len(valor) >= 10 and valor[4] == "-" and valor[7] == "-":
        try:
            data = datetime.strptime(valor[:10], "%Y-%m-%d")
            return data.strftime("%d/%m/%Y")
        except Exception:
            return valor[:10]

    try:
        data = datetime.fromisoformat(valor)
        return data.strftime("%d/%m/%Y")
    except Exception:
        return valor[:10]


def normalizar_data(valor):
    valor = str(valor or "").strip()
    if not valor:
        return datetime.now().strftime("%d/%m/%Y")
    datetime.strptime(valor, "%d/%m/%Y")
    return valor


def moeda(valor):
    return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def usuario_logado():
    return session.get("usuario")


def usuario_id_logado():
    return session.get("usuario_id")


def usuario_e_admin():
    return bool(session.get("is_admin"))


def exigir_login():
    if not usuario_logado():
        return jsonify({"ok": False, "mensagem": "Faça login primeiro."}), 401
    return None


def exigir_admin():
    if not usuario_logado():
        return jsonify({"ok": False, "mensagem": "Faça login primeiro."}), 401
    if not usuario_e_admin():
        return jsonify({"ok": False, "mensagem": "Acesso restrito ao administrador."}), 403
    return None


def filtro_usuario_sql(alias=""):
    if usuario_e_admin():
        return "1=1", []
    campo = f"{alias}.usuario_id" if alias else "usuario_id"
    return f"{campo} = %s", [usuario_id_logado()]


def filtro_periodo_sql(campo, inicio, fim):
    condicoes = [f"{campo} ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'"]
    params = []

    if inicio:
        normalizar_data(inicio)
        condicoes.append(f"TO_DATE({campo}, 'DD/MM/YYYY') >= TO_DATE(%s, 'DD/MM/YYYY')")
        params.append(inicio)

    if fim:
        normalizar_data(fim)
        condicoes.append(f"TO_DATE({campo}, 'DD/MM/YYYY') <= TO_DATE(%s, 'DD/MM/YYYY')")
        params.append(fim)

    return " AND ".join(condicoes), params


def lucro_emprestimos_sql():
    return """
        COALESCE(SUM(CASE
            WHEN p.tipo = 'juros' THEN p.valor_pago
            WHEN p.tipo = 'total' THEN e.juros
            ELSE 0
        END), 0)
    """


def registrar_log_admin(acao, sql_texto="", detalhes=""):
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_logs (usuario, acao, sql_texto, detalhes, data_hora, ip)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            usuario_logado() or "desconhecido",
            acao,
            sql_texto or "",
            detalhes or "",
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            request.remote_addr or ""
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass


def gerar_recibo_pdf(titulo, linhas, nome_base):
    if A4 is None:
        raise Exception("reportlab não está instalado.")

    pasta = Path(tempfile.gettempdir())
    arquivo = pasta / f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.pdf"

    doc = SimpleDocTemplate(str(arquivo), pagesize=A4, rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()

    elementos = [Paragraph(titulo, styles["Title"]), Spacer(1, 16)]
    dados = [["Campo", "Informação"]]

    for chave, valor in linhas:
        dados.append([str(chave), str(valor)])

    tabela = Table(dados, colWidths=[160, 330])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 18))
    elementos.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    doc.build(elementos)
    return str(arquivo)




# ---------------- RECURSOS AVANÇADOS ----------------

def garantir_recursos_avancados():
    """Cria colunas/tabelas extras sem apagar dados antigos."""
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_criacao TEXT DEFAULT TO_CHAR(NOW(), 'DD/MM/YYYY HH24:MI:SS')")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_login TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_logs (
                id BIGSERIAL PRIMARY KEY,
                usuario TEXT,
                tipo TEXT,
                data_hora TEXT NOT NULL,
                detalhes TEXT
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass


garantir_recursos_avancados()


def registrar_backup_log(tipo, detalhes=""):
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO backup_logs (usuario, tipo, data_hora, detalhes)
            VALUES (%s, %s, %s, %s)
        """, (
            usuario_logado() or "sistema",
            tipo,
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            detalhes or ""
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

# ---------------- FRONT ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- LOGIN ----------------

@app.route("/api/sessao", methods=["GET"])
def obter_sessao():
    return jsonify({
        "logado": bool(usuario_logado()),
        "usuario": usuario_logado() or "",
        "usuario_id": usuario_id_logado(),
        "is_admin": usuario_e_admin()
    })


@app.route("/api/verificar-tem-usuario", methods=["GET"])
def verificar_tem_usuario():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total = cursor.fetchone()[0] or 0
    cursor.close()
    conn.close()
    return jsonify({"tem_usuario": total > 0})


@app.route("/api/criar-usuario", methods=["POST"])
def criar_usuario():
    dados = request.get_json() or {}
    usuario = (dados.get("usuario") or "").strip()
    senha = (dados.get("senha") or "").strip()

    if not usuario or not senha:
        return jsonify({"ok": False, "mensagem": "Usuário e senha são obrigatórios."})

    if usuario.upper() == ADMIN_USUARIO:
        return jsonify({"ok": False, "mensagem": "Esse usuário é reservado para administrador."})

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "mensagem": "Esse usuário já existe. Escolha outro nome."})

        cursor.execute("""
            INSERT INTO usuarios (usuario, senha)
            VALUES (%s, %s)
            RETURNING id
        """, (usuario, senha))

        novo_id = cursor.fetchone()[0]
        conn.commit()

        session.permanent = True
        session["usuario_id"] = novo_id
        session["usuario"] = usuario
        session["is_admin"] = False

        cursor.close()
        conn.close()

        return jsonify({
            "ok": True,
            "mensagem": "Usuário criado com sucesso.",
            "usuario": usuario,
            "usuario_id": novo_id,
            "is_admin": False
        })

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/login", methods=["POST"])
def login():
    session.permanent = True

    dados = request.get_json() or {}
    usuario = (dados.get("usuario") or "").strip()
    senha = (dados.get("senha") or "").strip()

    if not usuario or not senha:
        return jsonify({"ok": False, "mensagem": "Informe usuário e senha."})

    if usuario.upper() == ADMIN_USUARIO and senha == ADMIN_SENHA:
        session["usuario_id"] = None
        session["usuario"] = ADMIN_USUARIO
        session["is_admin"] = True
        registrar_log_admin("LOGIN_ADMIN", "", "Administrador entrou no sistema")
        return jsonify({
            "ok": True,
            "mensagem": "Login admin realizado com sucesso.",
            "is_admin": True,
            "usuario": ADMIN_USUARIO
        })

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, usuario, COALESCE(ativo, TRUE)
        FROM usuarios
        WHERE usuario = %s AND senha = %s
    """, (usuario, senha))

    linha = cursor.fetchone()

    if not linha:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Usuário ou senha inválidos."})

    if linha[2] is False:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Usuário bloqueado. Fale com o administrador."})

    cursor.execute("UPDATE usuarios SET ultimo_login = %s WHERE id = %s", (
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        linha[0]
    ))
    conn.commit()
    cursor.close()
    conn.close()

    session["usuario_id"] = linha[0]
    session["usuario"] = linha[1]
    session["is_admin"] = False

    return jsonify({
        "ok": True,
        "mensagem": "Login realizado com sucesso.",
        "is_admin": False,
        "usuario": linha[1],
        "usuario_id": linha[0]
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    if usuario_logado():
        registrar_log_admin("LOGOUT", "", "Logout do sistema")
    session.clear()
    return jsonify({"ok": True})


# ---------------- BACKUP ----------------

@app.route("/api/backup-banco", methods=["GET"])
def backup_banco():
    return jsonify({
        "ok": False,
        "mensagem": "Agora o banco está no Supabase. O backup deve ser feito pelo painel do Supabase."
    })


@app.route("/api/restaurar-banco", methods=["POST"])
def restaurar_banco():
    return jsonify({
        "ok": False,
        "mensagem": "Restauração por arquivo .db não funciona mais, pois agora o banco é PostgreSQL/Supabase."
    })


# ---------------- RESUMOS ----------------

@app.route("/api/resumo", methods=["GET"])
def resumo():
    ver = exigir_login()
    if ver:
        return ver

    where_e, params_e = filtro_usuario_sql("e")
    where_v, params_v = filtro_usuario_sql("v")
    where_c, params_c = filtro_usuario_sql("c")
    where_p, params_p = filtro_usuario_sql("p")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT COALESCE(SUM(e.valor), 0)
        FROM emprestimos e
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
    """, params_e)
    capital_emprestado_aberto = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(e.total), 0)
        FROM emprestimos e
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
    """, params_e)
    total_em_aberto = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(p.valor_pago), 0)
        FROM pagamentos p
        WHERE {where_p}
    """, params_p)
    total_recebido_emprestimos = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT {lucro_emprestimos_sql()}
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
    """, params_p)
    lucro_emprestimos = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT {lucro_emprestimos_sql()}
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
          AND p.data_pagamento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(p.data_pagamento, 'DD/MM/YYYY')
              BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
    """, params_p)
    lucro_emprestimos_semanal = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT {lucro_emprestimos_sql()}
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
          AND p.data_pagamento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND EXTRACT(MONTH FROM TO_DATE(p.data_pagamento, 'DD/MM/YYYY')) = EXTRACT(MONTH FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM TO_DATE(p.data_pagamento, 'DD/MM/YYYY')) = EXTRACT(YEAR FROM CURRENT_DATE)
    """, params_p)
    lucro_emprestimos_mensal = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COALESCE(SUM(v.valor_venda), 0) FROM vendas v WHERE {where_v}", params_v)
    total_vendido = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COALESCE(SUM(v.valor_custo), 0) FROM vendas v WHERE {where_v}", params_v)
    custo_vendas = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COALESCE(SUM(v.lucro), 0) FROM vendas v WHERE {where_v}", params_v)
    lucro_vendas = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(v.lucro), 0)
        FROM vendas v
        WHERE {where_v}
          AND v.data_venda ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(v.data_venda, 'DD/MM/YYYY')
              BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
    """, params_v)
    lucro_vendas_semanal = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(v.lucro), 0)
        FROM vendas v
        WHERE {where_v}
          AND v.data_venda ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND EXTRACT(MONTH FROM TO_DATE(v.data_venda, 'DD/MM/YYYY')) = EXTRACT(MONTH FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM TO_DATE(v.data_venda, 'DD/MM/YYYY')) = EXTRACT(YEAR FROM CURRENT_DATE)
    """, params_v)
    lucro_vendas_mensal = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(v.valor_venda), 0)
        FROM vendas v
        WHERE {where_v}
          AND v.data_venda ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(v.data_venda, 'DD/MM/YYYY')
              BETWEEN CURRENT_DATE - INTERVAL '6 days' AND CURRENT_DATE
    """, params_v)
    total_vendido_semanal = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(v.valor_venda), 0)
        FROM vendas v
        WHERE {where_v}
          AND v.data_venda ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND EXTRACT(MONTH FROM TO_DATE(v.data_venda, 'DD/MM/YYYY')) = EXTRACT(MONTH FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM TO_DATE(v.data_venda, 'DD/MM/YYYY')) = EXTRACT(YEAR FROM CURRENT_DATE)
    """, params_v)
    total_vendido_mensal = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COUNT(*) FROM pagamentos p WHERE {where_p}", params_p)
    total_pagamentos = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COUNT(*) FROM vendas v WHERE {where_v}", params_v)
    total_vendas = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(e.total), 0)
        FROM emprestimos e
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
          AND e.data_vencimento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(e.data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """, params_e)
    total_atraso = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COUNT(DISTINCT e.cliente_id)
        FROM emprestimos e
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
          AND e.data_vencimento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(e.data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """, params_e)
    clientes_em_atraso = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(CASE
            WHEN p.tipo = 'juros' THEN p.valor_pago
            WHEN p.tipo = 'total' THEN e.juros
            ELSE 0
        END), 0)
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
          AND e.taxa = 20
    """, params_p)
    lucro_20 = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COALESCE(SUM(CASE
            WHEN p.tipo = 'juros' THEN p.valor_pago
            WHEN p.tipo = 'total' THEN e.juros
            ELSE 0
        END), 0)
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
          AND e.taxa = 30
    """, params_p)
    lucro_30 = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COUNT(*) FROM clientes c WHERE {where_c}", params_c)
    total_clientes = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    lucro_geral = float(lucro_emprestimos) + float(lucro_vendas)
    lucro_semanal_geral = float(lucro_emprestimos_semanal) + float(lucro_vendas_semanal)
    lucro_mensal_geral = float(lucro_emprestimos_mensal) + float(lucro_vendas_mensal)
    total_recebido_geral = float(total_recebido_emprestimos) + float(total_vendido)

    return jsonify({
        "total_recebido": round(total_recebido_geral, 2),
        "total_recebido_emprestimos": round(float(total_recebido_emprestimos), 2),
        "total_pagamentos": total_pagamentos,
        "total_vendas": total_vendas,
        "total_atraso": round(float(total_atraso), 2),
        "clientes_em_atraso": clientes_em_atraso,
        "total_clientes": total_clientes,
        "total_emprestado": round(float(capital_emprestado_aberto), 2),
        "capital_emprestado_aberto": round(float(capital_emprestado_aberto), 2),
        "total_em_aberto": round(float(total_em_aberto), 2),
        "lucro_total": round(lucro_geral, 2),
        "lucro_emprestimos": round(float(lucro_emprestimos), 2),
        "lucro_emprestimos_semanal": round(float(lucro_emprestimos_semanal), 2),
        "lucro_emprestimos_mensal": round(float(lucro_emprestimos_mensal), 2),
        "total_vendido": round(float(total_vendido), 2),
        "total_vendido_semanal": round(float(total_vendido_semanal), 2),
        "total_vendido_mensal": round(float(total_vendido_mensal), 2),
        "custo_vendas": round(float(custo_vendas), 2),
        "lucro_vendas": round(float(lucro_vendas), 2),
        "lucro_vendas_semanal": round(float(lucro_vendas_semanal), 2),
        "lucro_vendas_mensal": round(float(lucro_vendas_mensal), 2),
        "lucro_geral": round(lucro_geral, 2),
        "lucro_semanal_geral": round(lucro_semanal_geral, 2),
        "lucro_mensal_geral": round(lucro_mensal_geral, 2),
        "lucro_20": round(float(lucro_20), 2),
        "lucro_30": round(float(lucro_30), 2)
    })


@app.route("/api/dados-grafico-dashboard", methods=["GET"])
def dados_grafico_dashboard():
    ver = exigir_login()
    if ver:
        return ver

    where_e, params_e = filtro_usuario_sql("e")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM emprestimos e WHERE LOWER(TRIM(e.status)) = 'quitado' AND {where_e}", params_e)
    quitado = cursor.fetchone()[0] or 0

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM emprestimos e
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
          AND e.data_vencimento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(e.data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """, params_e)
    atraso = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COUNT(*) FROM emprestimos e WHERE e.taxa = 20 AND LOWER(TRIM(e.status)) = 'aberto' AND {where_e}", params_e)
    taxa20 = cursor.fetchone()[0] or 0

    cursor.execute(f"SELECT COUNT(*) FROM emprestimos e WHERE e.taxa = 30 AND LOWER(TRIM(e.status)) = 'aberto' AND {where_e}", params_e)
    taxa30 = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    return jsonify([
        {"nome": "Quitado", "valor": quitado},
        {"nome": "Atraso", "valor": atraso},
        {"nome": "Empréstimo 20%", "valor": taxa20},
        {"nome": "Empréstimo 30%", "valor": taxa30}
    ])


@app.route("/api/dashboard-completo", methods=["GET"])
def dashboard_completo():
    resumo_dados = resumo().get_json()
    grafico_dados = dados_grafico_dashboard().get_json()
    return jsonify({"resumo": resumo_dados, "grafico": grafico_dados})


# ---------------- CLIENTES ----------------

@app.route("/api/clientes", methods=["GET"])
def lista_clientes():
    ver = exigir_login()
    if ver:
        return ver

    where_c, params_c = filtro_usuario_sql("c")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT c.id, c.nome, c.telefone, c.cpf, c.endereco, c.data_contratacao, c.status
        FROM clientes c
        WHERE {where_c}
        ORDER BY c.id ASC
    """, params_c)

    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": item[0],
        "nome": item[1],
        "telefone": item[2] or "",
        "cpf": item[3] or "",
        "endereco": item[4] or "",
        "data_contratacao": formatar_data_texto(item[5]),
        "status": item[6] or "Aberto"
    } for item in dados])


@app.route("/api/clientes", methods=["POST"])
def cadastrar_cliente():
    ver = exigir_login()
    if ver:
        return ver

    if usuario_e_admin():
        return jsonify({"ok": False, "mensagem": "Admin não cadastra clientes. Entre com um usuário comum."})

    dados = request.get_json() or {}
    nome = (dados.get("nome") or "").strip()
    telefone = (dados.get("telefone") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    data_contratacao = (dados.get("data_contratacao") or "").strip() or datetime.now().strftime("%d/%m/%Y")

    if not nome:
        return jsonify({"ok": False, "mensagem": "Nome é obrigatório."})

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clientes (usuario_id, nome, telefone, cpf, endereco, data_contratacao, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (usuario_id_logado(), nome, telefone, cpf, endereco, data_contratacao, "Aberto"))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"ok": True, "mensagem": "Cliente cadastrado com sucesso."})


@app.route("/api/clientes/<int:cliente_id>", methods=["GET"])
def obter_cliente(cliente_id):
    ver = exigir_login()
    if ver:
        return ver

    where_c, params_c = filtro_usuario_sql("c")
    params = [cliente_id] + params_c

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT c.id, c.nome, c.telefone, c.cpf, c.endereco, c.data_contratacao, c.status
        FROM clientes c
        WHERE c.id = %s AND {where_c}
    """, params)

    cliente = cursor.fetchone()
    cursor.close()
    conn.close()

    if not cliente:
        return jsonify({"ok": False, "mensagem": "Cliente não encontrado."})

    return jsonify({"ok": True, "cliente": {
        "id": cliente[0],
        "nome": cliente[1] or "",
        "telefone": cliente[2] or "",
        "cpf": cliente[3] or "",
        "endereco": cliente[4] or "",
        "data_contratacao": cliente[5] or "",
        "status": cliente[6] or "Aberto"
    }})


@app.route("/api/clientes/<int:cliente_id>", methods=["PUT"])
def editar_cliente(cliente_id):
    ver = exigir_login()
    if ver:
        return ver

    dados = request.get_json() or {}
    nome = (dados.get("nome") or "").strip()
    telefone = (dados.get("telefone") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    data_contratacao = (dados.get("data_contratacao") or "").strip()
    status = (dados.get("status") or "Aberto").strip()

    where_c, params_c = filtro_usuario_sql("clientes")
    params = [nome, telefone, cpf, endereco, data_contratacao, status, cliente_id] + params_c

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE clientes
        SET nome = %s, telefone = %s, cpf = %s, endereco = %s, data_contratacao = %s, status = %s
        WHERE id = %s AND {where_c}
    """, params)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Cliente atualizado com sucesso."})


# ---------------- EMPRÉSTIMOS ----------------

@app.route("/api/emprestimos", methods=["GET"])
def lista_emprestimos():
    ver = exigir_login()
    if ver:
        return ver

    where_e, params_e = filtro_usuario_sql("e")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT e.id, c.nome, c.id, e.valor, e.taxa, e.juros, e.total,
               e.data_inicio, e.data_vencimento, e.status
        FROM emprestimos e
        JOIN clientes c ON e.cliente_id = c.id
        WHERE LOWER(TRIM(e.status)) = 'aberto'
          AND {where_e}
        ORDER BY e.id ASC
    """, params_e)

    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": item[0],
        "cliente": item[1],
        "cliente_id": item[2],
        "valor": float(item[3] or 0),
        "taxa": float(item[4] or 0),
        "juros": float(item[5] or 0),
        "total": float(item[6] or 0),
        "data_contratacao": formatar_data_texto(item[7]),
        "vencimento": formatar_data_texto(item[8]),
        "status": item[9]
    } for item in dados])


@app.route("/api/emprestimos", methods=["POST"])
def criar_emprestimo():
    ver = exigir_login()
    if ver:
        return ver

    if usuario_e_admin():
        return jsonify({"ok": False, "mensagem": "Admin não cadastra empréstimos. Entre com um usuário comum."})

    dados = request.get_json() or {}

    try:
        cliente_id = int(dados.get("cliente_id"))
        valor = float(dados.get("valor"))
        taxa = float(dados.get("taxa"))
    except Exception:
        return jsonify({"ok": False, "mensagem": "Dados inválidos."})

    data_inicio = (dados.get("data_inicio") or "").strip() or datetime.now().strftime("%d/%m/%Y")

    try:
        data_obj = datetime.strptime(data_inicio, "%d/%m/%Y")
    except Exception:
        return jsonify({"ok": False, "mensagem": "Data inválida. Use dd/mm/aaaa."})

    # Garante que o cliente pertence ao usuário logado
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM clientes WHERE id = %s AND usuario_id = %s", (cliente_id, usuario_id_logado()))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Cliente não encontrado para este usuário."})

    juros = round(valor * (taxa / 100), 2)
    total = round(valor + juros, 2)
    vencimento = (data_obj + timedelta(days=30)).strftime("%d/%m/%Y")

    cursor.execute("""
        INSERT INTO emprestimos (
            usuario_id, cliente_id, valor, taxa, juros, total,
            data_inicio, data_vencimento, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (usuario_id_logado(), cliente_id, valor, taxa, juros, total, data_inicio, vencimento, "Aberto"))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Empréstimo criado com sucesso."})


@app.route("/api/emprestimos/<int:emprestimo_id>/quitar", methods=["POST"])
def quitar_emprestimo(emprestimo_id):
    ver = exigir_login()
    if ver:
        return ver

    where_e, params_e = filtro_usuario_sql("e")
    params = [emprestimo_id] + params_e

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            SELECT e.total, e.status
            FROM emprestimos e
            WHERE e.id = %s AND {where_e}
            FOR UPDATE
        """, params)

        linha = cursor.fetchone()

        if not linha:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

        total = float(linha[0] or 0)
        status = (linha[1] or "").strip().lower()

        if status == "quitado":
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "mensagem": "Esse empréstimo já está quitado."})

        hoje = datetime.now().strftime("%d/%m/%Y")

        cursor.execute("""
            INSERT INTO pagamentos (usuario_id, emprestimo_id, valor_pago, tipo, data_pagamento)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id_logado(), emprestimo_id, total, "total", hoje))

        cursor.execute("""
            UPDATE emprestimos
            SET status = 'Quitado'
            WHERE id = %s
        """, (emprestimo_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "mensagem": "Empréstimo quitado com sucesso."})

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/emprestimos/<int:emprestimo_id>/pagar-juros", methods=["POST"])
def pagar_somente_juros(emprestimo_id):
    ver = exigir_login()
    if ver:
        return ver

    where_e, params_e = filtro_usuario_sql("e")
    params = [emprestimo_id] + params_e

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            SELECT e.valor, e.taxa, e.juros, e.data_vencimento, e.status
            FROM emprestimos e
            WHERE e.id = %s AND {where_e}
            FOR UPDATE
        """, params)

        dado = cursor.fetchone()

        if not dado:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

        status = (dado[4] or "").strip().lower()
        if status == "quitado":
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"ok": False, "mensagem": "Empréstimo já está quitado."})

        valor = float(dado[0] or 0)
        taxa = float(dado[1] or 0)
        juros = float(dado[2] or 0)
        hoje = datetime.now().strftime("%d/%m/%Y")

        cursor.execute("""
            INSERT INTO pagamentos (usuario_id, emprestimo_id, valor_pago, tipo, data_pagamento)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id_logado(), emprestimo_id, juros, "juros", hoje))

        try:
            vencimento_atual = datetime.strptime(dado[3], "%d/%m/%Y")
        except Exception:
            vencimento_atual = datetime.now()

        novo_vencimento = (vencimento_atual + timedelta(days=30)).strftime("%d/%m/%Y")
        novo_juros = round(valor * (taxa / 100), 2)
        novo_total = round(valor + novo_juros, 2)

        cursor.execute("""
            UPDATE emprestimos
            SET juros = %s, total = %s, data_vencimento = %s, status = 'Aberto'
            WHERE id = %s
        """, (novo_juros, novo_total, novo_vencimento, emprestimo_id))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"ok": True, "mensagem": "Pagamento de juros registrado com sucesso."})

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/emprestimos/<int:emprestimo_id>/trocar-taxa", methods=["POST"])
def alterar_taxa_emprestimo(emprestimo_id):
    ver = exigir_login()
    if ver:
        return ver

    dados = request.get_json() or {}
    try:
        nova_taxa = float(dados.get("nova_taxa"))
    except Exception:
        return jsonify({"ok": False, "mensagem": "Taxa inválida."})

    if nova_taxa not in (20, 30):
        return jsonify({"ok": False, "mensagem": "A taxa deve ser 20 ou 30."})

    where_e, params_e = filtro_usuario_sql("e")
    params = [emprestimo_id] + params_e

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"SELECT e.valor, e.status FROM emprestimos e WHERE e.id = %s AND {where_e}", params)
    dado = cursor.fetchone()

    if not dado:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

    if (dado[1] or "").strip().lower() == "quitado":
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Não é possível alterar taxa de empréstimo quitado."})

    valor = float(dado[0] or 0)
    novo_juros = round(valor * (nova_taxa / 100), 2)
    novo_total = round(valor + novo_juros, 2)

    cursor.execute("""
        UPDATE emprestimos
        SET taxa = %s, juros = %s, total = %s
        WHERE id = %s
    """, (nova_taxa, novo_juros, novo_total, emprestimo_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Taxa alterada com sucesso."})


# ---------------- VENDAS ----------------

@app.route("/api/vendas", methods=["GET"])
def lista_vendas():
    ver = exigir_login()
    if ver:
        return ver

    inicio = (request.args.get("inicio") or "").strip()
    fim = (request.args.get("fim") or "").strip()

    where_v, params_v = filtro_usuario_sql("v")
    params = list(params_v)

    periodo_sql = ""
    if inicio or fim:
        periodo_cond, periodo_params = filtro_periodo_sql("v.data_venda", inicio, fim)
        periodo_sql = f" AND {periodo_cond}"
        params.extend(periodo_params)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT v.id, v.produto, v.cliente, v.valor_venda, v.valor_custo, v.lucro, v.data_venda, v.observacao
        FROM vendas v
        WHERE {where_v}
          {periodo_sql}
        ORDER BY v.id DESC
    """, params)

    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": item[0],
        "produto": item[1] or "",
        "cliente": item[2] or "",
        "valor_venda": float(item[3] or 0),
        "valor_custo": float(item[4] or 0),
        "lucro": float(item[5] or 0),
        "data_venda": formatar_data_texto(item[6]),
        "observacao": item[7] or ""
    } for item in dados])


@app.route("/api/vendas", methods=["POST"])
def cadastrar_venda():
    ver = exigir_login()
    if ver:
        return ver

    if usuario_e_admin():
        return jsonify({"ok": False, "mensagem": "Admin não cadastra vendas. Entre com um usuário comum."})

    dados = request.get_json() or {}
    produto = (dados.get("produto") or "").strip()
    cliente = (dados.get("cliente") or "").strip()
    observacao = (dados.get("observacao") or "").strip()
    data_venda = (dados.get("data_venda") or "").strip() or datetime.now().strftime("%d/%m/%Y")

    try:
        valor_venda = float(dados.get("valor_venda") or 0)
        valor_custo = float(dados.get("valor_custo") or 0)
    except Exception:
        return jsonify({"ok": False, "mensagem": "Valores inválidos."})

    if not produto:
        return jsonify({"ok": False, "mensagem": "Produto é obrigatório."})

    lucro = round(valor_venda - valor_custo, 2)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vendas (usuario_id, produto, cliente, valor_venda, valor_custo, lucro, data_venda, observacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (usuario_id_logado(), produto, cliente, valor_venda, valor_custo, lucro, data_venda, observacao))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Venda registrada com sucesso."})


@app.route("/api/vendas/<int:venda_id>", methods=["GET"])
def obter_venda(venda_id):
    ver = exigir_login()
    if ver:
        return ver

    where_v, params_v = filtro_usuario_sql("v")
    params = [venda_id] + params_v

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT v.id, v.produto, v.cliente, v.valor_venda, v.valor_custo, v.lucro, v.data_venda, v.observacao
        FROM vendas v
        WHERE v.id = %s AND {where_v}
    """, params)

    venda = cursor.fetchone()
    cursor.close()
    conn.close()

    if not venda:
        return jsonify({"ok": False, "mensagem": "Venda não encontrada."})

    return jsonify({"ok": True, "venda": {
        "id": venda[0],
        "produto": venda[1] or "",
        "cliente": venda[2] or "",
        "valor_venda": float(venda[3] or 0),
        "valor_custo": float(venda[4] or 0),
        "lucro": float(venda[5] or 0),
        "data_venda": formatar_data_texto(venda[6]),
        "observacao": venda[7] or ""
    }})


@app.route("/api/vendas/<int:venda_id>", methods=["PUT"])
def editar_venda(venda_id):
    ver = exigir_login()
    if ver:
        return ver

    dados = request.get_json() or {}
    produto = (dados.get("produto") or "").strip()
    cliente = (dados.get("cliente") or "").strip()
    data_venda = (dados.get("data_venda") or "").strip()
    observacao = (dados.get("observacao") or "").strip()

    try:
        valor_venda = float(dados.get("valor_venda") or 0)
        valor_custo = float(dados.get("valor_custo") or 0)
    except Exception:
        return jsonify({"ok": False, "mensagem": "Valores inválidos."})

    if not produto:
        return jsonify({"ok": False, "mensagem": "Produto é obrigatório."})

    lucro = round(valor_venda - valor_custo, 2)
    where_v, params_v = filtro_usuario_sql("vendas")
    params = [produto, cliente, valor_venda, valor_custo, lucro, data_venda, observacao, venda_id] + params_v

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE vendas
        SET produto = %s, cliente = %s, valor_venda = %s, valor_custo = %s,
            lucro = %s, data_venda = %s, observacao = %s
        WHERE id = %s AND {where_v}
    """, params)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Venda atualizada com sucesso."})


@app.route("/api/vendas/<int:venda_id>", methods=["DELETE"])
def excluir_venda(venda_id):
    ver = exigir_login()
    if ver:
        return ver

    where_v, params_v = filtro_usuario_sql("vendas")
    params = [venda_id] + params_v

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM vendas WHERE id = %s AND {where_v}", params)
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Venda excluída com sucesso."})


# ---------------- HISTÓRICO / RECIBOS ----------------

@app.route("/api/historico/pagamentos", methods=["GET"])
def historico_pagamentos():
    ver = exigir_login()
    if ver:
        return ver

    inicio = (request.args.get("inicio") or "").strip()
    fim = (request.args.get("fim") or "").strip()

    where_p, params_p = filtro_usuario_sql("p")
    periodo_sql, periodo_params = filtro_periodo_sql("p.data_pagamento", inicio, fim)
    params = params_p + periodo_params

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT p.id, p.emprestimo_id, c.nome, p.valor_pago, p.tipo, p.data_pagamento, e.juros
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        JOIN clientes c ON c.id = e.cliente_id
        WHERE {where_p}
          AND {periodo_sql}
        ORDER BY p.id DESC
    """, params)

    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": item[0],
        "emprestimo_id": item[1],
        "cliente": item[2] or "",
        "valor_pago": float(item[3] or 0),
        "tipo": item[4] or "",
        "data_pagamento": formatar_data_texto(item[5]),
        "lucro": float(item[3] or 0) if str(item[4]).lower() == "juros" else float(item[6] or 0)
    } for item in dados])


@app.route("/api/historico/quitados", methods=["GET"])
def historico_quitados():
    ver = exigir_login()
    if ver:
        return ver

    inicio = (request.args.get("inicio") or "").strip()
    fim = (request.args.get("fim") or "").strip()

    where_e, params_e = filtro_usuario_sql("e")
    periodo_sql, periodo_params = filtro_periodo_sql("p.data_pagamento", inicio, fim)
    params = params_e + periodo_params

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT e.id, c.nome, e.valor, e.taxa, e.juros, e.total, e.data_inicio, e.data_vencimento, p.data_pagamento
        FROM emprestimos e
        JOIN clientes c ON c.id = e.cliente_id
        JOIN pagamentos p ON p.emprestimo_id = e.id AND p.tipo = 'total'
        WHERE LOWER(TRIM(e.status)) = 'quitado'
          AND {where_e}
          AND {periodo_sql}
        ORDER BY p.id DESC
    """, params)

    dados = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{
        "id": item[0],
        "cliente": item[1] or "",
        "valor": float(item[2] or 0),
        "taxa": float(item[3] or 0),
        "juros": float(item[4] or 0),
        "total": float(item[5] or 0),
        "data_inicio": formatar_data_texto(item[6]),
        "vencimento": formatar_data_texto(item[7]),
        "data_quitacao": formatar_data_texto(item[8])
    } for item in dados])


@app.route("/api/recibo/venda/<int:venda_id>", methods=["GET"])
def recibo_venda(venda_id):
    ver = exigir_login()
    if ver:
        return ver

    where_v, params_v = filtro_usuario_sql("v")
    params = [venda_id] + params_v

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT v.id, v.produto, v.cliente, v.valor_venda, v.valor_custo, v.lucro, v.data_venda, v.observacao
        FROM vendas v
        WHERE v.id = %s AND {where_v}
    """, params)

    venda = cursor.fetchone()
    cursor.close()
    conn.close()

    if not venda:
        return jsonify({"ok": False, "mensagem": "Venda não encontrada."})

    arquivo = gerar_recibo_pdf("Comprovante de venda", [
        ("Venda", venda[0]),
        ("Produto", venda[1] or "-"),
        ("Cliente", venda[2] or "-"),
        ("Valor da venda", moeda(venda[3])),
        ("Custo", moeda(venda[4])),
        ("Lucro", moeda(venda[5])),
        ("Data", formatar_data_texto(venda[6])),
        ("Observação", venda[7] or "-"),
    ], f"recibo_venda_{venda_id}")

    return send_file(arquivo, as_attachment=True, download_name=f"recibo_venda_{venda_id}.pdf")


@app.route("/api/recibo/pagamento/<int:pagamento_id>", methods=["GET"])
def recibo_pagamento(pagamento_id):
    ver = exigir_login()
    if ver:
        return ver

    where_p, params_p = filtro_usuario_sql("p")
    params = [pagamento_id] + params_p

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT p.id, p.emprestimo_id, c.nome, p.valor_pago, p.tipo, p.data_pagamento, e.juros, e.total
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        JOIN clientes c ON c.id = e.cliente_id
        WHERE p.id = %s AND {where_p}
    """, params)

    pag = cursor.fetchone()
    cursor.close()
    conn.close()

    if not pag:
        return jsonify({"ok": False, "mensagem": "Pagamento não encontrado."})

    tipo = "Pagamento de juros" if str(pag[4]).lower() == "juros" else "Quitação total"
    lucro = float(pag[3] or 0) if str(pag[4]).lower() == "juros" else float(pag[6] or 0)

    arquivo = gerar_recibo_pdf("Comprovante de pagamento", [
        ("Pagamento", pag[0]),
        ("Empréstimo", pag[1]),
        ("Cliente", pag[2] or "-"),
        ("Tipo", tipo),
        ("Valor pago", moeda(pag[3])),
        ("Lucro considerado", moeda(lucro)),
        ("Data", formatar_data_texto(pag[5])),
    ], f"recibo_pagamento_{pagamento_id}")

    return send_file(arquivo, as_attachment=True, download_name=f"recibo_pagamento_{pagamento_id}.pdf")


# ---------------- RELATÓRIOS ----------------

@app.route("/api/relatorio-resumo", methods=["GET"])
def relatorio_resumo():
    return resumo()


@app.route("/api/gerar-pdf", methods=["GET"])
def gerar_pdf():
    try:
        if gerar_relatorio:
            arquivo = gerar_relatorio()
            return send_file(arquivo, as_attachment=True, download_name="relatorio.pdf")
        return jsonify({"ok": False, "mensagem": "Gerador de relatório não encontrado."})
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/gerar-pdf-cliente/<int:cliente_id>", methods=["GET"])
def gerar_pdf_cliente(cliente_id):
    try:
        if gerar_relatorio_cliente:
            arquivo = gerar_relatorio_cliente(cliente_id)
            return send_file(arquivo, as_attachment=True, download_name="relatorio_cliente.pdf")
        return jsonify({"ok": False, "mensagem": "Gerador de relatório do cliente não encontrado."})
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


# ---------------- ADMIN ----------------

@app.route("/api/admin/tabelas", methods=["GET"])
def listar_tabelas_admin():
    ver = exigir_admin()
    if ver:
        return ver

    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas = [item[0] for item in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({"ok": True, "tabelas": tabelas, "banco": caminho_banco()})
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/admin/sql", methods=["POST"])
def executar_sql_admin():
    ver = exigir_admin()
    if ver:
        return ver

    dados = request.get_json() or {}
    sql = (dados.get("sql") or "").strip()

    if not sql:
        return jsonify({"ok": False, "mensagem": "Digite um SQL."})

    sql_limpo = sql.strip().rstrip(";")
    sql_lower = sql_limpo.lower()

    bloqueados = ["drop database", "truncate", "grant ", "revoke ", "alter user", "create user"]
    for comando in bloqueados:
        if comando in sql_lower:
            return jsonify({"ok": False, "mensagem": f"Comando bloqueado por segurança: {comando}"})

    conn = conectar()
    cursor = conn.cursor()

    try:
        if sql_lower.startswith("select") or sql_lower.startswith("with"):
            cursor.execute(sql_limpo)
            linhas = cursor.fetchall()
            colunas = [desc[0] for desc in cursor.description] if cursor.description else []

            cursor.close()
            conn.close()
            registrar_log_admin("SQL_SELECT", sql_limpo, f"{len(linhas)} linha(s) retornadas")

            return jsonify({
                "ok": True,
                "tipo": "consulta",
                "colunas": colunas,
                "linhas": [list(linha) for linha in linhas],
                "total_linhas": len(linhas),
                "mensagem": f"Consulta executada com sucesso. {len(linhas)} linha(s)."
            })

        cursor.execute(sql_limpo)
        conn.commit()
        afetadas = cursor.rowcount
        cursor.close()
        conn.close()

        registrar_log_admin("SQL_COMANDO", sql_limpo, f"Linhas afetadas: {afetadas}")

        return jsonify({
            "ok": True,
            "tipo": "comando",
            "linhas_afetadas": afetadas,
            "mensagem": f"Comando executado com sucesso. Linhas afetadas: {afetadas}."
        })

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/admin/logs", methods=["GET"])
def listar_logs_admin():
    ver = exigir_admin()
    if ver:
        return ver

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, usuario, acao, sql_texto, detalhes, data_hora, ip
        FROM admin_logs
        ORDER BY id DESC
        LIMIT 100
    """)
    logs = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "logs": [{
        "id": item[0],
        "usuario": item[1],
        "acao": item[2],
        "sql_texto": item[3],
        "detalhes": item[4],
        "data_hora": item[5],
        "ip": item[6]
    } for item in logs]})


# ---------------- GRÁFICOS PROFISSIONAIS ----------------

@app.route("/api/grafico-financeiro", methods=["GET"])
def grafico_financeiro():
    ver = exigir_login()
    if ver:
        return ver

    where_v, params_v = filtro_usuario_sql("v")
    where_p, params_p = filtro_usuario_sql("p")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT TO_CHAR(TO_DATE(v.data_venda, 'DD/MM/YYYY'), 'MM/YYYY') AS mes,
               COALESCE(SUM(v.valor_venda), 0) AS total_vendido,
               COALESCE(SUM(v.lucro), 0) AS lucro_vendas
        FROM vendas v
        WHERE {where_v}
          AND v.data_venda ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(v.data_venda, 'DD/MM/YYYY') >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY mes
        ORDER BY MIN(TO_DATE(v.data_venda, 'DD/MM/YYYY'))
    """, params_v)
    vendas = cursor.fetchall()

    cursor.execute(f"""
        SELECT TO_CHAR(TO_DATE(p.data_pagamento, 'DD/MM/YYYY'), 'MM/YYYY') AS mes,
               COALESCE(SUM(p.valor_pago), 0) AS total_recebido,
               {lucro_emprestimos_sql()} AS lucro_emprestimos
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
        WHERE {where_p}
          AND p.data_pagamento ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
          AND TO_DATE(p.data_pagamento, 'DD/MM/YYYY') >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY mes
        ORDER BY MIN(TO_DATE(p.data_pagamento, 'DD/MM/YYYY'))
    """, params_p)
    pagamentos = cursor.fetchall()

    cursor.close()
    conn.close()

    meses = {}
    for mes, total_vendido, lucro_vendas in vendas:
        meses.setdefault(mes, {"mes": mes, "vendas": 0, "recebido_emprestimos": 0, "lucro_vendas": 0, "lucro_emprestimos": 0})
        meses[mes]["vendas"] = float(total_vendido or 0)
        meses[mes]["lucro_vendas"] = float(lucro_vendas or 0)

    for mes, total_recebido, lucro_emprestimos in pagamentos:
        meses.setdefault(mes, {"mes": mes, "vendas": 0, "recebido_emprestimos": 0, "lucro_vendas": 0, "lucro_emprestimos": 0})
        meses[mes]["recebido_emprestimos"] = float(total_recebido or 0)
        meses[mes]["lucro_emprestimos"] = float(lucro_emprestimos or 0)

    dados = list(meses.values())
    for item in dados:
        item["lucro_total"] = round(item["lucro_vendas"] + item["lucro_emprestimos"], 2)
        item["entrada_total"] = round(item["vendas"] + item["recebido_emprestimos"], 2)

    return jsonify(dados)


# ---------------- RECUPERAÇÃO DE SENHA ----------------

@app.route("/api/recuperar-senha", methods=["POST"])
def recuperar_senha():
    dados = request.get_json() or {}
    usuario = (dados.get("usuario") or "").strip()

    if not usuario:
        return jsonify({"ok": False, "mensagem": "Informe o usuário para recuperação."})

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE LOWER(usuario) = LOWER(%s)", (usuario,))
    existe = cursor.fetchone()
    cursor.close()
    conn.close()

    if not existe:
        return jsonify({"ok": False, "mensagem": "Usuário não encontrado."})

    return jsonify({
        "ok": True,
        "mensagem": "Solicitação registrada. Peça ao administrador para redefinir sua senha no Painel Admin."
    })


# ---------------- PAINEL ADMIN COMPLETO ----------------

@app.route("/api/admin/usuarios", methods=["GET"])
def admin_listar_usuarios():
    ver = exigir_admin()
    if ver:
        return ver

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.usuario, COALESCE(u.ativo, TRUE), COALESCE(u.data_criacao, ''), COALESCE(u.ultimo_login, ''),
               (SELECT COUNT(*) FROM clientes c WHERE c.usuario_id = u.id) AS total_clientes,
               (SELECT COUNT(*) FROM emprestimos e WHERE e.usuario_id = u.id) AS total_emprestimos,
               (SELECT COUNT(*) FROM vendas v WHERE v.usuario_id = u.id) AS total_vendas
        FROM usuarios u
        ORDER BY u.id ASC
    """)
    usuarios = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({"ok": True, "usuarios": [{
        "id": item[0],
        "usuario": item[1],
        "ativo": bool(item[2]),
        "data_criacao": item[3],
        "ultimo_login": item[4],
        "total_clientes": item[5],
        "total_emprestimos": item[6],
        "total_vendas": item[7]
    } for item in usuarios]})


@app.route("/api/admin/usuarios/<int:usuario_id>/status", methods=["POST"])
def admin_alterar_status_usuario(usuario_id):
    ver = exigir_admin()
    if ver:
        return ver

    dados = request.get_json() or {}
    ativo = bool(dados.get("ativo"))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET ativo = %s WHERE id = %s", (ativo, usuario_id))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log_admin("ALTERAR_STATUS_USUARIO", "", f"Usuário {usuario_id} ativo={ativo}")
    return jsonify({"ok": True, "mensagem": "Status do usuário atualizado."})


@app.route("/api/admin/usuarios/<int:usuario_id>/senha", methods=["POST"])
def admin_redefinir_senha(usuario_id):
    ver = exigir_admin()
    if ver:
        return ver

    dados = request.get_json() or {}
    nova_senha = (dados.get("nova_senha") or "").strip()

    if len(nova_senha) < 4:
        return jsonify({"ok": False, "mensagem": "A nova senha deve ter pelo menos 4 caracteres."})

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (nova_senha, usuario_id))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log_admin("REDEFINIR_SENHA", "", f"Senha redefinida para usuário {usuario_id}")
    return jsonify({"ok": True, "mensagem": "Senha redefinida com sucesso."})


# ---------------- BACKUP AUTOMÁTICO / EXPORTAÇÃO ----------------

@app.route("/api/admin/backup-json", methods=["GET"])
def admin_backup_json():
    ver = exigir_admin()
    if ver:
        return ver

    tabelas = ["usuarios", "clientes", "emprestimos", "pagamentos", "vendas", "admin_logs"]
    backup = {
        "sistema": "FinancePro",
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "tabelas": {}
    }

    conn = conectar()
    cursor = conn.cursor()

    for tabela in tabelas:
        try:
            cursor.execute(f"SELECT * FROM {tabela}")
            colunas = [desc[0] for desc in cursor.description]
            linhas = cursor.fetchall()
            backup["tabelas"][tabela] = [dict(zip(colunas, [str(v) if v is not None else None for v in linha])) for linha in linhas]
        except Exception as e:
            backup["tabelas"][tabela] = {"erro": str(e)}

    cursor.close()
    conn.close()

    registrar_backup_log("manual", "Backup JSON exportado pelo administrador")

    import json
    conteudo = json.dumps(backup, ensure_ascii=False, indent=2)
    nome = f"backup_financepro_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"

    resposta = app.response_class(conteudo, mimetype="application/json")
    resposta.headers["Content-Disposition"] = f"attachment; filename={nome}"
    return resposta


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
