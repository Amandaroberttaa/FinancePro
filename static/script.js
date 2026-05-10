let graficoPizza = null;

function formatarMoeda(valor) {
  return Number(valor || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL"
  });
}

function escaparHtml(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function apiGet(url) {
  const resp = await fetch(url, { credentials: "same-origin" });
  return await resp.json();
}

async function apiPost(url, dados = {}) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(dados)
  });

  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return await resp.json();
  return resp;
}

async function apiPut(url, dados = {}) {
  const resp = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(dados)
  });
  return await resp.json();
}

async function apiDelete(url) {
  const resp = await fetch(url, {
    method: "DELETE",
    credentials: "same-origin"
  });
  return await resp.json();
}

async function trocarTela(nomeTela) {
  document.querySelectorAll(".screen").forEach(screen => screen.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));

  const tela = document.getElementById(`screen-${nomeTela}`);
  const botao = document.querySelector(`[data-screen="${nomeTela}"]`);

  if (tela) tela.classList.add("active");
  if (botao && botao.style.display !== "none") botao.classList.add("active");

  if (nomeTela === "dashboard") await carregarDashboard();
  if (nomeTela === "clientes") await carregarClientes();
  if (nomeTela === "emprestimos") {
    await carregarClientes();
    await carregarEmprestimos();
  }
  if (nomeTela === "vendas") {
    await carregarVendas();
    await carregarResumoVendas();
  }
  if (nomeTela === "relatorios") await carregarRelatorios();
  if (nomeTela === "admin") await carregarLogsAdmin();
}

function classeStatus(status) {
  const valor = String(status || "").toLowerCase();
  if (valor === "aberto") return "status-aberto";
  if (valor === "quitado") return "status-quitado";
  return "status-outro";
}

function atualizarInfoSessao(usuario, isAdmin) {
  const adminNav = document.getElementById("navAdmin");
  const adminBadge = document.getElementById("adminBadge");
  const userSessionCard = document.getElementById("userSessionCard");
  const userSessionName = document.getElementById("userSessionName");
  const adminScreen = document.getElementById("screen-admin");

  if (adminNav) adminNav.style.display = isAdmin ? "block" : "none";
  if (adminBadge) adminBadge.style.display = isAdmin ? "flex" : "none";
  if (userSessionCard) userSessionCard.style.display = usuario ? "flex" : "none";
  if (userSessionName) userSessionName.textContent = usuario || "-";

  if (!isAdmin && adminScreen && adminScreen.classList.contains("active")) {
    trocarTela("dashboard");
  }
}

function limparInfoSessao() {
  atualizarInfoSessao("", false);
}

async function verificarLoginInicial() {
  const resposta = await apiGet("/api/verificar-tem-usuario");
  const sessao = await apiGet("/api/sessao");

  const telaInicial = document.getElementById("screen-inicial");
  const telaLogin = document.getElementById("screen-login");
  const telaCriar = document.getElementById("screen-criar-usuario");
  const appLayout = document.getElementById("appLayout");

  if (sessao.logado) {
    if (telaInicial) telaInicial.style.display = "none";
    if (telaLogin) telaLogin.style.display = "none";
    if (telaCriar) telaCriar.style.display = "none";
    if (appLayout) appLayout.style.display = "flex";

    atualizarInfoSessao(sessao.usuario || "", !!sessao.is_admin);
    await carregarDashboard();
    return;
  }

  limparInfoSessao();

  if (telaInicial) telaInicial.style.display = "flex";

  if (resposta.tem_usuario) {
    if (telaCriar) telaCriar.style.display = "none";
    if (telaLogin) telaLogin.style.display = "none";
    if (appLayout) appLayout.style.display = "none";
  } else {
    if (telaInicial) telaInicial.style.display = "none";
    if (telaCriar) telaCriar.style.display = "flex";
    if (telaLogin) telaLogin.style.display = "none";
    if (appLayout) appLayout.style.display = "none";
  }
}

async function criarUsuarioInicial() {
  const usuario = document.getElementById("novoUsuario")?.value || "";
  const senha = document.getElementById("novaSenha")?.value || "";

  if (!usuario.trim() || !senha.trim()) {
    alert("Usuário e senha são obrigatórios.");
    return;
  }

  const resp = await apiPost("/api/criar-usuario", { usuario, senha });
  alert(resp.mensagem);

  if (resp.ok) {
    document.getElementById("formCriarUsuario")?.reset();
    voltarInicio();
  }
}

