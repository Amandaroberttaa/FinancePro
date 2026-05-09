import os
import sys
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, send_file, session

from banco import conectar, criar_tabelas, caminho_banco
from relatorio import gerar_relatorio, gerar_relatorio_cliente


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

criar_tabelas()

ADMIN_USUARIO = "ADM"
ADMIN_SENHA = "A1D2M3"


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


def acesso_local():
    ip = request.remote_addr or ""
    return ip in ("127.0.0.1", "::1", "localhost")


def usuario_logado():
    return session.get("usuario")


def usuario_e_admin():
    return bool(session.get("is_admin"))


def exigir_admin():
    if not usuario_logado():
        return jsonify({"ok": False, "mensagem": "Faça login primeiro."}), 401

    if not usuario_e_admin():
        return jsonify({"ok": False, "mensagem": "Acesso restrito ao administrador."}), 403

    if not acesso_local():
        return jsonify({"ok": False, "mensagem": "Acesso admin permitido apenas localmente."}), 403

    return None


def criar_tabelas_admin_log():
    conn = conectar()
    cursor = conn.cursor()

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

    conn.commit()
    cursor.close()
    conn.close()


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


criar_tabelas_admin_log()


# ---------------- FRONT ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- SESSÃO ----------------

@app.route("/api/sessao", methods=["GET"])
def obter_sessao():
    return jsonify({
        "logado": bool(usuario_logado()),
        "usuario": usuario_logado() or "",
        "is_admin": usuario_e_admin()
    })


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


# ---------------- LOGIN ----------------

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

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total = cursor.fetchone()[0] or 0

    if total > 0:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Já existe um usuário cadastrado."})

    try:
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha)
            VALUES (%s, %s)
        """, (usuario, senha))

        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": str(e)})

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Usuário criado com sucesso."})


@app.route("/api/login", methods=["POST"])
def login():
    dados = request.get_json() or {}
    usuario = (dados.get("usuario") or "").strip()
    senha = (dados.get("senha") or "").strip()

    if usuario.upper() == ADMIN_USUARIO and senha == ADMIN_SENHA:
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
        SELECT id, usuario
        FROM usuarios
        WHERE usuario = %s AND senha = %s
    """, (usuario, senha))

    linha = cursor.fetchone()

    cursor.close()
    conn.close()

    if not linha:
        return jsonify({"ok": False, "mensagem": "Usuário ou senha inválidos."})

    session["usuario"] = linha[1]
    session["is_admin"] = False

    return jsonify({
        "ok": True,
        "mensagem": "Login realizado com sucesso.",
        "is_admin": False,
        "usuario": linha[1]
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    if usuario_logado():
        registrar_log_admin("LOGOUT", "", "Logout do sistema")

    session.clear()
    return jsonify({"ok": True})


# ---------------- CONFIGURAÇÕES ----------------

@app.route("/api/obter-modo-taxa", methods=["GET"])
def obter_modo_taxa():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT valor
        FROM configuracoes
        WHERE chave = 'modo_taxa'
    """)

    linha = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({"modo_taxa": (linha[0] if linha else "ambos")})


# ---------------- RESUMO ----------------

@app.route("/api/resumo", methods=["GET"])
def resumo():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM emprestimos")
    total_emprestado = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
    """)
    total_em_aberto = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(CASE
            WHEN p.tipo = 'juros' THEN p.valor_pago
            WHEN p.tipo = 'total' THEN e.juros
            ELSE 0
        END), 0)
        FROM pagamentos p
        JOIN emprestimos e ON e.id = p.emprestimo_id
    """)
    lucro_total = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT cliente_id)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
          AND TO_DATE(data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """)
    clientes_em_atraso = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    return jsonify({
        "total_emprestado": round(float(total_emprestado), 2),
        "total_em_aberto": round(float(total_em_aberto), 2),
        "lucro_total": round(float(lucro_total), 2),
        "clientes_em_atraso": clientes_em_atraso,
        "total_clientes": total_clientes
    })


# ---------------- GRÁFICO ----------------

@app.route("/api/dados-grafico-dashboard", methods=["GET"])
def dados_grafico_dashboard():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'quitado'
    """)
    quitado = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
          AND TO_DATE(data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """)
    atraso = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM emprestimos WHERE taxa = 20")
    taxa20 = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM emprestimos WHERE taxa = 30")
    taxa30 = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    return jsonify([
        {"nome": "Quitado", "valor": quitado},
        {"nome": "Atraso", "valor": atraso},
        {"nome": "Empréstimo 20%", "valor": taxa20},
        {"nome": "Empréstimo 30%", "valor": taxa30}
    ])


