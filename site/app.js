/* Tira-Teima — site de consulta montado a partir de data/painel.json.
   Cada indicador e cada governo têm endereço próprio (#/i/<id>, #/g/<id>) para ser consultado e compartilhado. */
(() => {
  "use strict";

  const ABREV = { sarney: "S", collor: "C", itamar: "I", fhc1: "F1", fhc2: "F2", lula1: "L1", lula2: "L2",
                  dilma1: "D1", dilma2: "D2", temer: "T", bolsonaro: "B", lula3: "L3" };
  const TEMAS = [
    ["economia", "Economia e emprego", ["pib_crescimento", "pib_per_capita", "desemprego", "dolar"]],
    ["custo", "Custo de vida e renda", ["ipca", "salario_minimo", "cesta_sp", "gasolina", "gasolina_litros"]],
    ["fome", "Fome, pobreza e desigualdade", ["fome", "pobreza", "gini", "bolsa_familia"]],
    ["saude", "Saúde", ["mortalidade_infantil", "expectativa_vida", "leitos_sus", "gasto_saude"]],
    ["educacao", "Educação", ["analfabetismo", "ensino_superior", "universidades_federais", "municipios_federais", "gasto_educacao"]],
    ["seguranca", "Segurança", ["homicidios"]],
    ["ambiente", "Meio ambiente", ["desmatamento", "queimadas"]],
  ];
  const CURTO = {
    pib_crescimento: "PIB", pib_per_capita: "PIB per capita", ipca: "Inflação", salario_minimo: "Salário mínimo",
    cesta_sp: "Cesta básica SP", gasolina: "Gasolina", gasolina_litros: "Gasolina por salário", queimadas: "Queimadas",
    desmatamento: "Desmatamento", dolar: "Dólar", fome: "Mapa da Fome", pobreza: "Extrema pobreza", gini: "Desigualdade",
    mortalidade_infantil: "Mortalidade infantil", expectativa_vida: "Expectativa de vida", gasto_saude: "Investimento em saúde",
    desemprego: "Desemprego", homicidios: "Homicídios", bolsa_familia: "Bolsa Família", leitos_sus: "Leitos do SUS",
    analfabetismo: "Analfabetismo", universidades_federais: "Universidades federais", municipios_federais: "Cidades com ensino federal",
    ensino_superior: "Matrícula no ensino superior", gasto_educacao: "Investimento em educação",
  };
  // Palavras extras para a busca encontrar o indicador pelo nome popular.
  const SINONIMOS = {
    ipca: "preços carestia custo de vida", pib_crescimento: "economia crescimento recessão", dolar: "câmbio moeda",
    desemprego: "emprego trabalho desocupação", salario_minimo: "salário renda poder de compra", cesta_sp: "comida alimentos dieese",
    gasolina: "combustível petrobras", gasolina_litros: "combustível", fome: "fao subalimentação", pobreza: "miséria",
    gini: "desigualdade renda", bolsa_familia: "auxílio brasil transferência de renda", leitos_sus: "sus hospital internação",
    gasto_saude: "sus saúde investimento", gasto_educacao: "escola investimento", ensino_superior: "faculdade universidade",
    universidades_federais: "faculdade federal reuni", municipios_federais: "campus institutos federais interiorização",
    homicidios: "violência assassinatos segurança", desmatamento: "amazônia floresta prodes inpe", queimadas: "fogo incêndio inpe",
    analfabetismo: "alfabetização ler escrever", mortalidade_infantil: "bebês saúde", expectativa_vida: "longevidade saúde",
  };
  // Critério do ranking: [1º lugar, último lugar, o que o número do governo significa].
  const CRIT = {
    pib_crescimento: ["maior crescimento médio do PIB", "menor crescimento médio do PIB", "Média do crescimento anual do PIB durante o governo."],
    pib_per_capita: ["maior crescimento médio da riqueza por pessoa", "menor crescimento médio da riqueza por pessoa", "Média do crescimento anual do PIB por pessoa durante o governo."],
    desemprego: ["menor desemprego médio", "maior desemprego médio", "Média da taxa de desemprego durante o governo."],
    ipca: ["menor inflação média", "maior inflação média", "Inflação média por ano durante o governo."],
    salario_minimo: ["maior ganho de poder de compra do mínimo", "menor ganho (ou perda) de poder de compra do mínimo", "Quanto o poder de compra do salário mínimo mudou do começo ao fim do governo."],
    cesta_sp: ["cesta básica consumia a menor parte do salário mínimo", "cesta básica consumia a maior parte do salário mínimo", "Em média, quanto do salário mínimo a cesta básica de SP consumia."],
    gasolina: ["gasolina mais barata, em valores de hoje", "gasolina mais cara, em valores de hoje", "Preço médio do litro no governo, corrigido para reais de hoje."],
    gasolina_litros: ["mais litros por salário mínimo", "menos litros por salário mínimo", "Em média, quantos litros de gasolina um salário mínimo comprava."],
    pobreza: ["queda mais rápida da extrema pobreza", "queda mais lenta (ou alta) da extrema pobreza", "Quanto a extrema pobreza caiu (−) ou subiu (+) por ano, em %."],
    gini: ["queda mais rápida da desigualdade", "queda mais lenta (ou alta) da desigualdade", "Quanto o índice de Gini caiu (−) ou subiu (+) por ano, em pontos."],
    mortalidade_infantil: ["queda mais rápida da mortalidade infantil", "queda mais lenta (ou alta) da mortalidade infantil", "Quanto a mortalidade infantil caiu (−) ou subiu (+) por ano, em %."],
    expectativa_vida: ["maior aumento da expectativa de vida", "menor aumento (ou queda) da expectativa de vida", "Quantos anos de vida esperada foram ganhos (+) ou perdidos (−) por ano."],
    analfabetismo: ["queda mais rápida do analfabetismo", "queda mais lenta do analfabetismo", "Quanto o analfabetismo caiu (−) por ano, em %."],
    ensino_superior: ["maior aumento da taxa bruta de matrícula", "menor aumento da taxa bruta de matrícula", "Quantos pontos a taxa bruta de matrícula no ensino superior subiu por ano."],
    homicidios: ["menor taxa média de homicídios", "maior taxa média de homicídios", "Média da taxa de homicídios por 100 mil habitantes no governo."],
    desmatamento: ["menos desmatamento por ano", "mais desmatamento por ano", "Média da área desmatada por ano na Amazônia durante o governo."],
    queimadas: ["menos focos de queimada por ano", "mais focos de queimada por ano", "Média de focos de queimada por ano durante o governo."],
  };
  const explica = (id, ind) => (CRIT[id] ? CRIT[id][2] : `${ind.resumo_rotulo[0].toUpperCase()}${ind.resumo_rotulo.slice(1)}.`);

  const nf = (min, max) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max });
  const F = {
    pct: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(Math.abs(v) >= 100 ? 0 : 1, Math.abs(v) >= 100 ? 0 : 1).format(Math.abs(v)) + "%",
    pct_simples: (v) => (v < 0 ? "−" : "") + nf(Math.abs(v) >= 100 ? 0 : 1, Math.abs(v) >= 100 ? 0 : 1).format(Math.abs(v)) + "%",
    moeda: (v) => "R$ " + nf(2, 2).format(v),
    moeda_usd: (v) => "US$ " + nf(0, 0).format(v),
    inteiro: (v) => nf(0, 0).format(Math.round(v)),
    decimal: (v) => nf(1, 1).format(v),
    delta: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(2, 2).format(Math.abs(v)) + " por ano",
    delta_pct: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(1, 1).format(Math.abs(v)) + "% ao ano",
    inteiro_delta: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(0, 0).format(Math.abs(Math.round(v))),
    moeda_int: (v) => "R$ " + nf(0, 0).format(v),
    anos_mapa: (v) => `${v} ${v === 1 ? "ponto" : "pontos"} acima de 2,5%`,
  };
  const fmt = (tipo, v) => (v == null || Number.isNaN(v) ? "—" : (F[tipo] || F.pct_simples)(v));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const dataBR = (iso) => iso.split("-").reverse().join("/");
  const sem = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const $ = (sel) => document.querySelector(sel);

  /* ---------- tema claro/escuro ---------- */
  const raiz = document.documentElement;
  try { const t = localStorage.getItem("tema"); if (t) raiz.dataset.theme = t; } catch (_) {}
  $("#tema").addEventListener("click", () => {
    const escuro = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    raiz.dataset.theme = escuro ? "light" : "dark";
    try { localStorage.setItem("tema", raiz.dataset.theme); } catch (_) {}
    desenharGrafico();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", desenharGrafico);
  const cor = (n) => getComputedStyle(raiz).getPropertyValue(n).trim();

  /* ---------- governos ---------- */
  let GOV = [];
  const gov = (id) => GOV.find((g) => g.id === id);
  const nomeGov = (id) => gov(id)?.nome ?? "";
  const fimGov = (g) => (g.id === "lula3" ? "hoje" : dataBR(g.fim));
  const govDoMes = (ano, mes) => {
    const d = `${ano}-${String(mes).padStart(2, "0")}-15`;
    return GOV.find((g) => g.inicio <= d && d <= g.fim)?.id ?? null;
  };
  const govDoAno = (ano) => {
    let melhor = null, dias = -1;
    for (const g of GOV) {
      const a = Math.max(Date.parse(`${ano}-01-01`), Date.parse(g.inicio));
      const b = Math.min(Date.parse(`${ano}-12-31`), Date.parse(g.fim));
      if (b >= a && b - a > dias) { dias = b - a; melhor = g.id; }
    }
    return melhor;
  };
  const govDoPonto = (x) => (x.length > 4 ? govDoMes(+x.slice(0, 4), +x.slice(5, 7)) : govDoAno(+x));

  /* ---------- dados ---------- */
  let D = null;
  const resumoFmt = (ind) => ind.resumo_formato || ind.formato;
  const ast = (r) => (r?.parcial ? "*" : "");
  const presentes = (ids) => ids.filter((id) => D.indicadores[id]);
  const ORDEM = () => TEMAS.flatMap((t) => presentes(t[2]));
  const temaDe = (id) => TEMAS.find((t) => t[2].includes(id));

  fetch("data/painel.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((d) => {
      D = d; GOV = d.governos;
      $("#gerado-em").textContent = new Date(D.gerado_em).toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short" });
      busca();
      rotear();
    })
    .catch((e) => {
      $("#conteudo").innerHTML = `<div class="pagina"><h1>Os dados não carregaram</h1><p class="lede-pag">O arquivo de dados não respondeu (${esc(e.message)}). Recarregue a página em alguns instantes.</p></div>`;
    });

  /* ---------- rotas ---------- */
  const LEGADO = { comparativo: "comparar", indicadores: "indicadores", governos: "governos", calculadora: "calculadora", metodologia: "metodologia" };
  addEventListener("hashchange", rotear);
  function rotear() {
    if (!D) return;
    let h = location.hash.replace(/^#\/?/, "");
    // endereços antigos do site (#ind-pib_crescimento, #gov-lula1, #comparativo)
    if (h.startsWith("ind-")) { location.replace(`#/i/${h.slice(4)}`); return; }
    if (h.startsWith("gov-")) { location.replace(`#/g/${h.slice(4)}`); return; }
    if (LEGADO[h] && !location.hash.startsWith("#/")) { location.replace(`#/${LEGADO[h]}`); return; }
    const [rota, arg] = h.split("/");
    grafico?.destroy(); grafico = null;
    const main = $("#conteudo");
    let titulo = "";
    if (rota === "i" && D.indicadores[arg]) titulo = paginaIndicador(main, arg);
    else if (rota === "g" && gov(arg)) titulo = paginaGoverno(main, arg);
    else if (rota === "indicadores") titulo = paginaIndice(main);
    else if (rota === "governos") titulo = paginaGovernos(main);
    else if (rota === "comparar") titulo = paginaComparar(main);
    else if (rota === "calculadora") titulo = paginaCalculadora(main);
    else if (rota === "metodologia") titulo = paginaMetodologia(main);
    else if (rota === "i" || rota === "g") {
      main.innerHTML = `<div class="pagina estreita"><h1>Página não encontrada</h1><p class="lede-pag">Este endereço não corresponde a nenhum ${rota === "i" ? "indicador" : "governo"}. Veja a <a href="#/${rota === "i" ? "indicadores" : "governos"}">lista completa</a> ou use a busca no topo.</p></div>`;
      titulo = "Página não encontrada";
    } else titulo = paginaInicio(main);
    document.title = titulo ? `${titulo} · Tira-Teima` : "Tira-Teima · Os números do Brasil, governo a governo";
    const secao = { i: "indicadores", g: "governos" }[rota] || rota;
    for (const a of document.querySelectorAll(".menu a")) {
      if (a.dataset.rota === secao) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    }
    scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }

  /* ---------- busca ---------- */
  function busca() {
    const input = $("#busca"), lista = $("#busca-res");
    const itens = [
      ...ORDEM().map((id) => {
        const ind = D.indicadores[id];
        return { href: `#/i/${id}`, titulo: ind.pergunta || ind.titulo, sub: `${ind.titulo} · ${temaDe(id)[1]}`,
                 chave: sem(`${ind.titulo} ${ind.pergunta} ${CURTO[id]} ${SINONIMOS[id] || ""} ${temaDe(id)[1]}`) };
      }),
      ...GOV.map((g) => ({ href: `#/g/${g.id}`, titulo: `${g.nome}`, sub: `${g.presidente}, ${dataBR(g.inicio)} a ${fimGov(g)}`,
                           chave: sem(`${g.nome} ${g.presidente} governo`) })),
    ];
    let achados = [], ativo = -1;
    const fechar = () => { lista.hidden = true; input.setAttribute("aria-expanded", "false"); ativo = -1; };
    const marcar = () => lista.querySelectorAll("a").forEach((a, i) => a.classList.toggle("ativo", i === ativo));
    input.addEventListener("input", () => {
      const q = sem(input.value.trim());
      if (!q) { fechar(); return; }
      const termos = q.split(/\s+/);
      achados = itens.filter((it) => termos.every((t) => it.chave.includes(t))).slice(0, 8);
      lista.innerHTML = achados.length
        ? achados.map((it) => `<li role="option"><a href="${it.href}">${esc(it.titulo)}<small>${esc(it.sub)}</small></a></li>`).join("")
        : `<li class="vazio">Nada encontrado para “${esc(input.value.trim())}”. Tente outra palavra, como “preços” ou “Amazônia”.</li>`;
      lista.hidden = false; input.setAttribute("aria-expanded", "true"); ativo = achados.length ? 0 : -1; marcar();
    });
    input.addEventListener("keydown", (e) => {
      if (lista.hidden) return;
      if (e.key === "ArrowDown") { ativo = Math.min(ativo + 1, achados.length - 1); marcar(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { ativo = Math.max(ativo - 1, 0); marcar(); e.preventDefault(); }
      else if (e.key === "Enter" && achados[ativo]) { location.hash = achados[ativo].href; input.value = ""; fechar(); input.blur(); }
      else if (e.key === "Escape") fechar();
    });
    lista.addEventListener("click", (e) => { if (e.target.closest("a")) { input.value = ""; fechar(); } });
    document.addEventListener("click", (e) => { if (!e.target.closest(".busca")) fechar(); });
  }

  /* ---------- início ---------- */
  function regua() {
    const t0 = Date.parse(GOV[0].inicio), t1 = Date.now();
    return `<div class="regua"><p class="regua-tit">Os doze períodos desde a redemocratização. Toque num governo para ver os resultados dele.</p>
      <nav class="regua-faixa" aria-label="Governos">${GOV.map((g) => {
        const peso = (Math.min(Date.parse(g.fim), t1) - Date.parse(g.inicio)) / (t1 - t0);
        return `<a href="#/g/${g.id}" style="flex:${peso} 1 0" title="${esc(g.nome)}: ${esc(g.presidente)}, ${dataBR(g.inicio)} a ${fimGov(g)}" aria-label="${esc(g.nome)}"><span class="nm-longo">${esc(g.nome)}</span><span class="nm-curto" aria-hidden="true">${ABREV[g.id]}</span><small>${g.inicio.slice(0, 4)}</small></a>`;
      }).join("")}</nav></div>`;
  }

  function indiceHTML() {
    return `<div class="indice">${TEMAS.filter((t) => presentes(t[2]).length).map(([, nome, ids]) => `
      <section class="indice-tema"><h2>${esc(nome)}</h2><ul>${presentes(ids).map((id) => {
        const ind = D.indicadores[id];
        return `<li><a href="#/i/${id}">${esc(ind.pergunta || ind.titulo)}<small>${esc(ind.titulo)}</small></a></li>`;
      }).join("")}</ul></section>`).join("")}</div>`;
  }

  function paginaInicio(main) {
    main.innerHTML = `<div class="pagina">
      <div class="inicio-topo">
        <div><h1>Os números do Brasil, governo a governo</h1>
          <p class="lede">De Sarney a Lula 3. Cada pergunta abaixo tem uma página com o número oficial, o gráfico ano a ano, o resultado de cada governo e a fonte para conferir.</p></div>
        <p class="leitura"><b>Como ler.</b> Os números mostram o que aconteceu durante cada governo, não o que cada governo causou. Crises internacionais, preço de commodities, pandemia e decisões de mandatos anteriores também pesam.</p>
      </div>
      ${regua()}
      ${indiceHTML()}
      <div class="ferramentas">
        <a class="ferramenta" href="#/comparar"><b>Comparar dois governos</b><span>Indicador por indicador, lado a lado.</span></a>
        <a class="ferramenta" href="#/calculadora"><b>Corrigir um preço antigo</b><span>Quanto valia “R$ 0,50 em 1995” em dinheiro de hoje.</span></a>
        <a class="ferramenta" href="#/metodologia"><b>Como calculamos</b><span>As regras, os limites e a situação de cada fonte.</span></a>
      </div></div>`;
    ajustarRegua();
    return "";
  }

  // Na régua, governos curtos mostram a sigla quando o nome não cabe.
  function ajustarRegua() {
    for (const a of document.querySelectorAll(".regua-faixa a")) {
      a.classList.remove("estreito");
      if (a.querySelector(".nm-longo").scrollWidth > a.clientWidth - 12) a.classList.add("estreito");
    }
  }

  function paginaIndice(main) {
    main.innerHTML = `<div class="pagina"><h1>Indicadores</h1>
      <p class="lede-pag">${ORDEM().length} perguntas em sete temas. Escolha uma para ver o número oficial, o gráfico e o resultado de cada governo.</p>
      ${indiceHTML()}</div>`;
    return "Indicadores";
  }

  /* ---------- página de indicador ---------- */
  function trajeto(ind, r) {
    const mudou = (a, b) => {
      if (!(a > 0) || !(b > 0)) return "";
      const p = (b / a - 1) * 100;
      if (Math.abs(p) < 0.5) return ", ficou estável";
      return `, ${p > 0 ? "subiu" : "caiu"} ${nf(0, 0).format(Math.abs(p))}%`;
    };
    if (r.de != null && r.para != null)
      return `${fmt(ind.formato, r.de)} → ${fmt(ind.formato, r.para)}${r.periodo ? ` (${r.periodo})` : ""}${mudou(r.de, r.para)}`;
    const fr = ind.resumo_formato === "anos_mapa" ? ind.formato : resumoFmt(ind);
    const nivel = !ind.resumo_formato || ind.resumo_formato === "anos_mapa";
    if (r.inicio_val != null && r.fim_val != null)
      return `${r.inicio_ano}: ${fmt(fr, r.inicio_val)} → ${r.fim_ano}: ${fmt(fr, r.fim_val)}${nivel ? mudou(r.inicio_val, r.fim_val) : ""}`;
    return "";
  }

  function posTexto(id, ind, r) {
    const empatados = Object.values(ind.resumo).filter((x) => x.posicao === r.posicao).length;
    return empatados > 1 ? `empatado em ${r.posicao}º de ${r.total}` : `${r.posicao}º de ${r.total}`;
  }

  function linhasTabela(id, ind, ordem) {
    let ids = GOV.map((g) => g.id).filter((g) => ind.resumo[g]);
    if (ordem === "rank" && ind.direcao) ids.sort((a, b) => ind.resumo[a].posicao - ind.resumo[b].posicao);
    const vals = ids.map((g) => ind.resumo[g].valor);
    const log = ind.escala === "log";
    const tx = (v) => (log ? Math.log10(Math.max(v, 1)) : v);
    const lo = Math.min(0, ...vals.map(tx)), hi = Math.max(0, ...vals.map(tx));
    const amp = hi - lo || 1;
    const zero = ((0 - lo) / amp) * 100;
    return ids.map((g) => {
      const r = ind.resumo[g];
      const a = ((Math.min(0, tx(r.valor)) - lo) / amp) * 100, b = ((Math.max(0, tx(r.valor)) - lo) / amp) * 100;
      const marca = r.avaliacao === "bom" ? '<span class="marcador bom" aria-label="entre os melhores">✓</span>'
        : r.avaliacao === "ruim" ? '<span class="marcador ruim" aria-label="entre os piores">✕</span>' : '<span class="marcador"></span>';
      const t = trajeto(ind, r);
      return `<tr class="${r.avaliacao || ""}">
        <td class="pos">${ind.direcao && r.posicao ? `${marca}${r.posicao}º` : ""}</td>
        <th scope="row"><a href="#/g/${g}">${esc(nomeGov(g))}</a>${t ? `<span class="traj">${esc(t)}</span>` : ""}</th>
        <td class="barra-c"><div class="barrinha"><span style="left:${a}%;width:${Math.max(b - a, 0.6)}%"></span>${lo < 0 ? `<i class="zero" style="left:${zero}%"></i>` : ""}</div></td>
        <td class="num">${fmt(resumoFmt(ind), r.valor)}${ast(r)}</td></tr>`;
    }).join("");
  }

  function paginaIndicador(main, id) {
    const ind = D.indicadores[id];
    const [, nomeTema] = temaDe(id);
    const ordem = ORDEM(), k = ordem.indexOf(id);
    const ant = ordem[k - 1], prox = ordem[k + 1];
    const m = ind.melhor && ind.resumo[ind.melhor], p = ind.pior && ind.resumo[ind.pior];
    const c = CRIT[id];
    const ultimo = [...ind.serie].reverse().find((x) => x.y != null);
    const fmtSerie = ind.formato;

    let veredito;
    if (m && p) {
      veredito = `<p><span class="marcador bom">✓</span>Melhor resultado: <mark>${esc(nomeGov(ind.melhor))}</mark>, com ${fmt(resumoFmt(ind), m.valor)}${ast(m)} <span class="mudo">(${esc(ind.resumo_rotulo)})</span>.</p>
        <p><span class="marcador ruim">✕</span>Pior resultado: <mark>${esc(nomeGov(ind.pior))}</mark>, com ${fmt(resumoFmt(ind), p.valor)}${ast(p)} <span class="mudo">(${esc(ind.resumo_rotulo)})</span>.${p.sentido === "melhorou" ? " O indicador melhorou nesse governo, só que menos que nos outros." : ""}</p>
        <p class="criterio">Critério: ${esc(c ? c[0] : "")} fica em 1º. ${esc(explica(id, ind))} ✓ e ✕ marcam o quarto melhor e o quarto pior dos governos com dado.</p>`;
    } else {
      if (ind.limite && ultimo && ultimo.y <= ind.limite.valor) {
        veredito = `<p>Último dado: <mark>abaixo de ${fmt(fmtSerie, ind.limite.valor)}</mark>, fora do Mapa da Fome (média de ${+ultimo.x - 1} a ${+ultimo.x + 1}).</p>
        <p class="criterio">Este indicador não tem ranking entre governos. ${esc(explica(id, ind))} Os valores de cada governo estão na tabela abaixo.</p>`;
      } else veredito = `<p>Último dado: <mark>${fmt(fmtSerie, ultimo?.y)}</mark>${ultimo ? `, em ${ultimo.x.length > 4 ? `${ultimo.x.slice(5, 7)}/${ultimo.x.slice(0, 4)}` : ultimo.x}` : ""}.</p>
        <p class="criterio">Este indicador não tem ranking entre governos. ${esc(explica(id, ind))} Os valores de cada governo estão na tabela abaixo.</p>`;
    }
    const temRank = !!ind.direcao;
    const marcosLeg = (() => {
      const labels = ind.serie.map((x) => x.x), anual = labels[0]?.length === 4;
      const ms = (D.marcos || []).filter((mm) => labels.includes(anual ? mm.data.slice(0, 4) : mm.data));
      return ms.length ? `<p class="marcos-leg"><i></i>Marcos: ${ms.map((mm) => `${esc(mm.rotulo)} (${mm.data.slice(0, 4)})`).join("; ")}.</p>` : "";
    })();

    main.innerHTML = `<div class="pagina com-lado">
      <nav class="lado" aria-label="Indicadores">${TEMAS.filter((t) => presentes(t[2]).length).map(([, nome, ids]) =>
        `<h2>${esc(nome)}</h2><ul>${presentes(ids).map((x) => `<li><a href="#/i/${x}"${x === id ? ' aria-current="page"' : ""}>${esc(CURTO[x])}</a></li>`).join("")}</ul>`).join("")}</nav>
      <article>
        <div class="ir-para"><label class="sr" for="ir-para">Ir para outro indicador</label><select id="ir-para">${TEMAS.map(([, nome, ids]) =>
          `<optgroup label="${esc(nome)}">${presentes(ids).map((x) => `<option value="${x}"${x === id ? " selected" : ""}>${esc(CURTO[x])}</option>`).join("")}</optgroup>`).join("")}</select></div>
        <p class="trilha-nav"><a href="#/indicadores">Indicadores</a> / ${esc(nomeTema)}</p>
        <header class="ind-cab"><h1>${esc(ind.pergunta || ind.titulo)}</h1>
          <p class="unidade">${esc(ind.titulo)}, em ${esc(ind.unidade)}</p></header>
        <div class="veredito">${veredito}</div>
        ${ind.aviso ? `<p class="ressalva"><b>Antes de tirar conclusões.</b> ${esc(ind.aviso)}</p>` : ""}
        ${faixaMapaFome(ind)}

        <section class="bloco-ind"><h2>Ano a ano</h2>
          <p class="sub">${esc(ind.descricao)}</p>
          <div class="grafico"><canvas id="g-serie" role="img" aria-label="${esc(ind.titulo)} ao longo do tempo, com faixas por governo"></canvas></div>
          ${marcosLeg}</section>

        <section class="bloco-ind"><h2>Por governo</h2>
          <p class="sub">${esc(explica(id, ind))}${temRank ? "" : " Sem ranking."} Toque no nome para ver todos os resultados daquele governo.</p>
          ${temRank ? `<div class="alternar" role="group" aria-label="Ordem da tabela"><button type="button" data-ordem="rank" aria-pressed="true">Do melhor para o pior</button><button type="button" data-ordem="crono" aria-pressed="false">Ordem cronológica</button></div>` : ""}
          <div class="tab-wrap"><table class="tab-gov"><thead><tr><th class="pos">${temRank ? "Posição" : ""}</th><th>Governo</th><th class="barra-c"></th><th class="num">${esc(ind.resumo_rotulo || "")}</th></tr></thead>
            <tbody id="tab-gov">${linhasTabela(id, ind, temRank ? "rank" : "crono")}</tbody></table></div>
          <p class="legenda-tab">${temRank ? "✓ entre os melhores · ✕ entre os piores. " : ""}${Object.values(ind.resumo).some((r) => r.parcial) ? "* Lula 3 está em andamento: valor parcial. " : ""}Governos sem dado suficiente (menos de 75% do período) ficam fora.</p>
        </section>

        <div class="detalhes">
          <details><summary>De onde vem o número</summary><div class="corpo">
            <p>Fonte: <a href="${esc(ind.fonte_url)}" target="_blank" rel="noopener">${esc(ind.fonte)}</a>.</p>
            ${ind.notas ? notasHTML(ind) : ""}
            <p><button type="button" class="botao" id="baixar-csv">Baixar dados e cálculo (CSV)</button></p></div></details>
          <details><summary>Como cada governo é comparado</summary><div class="corpo">
            <p>${esc(explica(id, ind))} ${temRank ? `Em 1º fica o governo com ${esc(c ? c[0] : "o melhor resultado")}.` : "Este indicador não tem ranking."}</p>
            <p>Dados mensais pertencem a quem governava no dia 15; dados anuais são divididos pelos dias de cada governo no ano. Um governo só entra se a série cobrir pelo menos 75% do período dele. As regras completas estão em <a href="#/metodologia">Como calculamos</a>.</p></div></details>
        </div>

        <nav class="vizinhos" aria-label="Outros indicadores">
          ${ant ? `<a href="#/i/${ant}"><small>Anterior</small>${esc(D.indicadores[ant].pergunta || D.indicadores[ant].titulo)}</a>` : ""}
          ${prox ? `<a class="prox" href="#/i/${prox}"><small>Próximo</small>${esc(D.indicadores[prox].pergunta || D.indicadores[prox].titulo)}</a>` : ""}
        </nav>
      </article></div>`;

    $("#ir-para").addEventListener("change", (e) => { location.hash = `#/i/${e.target.value}`; });
    for (const b of main.querySelectorAll(".alternar button")) {
      b.addEventListener("click", () => {
        main.querySelectorAll(".alternar button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        $("#tab-gov").innerHTML = linhasTabela(id, ind, b.dataset.ordem);
      });
    }
    $("#baixar-csv").addEventListener("click", () => csvIndicador(id, ind));
    indAtual = ind;
    desenharGrafico();
    return ind.pergunta || ind.titulo;
  }

  function notasHTML(ind) {
    const painel = ind.notas.some((n) => /terrabrasilis/.test(n.url));
    return `<p>Valor de cada ano e o documento do INPE de onde ele saiu:</p><ul>${ind.notas.map((n) =>
      `<li>${n.ano}: ${nf(0, 0).format(n.valor)} km², taxa ${n.tipo === "consolidada" ? "consolidada" : "estimada (ainda sem consolidação)"}. <a href="${esc(n.url)}" target="_blank" rel="noopener">${/terrabrasilis/.test(n.url) ? "Painel PRODES do INPE" : "Nota técnica do INPE (PDF)"}</a></li>`).join("")}</ul>
      ${painel ? "<p>Os anos ligados ao painel foram transcritos da série histórica que o INPE apresentou na coletiva do PRODES 2026 (16/10/2026), cujo PDF está no portal gov.br e fica restrito durante o período eleitoral. A cada atualização, o site confere essa série com as notas técnicas nos anos em comum.</p>" : ""}`;
  }

  function faixaMapaFome(ind) {
    if (!ind.mapa_fome) return "";
    const anos = Object.entries(ind.mapa_fome).filter(([a]) => +a >= 2000);
    if (!anos.length) return "";
    return `<div class="mapa-fome bloco-ind"><h2>Brasil no Mapa da Fome</h2>
      <p class="sub">Cada quadro é uma média de três anos feita pela FAO; o rótulo mostra o triênio.</p>
      <div class="mf-anos">${anos.map(([a, no]) => `<span class="mf-ano ${no ? "no" : "fora"}" title="${+a - 1} a ${+a + 1}: ${no ? "no Mapa da Fome" : "fora do Mapa da Fome"}"><b>${no ? "✕" : "✓"}</b>${String(+a - 1).slice(2)}–${String(+a + 1).slice(2)}</span>`).join("")}</div>
      <p class="mf-leg">✕ no mapa (mais de 2,5% da população subalimentada). ✓ fora do mapa.</p></div>`;
  }

  function csvIndicador(id, ind) {
    const q = (v) => (v === null || v === undefined ? "" : /[",;\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
    const L = [["# " + ind.titulo + " (" + ind.unidade + ")"], ["# fonte: " + ind.fonte + " (" + ind.fonte_url + ")"], ["# regra: " + explica(id, ind)], [],
      ["periodo", "valor"], ...ind.serie.map((p) => [p.x, p.y]), [],
      ["governo", "periodo_com_dado", ind.resumo_rotulo || "resumo", "valor_inicio", "ano_inicio", "valor_fim", "ano_fim", "posicao"]];
    for (const [g, r] of Object.entries(ind.resumo || {}))
      L.push([nomeGov(g), r.periodo, r.valor, r.inicio_val, r.inicio_ano, r.fim_val, r.fim_ano, r.posicao]);
    if (ind.notas) { L.push([], ["ano", "km2", "tipo", "documento"]); ind.notas.forEach((n) => L.push([n.ano, n.valor, n.tipo, n.url])); }
    const blob = new Blob(["﻿" + L.map((l) => l.map(q).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `tira-teima_${id}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  /* ---------- governos ---------- */
  function paginaGovernos(main) {
    main.innerHTML = `<div class="pagina estreita"><h1>Governos</h1>
      <p class="lede-pag">Doze períodos desde a redemocratização. Nos dois impeachments, o vice entra na data em que assumiu como interino.</p>
      <ul class="lista-gov">${GOV.map((g) => `<li><a href="#/g/${g.id}"><b>${esc(g.nome)}</b><span>${esc(g.presidente)}</span><small>${dataBR(g.inicio)} a ${fimGov(g)}</small></a></li>`).join("")}</ul></div>`;
    return "Governos";
  }

  function paginaGoverno(main, gid) {
    const g = gov(gid);
    const ctx = (D.contexto || {})[gid] || [];
    const fortes = [], fracos = [], todos = [];
    for (const id of ORDEM()) {
      const ind = D.indicadores[id], r = ind.resumo[gid];
      if (!r) continue;
      const item = `<li><a href="#/i/${id}"><span class="nome">${esc(CURTO[id])}</span><span class="val">${fmt(resumoFmt(ind), r.valor)}${ast(r)}<span class="un">${esc(ind.resumo_rotulo || "")}</span></span>
        <span class="pos">${r.posicao ? `${posTexto(id, ind, r)}. 1º = ${esc(CRIT[id] ? CRIT[id][0] : "")}.` : esc(ind.resumo_rotulo || "")}${r.sentido === "melhorou" && r.avaliacao === "ruim" ? " O indicador melhorou, só que menos que nos outros governos." : ""}${r.sentido === "piorou" && r.avaliacao === "bom" ? " O indicador piorou, só que menos que nos outros governos." : ""}</span></a></li>`;
      if (r.avaliacao === "bom") fortes.push(item);
      else if (r.avaliacao === "ruim") fracos.push(item);
      todos.push(`<tr class="${r.avaliacao || ""}"><td class="pos">${r.avaliacao === "bom" ? '<span class="marcador bom">✓</span>' : r.avaliacao === "ruim" ? '<span class="marcador ruim">✕</span>' : ""}${r.posicao ? `${r.posicao}º` : ""}</td>
        <th scope="row"><a href="#/i/${id}">${esc(CURTO[id])}</a><span class="traj">${esc(ind.resumo_rotulo || "")}</span></th>
        <td class="per">${esc(r.periodo || "")}</td><td class="num">${fmt(resumoFmt(ind), r.valor)}${ast(r)}</td></tr>`);
    }
    main.innerHTML = `<div class="pagina">
      <nav class="gov-nav" aria-label="Outros governos">${GOV.map((x) => `<a href="#/g/${x.id}"${x.id === gid ? ' aria-current="page"' : ""}>${esc(x.nome)}</a>`).join("")}</nav>
      <header class="gov-cab"><h1>${esc(g.nome)}</h1><p class="datas">${esc(g.presidente)}, de ${dataBR(g.inicio)} a ${fimGov(g)}${gid === "lula3" ? " (em andamento, valores parciais marcados com *)" : ""}</p></header>
      ${ctx.length ? `<ul class="contexto">${ctx.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      <div class="colunas-gov">
        <section><h2><span class="marcador bom">✓</span>Entre os melhores</h2><ul class="lista-res">${fortes.join("") || '<li class="vazio">Em nenhum indicador ficou entre os melhores.</li>'}</ul></section>
        <section><h2><span class="marcador ruim">✕</span>Entre os piores</h2><ul class="lista-res">${fracos.join("") || '<li class="vazio">Em nenhum indicador ficou entre os piores.</li>'}</ul></section>
      </div>
      <section class="bloco-ind"><h2>Todos os indicadores deste governo</h2>
        <p class="sub">Posição entre os governos com dado. Indicadores sem ranking aparecem sem posição.</p>
        <div class="tab-wrap"><table class="tab-gov"><thead><tr><th class="pos">Posição</th><th>Indicador</th><th>Período com dado</th><th class="num">Valor</th></tr></thead><tbody>${todos.join("")}</tbody></table></div>
      </section></div>`;
    return g.nome;
  }

  /* ---------- comparar ---------- */
  let duelo = null;
  function paginaComparar(main) {
    const opts = GOV.map((g) => `<option value="${g.id}">${esc(g.nome)} (${g.inicio.slice(0, 4)}–${g.id === "lula3" ? "hoje" : g.fim.slice(0, 4)})</option>`).join("");
    main.innerHTML = `<div class="pagina">
      <h1>Comparar dois governos</h1>
      <p class="lede-pag">Escolha dois períodos e veja, indicador por indicador, quem teve o melhor resultado pelo critério escrito em cada linha.</p>
      <div class="seletor"><label>Governo A<select id="du-a">${opts}</select></label><span class="x">e</span><label>Governo B<select id="du-b">${opts}</select></label></div>
      <div id="duelo"></div>
      <section class="bloco-ind"><h2>Todos os governos de uma vez</h2>
        <p class="sub"><span class="pt bom"></span> entre os melhores, <span class="pt ruim"></span> entre os piores, <span class="pt meio"></span> no meio, <span class="pt sem"></span> sem ranking. Ponto vazio na linha: sem dado. Passe o mouse ou toque para ver o número.</p>
        <div class="tab-wrap" tabindex="0" role="region" aria-label="Todos os governos"><table class="placar" id="placar"></table></div>
        <p class="aviso-curto">Este placar não é uma conclusão das fontes oficiais. Os dados vêm delas; a forma de resumir cada governo e de ordenar é do site e está descrita em cada indicador. Contar pontos não diz quais indicadores pesam mais.</p>
      </section></div>`;
    const sa = $("#du-a"), sb = $("#du-b");
    sa.value = duelo?.[0] || GOV.at(-2).id; sb.value = duelo?.[1] || GOV.at(-1).id;
    const desenhar = () => {
      duelo = [sa.value, sb.value];
      const A = sa.value, B = sb.value;
      if (A === B) { $("#duelo").innerHTML = '<p class="aviso-curto">Escolha dois governos diferentes.</p>'; return; }
      let pa = 0, pb = 0, h = "";
      for (const [, nomeTema, ids] of TEMAS) {
        const linhas = presentes(ids).map((id) => {
          const ind = D.indicadores[id], ra = ind.resumo[A], rb = ind.resumo[B];
          let ganha = null;
          if (ind.direcao && ra && rb && Math.abs(ra.valor - rb.valor) > 1e-9) {
            const aMelhor = ind.direcao === "maior" ? ra.valor > rb.valor : ra.valor < rb.valor;
            ganha = aMelhor ? "A" : "B"; aMelhor ? pa++ : pb++;
          }
          const cel = (r, lado) => !r ? '<td class="v sem">sem dado</td>'
            : `<td class="v${ganha === lado ? " ganha" : ""}">${ganha === lado ? '<span class="marcador bom">✓</span>' : ""}${fmt(resumoFmt(ind), r.valor)}${ast(r)}${trajeto(ind, r) ? `<small>${esc(trajeto(ind, r))}</small>` : ""}</td>`;
          const nota = !ind.direcao ? "Sem ranking." : ra && rb && !ganha ? "Empate." : `✓ = ${CRIT[id] ? CRIT[id][0] : ""}.`;
          return `<tr><th scope="row"><a href="#/i/${id}">${esc(ind.pergunta || ind.titulo)}</a><small>${esc(nota)}</small></th>${cel(ra, "A")}${cel(rb, "B")}</tr>`;
        });
        if (linhas.length) h += `<tr class="tema-l"><td colspan="3">${esc(nomeTema)}</td></tr>${linhas.join("")}`;
      }
      $("#duelo").innerHTML = `<p class="placar-duelo"><span><b>${pa}</b>indicadores com ${esc(nomeGov(A))} à frente</span><span><b>${pb}</b>com ${esc(nomeGov(B))} à frente</span></p>
        <p class="aviso-curto">Só contam os indicadores com ranking em que os dois têm dado. Leia cada linha: contar vitórias não diz quais indicadores pesam mais.</p>
        <div class="tab-wrap" style="margin-top:16px"><table class="duelo"><colgroup><col class="c-ind"><col><col></colgroup><thead><tr><th>Indicador</th><th class="v">${esc(nomeGov(A))}</th><th class="v">${esc(nomeGov(B))}</th></tr></thead><tbody>${h}</tbody></table></div>`;
    };
    sa.addEventListener("change", desenhar); sb.addEventListener("change", desenhar);
    desenhar();
    placar();
    return "Comparar dois governos";
  }

  function placar() {
    const conta = Object.fromEntries(GOV.map((g) => [g.id, { bom: 0, ruim: 0 }]));
    let corpo = "";
    for (const [, nomeTema, ids] of TEMAS) {
      if (!presentes(ids).length) continue;
      corpo += `<tr class="tema-l"><th colspan="${GOV.length + 1}">${esc(nomeTema)}</th></tr>`;
      for (const id of presentes(ids)) {
        const ind = D.indicadores[id];
        corpo += `<tr><td class="nome"><a href="#/i/${id}">${esc(CURTO[id])}</a></td>`;
        for (const g of GOV) {
          const r = ind.resumo[g.id];
          if (!r) { corpo += '<td><span class="mudo">·</span></td>'; continue; }
          if (r.avaliacao) conta[g.id][r.avaliacao]++;
          const cls = !ind.direcao ? "sem" : r.avaliacao === "bom" ? "bom" : r.avaliacao === "ruim" ? "ruim" : "meio";
          const dica = `${g.nome}, ${CURTO[id]}: ${fmt(resumoFmt(ind), r.valor)}${r.parcial ? " (parcial)" : ""}${r.posicao ? `, ${r.posicao}º de ${r.total}` : ""}`;
          corpo += `<td title="${esc(dica)}"><span class="pt ${cls}" tabindex="0" role="img" aria-label="${esc(dica)}"></span></td>`;
        }
        corpo += "</tr>";
      }
    }
    $("#placar").innerHTML = `<thead><tr><th></th>${GOV.map((g) => `<th><a href="#/g/${g.id}">${esc(g.nome)}</a><small>${g.inicio.slice(0, 4)}</small></th>`).join("")}</tr>
      <tr class="total"><td class="nome">Total de ✓ e ✕</td>${GOV.map((g) => `<td><span class="cont bom">${conta[g.id].bom}</span> <span class="cont ruim">${conta[g.id].ruim}</span></td>`).join("")}</tr></thead><tbody>${corpo}</tbody>`;
  }

  /* ---------- calculadora ---------- */
  const MOEDAS = [
    ["1986-02-28", "Cruzeiro", "Cr$"], ["1989-01-16", "Cruzado", "Cz$"], ["1990-03-16", "Cruzado Novo", "NCz$"],
    ["1993-08-01", "Cruzeiro", "Cr$"], ["1994-07-01", "Cruzeiro Real", "CR$"], ["9999-12-31", "Real", "R$"],
  ];
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const moedaDo = (ym) => MOEDAS.find(([ate]) => `${ym}-15` < ate);
  const paraReais = (valor, ym) => D.calculadora.trocas.reduce((v, t) => (`${ym}-15` < t.data ? v / t.fator : v), valor);

  function paginaCalculadora(main) {
    main.innerHTML = `<div class="pagina estreita">
      <h1>Quanto valia de verdade?</h1>
      <p class="lede-pag">“A gasolina custava R$ 0,50.” Pode ser verdade, mas R$ 0,50 de 1995 não é R$ 0,50 de hoje. Digite um valor e o mês: a conta mostra o valor corrigido pela inflação e quanto ele pesava no salário mínimo da época.</p>
      <form class="calc" id="calc" onsubmit="return false">
        <label>Valor em <span id="calc-moeda"></span><input id="calc-valor" inputmode="decimal" autocomplete="off"></label>
        <label>Mês<select id="calc-mes"></select></label>
        <label>Ano<select id="calc-ano"></select></label>
      </form>
      <div class="calc-res" id="calc-res" aria-live="polite"></div></div>`;
    const C = D.calculadora;
    const anos = [...new Set(C.meses.map((m) => m.slice(0, 4)))];
    const selAno = $("#calc-ano"), selMes = $("#calc-mes");
    selAno.innerHTML = anos.map((a) => `<option>${a}</option>`).join("");
    selMes.innerHTML = MESES.map((m, i) => `<option value="${String(i + 1).padStart(2, "0")}">${m}</option>`).join("");
    selAno.value = "1995"; selMes.value = "01";
    $("#calc-valor").value = "0,50";
    const smHoje = [...C.salario].reverse().find((v) => v != null);
    const calc = () => {
      const ym = `${selAno.value}-${selMes.value}`;
      const i = C.meses.indexOf(ym);
      const moeda = moedaDo(ym);
      $("#calc-moeda").textContent = `${moeda[1]} (${moeda[2]})`;
      const bruto = $("#calc-valor").value.trim();
      const v = parseFloat(bruto.includes(",") ? bruto.replace(/\./g, "").replace(",", ".") : bruto);
      const out = $("#calc-res");
      if (i < 0 || !(v > 0)) { out.innerHTML = '<p class="calc-nota">Digite um valor maior que zero e escolha um mês com dado (a série começa em 1985).</p>'; return; }
      const reais = paraReais(v, ym);
      const hoje = reais / C.indice[i];
      const sm = C.salario[i];
      const pct = sm ? (reais / sm) * 100 : null;
      const casas = pct != null && pct < 1 ? 2 : 1;
      const quando = `${MESES[+selMes.value - 1]}/${selAno.value}`;
      out.innerHTML = `
        <div class="calc-card"><span>Corrigido pela inflação (IPCA)</span><b>${F.moeda(hoje)}</b><small>em reais de ${esc(C.ref)}</small></div>
        ${pct != null ? `<div class="calc-card"><span>Peso no salário mínimo de ${quando}</span><b>${nf(casas, casas).format(pct)}%</b><small>o mínimo era ${moeda[2]} ${nf(2, 2).format(sm * (v / reais))}</small></div>
        <div class="calc-card"><span>O mesmo peso no mínimo de hoje</span><b>${F.moeda((pct / 100) * smHoje)}</b><small>${nf(casas, casas).format(pct)}% de ${F.moeda(smHoje)}</small></div>` : ""}
        <p class="calc-nota">${moeda[2] !== "R$" ? `Valor convertido de ${esc(moeda[1])} para reais pelos fatores oficiais das trocas de moeda. ` : ""}As contas respondem perguntas diferentes: a primeira diz quanto aquilo custaria hoje se acompanhasse a inflação; as outras dizem quanto pesava no bolso de quem ganhava o mínimo.</p>`;
    };
    $("#calc").addEventListener("input", calc);
    $("#calc").addEventListener("change", calc);
    calc();
    return "Calculadora";
  }

  /* ---------- metodologia ---------- */
  function paginaMetodologia(main) {
    main.innerHTML = `<div class="pagina estreita texto">
      <h1>Como calculamos</h1>
      <p class="lede-pag">As regras valem igualmente para todos os governos. Os números mostram o que aconteceu durante cada governo, não o que cada governo causou.</p>

      <h2>Quem fica em 1º</h2>
      <ul>
        <li><strong>Maior é melhor:</strong> crescimento do PIB e do PIB per capita, ganho real do salário mínimo, litros de gasolina por salário, aumento da expectativa de vida e da taxa de matrícula no ensino superior.</li>
        <li><strong>Menor é melhor:</strong> desemprego, inflação, peso da cesta básica no salário, preço real da gasolina, extrema pobreza, desigualdade, mortalidade infantil, analfabetismo, homicídios, desmatamento e focos de queimada.</li>
        <li><strong>Sem ranking:</strong> dólar, investimento público em saúde e em educação, universidades federais, cidades com ensino federal, Bolsa Família, leitos do SUS e Mapa da Fome. Câmbio alto ajuda exportadores e encarece importados; investimento é meio, e o resultado aparece nos indicadores de saúde e educação; a FAO não mede abaixo de 2,5%, então não dá para comparar quem já estava fora do Mapa da Fome.</li>
        <li>Entre os governos com dado, o quarto melhor (arredondado para cima) recebe ✓ e o quarto pior recebe ✕. Com 12 governos, são 3 de cada lado. ✓ e ✕ não dizem se o número subiu ou desceu, só se o resultado ficou entre os melhores ou os piores.</li>
        <li>Um governo só entra no ranking de um indicador se a série cobrir pelo menos 75% do período dele. Lula 3 entra com os dados até agora, marcado com *.</li>
      </ul>

      <h2>Ritmo, não nível</h2>
      <p>Mortalidade infantil, expectativa de vida, analfabetismo, ensino superior, extrema pobreza e desigualdade mudam devagar ao longo de décadas. Comparar o nível premiaria quem governou depois. Por isso o ranking mede quanto o indicador melhorou ou piorou por ano durante cada governo, do ano anterior à posse até o último ano do mandato. Extrema pobreza, mortalidade infantil e analfabetismo usam a variação percentual, para não favorecer quem começou de um patamar mais alto. Gini, expectativa de vida e ensino superior usam a variação em pontos. Lacunas de até 2 anos são preenchidas por interpolação linear; lacunas maiores deixam o governo sem resultado.</p>

      <h2>Como cada número vai para um governo</h2>
      <ul>
        <li><strong>Dados mensais:</strong> o mês pertence a quem governava no dia 15. Nos dois impeachments, o vice entra na data em que assumiu como interino: Itamar em 02/10/1992 e Temer em 12/05/2016.</li>
        <li><strong>Dados anuais:</strong> o ano é dividido na proporção dos dias de cada governo. Nos gráficos, o ano aparece na faixa de quem governou mais dias.</li>
        <li><strong>Inflação:</strong> média anual equivalente ao IPCA acumulado em todos os meses do mandato.</li>
        <li><strong>Salário mínimo:</strong> média do poder de compra nos últimos 12 meses do governo comparada com a dos 12 meses anteriores à posse. Médias evitam as distorções da hiperinflação.</li>
        <li><strong>PIB per capita:</strong> de 1997 a 2023, a variação em volume do PIB per capita publicada pelo IBGE (Contas Nacionais). Fora desses anos, crescimento real do PIB descontado o crescimento da população estimada ou projetada pelo IBGE.</li>
        <li><strong>Desmatamento:</strong> taxa PRODES/INPE da Amazônia Legal. O ano PRODES vai de agosto a julho, então o PRODES 2023 inclui agosto a dezembro de 2022.</li>
        <li><strong>Moedas antes do Real:</strong> de 1986 a 1994 o Brasil trocou de moeda cinco vezes. Salário mínimo e cesta básica são convertidos para reais pelos fatores oficiais de cada troca e depois corrigidos pelo IPCA.</li>
        <li><strong>Valores em reais de hoje:</strong> salário mínimo e gasolina são corrigidos pelo IPCA até o último mês divulgado. O dólar aparece em valor nominal, só a partir do Plano Real.</li>
      </ul>

      <h2>Limites</h2>
      <ul>
        <li>Correlação não é causalidade: um indicador melhor ou pior não prova efeito de política de governo.</li>
        <li>Governos têm durações diferentes. Médias de períodos curtos oscilam mais.</li>
        <li>A cesta básica é a de São Paulo (DIEESE), comparada ao salário mínimo bruto.</li>
        <li>Focos de queimada vêm do satélite de referência do INPE, com série comparável desde 2003. Contagem de focos não é área queimada.</li>
        <li>A pesquisa de preços de combustíveis da ANP começa em julho de 2001 e não foi feita entre 18/8 e 17/10/2020.</li>
        <li>Fome, pobreza, mortalidade, expectativa de vida e educação vêm de bases da ONU (FAO, OMS, UNESCO, IGME) publicadas pelo Banco Mundial e calculadas com dados do IBGE, INEP e Ministério da Saúde, quando não há série oficial brasileira comparável.</li>
        <li>Fontes oficiais revisam dados. A cada atualização o site baixa as séries de novo.</li>
      </ul>

      <h2>Períodos de governo</h2>
      <div class="tab-wrap"><table class="tab-simples"><thead><tr><th>Período</th><th>Presidente</th><th>Início</th><th>Fim</th></tr></thead><tbody>
        ${GOV.map((g) => `<tr><td><a href="#/g/${g.id}">${esc(g.nome)}</a></td><td>${esc(g.presidente)}</td><td>${dataBR(g.inicio)}</td><td>${g.id === "lula3" ? "em curso" : dataBR(g.fim)}</td></tr>`).join("")}</tbody></table></div>

      <h2>Situação das fontes nesta atualização</h2>
      <p>“Cópia anterior” quer dizer que a fonte não respondeu nesta atualização e o site manteve os últimos dados válidos.</p>
      <div class="tab-wrap" style="margin-top:12px"><table class="tab-simples"><thead><tr><th>Série</th><th>Fonte</th><th>Situação</th><th>Último dado</th></tr></thead><tbody>
        ${D.fontes.map((s) => `<tr><td>${esc(s.indicador)}</td><td>${esc(s.fonte)}</td><td class="${s.status === "atualizado" ? "st-ok" : "st-alerta"}">${esc(s.status)}</td><td>${esc(s.ultima_obs || "—")}</td></tr>`).join("")}</tbody></table></div>
    </div>`;
    return "Como calculamos";
  }

  /* ---------- gráfico ano a ano ---------- */
  let grafico = null, indAtual = null;
  function faixas(labels, largura) {
    const out = {};
    let i = 0, n = 0;
    while (i < labels.length) {
      const g = govDoPonto(labels[i]);
      let j = i;
      while (j + 1 < labels.length && govDoPonto(labels[j + 1]) === g) j++;
      if (g) {
        const px = ((j - i + 1) / labels.length) * largura;
        const nome = nomeGov(g);
        out[`f${n}`] = {
          type: "box", xMin: i - 0.5, xMax: j + 0.5, drawTime: "beforeDatasetsDraw",
          backgroundColor: n % 2 ? cor("--faixa-b") : cor("--faixa-a"), borderWidth: 0,
          label: {
            display: px >= 16, content: px < nome.length * 6.8 + 8 ? ABREV[g] : nome,
            position: { x: "center", y: "start" }, color: cor("--tinta-3"),
            font: { family: "Archivo", size: 11, weight: 600 }, padding: 4,
          },
        };
        n++;
      }
      i = j + 1;
    }
    return out;
  }

  function marcos(labels, largura, anual) {
    const out = {};
    let n = 0;
    for (const [k, m] of (D.marcos || []).entries()) {
      const i = labels.indexOf(anual ? m.data.slice(0, 4) : m.data);
      if (i < 0) continue;
      out[`m${k}`] = {
        type: "line", xMin: i, xMax: i, borderColor: cor("--acento"), borderWidth: 1, borderDash: [3, 3], drawTime: "afterDatasetsDraw",
        label: { display: largura >= 420, content: m.curto, position: "start", yAdjust: n % 2 ? -20 : -4,
                 backgroundColor: cor("--superficie"), color: cor("--acento"), font: { family: "Archivo", size: 10.5, weight: 600 }, padding: { x: 3, y: 1 } },
      };
      n++;
    }
    return out;
  }

  function desenharGrafico() {
    const canvas = document.getElementById("g-serie");
    if (!canvas || !indAtual || !window.Chart) return;
    grafico?.destroy();
    const ind = indAtual;
    Chart.defaults.font.family = "Archivo, system-ui, sans-serif";
    Chart.defaults.color = cor("--tinta-2");
    const labels = ind.serie.map((p) => p.x), valores = ind.serie.map((p) => p.y);
    const barra = ind.grafico === "barra", pontos = ind.grafico === "linha_anual", log = ind.escala === "log";
    const anoAtual = String(new Date().getFullYear());
    const parcial = (x) => barra && x === anoAtual;
    const serie = cor("--serie"), suave = cor("--serie-suave");
    const largura = canvas.parentElement.clientWidth - 56;
    const mensal = labels.length && labels[0].length > 4;
    const span = +labels.at(-1).slice(0, 4) - +labels[0].slice(0, 4);
    const passo = largura < 420 ? (span > 25 ? 10 : 5) : largura < 700 ? (span > 25 ? 5 : 4) : span > 25 ? 5 : 2;
    const limite = ind.limite ? { lim: { type: "line", yMin: ind.limite.valor, yMax: ind.limite.valor, borderColor: cor("--ruim"), borderWidth: 1.5, borderDash: [6, 4], drawTime: "afterDatasetsDraw",
      label: { display: true, content: ind.limite.rotulo, position: "end", yAdjust: -10, backgroundColor: cor("--superficie"), color: cor("--ruim"), font: { family: "Archivo", size: 11, weight: 600 }, padding: { x: 4, y: 2 } } } } : {};
    grafico = new Chart(canvas, {
      type: barra ? "bar" : "line",
      data: { labels, datasets: [{
        data: valores,
        backgroundColor: barra ? labels.map((x) => (parcial(x) ? suave : serie)) : serie,
        borderColor: serie, borderWidth: barra ? 0 : 2, borderRadius: barra ? 2 : 0, maxBarThickness: 18,
        categoryPercentage: 0.86, barPercentage: 0.92,
        pointRadius: pontos ? 3 : 0, pointBackgroundColor: serie, pointHoverRadius: 5, pointHoverBorderWidth: 2,
        pointHoverBackgroundColor: serie, pointHoverBorderColor: cor("--superficie"), spanGaps: pontos,
        segment: pontos ? { borderDash: (c) => (c.p0.skip || c.p1.skip ? [4, 4] : undefined) } : undefined,
      }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: 18 } },
        scales: {
          x: { grid: { display: false }, border: { color: cor("--linha-forte") },
               ticks: { autoSkip: false, maxRotation: 0, color: cor("--tinta-3"), font: { size: 12 },
                        callback(v) { const x = labels[v]; if (mensal && !x.endsWith("-01")) return null; const a = +x.slice(0, 4); return a % passo === 0 ? String(a) : null; } } },
          y: { type: log ? "logarithmic" : "linear", beginAtZero: barra && !log, grace: log ? undefined : "8%",
               max: log ? Math.max(...valores) * 4 : undefined,
               grid: { color: (c) => (c.tick.value === 0 ? cor("--tinta-3") : cor("--grade")) }, border: { display: false },
               ticks: { color: cor("--tinta-3"), font: { size: 12 }, maxTicksLimit: 6,
                        callback(v) { if (log && ![1, 10, 100, 1000, 10000].includes(v)) return null; return fmt(ind.formato === "pct" ? "pct_simples" : ind.formato, v); } } },
        },
        plugins: {
          legend: { display: false },
          annotation: { annotations: { ...faixas(labels, largura), ...marcos(labels, largura, !mensal), ...limite } },
          tooltip: {
            backgroundColor: cor("--superficie"), titleColor: cor("--tinta"), bodyColor: cor("--tinta-2"),
            borderColor: cor("--linha-forte"), borderWidth: 1, padding: 10, displayColors: false,
            titleFont: { weight: 650 }, bodyFont: { size: 13 },
            callbacks: {
              title: (it) => { const x = it[0].label; const q = x.length > 4 ? `${x.slice(5, 7)}/${x.slice(0, 4)}` : x; const g = nomeGov(govDoPonto(x)); return g ? `${q}, ${g}` : q; },
              label: (it) => {
                const linhas = [fmt(ind.formato, it.parsed.y) + (parcial(it.label) ? (ind.notas ? " (estimativa)" : " (ano incompleto)") : "")];
                const n = ind.serie[it.dataIndex]?.n;
                if (n != null) linhas[0] += " em valores de hoje", linhas.push(`R$ ${nf(2, 2).format(n)} na época`);
                return linhas;
              },
            },
          },
        },
      },
    });
  }

  let tRes, larguraAnterior = innerWidth;
  addEventListener("resize", () => {
    if (innerWidth === larguraAnterior) return;
    larguraAnterior = innerWidth;
    clearTimeout(tRes); tRes = setTimeout(() => { desenharGrafico(); if (document.querySelector(".regua-faixa")) ajustarRegua(); }, 200);
  });
})();