async function fazerLogin() {
  const usuario = document.getElementById("loginUsuario")?.value || "";
  const senha = document.getElementById("loginSenha")?.value || "";

  const resposta = await apiPost("/api/login", { usuario, senha });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  document.getElementById("screen-inicial").style.display = "none";
  document.getElementById("screen-login").style.display = "none";
  document.getElementById("screen-criar-usuario").style.display = "none";
  document.getElementById("appLayout").style.display = "flex";

  document.getElementById("formLogin")?.reset();

  atualizarInfoSessao(resposta.usuario || "", !!resposta.is_admin);
  await carregarDashboard();
}

async function sairSistema() {
  await apiPost("/api/logout");
  document.getElementById("appLayout").style.display = "none";
  document.getElementById("screen-criar-usuario").style.display = "none";
  document.getElementById("screen-login").style.display = "flex";
  limparInfoSessao();
}

async function carregarResumo() {
  const dados = await apiGet("/api/resumo");

  if (document.getElementById("totalEmprestado")) document.getElementById("totalEmprestado").innerText = formatarMoeda(dados.total_emprestado);
  if (document.getElementById("totalAberto")) document.getElementById("totalAberto").innerText = formatarMoeda(dados.total_em_aberto);
  if (document.getElementById("lucroTotal")) document.getElementById("lucroTotal").innerText = formatarMoeda(dados.lucro_emprestimos || dados.lucro_total);
  if (document.getElementById("clientesEmAtraso")) document.getElementById("clientesEmAtraso").innerText = dados.clientes_em_atraso;
  if (document.getElementById("totalClientes")) document.getElementById("totalClientes").innerText = dados.total_clientes || 0;

  if (document.getElementById("dashTotalVendas")) document.getElementById("dashTotalVendas").innerText = formatarMoeda(dados.total_vendas);
  if (document.getElementById("dashLucroVendas")) document.getElementById("dashLucroVendas").innerText = formatarMoeda(dados.lucro_vendas);
  if (document.getElementById("dashLucroGeral")) document.getElementById("dashLucroGeral").innerText = formatarMoeda(dados.lucro_geral);
}

async function carregarGraficoStatus() {
  const canvas = document.getElementById("graficoStatus");
  if (!canvas || typeof Chart === "undefined") return;

  const dados = await apiGet("/api/dados-grafico-dashboard");

  const labels = dados.map(item => item.nome);
  const valores = dados.map(item => item.valor);

  if (graficoPizza) graficoPizza.destroy();

  graficoPizza = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: valores,
        backgroundColor: ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6"],
        borderWidth: 0
      }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

async function carregarDashboard() {
  await carregarResumo();
  await carregarGraficoStatus();
}

async function carregarClientes() {
  const clientes = await apiGet("/api/clientes");
  const lista = document.getElementById("listaClientes");
  const select = document.getElementById("emprestimoCliente");
  const totalClientesCadastro = document.getElementById("totalClientesCadastro");

  if (lista) lista.innerHTML = "";
  if (select) select.innerHTML = `<option value="">Selecione o cliente</option>`;
  if (totalClientesCadastro) totalClientesCadastro.innerText = clientes.length;

  if (!clientes.length && lista) lista.innerHTML = "<p>Nenhum cliente cadastrado.</p>";

  clientes.forEach(cliente => {
    if (lista) {
      const item = document.createElement("div");
      item.className = "client-item";
      item.innerHTML = `
        <div class="client-info">
          <strong>${cliente.id} - ${escaparHtml(cliente.nome)}</strong>
          <span>Telefone: ${escaparHtml(cliente.telefone || "Sem telefone")}</span>
          <span>CPF: ${escaparHtml(cliente.cpf || "Não informado")}</span>
          <span>Endereço: ${escaparHtml(cliente.endereco || "Não informado")}</span>
          <span>Contratação: ${escaparHtml(cliente.data_contratacao || "-")}</span>
          <span>Status: ${escaparHtml(cliente.status || "Aberto")}</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px; align-items:flex-end;">
          <button class="action-btn secondary" onclick="abrirEdicaoCliente(${cliente.id})">Editar</button>
          <button class="action-btn warning" onclick="baixarPdfCliente(${cliente.id})">PDF cliente</button>
        </div>
      `;
      lista.appendChild(item);
    }

    if (select) {
      const option = document.createElement("option");
      option.value = cliente.id;
      option.textContent = `${cliente.id} - ${cliente.nome}`;
      select.appendChild(option);
    }
  });
}