# ---------------- CLIENTES ----------------

@app.route("/api/clientes", methods=["GET"])
def lista_clientes():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, cpf, endereco, data_contratacao, status
        FROM clientes
        ORDER BY id ASC
    """)

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([
        {
            "id": item[0],
            "nome": item[1],
            "telefone": item[2] or "",
            "cpf": item[3] or "",
            "endereco": item[4] or "",
            "data_contratacao": formatar_data_texto(item[5]),
            "status": item[6] or "Aberto"
        }
        for item in dados
    ])


@app.route("/api/clientes", methods=["POST"])
def cadastrar_cliente():
    dados = request.get_json() or {}

    nome = (dados.get("nome") or "").strip()
    telefone = (dados.get("telefone") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    data_contratacao = (dados.get("data_contratacao") or "").strip()

    if not nome:
        return jsonify({"ok": False, "mensagem": "Nome é obrigatório."})

    if not data_contratacao:
        data_contratacao = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO clientes (nome, telefone, cpf, endereco, data_contratacao, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (nome, telefone, cpf, endereco, data_contratacao, "Aberto"))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/clientes/<int:cliente_id>", methods=["GET"])
def obter_cliente(cliente_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, cpf, endereco, data_contratacao, status
        FROM clientes
        WHERE id = %s
    """, (cliente_id,))

    cliente = cursor.fetchone()

    cursor.close()
    conn.close()

    if not cliente:
        return jsonify({"ok": False, "mensagem": "Cliente não encontrado."})

    return jsonify({
        "ok": True,
        "cliente": {
            "id": cliente[0],
            "nome": cliente[1] or "",
            "telefone": cliente[2] or "",
            "cpf": cliente[3] or "",
            "endereco": cliente[4] or "",
            "data_contratacao": cliente[5] or "",
            "status": cliente[6] or "Aberto"
        }
    })


@app.route("/api/clientes/<int:cliente_id>", methods=["PUT"])
def editar_cliente(cliente_id):
    dados = request.get_json() or {}

    nome = (dados.get("nome") or "").strip()
    telefone = (dados.get("telefone") or "").strip()
    cpf = (dados.get("cpf") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    data_contratacao = (dados.get("data_contratacao") or "").strip()
    status = (dados.get("status") or "Aberto").strip()

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE clientes
        SET nome = %s,
            telefone = %s,
            cpf = %s,
            endereco = %s,
            data_contratacao = %s,
            status = %s
        WHERE id = %s
    """, (nome, telefone, cpf, endereco, data_contratacao, status, cliente_id))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Cliente atualizado com sucesso."})


# ---------------- EMPRÉSTIMOS ----------------

@app.route("/api/emprestimos", methods=["GET"])
def lista_emprestimos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT emprestimos.id,
               clientes.nome,
               clientes.id,
               emprestimos.valor,
               emprestimos.taxa,
               emprestimos.juros,
               emprestimos.total,
               emprestimos.data_inicio,
               emprestimos.data_vencimento,
               emprestimos.status
        FROM emprestimos
        JOIN clientes ON emprestimos.cliente_id = clientes.id
        ORDER BY emprestimos.id ASC
    """)

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([
        {
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
        }
        for item in dados
    ])


