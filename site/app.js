/* Painel Brasil — renderização do site a partir de data/painel.json */
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
  const ORDEM = TEMAS.flatMap((t) => t[2]);
  const CURTO = {
    pib_crescimento: ["PIB", "cresc. médio/ano"],
    pib_per_capita: ["PIB per capita", "cresc. médio/ano"],
    ipca: ["Inflação", "média/ano"],
    salario_minimo: ["Salário mínimo", "ganho real"],
    cesta_sp: ["Cesta básica SP", "% do mínimo"],
    gasolina: ["Gasolina", "R$/l de hoje"],
    gasolina_litros: ["Gasolina por salário", "litros/salário mínimo"],
    queimadas: ["Queimadas", "focos/ano"],
    desmatamento: ["Desmatamento Amazônia", "km²/ano"],
    dolar: ["Dólar", "média R$"],
    fome: ["Mapa da Fome", "pontos acima de 2,5%"],
    pobreza: ["Extrema pobreza", "variação %/ano"],
    gini: ["Desigualdade", "Gini, variação/ano"],
    mortalidade_infantil: ["Mortalidade infantil", "variação %/ano"],
    expectativa_vida: ["Expectativa de vida", "anos, variação/ano"],
    gasto_saude: ["Gasto em saúde", "% do PIB"],
    desemprego: ["Desemprego", "média, % (desde 2012)"],
    homicidios: ["Homicídios", "por 100 mil hab."],
    bolsa_familia: ["Bolsa Família", "benefícios, média"],
    leitos_sus: ["Leitos SUS", "por 10 mil hab."],
    analfabetismo: ["Analfabetismo", "variação %/ano"],
    universidades_federais: ["Universidades federais", "novas no governo"],
    municipios_federais: ["Cidades com ensino federal", "novas no governo"],
    ensino_superior: ["Matrícula no ensino superior (taxa bruta)", "variação/ano"],
    gasto_educacao: ["Gasto em educação", "% do PIB"],
  };

  // Critério do ranking em palavras e o que o número-resumo significa. Evita que a pessoa leia
  // "✓" como "subiu" ou confunda média com variação.
  const CRIT = {
    pib_crescimento: ["maior crescimento médio do PIB", "menor crescimento médio do PIB", "Média do crescimento anual do PIB durante o governo."],
    pib_per_capita: ["maior crescimento médio da riqueza por pessoa", "menor crescimento médio da riqueza por pessoa", "Média do crescimento anual do PIB por pessoa durante o governo."],
    desemprego: ["menor desemprego médio", "maior desemprego médio", "Média da taxa de desemprego durante o governo."],
    dolar: null,
    ipca: ["menor inflação média", "maior inflação média", "Inflação média por ano durante o governo."],
    salario_minimo: ["maior ganho de poder de compra do mínimo", "menor ganho (ou perda) de poder de compra do mínimo", "Quanto o poder de compra do salário mínimo mudou do começo ao fim do governo."],
    cesta_sp: ["cesta básica consumia a menor parte do salário mínimo", "cesta básica consumia a maior parte do salário mínimo", "Em média, quanto do salário mínimo a cesta básica de SP consumia."],
    gasolina: ["gasolina mais barata, em valores de hoje", "gasolina mais cara, em valores de hoje", "Preço médio do litro no governo, corrigido para reais de hoje."],
    gasolina_litros: ["mais litros por salário mínimo", "menos litros por salário mínimo", "Em média, quantos litros de gasolina um salário mínimo comprava."],
    fome: null,
    pobreza: ["queda mais rápida da extrema pobreza", "queda mais lenta (ou alta) da extrema pobreza", "Quanto a extrema pobreza caiu (−) ou subiu (+) por ano, em %."],
    gini: ["queda mais rápida da desigualdade", "queda mais lenta (ou alta) da desigualdade", "Quanto o índice de Gini caiu (−) ou subiu (+) por ano, em pontos."],
    bolsa_familia: null,
    mortalidade_infantil: ["queda mais rápida da mortalidade infantil", "queda mais lenta (ou alta) da mortalidade infantil", "Quanto a mortalidade infantil caiu (−) ou subiu (+) por ano, em %."],
    expectativa_vida: ["maior aumento da expectativa de vida", "menor aumento (ou queda) da expectativa de vida", "Quantos anos de vida esperada foram ganhos (+) ou perdidos (−) por ano."],
    leitos_sus: null, gasto_saude: null, gasto_educacao: null, universidades_federais: null, municipios_federais: null,
    analfabetismo: ["queda mais rápida do analfabetismo", "queda mais lenta do analfabetismo", "Quanto o analfabetismo caiu (−) por ano, em %."],
    ensino_superior: ["maior aumento da taxa bruta de matrícula", "menor aumento da taxa bruta de matrícula", "Quantos pontos a taxa bruta de matrícula no ensino superior subiu por ano."],
    homicidios: ["menor taxa média de homicídios", "maior taxa média de homicídios", "Média da taxa de homicídios por 100 mil habitantes no governo."],
    desmatamento: ["menos desmatamento por ano", "mais desmatamento por ano", "Média da área desmatada por ano na Amazônia durante o governo."],
    queimadas: ["menos focos de queimada por ano", "mais focos de queimada por ano", "Média de focos de queimada por ano durante o governo."],
  };
  const explica = (id, ind) => (CRIT[id] ? CRIT[id][2] : `${ind.resumo_rotulo[0].toUpperCase()}${ind.resumo_rotulo.slice(1)}.`);

  const nf = (min, max) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max });
  const F = {
    pct: (v) => (v > 0 ? "+" : "") + nf(Math.abs(v) >= 100 ? 0 : 1, Math.abs(v) >= 100 ? 0 : 1).format(v) + "%",
    pct_simples: (v) => nf(Math.abs(v) >= 100 ? 0 : 1, Math.abs(v) >= 100 ? 0 : 1).format(v) + "%",
    moeda: (v) => "R$ " + nf(2, 2).format(v),
    moeda_usd: (v) => "US$ " + nf(0, 0).format(v),
    inteiro: (v) => nf(0, 0).format(Math.round(v)),
    decimal: (v) => nf(1, 1).format(v),
    delta: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(2, 2).format(Math.abs(v)) + "/ano",
    delta_pct: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(1, 1).format(Math.abs(v)) + "% ao ano",
    inteiro_delta: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(0, 0).format(Math.abs(Math.round(v))),
    moeda_int: (v) => "R$ " + nf(0, 0).format(v),
    anos_mapa: (v) => `${v} ${v === 1 ? "ponto" : "pontos"} acima de 2,5%`,
  };
  const fmt = (tipo, v) => (v == null || Number.isNaN(v) ? "—" : (F[tipo] || F.pct_simples)(v));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const el = (tag, attrs = {}, html = "") => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (html) e.innerHTML = html;
    return e;
  };
  const dataBR = (iso) => iso.split("-").reverse().join("/");

  /* ---------- tema ---------- */
  const raiz = document.documentElement;
  try { const t = localStorage.getItem("tema"); if (t) raiz.dataset.theme = t; } catch (_) {}
  document.getElementById("tema").addEventListener("click", () => {
    const escuro = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    raiz.dataset.theme = escuro ? "light" : "dark";
    try { localStorage.setItem("tema", raiz.dataset.theme); } catch (_) {}
    redesenhar();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redesenhar);
  const cor = (n) => getComputedStyle(raiz).getPropertyValue(n).trim();

  /* ---------- governo de cada ponto ---------- */
  let GOV = [];
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
  const gov = (id) => GOV.find((g) => g.id === id);
  const nomeGov = (id) => gov(id)?.nome ?? "";

  /* ---------- carga ---------- */
  let D = null;
  const graficos = [];
  fetch("data/painel.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((d) => { D = d; GOV = d.governos; montar(); })
    .catch((e) => {
      document.getElementById("lista-indicadores").innerHTML =
        `<p class="indisponivel">Não foi possível carregar os dados (${esc(e.message)}).</p>`;
    });

  const indicadores = () => ORDEM.filter((id) => D.indicadores[id]).map((id) => [id, D.indicadores[id]]);
  const resumoFmt = (ind) => ind.resumo_formato || ind.formato;
  const ast = (r) => (r?.parcial ? '<span class="parcial-tag">*</span>' : "");

  function montar() {
    document.getElementById("gerado-em").textContent =
      new Date(D.gerado_em).toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short" });
    linhaDoTempo();
    calculadora();
    cardsGoverno();
    tabelaComparativo();
    tabelaGovernos();
    tabelaStatus();
    const lista = document.getElementById("lista-indicadores");
    const chips = document.getElementById("chips");
    for (const [tema, nome, ids] of TEMAS) {
      const presentes = ids.filter((id) => D.indicadores[id]);
      if (!presentes.length) continue;
      chips.append(el("a", { href: `#tema-${tema}`, class: "chip-tema" }, esc(nome)));
      lista.append(el("h3", { class: "tema-titulo", id: `tema-${tema}` }, esc(nome)));
      for (const id of presentes) lista.append(cartaoIndicador(id, D.indicadores[id]));
    }
    redesenhar();
  }

  /* ---------- linha do tempo ---------- */
  function linhaDoTempo() {
    const box = document.getElementById("linha-tempo");
    const t0 = Date.parse(GOV[0].inicio), t1 = Date.now();
    for (const g of GOV) {
      const fim = Math.min(Date.parse(g.fim), t1);
      const seg = el("a", { class: "lt-seg", href: `#gov-${g.id}`, title: `${g.nome}: ${g.presidente}` });
      seg.style.flex = `${(fim - Date.parse(g.inicio)) / (t1 - t0)} 1 0`;
      seg.innerHTML = `<span class="lt-nome">${esc(g.nome)}</span><span class="lt-anos">${g.inicio.slice(0, 4)}</span>`;
      box.append(seg);
    }
  }

  /* ---------- calculadora ---------- */
  const MOEDAS = [
    ["1986-02-28", "Cruzeiro", "Cr$"], ["1989-01-16", "Cruzado", "Cz$"], ["1990-03-16", "Cruzado Novo", "NCz$"],
    ["1993-08-01", "Cruzeiro", "Cr$"], ["1994-07-01", "Cruzeiro Real", "CR$"], ["9999-12-31", "Real", "R$"],
  ];
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const moedaDo = (ym) => MOEDAS.find(([ate]) => `${ym}-15` < ate);
  const paraReais = (valor, ym) =>
    D.calculadora.trocas.reduce((v, t) => (`${ym}-15` < t.data ? v / t.fator : v), valor);

  function calculadora() {
    const C = D.calculadora;
    const box = document.getElementById("calc");
    if (!C || !box) return;
    const anos = [...new Set(C.meses.map((m) => m.slice(0, 4)))];
    const selAno = box.querySelector("#calc-ano"), selMes = box.querySelector("#calc-mes");
    selAno.innerHTML = anos.map((a) => `<option>${a}</option>`).join("");
    selMes.innerHTML = MESES.map((m, i) => `<option value="${String(i + 1).padStart(2, "0")}">${m}</option>`).join("");
    selAno.value = "1995"; selMes.value = "01";
    box.querySelector("#calc-valor").value = "0,50";
    const smHoje = [...C.salario].reverse().find((v) => v != null);
    const calc = () => {
      const ym = `${selAno.value}-${selMes.value}`;
      const i = C.meses.indexOf(ym);
      const moeda = moedaDo(ym);
      box.querySelector("#calc-moeda").textContent = `${moeda[1]} (${moeda[2]})`;
      const bruto = box.querySelector("#calc-valor").value.trim();
      const v = parseFloat(bruto.includes(",") ? bruto.replace(/\./g, "").replace(",", ".") : bruto);
      const out = document.getElementById("calc-res");
      if (i < 0 || !(v > 0)) { out.innerHTML = '<p class="vazio">Escolha um mês com dado e digite um valor.</p>'; return; }
      const reais = paraReais(v, ym);
      const hoje = reais / C.indice[i];
      const sm = C.salario[i];
      const pct = sm ? (reais / sm) * 100 : null;
      const quando = `${MESES[+selMes.value - 1]}/${selAno.value}`;
      out.innerHTML = `
        <div class="calc-card"><span>Corrigido pela inflação (IPCA)</span><b>${F.moeda(hoje)}</b><small>em reais de ${esc(C.ref)}</small></div>
        ${pct != null ? `<div class="calc-card"><span>Peso no salário mínimo de ${quando}</span><b>${nf(pct < 1 ? 2 : 1, pct < 1 ? 2 : 1).format(pct)}%</b><small>o mínimo era ${moeda[2]} ${nf(2, 2).format(sm * (v / reais))}</small></div>
        <div class="calc-card"><span>O mesmo peso no salário mínimo de hoje</span><b>${F.moeda((pct / 100) * smHoje)}</b><small>${nf(pct < 1 ? 2 : 1, pct < 1 ? 2 : 1).format(pct)}% de ${F.moeda(smHoje)}</small></div>` : ""}
        <p class="calc-nota">${moeda[2] !== "R$" ? `Valor convertido de ${esc(moeda[1])} para reais pelos fatores oficiais das trocas de moeda. ` : ""}As duas contas respondem perguntas diferentes: a primeira diz quanto aquilo custaria hoje se acompanhasse a inflação; as outras dizem quanto pesava no bolso de quem ganhava o mínimo.</p>`;
    };
    box.addEventListener("input", calc);
    box.addEventListener("change", calc);
    calc();
  }

  /* ---------- cards por governo ---------- */
  function cardsGoverno() {
    const box = document.getElementById("cards-gov");
    const ctx = D.contexto || {};
    for (const g of GOV) {
      const fortes = [], fracos = [], trilhas = [];
      for (const [id, ind] of indicadores()) {
        const r = ind.resumo[g.id];
        if (!r || !r.posicao) continue;
        const valor = `${fmt(resumoFmt(ind), r.valor)}${ast(r)}`;
        const item = (lado) => `<li><span class="it-nome">${esc(CURTO[id][0])}</span>
            <span class="it-valor">${valor}</span>
            <span class="it-pos">${posTexto(ind, r, lado)}</span>
            ${trajeto(ind, r) ? `<span class="it-traj">${trajeto(ind, r)}</span>` : ""}</li>`;
        if (r.avaliacao === "bom") fortes.push(item("bom"));
        if (r.avaliacao === "ruim") fracos.push(item("ruim"));
        const x = r.total > 1 ? ((r.posicao - 1) / (r.total - 1)) * 100 : 50;
        trilhas.push(`<div class="trilha" title="${esc(ind.titulo)}: ${r.posicao}º de ${r.total}">
            <span class="tr-nome">${esc(CURTO[id][0])}</span>
            <span class="tr-pista"><span class="tr-ponto ${r.avaliacao || ""}" style="left:${x}%"></span></span></div>`);
      }
      const fim = g.id === "lula3" ? "em curso" : dataBR(g.fim);
      const card = el("article", { class: "card-gov", id: `gov-${g.id}` });
      card.innerHTML = `
        <header><h3>${esc(g.nome)}</h3><p>${esc(g.presidente)} · ${dataBR(g.inicio)} – ${fim}</p></header>
        <div class="listas">
          <div><h4 class="h-bom">✓ Entre os melhores resultados</h4>${fortes.length ? `<ul>${fortes.join("")}</ul>` : '<p class="vazio">Em nenhum indicador ficou entre os melhores.</p>'}</div>
          <div><h4 class="h-ruim">✕ Entre os piores resultados</h4>${fracos.length ? `<ul>${fracos.join("")}</ul>` : '<p class="vazio">Em nenhum indicador ficou entre os piores.</p>'}</div>
        </div>
        <p class="card-nota">Comparado em ${trilhas.length} indicadores com dado para este período. Nos demais ficou no meio da tabela.</p>
        ${ctx[g.id] ? `<details class="contexto"><summary>Contexto do período</summary><ul>${ctx[g.id].map((c) => `<li>${esc(c)}</li>`).join("")}</ul></details>` : ""}`;
      box.append(card);
    }
  }

  // Texto da posição, sem ambiguidade em empates e com o sentido real da mudança.
  function posTexto(ind, r, lado) {
    const id = Object.keys(D.indicadores).find((k) => D.indicadores[k] === ind);
    const c = CRIT[id];
    const empatados = Object.values(ind.resumo).filter((x) => x.posicao === r.posicao).length;
    const lugar = empatados > 1 ? `empatado em ${r.posicao}º de ${r.total}` : `${r.posicao}º de ${r.total}`;
    let t = c ? `${lugar} (1º = ${c[0]})` : lugar;
    if (lado === "ruim" && r.sentido === "melhorou") t += " · o indicador melhorou, só que menos que nos outros governos";
    if (lado === "bom" && r.sentido === "piorou") t += " · o indicador piorou, só que menos que nos outros governos";
    return t;
  }

  // "de X para Y": como o indicador começou e terminou dentro do governo.
  function trajeto(ind, r) {
    const f = ind.formato;
    const mudou = (a, b) => {
      if (!(a > 0) || !(b > 0)) return "";
      const p = (b / a - 1) * 100;
      if (Math.abs(p) < 0.5) return " · ficou estável";
      return ` · ${p > 0 ? "subiu" : "caiu"} ${nf(0, 0).format(Math.abs(p))}%`;
    };
    if (r.de != null && r.para != null) return `${fmt(f, r.de)} → ${fmt(f, r.para)}${r.periodo ? ` (${esc(r.periodo)})` : ""}${mudou(r.de, r.para)}`;
    const fr = ind.resumo_formato === "anos_mapa" ? f : resumoFmt(ind); // médias: início e fim na unidade do resumo
    const nivel = !ind.resumo_formato || ind.resumo_formato === "anos_mapa"; // só faz sentido dizer subiu/caiu para níveis
    if (r.inicio_val != null && r.fim_val != null)
      return `${r.inicio_ano}: ${fmt(fr, r.inicio_val)} → ${r.fim_ano}: ${fmt(fr, r.fim_val)}${nivel ? mudou(r.inicio_val, r.fim_val) : ""}`;
    return "";
  }

  /* ---------- tabela comparativa ---------- */
  function tabelaComparativo() {
    duelo();
    placar();
    document.getElementById("placar-numeros").addEventListener("change", placar);
  }

  // Compara dois governos indicador por indicador.
  function duelo() {
    const sa = document.getElementById("duelo-a"), sb = document.getElementById("duelo-b");
    const opts = GOV.map((g) => `<option value="${g.id}">${esc(g.nome)}${innerWidth > 560 ? ` (${g.inicio.slice(0, 4)}–${g.id === "lula3" ? "hoje" : g.fim.slice(0, 4)})` : ""}</option>`).join("");
    sa.innerHTML = opts; sb.innerHTML = opts;
    sa.value = GOV.at(-2).id; sb.value = GOV.at(-1).id;
    const desenhar = () => {
      const A = sa.value, B = sb.value;
      let placarA = 0, placarB = 0, h = "";
      for (const [, nomeTema, ids] of TEMAS) {
        const linhas = ids.filter((id) => D.indicadores[id]).map((id) => {
          const ind = D.indicadores[id];
          const ra = ind.resumo[A], rb = ind.resumo[B];
          let ganhador = null;
          if (ind.direcao && ra && rb && Math.abs(ra.valor - rb.valor) > 1e-9) {
            const aMelhor = ind.direcao === "maior" ? ra.valor > rb.valor : ra.valor < rb.valor;
            ganhador = aMelhor ? "A" : "B";
            aMelhor ? placarA++ : placarB++;
          }
          const cel = (r, lado) => {
            if (!r) return `<td class="du-val sem-dado">sem dado</td>`;
            const win = ganhador === lado;
            return `<td class="du-val${win ? " du-win" : ""}">${win ? '<span class="du-ic">✓</span>' : ""}<b>${fmt(resumoFmt(ind), r.valor)}${ast(r)}</b>${trajeto(ind, r) ? `<small>${trajeto(ind, r)}</small>` : ""}</td>`;
          };
          const nota = !ind.direcao ? '<small class="du-sem">sem ranking</small>' : ra && rb && !ganhador ? '<small class="du-sem">empate</small>' : "";
          return `<tr>${cel(ra, "A")}<th scope="row"><a href="#ind-${id}">${esc(ind.pergunta || ind.titulo)}</a><small>${esc(explica(id, ind))}${CRIT[id] ? ` ✓ = ${esc(CRIT[id][0])}` : ""}</small>${nota}</th>${cel(rb, "B")}</tr>`;
        });
        if (linhas.length) h += `<tr class="du-tema"><td colspan="3">${esc(nomeTema)}</td></tr>${linhas.join("")}`;
      }
      const nA = nomeGov(A), nB = nomeGov(B);
      document.getElementById("duelo").innerHTML = A === B ? '<p class="vazio">Escolha dois governos diferentes.</p>' : `
        <div class="du-placar"><div><b>${placarA}</b><span>indicadores em que ${esc(nA)} foi melhor</span></div>
          <div><b>${placarB}</b><span>indicadores em que ${esc(nB)} foi melhor</span></div></div>
        <p class="du-aviso">O placar só conta os indicadores em que os dois têm dado e há ranking. Contar vitórias não diz quais indicadores pesam mais, e o resumo de cada governo é um cálculo do site com regras declaradas, não uma conclusão das fontes. Leia cada linha.</p>
        <div class="tabela-rolagem"><table class="duelo"><thead><tr><th>${esc(nA)}</th><th></th><th>${esc(nB)}</th></tr></thead><tbody>${h}</tbody></table></div>`;
    };
    sa.addEventListener("change", desenhar); sb.addEventListener("change", desenhar);
    desenhar();
  }

  // Placar visual: uma bolinha por indicador e governo.
  function placar() {
    const t = document.getElementById("tabela-comparativo");
    const numeros = document.getElementById("placar-numeros").checked;
    const conta = Object.fromEntries(GOV.map((g) => [g.id, { bom: 0, ruim: 0 }]));
    let corpo = "";
    for (const [, nomeTema, ids] of TEMAS) {
      const presentes = ids.filter((id) => D.indicadores[id]);
      if (!presentes.length) continue;
      corpo += `<tr class="linha-tema"><th colspan="${GOV.length + 1}">${esc(nomeTema)}</th></tr>`;
      for (const id of presentes) {
        const ind = D.indicadores[id];
        corpo += `<tr><td class="gov"><a href="#ind-${id}">${esc(CURTO[id][0])}</a><small>${esc(CURTO[id][1])}</small></td>`;
        for (const g of GOV) {
          const r = ind.resumo[g.id];
          if (!r) { corpo += '<td class="pl"><span class="pl-vazio" title="sem dado">·</span></td>'; continue; }
          if (r.avaliacao) conta[g.id][r.avaliacao]++;
          const cls = !ind.direcao ? "pl-sem" : r.avaliacao === "bom" ? "pl-bom" : r.avaliacao === "ruim" ? "pl-ruim" : "pl-meio";
          const dica = `${g.nome} · ${ind.titulo}: ${fmt(resumoFmt(ind), r.valor)}${r.parcial ? " (parcial)" : ""}${r.posicao ? ` · ${r.posicao}º de ${r.total}` : ""}`;
          corpo += numeros
            ? `<td class="pl pl-num ${cls}" title="${esc(dica)}">${fmt(resumoFmt(ind), r.valor)}${ast(r)}</td>`
            : `<td class="pl" title="${esc(dica)}"><span class="pl-dot ${cls}" tabindex="0" aria-label="${esc(dica)}"></span></td>`;
        }
        corpo += "</tr>";
      }
    }
    const cab = `<thead><tr><th></th>${GOV.map((g) => `<th><a href="#gov-${g.id}">${esc(g.nome)}</a><small>${g.inicio.slice(0, 4)}</small></th>`).join("")}</tr>
      <tr class="pl-resumo"><th>Total</th>${GOV.map((g) => `<td><span class="pl-cont bom">${conta[g.id].bom}</span><span class="pl-cont ruim">${conta[g.id].ruim}</span></td>`).join("")}</tr></thead>`;
    t.innerHTML = cab + `<tbody>${corpo}</tbody>`;
  }

  function tabelaGovernos() {
    let h = '<div class="tabela-rolagem"><table><thead><tr><th>Período</th><th style="text-align:left">Presidente</th><th>Início</th><th>Fim</th></tr></thead><tbody>';
    for (const g of GOV) {
      h += `<tr><td>${esc(g.nome)}</td><td style="text-align:left">${esc(g.presidente)}</td><td class="num">${dataBR(g.inicio)}</td><td class="num">${g.id === "lula3" ? "em curso" : dataBR(g.fim)}</td></tr>`;
    }
    document.getElementById("tabela-governos").innerHTML = h + "</tbody></table></div>";
  }

  function tabelaStatus() {
    let h = "<thead><tr><th>Série</th><th style='text-align:left'>Fonte</th><th>Situação</th><th>Último dado</th></tr></thead><tbody>";
    for (const s of D.fontes) {
      const ok = s.status === "atualizado";
      h += `<tr><td>${esc(s.indicador)}</td><td style="text-align:left">${esc(s.fonte)}</td><td class="${ok ? "st-ok" : "st-alerta"}">${esc(s.status)}</td><td class="num">${esc(s.ultima_obs || "—")}</td></tr>`;
    }
    document.getElementById("tabela-status").innerHTML = h + "</tbody>";
  }

  /* ---------- cartão de indicador ---------- */
  function cartaoIndicador(id, ind) {
    const c = el("article", { class: "ind", id: `ind-${id}` });
    const m = ind.melhor && ind.resumo[ind.melhor], p = ind.pior && ind.resumo[ind.pior];
    const destaque = m && p ? `<div class="hero">
        <div class="hero-item bom"><span class="hero-rot">✓ Melhor resultado · ${esc(CRIT[id] ? CRIT[id][0] : "")}</span><b>${esc(nomeGov(ind.melhor))}</b><span class="hero-val">${fmt(resumoFmt(ind), m.valor)}${ast(m)}</span>${trajeto(ind, m) ? `<span class="hero-traj">${trajeto(ind, m)}</span>` : ""}</div>
        <div class="hero-item ruim"><span class="hero-rot">✕ Pior resultado · ${esc(CRIT[id] ? CRIT[id][1] : "")}</span><b>${esc(nomeGov(ind.pior))}</b><span class="hero-val">${fmt(resumoFmt(ind), p.valor)}${ast(p)}</span>${trajeto(ind, p) ? `<span class="hero-traj">${trajeto(ind, p)}</span>` : ""}${p.sentido === "melhorou" ? '<span class="hero-traj">melhorou no período, mas menos que os outros governos</span>' : ""}</div>
      </div>` : "";
    c.innerHTML = `
      <p class="ind-kicker">${esc(ind.titulo)} · <span>${esc(ind.unidade)}</span></p>
      <h3>${esc(ind.pergunta || ind.titulo)}</h3>
      <p class="ind-desc">${esc(ind.descricao)}</p>
      <p class="ind-explica"><b>Como comparamos os governos:</b> ${esc(explica(id, ind))} ${CRIT[id] ? `Melhor resultado = ${esc(CRIT[id][0])}.` : "Este indicador não tem ranking."}</p>
      ${ind.aviso ? `<p class="ind-aviso" role="note"><b>Antes de tirar conclusões:</b> ${esc(ind.aviso)}</p>` : ""}
      ${destaque}
      ${faixaMapaFome(ind)}
      <div class="ind-graficos">
        <figure class="fig-serie"><figcaption>Ano a ano</figcaption>
          <div class="grafico"><canvas class="c-serie" role="img" aria-label="${esc(ind.titulo)} ao longo do tempo, com faixas por governo"></canvas></div>
          <p class="legenda-marcos">${legendaMarcos(ind.serie.map((p) => p.x), ind.serie[0]?.x.length === 4)}</p></figure>
        <figure class="fig-rank"><figcaption>${ind.direcao ? `Do melhor para o pior (1º = ${esc(CRIT[id] ? CRIT[id][0] : "melhor")})` : `Por governo, em ordem cronológica (sem ranking)`}</figcaption>
          <div class="grafico grafico-rank"><canvas class="c-rank" role="img" aria-label="${esc(ind.titulo)} por governo"></canvas></div></figure>
      </div>
      <p class="fonte">Fonte: <a href="${esc(ind.fonte_url)}" target="_blank" rel="noopener">${esc(ind.fonte)}</a> · <button type="button" class="baixar-csv" data-id="${esc(id)}">Baixar dados e cálculo (CSV)</button></p>
      ${ind.notas ? `<details class="notas"><summary>Valor de cada ano e o documento do INPE de onde ele saiu</summary><ul>${
        ind.notas.map((n) => `<li><b>${n.ano}</b>: ${Math.round(n.valor).toLocaleString("pt-BR")} km² (taxa ${n.tipo === "consolidada" ? "consolidada" : "estimada, ainda sem consolidação"}) · <a href="${esc(n.url)}" target="_blank" rel="noopener">${/apresentacao/.test(n.url) ? "apresentação oficial do INPE (PDF)" : "nota técnica do INPE (PDF)"}</a></li>`).join("")
      }</ul></details>` : ""}`;
    c._ind = ind;
    return c;
  }

  /* ---------- download CSV: série + resumo por governo ---------- */
  function csvIndicador(id, ind) {
    const q = (v) => (v === null || v === undefined ? "" : /[",;\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
    const L = [["# " + ind.titulo + " — " + ind.unidade], ["# fonte: " + ind.fonte + " (" + ind.fonte_url + ")"], ["# regra: " + explica(id, ind)], [],
      ["periodo", "valor"], ...ind.serie.map((p) => [p.x, p.y]), [],
      ["governo", "periodo_com_dado", ind.resumo_rotulo || "resumo", "valor_inicio", "ano_inicio", "valor_fim", "ano_fim", "posicao"]];
    for (const [g, r] of Object.entries(ind.resumo || {}))
      L.push([nomeGov(g), r.periodo, r.valor, r.inicio_val, r.inicio_ano, r.fim_val, r.fim_ano, r.posicao]);
    if (ind.notas) { L.push([], ["ano", "km2", "tipo", "nota_tecnica"]); ind.notas.forEach((n) => L.push([n.ano, n.valor, n.tipo, n.url])); }
    const blob = new Blob(["\ufeff" + L.map((l) => l.map(q).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `tira-teima_${id}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".baixar-csv"); if (!b) return;
    const card = b.closest(".ind"); if (card && card._ind) csvIndicador(b.dataset.id, card._ind);
  });

  /* ---------- gráficos ---------- */
  function redesenhar() {
    if (!D) return;
    for (const g of graficos.splice(0)) g.destroy();
    Chart.defaults.font.family = "IBM Plex Sans, system-ui, sans-serif";
    Chart.defaults.color = cor("--ink-2");
    for (const card of document.querySelectorAll(".ind")) {
      graficos.push(graficoSerie(card), graficoRanking(card));
    }
  }

  const tooltipBase = () => ({
    backgroundColor: cor("--surface"), titleColor: cor("--ink"), bodyColor: cor("--ink-2"),
    borderColor: cor("--rule"), borderWidth: 1, padding: 10, displayColors: false,
    titleFont: { weight: 600 }, bodyFont: { family: "IBM Plex Mono", size: 12 },
  });

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
          backgroundColor: n % 2 ? cor("--band-b") : cor("--band-a"), borderWidth: 0,
          label: {
            display: px >= 14, content: px < nome.length * 6.6 + 6 ? ABREV[g] : nome,
            position: { x: "center", y: "start" }, color: cor("--ink-3"),
            font: { family: "IBM Plex Sans", size: 10.5, weight: 500 }, padding: 3,
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
      const alvo = anual ? m.data.slice(0, 4) : m.data;
      const i = labels.indexOf(alvo);
      if (i < 0) continue;
      out[`m${k}`] = {
        type: "line", xMin: i, xMax: i, borderColor: cor("--accent"), borderWidth: 1, borderDash: [3, 3],
        drawTime: "afterDatasetsDraw",
        label: {
          display: largura >= 380, content: m.curto, position: "start", yAdjust: n % 2 ? -20 : -4,
          backgroundColor: cor("--surface"), color: cor("--accent"),
          font: { family: "IBM Plex Sans", size: 10, weight: 600 }, padding: { x: 3, y: 1 },
        },
      };
      n++;
    }
    return out;
  }

  function limite(ind) {
    if (!ind.limite) return {};
    return {
      lim: {
        type: "line", yMin: ind.limite.valor, yMax: ind.limite.valor, borderColor: cor("--ruim"), borderWidth: 1.5,
        borderDash: [6, 4], drawTime: "afterDatasetsDraw",
        label: { display: true, content: ind.limite.rotulo, position: "end", yAdjust: -10, backgroundColor: cor("--surface"),
                 color: cor("--ruim-txt"), font: { family: "IBM Plex Sans", size: 10.5, weight: 600 }, padding: { x: 4, y: 2 } },
      },
    };
  }

  function faixaMapaFome(ind) {
    if (!ind.mapa_fome) return "";
    const anos = Object.entries(ind.mapa_fome).filter(([a]) => +a >= 2000);
    if (!anos.length) return "";
    return `<div class="mapa-fome" aria-label="Anos em que o Brasil estava no Mapa da Fome">
      <p class="mf-tit">Brasil no Mapa da Fome (cada ponto = média de três anos centrada nele; o rótulo mostra o triênio)</p>
      <div class="mf-anos">${anos.map(([a, no]) => `<span class="mf-ano ${no ? "no" : "fora"}" title="${+a - 1}–${+a + 1}: ${no ? "no Mapa da Fome" : "fora do Mapa da Fome"}"><b>${no ? "✕" : "✓"}</b>${String(+a - 1).slice(2)}–${String(+a + 1).slice(2)}</span>`).join("")}</div>
      <p class="mf-leg"><span class="mf-ano no"><b>✕</b></span> no mapa (acima de 2,5%) <span class="mf-ano fora"><b>✓</b></span> fora do mapa</p></div>`;
  }

  function legendaMarcos(labels, anual) {
    const ms = (D.marcos || []).filter((m) => labels.includes(anual ? m.data.slice(0, 4) : m.data));
    if (!ms.length) return "";
    return '<span class="lm-traco"></span> Marcos: ' + ms.map((m) => `${esc(m.rotulo)} (${m.data.slice(0, 4)})`).join(" · ");
  }

  function graficoSerie(card) {
    const ind = card._ind;
    const canvas = card.querySelector(".c-serie");
    const labels = ind.serie.map((p) => p.x);
    const valores = ind.serie.map((p) => p.y);
    const barra = ind.grafico === "barra";
    const pontos = ind.grafico === "linha_anual";
    const log = ind.escala === "log";
    const anoAtual = String(new Date().getFullYear());
    const parcial = (x) => barra && x === anoAtual;
    const serie = cor("--series"), suave = cor("--series-soft");
    const largura = canvas.parentElement.clientWidth - 56;
    const anos = labels.length && labels[0].length > 4;
    const span = +labels.at(-1).slice(0, 4) - +labels[0].slice(0, 4);
    const passo = largura < 420 ? (span > 25 ? 10 : 5) : largura < 700 ? (span > 25 ? 5 : 4) : span > 25 ? 5 : 2;

    return new Chart(canvas, {
      type: barra ? "bar" : "line",
      data: {
        labels,
        datasets: [{
          data: valores,
          backgroundColor: barra ? labels.map((x) => (parcial(x) ? suave : serie)) : serie,
          borderColor: serie, borderWidth: barra ? 0 : 2,
          borderRadius: barra ? 2 : 0, maxBarThickness: 18, categoryPercentage: 0.86, barPercentage: 0.92,
          pointRadius: pontos ? 3 : 0, pointBackgroundColor: serie, pointHoverRadius: 5, pointHoverBorderWidth: 2,
          pointHoverBackgroundColor: serie, pointHoverBorderColor: cor("--surface"), spanGaps: pontos,
          segment: pontos ? { borderDash: (c) => (c.p0.skip || c.p1.skip ? [4, 4] : undefined) } : undefined,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: 16 } },
        scales: {
          x: {
            grid: { display: false }, border: { color: cor("--rule") },
            ticks: {
              autoSkip: false, maxRotation: 0, color: cor("--ink-3"), font: { size: 11 },
              callback(v) {
                const x = labels[v];
                if (anos && !x.endsWith("-01")) return null;
                const ano = +x.slice(0, 4);
                return ano % passo === 0 ? String(ano) : null;
              },
            },
          },
          y: {
            type: log ? "logarithmic" : "linear",
            beginAtZero: barra && !log,
            grace: log ? undefined : "8%",
            max: log ? Math.max(...valores) * 4 : undefined,
            grid: { color: (c) => (c.tick.value === 0 ? cor("--ink-3") : cor("--grid")) },
            border: { display: false },
            ticks: {
              color: cor("--ink-3"), font: { size: 11 }, maxTicksLimit: 6,
              callback(v) {
                if (log && ![1, 10, 100, 1000, 10000].includes(v)) return null;
                return fmt(ind.formato === "pct" ? "pct_simples" : ind.formato, v);
              },
            },
          },
        },
        plugins: {
          legend: { display: false },
          annotation: { annotations: { ...faixas(labels, largura), ...marcos(labels, largura, !anos), ...limite(ind) } },
          tooltip: {
            ...tooltipBase(),
            callbacks: {
              title: (it) => {
                const x = it[0].label;
                const quando = x.length > 4 ? `${x.slice(5, 7)}/${x.slice(0, 4)}` : x;
                const g = nomeGov(govDoPonto(x));
                return g ? `${quando} · ${g}` : quando;
              },
              label: (it) => {
                const linhas = [fmt(ind.formato, it.parsed.y) + (parcial(it.label) ? " (ano incompleto)" : "")];
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

  // Escreve o valor de cada barra numa coluna à direita do gráfico, alinhada, sem encostar nas barras nem nos nomes.
  const rotulosBarra = {
    id: "rotulosBarra",
    afterDatasetsDraw(chart, _a, opts) {
      const { ctx, chartArea } = chart;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = "500 11.5px IBM Plex Mono, ui-monospace, monospace";
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      ctx.fillStyle = opts.cor;
      meta.data.forEach((bar, i) => ctx.fillText(opts.textos[i], chartArea.right + 10, bar.y));
      ctx.restore();
    },
  };

  function graficoRanking(card) {
    const ind = card._ind;
    const canvas = card.querySelector(".c-rank");
    let ids = GOV.map((g) => g.id).filter((g) => ind.resumo[g]);
    if (ind.direcao) ids.sort((a, b) => ind.resumo[a].posicao - ind.resumo[b].posicao);
    const r = ids.map((g) => ind.resumo[g]);
    const valores = r.map((x) => x.valor);
    const log = ind.escala === "log";
    const corDe = (x) => (x.avaliacao === "bom" ? cor("--bom") : x.avaliacao === "ruim" ? cor("--ruim") : cor("--neutro"));
    const textos = r.map((x) => fmt(resumoFmt(ind), x.valor) + (x.parcial ? "*" : ""));
    const min = Math.min(0, ...valores), max = Math.max(0, ...valores);
    const folga = (max - min) * 0.04 || 1;
    const larguraTexto = Math.max(...textos.map((t) => t.length)) * 7.2 + 16;
    canvas.parentElement.style.height = `${Math.max(150, ids.length * 26 + 36)}px`;

    return new Chart(canvas, {
      type: "bar",
      plugins: [rotulosBarra],
      data: {
        labels: ids.map((g) => (ind.direcao ? `${ind.resumo[g].posicao}º  ` : "") + nomeGov(g)),
        datasets: [{
          data: valores, backgroundColor: r.map((x) => (x.parcial ? corDe(x) + "99" : corDe(x))),
          borderRadius: 3, barPercentage: 0.78, categoryPercentage: 0.95, minBarLength: 2,
        }],
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: false,
        layout: { padding: { right: larguraTexto } },
        scales: {
          x: log
            ? { type: "logarithmic", display: false, max: Math.max(...valores) * 1.2 }
            : { display: false, min: min < 0 ? min - folga : 0, max: max + folga },
          y: { grid: { display: false }, border: { display: false },
               ticks: { color: cor("--ink-2"), font: { size: 12 }, autoSkip: false } },
        },
        plugins: {
          legend: { display: false },
          rotulosBarra: { textos, cor: cor("--ink"), log },
          tooltip: {
            ...tooltipBase(),
            callbacks: {
              title: (it) => nomeGov(ids[it[0].dataIndex]),
              label: (it) => {
                const x = r[it.dataIndex];
                const linhas = [fmt(resumoFmt(ind), x.valor) + (x.parcial ? " (parcial)" : "")];
                const t = trajeto(ind, x);
                if (t) linhas.push(t);
                if (x.avaliacao) linhas.push((x.avaliacao === "bom" ? "✓ " : "✕ ") + posTexto(ind, x, x.avaliacao));
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
    clearTimeout(tRes); tRes = setTimeout(redesenhar, 200);
  });
})();