async function adicionarCliente() {
  const nome = document.getElementById("novoNome")?.value || "";
  const telefone = document.getElementById("novoTelefone")?.value || "";
  const cpf = document.getElementById("novoCpf")?.value || "";
  const endereco = document.getElementById("novoEndereco")?.value || "";
  const data_contratacao = document.getElementById("novaDataContratacao")?.value || "";

  const resposta = await apiPost("/api/clientes", { nome, telefone, cpf, endereco, data_contratacao });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  document.getElementById("novoNome").value = "";
  document.getElementById("novoTelefone").value = "";
  document.getElementById("novoCpf").value = "";
  document.getElementById("novoEndereco").value = "";
  document.getElementById("novaDataContratacao").value = "";

  await carregarClientes();
  await carregarDashboard();
}

async function abrirEdicaoCliente(clienteId) {
  const resposta = await apiGet(`/api/clientes/${clienteId}`);

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  const c = resposta.cliente;

  document.getElementById("painelEditarCliente").style.display = "block";
  document.getElementById("editarClienteId").value = c.id;
  document.getElementById("editarNome").value = c.nome || "";
  document.getElementById("editarTelefone").value = c.telefone || "";
  document.getElementById("editarCpf").value = c.cpf || "";
  document.getElementById("editarEndereco").value = c.endereco || "";
  document.getElementById("editarDataContratacao").value = c.data_contratacao || "";
  document.getElementById("editarStatus").value = c.status || "Aberto";
}

async function salvarEdicaoCliente() {
  const clienteId = document.getElementById("editarClienteId").value;
  const nome = document.getElementById("editarNome").value;
  const telefone = document.getElementById("editarTelefone").value;
  const cpf = document.getElementById("editarCpf").value;
  const endereco = document.getElementById("editarEndereco").value;
  const data_contratacao = document.getElementById("editarDataContratacao").value;
  const status = document.getElementById("editarStatus").value;

  const resposta = await apiPut(`/api/clientes/${clienteId}`, {
    nome, telefone, cpf, endereco, data_contratacao, status
  });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  alert(resposta.mensagem);
  document.getElementById("painelEditarCliente").style.display = "none";
  await carregarClientes();
  await carregarDashboard();
}

function baixarPdfCliente(clienteId) {
  window.open(`/api/gerar-pdf-cliente/${clienteId}`, "_blank");
}

async function carregarEmprestimos() {
  const emprestimos = await apiGet("/api/emprestimos");
  const tabela = document.getElementById("tabelaEmprestimos");
  if (!tabela) return;

  tabela.innerHTML = "";

  if (!emprestimos.length) {
    tabela.innerHTML = `<tr><td colspan="10">Nenhum empréstimo aberto.</td></tr>`;
    return;
  }

  emprestimos.forEach(item => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${escaparHtml(item.cliente)}</td>
      <td>${formatarMoeda(item.valor)}</td>
      <td>${item.taxa}%</td>
      <td>${formatarMoeda(item.juros)}</td>
      <td>${formatarMoeda(item.total)}</td>
      <td>${item.data_contratacao || "-"}</td>
      <td>${item.vencimento || "-"}</td>
      <td><span class="status-tag ${classeStatus(item.status)}">${item.status}</span></td>
      <td>
        <button class="action-btn" onclick="confirmarQuitado(${item.id})">Quitar</button>
        <button class="action-btn secondary" onclick="confirmarJuros(${item.id})">Pagar juros</button>
        <button class="action-btn warning" onclick="alterarTaxaEmprestimo(${item.id}, ${item.taxa})">
          ${Number(item.taxa) === 20 ? "Trocar p/ 30%" : "Trocar p/ 20%"}
        </button>
      </td>
    `;
    tabela.appendChild(tr);
  });
}

async function adicionarEmprestimo() {
  const cliente_id = document.getElementById("emprestimoCliente")?.value || "";
  const valor = document.getElementById("emprestimoValor")?.value || "";
  const data_inicio = document.getElementById("emprestimoData")?.value || "";
  const taxa = document.getElementById("emprestimoTaxa")?.value || "30";

  const resposta = await apiPost("/api/emprestimos", { cliente_id, valor, data_inicio, taxa });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  document.getElementById("emprestimoCliente").value = "";
  document.getElementById("emprestimoValor").value = "";
  document.getElementById("emprestimoData").value = "";
  document.getElementById("emprestimoTaxa").value = "30";

  await carregarEmprestimos();
  await carregarDashboard();
  await carregarRelatorios();
}

async function confirmarQuitado(id) {
  const ok = confirm("Confirmar pagamento total?");
  if (!ok) return;

  const resposta = await apiPost(`/api/emprestimos/${id}/quitar`);

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  alert(resposta.mensagem);
  await carregarEmprestimos();
  await carregarDashboard();
  await carregarRelatorios();
}

async function confirmarJuros(id) {
  const ok = confirm("Confirmar pagamento somente dos juros?");
  if (!ok) return;

  const resposta = await apiPost(`/api/emprestimos/${id}/pagar-juros`);

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  alert(resposta.mensagem);
  await carregarEmprestimos();
  await carregarDashboard();
  await carregarRelatorios();
}

async function alterarTaxaEmprestimo(id, taxaAtual) {
  const novaTaxa = Number(taxaAtual) === 20 ? 30 : 20;

  const ok = confirm(`Deseja trocar a taxa para ${novaTaxa}%?`);
  if (!ok) return;

  const resposta = await apiPost(`/api/emprestimos/${id}/trocar-taxa`, { nova_taxa: novaTaxa });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  alert(resposta.mensagem);
  await carregarEmprestimos();
  await carregarDashboard();
  await carregarRelatorios();
}

async function carregarVendas() {
  const vendas = await apiGet("/api/vendas");
  const tabela = document.getElementById("tabelaVendas");
  if (!tabela) return;

  tabela.innerHTML = "";

  if (!vendas.length) {
    tabela.innerHTML = `<tr><td colspan="9">Nenhuma venda registrada.</td></tr>`;
    return;
  }

  vendas.forEach(venda => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${venda.id}</td>
      <td>${escaparHtml(venda.produto)}</td>
      <td>${escaparHtml(venda.cliente || "-")}</td>
      <td>${formatarMoeda(venda.valor_venda)}</td>
      <td>${formatarMoeda(venda.valor_custo)}</td>
      <td>${formatarMoeda(venda.lucro)}</td>
      <td>${escaparHtml(venda.data_venda || "-")}</td>
      <td>${escaparHtml(venda.observacao || "-")}</td>
      <td>
        <button class="action-btn warning" onclick="excluirVenda(${venda.id})">Excluir</button>
      </td>
    `;
    tabela.appendChild(tr);
  });
}