@app.route("/api/emprestimos", methods=["POST"])
def criar_emprestimo():
    dados = request.get_json() or {}

    try:
        cliente_id = int(dados.get("cliente_id"))
        valor = float(dados.get("valor"))
        taxa = float(dados.get("taxa"))
    except Exception:
        return jsonify({"ok": False, "mensagem": "Dados inválidos."})

    data_inicio = (dados.get("data_inicio") or "").strip()

    if not data_inicio:
        data_inicio = datetime.now().strftime("%d/%m/%Y")

    try:
        data_obj = datetime.strptime(data_inicio, "%d/%m/%Y")
    except Exception:
        return jsonify({"ok": False, "mensagem": "Data inválida. Use dd/mm/aaaa."})

    juros = round(valor * (taxa / 100), 2)
    total = round(valor + juros, 2)
    vencimento = (data_obj + timedelta(days=30)).strftime("%d/%m/%Y")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO emprestimos (
            cliente_id, valor, taxa, juros, total,
            data_inicio, data_vencimento, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        cliente_id, valor, taxa, juros, total,
        data_inicio, vencimento, "Aberto"
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/emprestimos/<int:emprestimo_id>/quitar", methods=["POST"])
def quitar_emprestimo(emprestimo_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT total, status
        FROM emprestimos
        WHERE id = %s
    """, (emprestimo_id,))

    linha = cursor.fetchone()

    if not linha:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

    status = (linha[1] or "").strip().lower()

    if status == "quitado":
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Esse empréstimo já está quitado."})

    total = linha[0] or 0
    hoje = datetime.now().strftime("%d/%m/%Y")

    cursor.execute("""
        INSERT INTO pagamentos (emprestimo_id, valor_pago, tipo, data_pagamento)
        VALUES (%s, %s, %s, %s)
    """, (emprestimo_id, total, "total", hoje))

    cursor.execute("""
        UPDATE emprestimos
        SET status = 'Quitado'
        WHERE id = %s
    """, (emprestimo_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Pagamento total registrado com sucesso."})


@app.route("/api/emprestimos/<int:emprestimo_id>/pagar-juros", methods=["POST"])
def pagar_somente_juros(emprestimo_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT valor, taxa, juros, data_vencimento, status
        FROM emprestimos
        WHERE id = %s
    """, (emprestimo_id,))

    dado = cursor.fetchone()

    if not dado:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

    status = (dado[4] or "").strip().lower()

    if status == "quitado":
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Empréstimo já está quitado."})

    valor = float(dado[0] or 0)
    taxa = float(dado[1] or 0)
    juros = float(dado[2] or 0)
    hoje = datetime.now().strftime("%d/%m/%Y")

    cursor.execute("""
        INSERT INTO pagamentos (emprestimo_id, valor_pago, tipo, data_pagamento)
        VALUES (%s, %s, %s, %s)
    """, (emprestimo_id, juros, "juros", hoje))

    try:
        vencimento_atual = datetime.strptime(dado[3], "%d/%m/%Y")
    except Exception:
        vencimento_atual = datetime.now()

    novo_vencimento = (vencimento_atual + timedelta(days=30)).strftime("%d/%m/%Y")
    novo_juros = round(valor * (taxa / 100), 2)
    novo_total = round(valor + novo_juros, 2)

    cursor.execute("""
        UPDATE emprestimos
        SET juros = %s,
            total = %s,
            data_vencimento = %s,
            status = 'Aberto'
        WHERE id = %s
    """, (novo_juros, novo_total, novo_vencimento, emprestimo_id))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Pagamento de juros registrado com sucesso."})


@app.route("/api/emprestimos/<int:emprestimo_id>/trocar-taxa", methods=["POST"])
def alterar_taxa_emprestimo(emprestimo_id):
    dados = request.get_json() or {}

    try:
        nova_taxa = float(dados.get("nova_taxa"))
    except Exception:
        return jsonify({"ok": False, "mensagem": "Taxa inválida."})

    if nova_taxa not in (20, 30):
        return jsonify({"ok": False, "mensagem": "A taxa deve ser 20 ou 30."})

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT valor, status
        FROM emprestimos
        WHERE id = %s
    """, (emprestimo_id,))

    dado = cursor.fetchone()

    if not dado:
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Empréstimo não encontrado."})

    status = (dado[1] or "").strip().lower()

    if status == "quitado":
        cursor.close()
        conn.close()
        return jsonify({"ok": False, "mensagem": "Não é possível alterar taxa de empréstimo quitado."})

    valor = float(dado[0] or 0)
    novo_juros = round(valor * (nova_taxa / 100), 2)
    novo_total = round(valor + novo_juros, 2)

    cursor.execute("""
        UPDATE emprestimos
        SET taxa = %s,
            juros = %s,
            total = %s
        WHERE id = %s
    """, (nova_taxa, novo_juros, novo_total, emprestimo_id))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "mensagem": "Taxa alterada com sucesso."})


# ---------------- RELATÓRIOS ----------------

@app.route("/api/relatorio-resumo", methods=["GET"])
def relatorio_resumo():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(valor_pago), 0) FROM pagamentos")
    total_recebido = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM pagamentos")
    total_pagamentos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM emprestimos
        WHERE LOWER(TRIM(status)) = 'aberto'
          AND TO_DATE(data_vencimento, 'DD/MM/YYYY') < CURRENT_DATE
    """)
    total_atraso = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM emprestimos")
    total_emprestado = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(juros), 0) FROM emprestimos WHERE taxa = 20")
    lucro_20 = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(juros), 0) FROM emprestimos WHERE taxa = 30")
    lucro_30 = cursor.fetchone()[0] or 0

    cursor.close()
    conn.close()

    return jsonify({
        "total_recebido": round(float(total_recebido), 2),
        "total_pagamentos": total_pagamentos,
        "total_atraso": round(float(total_atraso), 2),
        "total_emprestado": round(float(total_emprestado), 2),
        "lucro_20": round(float(lucro_20), 2),
        "lucro_30": round(float(lucro_30), 2),
        "lucro_semanal": 0,
        "lucro_mensal": 0
    })