async function carregarResumoVendas() {
  const rel = await apiGet("/api/relatorio-resumo");

  if (document.getElementById("vendasTotalVendido")) {
    document.getElementById("vendasTotalVendido").innerText = formatarMoeda(rel.total_vendas);
  }

  if (document.getElementById("vendasLucro")) {
    document.getElementById("vendasLucro").innerText = formatarMoeda(rel.lucro_vendas);
  }
}

async function adicionarVenda() {
  const produto = document.getElementById("vendaProduto")?.value || "";
  const cliente = document.getElementById("vendaCliente")?.value || "";
  const valor_venda = document.getElementById("vendaValor")?.value || "";
  const valor_custo = document.getElementById("vendaCusto")?.value || "";
  const data_venda = document.getElementById("vendaData")?.value || "";
  const observacao = document.getElementById("vendaObservacao")?.value || "";

  const resposta = await apiPost("/api/vendas", {
    produto,
    cliente,
    valor_venda,
    valor_custo,
    data_venda,
    observacao
  });

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  document.getElementById("vendaProduto").value = "";
  document.getElementById("vendaCliente").value = "";
  document.getElementById("vendaValor").value = "";
  document.getElementById("vendaCusto").value = "";
  document.getElementById("vendaData").value = "";
  document.getElementById("vendaObservacao").value = "";

  alert(resposta.mensagem);

  await carregarVendas();
  await carregarResumoVendas();
  await carregarDashboard();
  await carregarRelatorios();
}

async function excluirVenda(id) {
  const ok = confirm("Deseja excluir esta venda?");
  if (!ok) return;

  const resposta = await apiDelete(`/api/vendas/${id}`);

  if (!resposta.ok) {
    alert(resposta.mensagem);
    return;
  }

  alert(resposta.mensagem);

  await carregarVendas();
  await carregarResumoVendas();
  await carregarDashboard();
  await carregarRelatorios();
}

async function carregarRelatorios() {
  const rel = await apiGet("/api/relatorio-resumo");

  if (document.getElementById("totalRecebido")) document.getElementById("totalRecebido").innerText = formatarMoeda(rel.total_recebido);
  if (document.getElementById("totalPagamentos")) document.getElementById("totalPagamentos").innerText = rel.total_pagamentos;
  if (document.getElementById("totalAtraso")) document.getElementById("totalAtraso").innerText = formatarMoeda(rel.total_atraso);
  if (document.getElementById("relTotalEmprestado")) document.getElementById("relTotalEmprestado").innerText = formatarMoeda(rel.total_emprestado);
  if (document.getElementById("relTotalEmAberto")) document.getElementById("relTotalEmAberto").innerText = formatarMoeda(rel.total_em_aberto);
  if (document.getElementById("relLucro20")) document.getElementById("relLucro20").innerText = formatarMoeda(rel.lucro_20);
  if (document.getElementById("relLucro30")) document.getElementById("relLucro30").innerText = formatarMoeda(rel.lucro_30);

  if (document.getElementById("relLucroEmprestimos")) document.getElementById("relLucroEmprestimos").innerText = formatarMoeda(rel.lucro_emprestimos);
  if (document.getElementById("relLucroVendas")) document.getElementById("relLucroVendas").innerText = formatarMoeda(rel.lucro_vendas);
  if (document.getElementById("relLucroGeral")) document.getElementById("relLucroGeral").innerText = formatarMoeda(rel.lucro_geral);
  if (document.getElementById("relTotalVendas")) document.getElementById("relTotalVendas").innerText = formatarMoeda(rel.total_vendas);
  if (document.getElementById("relCustoVendas")) document.getElementById("relCustoVendas").innerText = formatarMoeda(rel.custo_vendas);

  if (document.getElementById("relLucroEmprestimosSemanal")) document.getElementById("relLucroEmprestimosSemanal").innerText = formatarMoeda(rel.lucro_emprestimos_semanal);
  if (document.getElementById("relLucroVendasSemanal")) document.getElementById("relLucroVendasSemanal").innerText = formatarMoeda(rel.lucro_vendas_semanal);
  if (document.getElementById("relLucroSemanal")) document.getElementById("relLucroSemanal").innerText = formatarMoeda(rel.lucro_semanal);
  if (document.getElementById("relLucroMensal")) document.getElementById("relLucroMensal").innerText = formatarMoeda(rel.lucro_mensal);
}

function gerarPdf() {
  window.open("/api/gerar-pdf", "_blank");
}

function configurarMenu() {
  document.querySelectorAll(".nav-item").forEach(botao => {
    botao.addEventListener("click", () => {
      if (botao.style.display === "none") return;
      trocarTela(botao.dataset.screen);
    });
  });
}

function configurarFormsAuth() {
  const formCriarUsuario = document.getElementById("formCriarUsuario");
  const formLogin = document.getElementById("formLogin");

  if (formCriarUsuario) {
    formCriarUsuario.addEventListener("submit", async event => {
      event.preventDefault();
      await criarUsuarioInicial();
    });
  }

  if (formLogin) {
    formLogin.addEventListener("submit", async event => {
      event.preventDefault();
      await fazerLogin();
    });
  }
}

function configurarEnterCadastros() {
  const ids = [
    "novoNome", "novoTelefone", "novoCpf", "novoEndereco", "novaDataContratacao",
    "emprestimoCliente", "emprestimoValor", "emprestimoData", "emprestimoTaxa",
    "vendaProduto", "vendaCliente", "vendaValor", "vendaCusto", "vendaData", "vendaObservacao"
  ];

  ids.forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();

          if (id.startsWith("venda")) {
            adicionarVenda();
          } else if (id.startsWith("emprestimo")) {
            adicionarEmprestimo();
          } else {
            adicionarCliente();
          }
        }
      });
    }
  });
}

async function carregarTabelasAdmin() {
  const lista = document.getElementById("adminListaTabelas");
  const mensagem = document.getElementById("adminMensagem");

  if (!lista) return;

  lista.innerHTML = "<option value=''>Carregando...</option>";
  if (mensagem) mensagem.innerHTML = "";

  try {
    const resposta = await apiGet("/api/admin/tabelas");

    if (!resposta.ok) {
      lista.innerHTML = "<option value=''>Falha ao carregar</option>";
      if (mensagem) mensagem.innerHTML = `<div class="admin-alert error">${escaparHtml(resposta.mensagem || "Erro ao carregar tabelas.")}</div>`;
      return;
    }

    lista.innerHTML = "<option value=''>Selecione uma tabela</option>";

    resposta.tabelas.forEach(tabela => {
      const option = document.createElement("option");
      option.value = tabela;
      option.textContent = tabela;
      lista.appendChild(option);
    });

    if (mensagem) {
      mensagem.innerHTML = `<div class="admin-alert success">Tabelas carregadas com sucesso.<br>Banco usado: ${escaparHtml(resposta.banco || "-")}</div>`;
    }
  } catch (erro) {
    lista.innerHTML = "<option value=''>Erro na requisição</option>";
    if (mensagem) mensagem.innerHTML = `<div class="admin-alert error">${escaparHtml(erro.message || "Erro inesperado.")}</div>`;
  }
}