@app.route("/api/gerar-pdf", methods=["GET"])
def gerar_pdf():
    try:
        arquivo = gerar_relatorio()

        return send_file(
            arquivo,
            as_attachment=True,
            download_name="relatorio.pdf"
        )
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/gerar-pdf-cliente/<int:cliente_id>", methods=["GET"])
def gerar_pdf_cliente(cliente_id):
    try:
        arquivo = gerar_relatorio_cliente(cliente_id)

        return send_file(
            arquivo,
            as_attachment=True,
            download_name="relatorio_cliente.pdf"
        )
    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


# ---------------- ADMIN SQL ----------------

@app.route("/api/admin/tabelas", methods=["GET"])
def listar_tabelas_admin():
    try:
        verificacao = exigir_admin()
        if verificacao:
            return verificacao

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        tabelas = [item[0] for item in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({
            "ok": True,
            "tabelas": tabelas,
            "banco": caminho_banco(),
            "database_list": []
        })

    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/admin/sql", methods=["POST"])
def executar_sql_admin():
    try:
        verificacao = exigir_admin()
        if verificacao:
            return verificacao

        dados = request.get_json() or {}
        sql = (dados.get("sql") or "").strip()

        if not sql:
            return jsonify({"ok": False, "mensagem": "Digite um SQL."})

        sql_limpo = sql.strip().rstrip(";")
        sql_lower = sql_limpo.lower()

        comandos_bloqueados = [
            "drop database",
            "attach database",
            "detach database",
            "vacuum into",
            "pragma key",
        ]

        for comando in comandos_bloqueados:
            if comando in sql_lower:
                return jsonify({
                    "ok": False,
                    "mensagem": f"Comando bloqueado por segurança: {comando}"
                })

        conn = conectar()
        cursor = conn.cursor()

        if sql_lower.startswith("select") or sql_lower.startswith("with"):
            cursor.execute(sql_limpo)
            linhas = cursor.fetchall()

            colunas = []
            if cursor.description:
                colunas = [col[0] for col in cursor.description]

            resultado_linhas = [list(linha) for linha in linhas]

            cursor.close()
            conn.close()

            registrar_log_admin(
                "SQL_SELECT",
                sql_limpo,
                f"{len(resultado_linhas)} linha(s) retornadas"
            )

            return jsonify({
                "ok": True,
                "tipo": "consulta",
                "colunas": colunas,
                "linhas": resultado_linhas,
                "total_linhas": len(resultado_linhas),
                "mensagem": f"Consulta executada com sucesso. {len(resultado_linhas)} linha(s)."
            })

        cursor.execute(sql_limpo)
        conn.commit()

        afetadas = cursor.rowcount

        cursor.close()
        conn.close()

        registrar_log_admin(
            "SQL_COMANDO",
            sql_limpo,
            f"Linhas afetadas: {afetadas}. Backup: Supabase"
        )

        return jsonify({
            "ok": True,
            "tipo": "comando",
            "linhas_afetadas": afetadas,
            "backup": "",
            "mensagem": f"Comando executado com sucesso. Linhas afetadas: {afetadas}."
        })

    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


@app.route("/api/admin/logs", methods=["GET"])
def listar_logs_admin():
    try:
        verificacao = exigir_admin()
        if verificacao:
            return verificacao

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

        return jsonify({
            "ok": True,
            "logs": [
                {
                    "id": item[0],
                    "usuario": item[1],
                    "acao": item[2],
                    "sql_texto": item[3],
                    "detalhes": item[4],
                    "data_hora": item[5],
                    "ip": item[6]
                }
                for item in logs
            ]
        })

    except Exception as e:
        return jsonify({"ok": False, "mensagem": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)