function usarTabelaAdmin() {
  const tabela = document.getElementById("adminListaTabelas")?.value || "";
  const sql = document.getElementById("adminSql");

  if (!tabela || !sql) return;
  sql.value = `SELECT * FROM ${tabela} LIMIT 100;`;
}

async function executarSqlAdmin() {
  const sql = document.getElementById("adminSql")?.value || "";
  const mensagem = document.getElementById("adminMensagem");
  const resultado = document.getElementById("adminResultado");

  if (!sql.trim()) {
    alert("Digite um SQL.");
    return;
  }

  const confirmar = confirm("Deseja executar este SQL?");
  if (!confirmar) return;

  if (mensagem) mensagem.innerHTML = "Executando...";
  if (resultado) resultado.innerHTML = "";

  const resposta = await apiPost("/api/admin/sql", { sql });

  if (!resposta.ok) {
    if (mensagem) mensagem.innerHTML = `<div class="admin-alert error">${escaparHtml(resposta.mensagem)}</div>`;
    return;
  }

  if (mensagem) {
    mensagem.innerHTML = `<div class="admin-alert success">${escaparHtml(resposta.mensagem || "Executado com sucesso.")}</div>`;
  }

  if (resposta.tipo === "consulta") {
    renderizarResultadoAdmin(resposta.colunas || [], resposta.linhas || []);
  } else {
    if (resultado) {
      resultado.innerHTML = `<div class="admin-box-info"><strong>Comando executado.</strong><br>Linhas afetadas: ${Number(resposta.linhas_afetadas ?? 0)}</div>`;
    }

    await carregarDashboard();
    await carregarLogsAdmin();
  }
}

function renderizarResultadoAdmin(colunas, linhas) {
  const resultado = document.getElementById("adminResultado");
  if (!resultado) return;

  let html = `<div class="table-wrap"><table><thead><tr>`;
  colunas.forEach(coluna => html += `<th>${escaparHtml(coluna)}</th>`);
  html += `</tr></thead><tbody>`;

  if (!linhas.length) {
    html += `<tr><td colspan="${colunas.length}">Nenhum resultado.</td></tr>`;
  } else {
    linhas.forEach(linha => {
      html += `<tr>`;
      linha.forEach(valor => html += `<td>${escaparHtml(valor)}</td>`);
      html += `</tr>`;
    });
  }

  html += `</tbody></table></div>`;
  resultado.innerHTML = html;
}

function preencherExemploAdmin(tipo) {
  const sql = document.getElementById("adminSql");
  if (!sql) return;

  if (tipo === "clientes") sql.value = "SELECT * FROM clientes ORDER BY id DESC LIMIT 50;";
  if (tipo === "emprestimos") sql.value = "SELECT * FROM emprestimos ORDER BY id DESC LIMIT 50;";
  if (tipo === "pagamentos") sql.value = "SELECT * FROM pagamentos ORDER BY id DESC LIMIT 50;";
  if (tipo === "vendas") sql.value = "SELECT * FROM vendas ORDER BY id DESC LIMIT 50;";
}

async function carregarLogsAdmin() {
  const area = document.getElementById("adminLogsResultado");
  if (!area) return;

  area.innerHTML = "Carregando logs...";

  const resposta = await apiGet("/api/admin/logs");

  if (!resposta.ok) {
    area.innerHTML = `<div class="admin-alert error">${escaparHtml(resposta.mensagem)}</div>`;
    return;
  }

  if (!resposta.logs || !resposta.logs.length) {
    area.innerHTML = `<div class="admin-box-info">Nenhum log encontrado.</div>`;
    return;
  }

  let html = `<div class="table-wrap"><table><thead><tr>
    <th>ID</th><th>Usuário</th><th>Ação</th><th>SQL</th><th>Detalhes</th><th>Data/Hora</th><th>IP</th>
  </tr></thead><tbody>`;

  resposta.logs.forEach(item => {
    html += `<tr>
      <td>${escaparHtml(item.id)}</td>
      <td>${escaparHtml(item.usuario)}</td>
      <td>${escaparHtml(item.acao)}</td>
      <td>${escaparHtml(item.sql_texto)}</td>
      <td>${escaparHtml(item.detalhes)}</td>
      <td>${escaparHtml(item.data_hora)}</td>
      <td>${escaparHtml(item.ip)}</td>
    </tr>`;
  });

  html += `</tbody></table></div>`;
  area.innerHTML = html;
}

async function atualizarTudo() {
  await carregarDashboard();
}

async function iniciarSistema() {
  configurarMenu();
  configurarFormsAuth();
  configurarEnterCadastros();
  await verificarLoginInicial();
}

document.addEventListener("DOMContentLoaded", () => {
  iniciarSistema();
});

function abrirLogin() {
  document.getElementById("screen-inicial").style.display = "none";
  document.getElementById("screen-criar-usuario").style.display = "none";
  document.getElementById("screen-login").style.display = "flex";
}

function abrirCriarUsuario() {
  document.getElementById("screen-inicial").style.display = "none";
  document.getElementById("screen-login").style.display = "none";
  document.getElementById("screen-criar-usuario").style.display = "flex";
}

function voltarInicio() {
  document.getElementById("screen-login").style.display = "none";
  document.getElementById("screen-criar-usuario").style.display = "none";
  document.getElementById("screen-inicial").style.display = "flex";
}

function fazerBackupBanco() {
  window.open("/api/backup-banco", "_blank");
}


/* =========================================================
   OTIMIZAÇÃO PROFISSIONAL: cache inteligente, dashboard único,
   caixa diário e atualização automática em tempo real
   ========================================================= */
const financeproCache = {
  dados: {},
  duracao: 12000
};

function limparCacheFinancePro() {
  financeproCache.dados = {};
}

async function apiGetCache(url, ttl = financeproCache.duracao) {
  const agora = Date.now();
  const item = financeproCache.dados[url];

  if (item && (agora - item.timestamp) < ttl) {
    return item.valor;
  }

  const valor = await apiGet(url);
  financeproCache.dados[url] = { valor, timestamp: agora };
  return valor;
}

function atualizarStatusTempoReal() {
  const ultima = document.getElementById("ultimaAtualizacao");
  if (!ultima) return;

  const agora = new Date();
  ultima.textContent = `Última atualização: ${agora.toLocaleTimeString("pt-BR")}`;
}

function renderizarResumo(dados) {
  if (!dados) return;

  if (document.getElementById("totalEmprestado")) document.getElementById("totalEmprestado").innerText = formatarMoeda(dados.total_emprestado);
  if (document.getElementById("totalAberto")) document.getElementById("totalAberto").innerText = formatarMoeda(dados.total_em_aberto);
  if (document.getElementById("lucroTotal")) document.getElementById("lucroTotal").innerText = formatarMoeda(dados.lucro_emprestimos || dados.lucro_total || 0);
  if (document.getElementById("clientesEmAtraso")) document.getElementById("clientesEmAtraso").innerText = dados.clientes_em_atraso || 0;
  if (document.getElementById("totalClientes")) document.getElementById("totalClientes").innerText = dados.total_clientes || 0;

  if (document.getElementById("dashTotalVendas")) document.getElementById("dashTotalVendas").innerText = formatarMoeda(dados.total_vendido || 0);
  if (document.getElementById("dashLucroVendas")) document.getElementById("dashLucroVendas").innerText = formatarMoeda(dados.lucro_vendas || 0);
  if (document.getElementById("dashLucroGeral")) document.getElementById("dashLucroGeral").innerText = formatarMoeda(dados.lucro_geral || dados.lucro_total || 0);
}

function renderizarCaixaDiario(caixa) {
  if (!caixa) return;

  if (document.getElementById("caixaEntradasHoje")) document.getElementById("caixaEntradasHoje").innerText = formatarMoeda(caixa.entradas_gerais || 0);
  if (document.getElementById("caixaLucroHoje")) document.getElementById("caixaLucroHoje").innerText = formatarMoeda(caixa.lucro_dia || 0);
  if (document.getElementById("caixaEmprestimosHoje")) document.getElementById("caixaEmprestimosHoje").innerText = formatarMoeda(caixa.entradas_emprestimos || 0);
  if (document.getElementById("caixaVendasHoje")) document.getElementById("caixaVendasHoje").innerText = formatarMoeda(caixa.entradas_vendas || 0);
}

function renderizarGraficoStatus(dados) {
  const canvas = document.getElementById("graficoStatus");
  if (!canvas || typeof Chart === "undefined" || !Array.isArray(dados)) return;

  const labels = dados.map(item => item.nome);
  const valores = dados.map(item => item.valor);

  if (graficoPizza) graficoPizza.destroy();

  graficoPizza = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: valores,
        backgroundColor: ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6"],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false
    }
  });
}

async function carregarResumo() {
  const dados = await apiGetCache("/api/resumo");
  renderizarResumo(dados);
}

async function carregarGraficoStatus() {
  const dados = await apiGetCache("/api/dados-grafico-dashboard");
  renderizarGraficoStatus(dados);
}

async function carregarDashboard(forcar = false) {
  if (forcar) limparCacheFinancePro();

  try {
    const dados = await apiGetCache("/api/dashboard-completo", forcar ? 0 : 10000);
    renderizarResumo(dados.resumo);
    renderizarGraficoStatus(dados.grafico);
    renderizarCaixaDiario(dados.caixa);
    atualizarStatusTempoReal();
  } catch (erro) {
    console.error("Erro ao carregar dashboard completo:", erro);
    await carregarResumo();
    await carregarGraficoStatus();
  }
}

async function carregarResumoVendas() {
  const rel = await apiGetCache("/api/relatorio-resumo", 8000);

  if (document.getElementById("vendasTotalVendido")) {
    document.getElementById("vendasTotalVendido").innerText = formatarMoeda(rel.total_vendido || 0);
  }

  if (document.getElementById("vendasLucro")) {
    document.getElementById("vendasLucro").innerText = formatarMoeda(rel.lucro_vendas || 0);
  }
}

async function atualizarTelaAtual(forcar = false) {
  const telaAtiva = document.querySelector(".screen.active");
  const idTela = telaAtiva?.id || "screen-dashboard";

  if (forcar) limparCacheFinancePro();

  if (idTela === "screen-dashboard") {
    await carregarDashboard(forcar);
    return;
  }

  if (idTela === "screen-vendas") {
    if (forcar) await carregarVendas();
    await carregarResumoVendas();
    await carregarDashboard(forcar);
    return;
  }

  if (idTela === "screen-emprestimos") {
    if (forcar) await carregarEmprestimos();
    await carregarDashboard(forcar);
    return;
  }

  if (idTela === "screen-relatorios") {
    await carregarRelatorios();
    return;
  }

  if (idTela === "screen-clientes" && forcar) {
    await carregarClientes();
  }
}

async function atualizarTudo() {
  await atualizarTelaAtual(true);
}

function iniciarAtualizacaoAutomatica() {
  if (window.financeproIntervaloTempoReal) return;

  window.financeproIntervaloTempoReal = setInterval(async () => {
    const appLayout = document.getElementById("appLayout");
    const logado = appLayout && appLayout.style.display !== "none";

    if (!logado || document.hidden) return;

    try {
      await atualizarTelaAtual(false);
    } catch (erro) {
      console.warn("Falha na atualização automática:", erro);
    }
  }, 20000);
}

const adicionarVendaOriginalTempoReal = typeof adicionarVenda === "function" ? adicionarVenda : null;
async function adicionarVenda() {
  if (adicionarVendaOriginalTempoReal) {
    await adicionarVendaOriginalTempoReal();
    limparCacheFinancePro();
    await atualizarTelaAtual(true);
  }
}

const excluirVendaOriginalTempoReal = typeof excluirVenda === "function" ? excluirVenda : null;
async function excluirVenda(id) {
  if (excluirVendaOriginalTempoReal) {
    await excluirVendaOriginalTempoReal(id);
    limparCacheFinancePro();
    await atualizarTelaAtual(true);
  }
}

const confirmarQuitadoOriginalTempoReal = typeof confirmarQuitado === "function" ? confirmarQuitado : null;
async function confirmarQuitado(id) {
  if (confirmarQuitadoOriginalTempoReal) {
    await confirmarQuitadoOriginalTempoReal(id);
    limparCacheFinancePro();
    await atualizarTelaAtual(true);
  }
}

const confirmarJurosOriginalTempoReal = typeof confirmarJuros === "function" ? confirmarJuros : null;
async function confirmarJuros(id) {
  if (confirmarJurosOriginalTempoReal) {
    await confirmarJurosOriginalTempoReal(id);
    limparCacheFinancePro();
    await atualizarTelaAtual(true);
  }
}

const adicionarEmprestimoOriginalTempoReal = typeof adicionarEmprestimo === "function" ? adicionarEmprestimo : null;
async function adicionarEmprestimo() {
  if (adicionarEmprestimoOriginalTempoReal) {
    await adicionarEmprestimoOriginalTempoReal();
    limparCacheFinancePro();
    await atualizarTelaAtual(true);
  }
}

const iniciarSistemaOriginalTempoReal = typeof iniciarSistema === "function" ? iniciarSistema : null;
async function iniciarSistema() {
  if (iniciarSistemaOriginalTempoReal) {
    await iniciarSistemaOriginalTempoReal();
  }
  iniciarAtualizacaoAutomatica();
}
