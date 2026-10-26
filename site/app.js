/* Painel Brasil — renderização do site a partir de data/painel.json */
(() => {
  "use strict";

  const ABREV = { lula1: "L1", lula2: "L2", dilma1: "D1", dilma2: "D2", temer: "T", bolsonaro: "B", lula3: "L3" };
  const ORDEM_COMPARATIVO = ["pib_crescimento", "pib_per_capita", "ipca", "salario_minimo", "cesta_sp", "gasolina", "dolar", "queimadas"];
  const ROTULO_CURTO = {
    pib_crescimento: ["PIB", "média anual"],
    pib_per_capita: ["PIB per capita", "cresc. médio anual"],
    ipca: ["Inflação", "média anual"],
    salario_minimo: ["Salário mínimo", "ganho real"],
    cesta_sp: ["Cesta básica SP", "% do mínimo"],
    gasolina: ["Gasolina", "R$/l, valor de hoje"],
    dolar: ["Dólar", "média R$"],
    queimadas: ["Queimadas", "focos/ano"],
  };

  const nf = (min, max) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max });
  const F = {
    pct: (v) => (v > 0 ? "+" : "") + nf(1, 1).format(v) + "%",
    pct_simples: (v) => nf(1, 1).format(v) + "%",
    moeda: (v) => "R$ " + nf(2, 2).format(v),
    moeda_usd: (v) => "US$ " + nf(0, 0).format(v),
    inteiro: (v) => nf(0, 0).format(Math.round(v)),
  };
  const fmt = (tipo, v) => (v == null || Number.isNaN(v) ? "—" : (F[tipo] || F.pct_simples)(v));
  const el = (tag, attrs = {}, html = "") => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (html) e.innerHTML = html;
    return e;
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  /* ---------- tema ---------- */
  const raiz = document.documentElement;
  try { const t = localStorage.getItem("tema"); if (t) raiz.dataset.theme = t; } catch (_) {}
  document.getElementById("tema").addEventListener("click", () => {
    const escuro = raiz.dataset.theme
      ? raiz.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
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
    // ano anual: governo com mais dias no ano (2016 → Temer)
    let melhor = null, dias = -1;
    for (const g of GOV) {
      const a = Math.max(Date.parse(`${ano}-01-01`), Date.parse(g.inicio));
      const b = Math.min(Date.parse(`${ano}-12-31`), Date.parse(g.fim));
      if (b >= a && b - a > dias) { dias = b - a; melhor = g.id; }
    }
    return melhor;
  };
  const govDoPonto = (x) => (x.length > 4 ? govDoMes(+x.slice(0, 4), +x.slice(5, 7)) : govDoAno(+x));
  const nomeGov = (id) => GOV.find((g) => g.id === id)?.nome ?? "";

  /* ---------- render ---------- */
  let DADOS = null;
  const graficos = [];

  fetch("data/painel.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((d) => { DADOS = d; GOV = d.governos; montar(); })
    .catch((e) => {
      document.getElementById("lista-indicadores").innerHTML =
        `<p class="indisponivel">Não foi possível carregar os dados (${esc(e.message)}).</p>`;
    });

  function montar() {
    const d = DADOS;
    document.getElementById("gerado-em").textContent =
      new Date(d.gerado_em).toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short" });
    linhaDoTempo();
    tabelaComparativo();
    tabelaGovernos();
    tabelaStatus();
    const lista = document.getElementById("lista-indicadores");
    const chips = document.getElementById("chips");
    for (const id of ORDEM_COMPARATIVO) {
      const ind = d.indicadores[id];
      if (!ind) continue;
      chips.append(el("a", { href: `#ind-${id}` }, esc(ind.titulo)));
      lista.append(cartao(id, ind));
    }
    redesenhar();
  }

  function linhaDoTempo() {
    const box = document.getElementById("linha-tempo");
    const t0 = Date.parse(GOV[0].inicio), t1 = Date.parse(GOV.at(-1).fim);
    for (const g of GOV) {
      const w = (Date.parse(g.fim) - Date.parse(g.inicio)) / (t1 - t0);
      const seg = el("div", { class: "lt-seg", title: `${g.nome}: ${g.presidente}` });
      seg.style.flex = `${w} 1 0`;
      const fim = g.id === "lula3" ? "hoje" : g.fim.slice(0, 4);
      seg.innerHTML = `<span class="lt-nome">${esc(g.nome)}</span><span class="lt-anos">${g.inicio.slice(0, 4)}–${fim}</span>`;
      box.append(seg);
    }
  }

  const resumoFmt = (ind) => ind.resumo_formato || ind.formato;

  function tabelaComparativo() {
    const t = document.getElementById("tabela-comparativo");
    const ids = ORDEM_COMPARATIVO.filter((id) => DADOS.indicadores[id]);
    let h = "<thead><tr><th>Governo</th>";
    for (const id of ids) h += `<th>${ROTULO_CURTO[id][0]}<small>${ROTULO_CURTO[id][1]}</small></th>`;
    h += "</tr></thead><tbody>";
    for (const g of GOV) {
      const fim = g.id === "lula3" ? "em curso" : g.fim.split("-").reverse().join("/");
      h += `<tr><td class="gov">${esc(g.nome)}<small>${g.inicio.split("-").reverse().join("/")} – ${fim}</small></td>`;
      for (const id of ids) {
        const ind = DADOS.indicadores[id];
        const r = ind.resumo[g.id];
        h += r
          ? `<td class="num">${fmt(resumoFmt(ind), r.valor)}${r.parcial ? '<span class="parcial-tag">*</span>' : ""}</td>`
          : `<td class="num sem-dado">—</td>`;
      }
      h += "</tr>";
    }
    t.innerHTML = h + "</tbody>";
  }

  function tabelaGovernos() {
    let h = '<div class="tabela-rolagem"><table><thead><tr><th>Período</th><th>Presidente</th><th>Início</th><th>Fim</th></tr></thead><tbody>';
    for (const g of GOV) {
      h += `<tr><td>${esc(g.nome)}</td><td style="text-align:left">${esc(g.presidente)}</td><td class="num">${g.inicio.split("-").reverse().join("/")}</td><td class="num">${g.id === "lula3" ? "em curso" : g.fim.split("-").reverse().join("/")}</td></tr>`;
    }
    document.getElementById("tabela-governos").innerHTML = h + "</tbody></table></div>";
  }

  function tabelaStatus() {
    let h = "<thead><tr><th>Série</th><th style='text-align:left'>Fonte</th><th>Situação</th><th>Último dado</th></tr></thead><tbody>";
    for (const s of DADOS.fontes) {
      const ok = s.status === "atualizado";
      h += `<tr><td>${esc(s.indicador)}</td><td style="text-align:left">${esc(s.fonte)}</td><td class="${ok ? "st-ok" : "st-alerta"}">${esc(s.status)}</td><td class="num">${esc(s.ultima_obs || "—")}</td></tr>`;
    }
    document.getElementById("tabela-status").innerHTML = h + "</tbody>";
  }

  function cartao(id, ind) {
    const c = el("article", { class: "ind", id: `ind-${id}` });
    c.innerHTML = `
      <div class="ind-cab"><h3>${esc(ind.titulo)}</h3><span class="ind-unid">${esc(ind.unidade)}</span></div>
      <p class="ind-desc">${esc(ind.descricao)}</p>
      <div class="grafico"><canvas role="img" aria-label="${esc(ind.titulo)} de 2003 a hoje, com faixas por governo"></canvas></div>
      <div class="mini">${GOV.map((g) => {
        const r = ind.resumo[g.id];
        return `<div><span>${esc(g.nome)}</span><b>${r ? fmt(resumoFmt(ind), r.valor) : "—"}${r?.parcial ? '<span class="parcial-tag">*</span>' : ""}</b></div>`;
      }).join("")}</div>
      <p class="mini-rot">Por governo: ${esc(ind.resumo_rotulo)}.</p>
      <p class="fonte">Fonte: <a href="${esc(ind.fonte_url)}" target="_blank" rel="noopener">${esc(ind.fonte)}</a></p>`;
    c._ind = ind;
    return c;
  }

  function faixas(labels, largura) {
    const out = {};
    let i = 0, n = 0;
    while (i < labels.length) {
      const g = govDoPonto(labels[i]);
      let j = i;
      while (j + 1 < labels.length && govDoPonto(labels[j + 1]) === g) j++;
      if (g) {
        out[`f${n}`] = {
          type: "box", xMin: i - 0.5, xMax: j + 0.5, drawTime: "beforeDatasetsDraw",
          backgroundColor: n % 2 ? cor("--band-b") : cor("--band-a"), borderWidth: 0,
          label: {
            display: true, content: largura < 620 ? ABREV[g] : nomeGov(g),
            position: { x: "center", y: "start" }, color: cor("--ink-3"),
            font: { family: "IBM Plex Sans", size: 11, weight: 500 }, padding: 4,
          },
        };
        n++;
      }
      i = j + 1;
    }
    return out;
  }

  function redesenhar() {
    if (!DADOS) return;
    for (const g of graficos.splice(0)) g.destroy();
    Chart.defaults.font.family = "IBM Plex Sans, system-ui, sans-serif";
    Chart.defaults.color = cor("--ink-2");
    for (const card of document.querySelectorAll(".ind")) graficos.push(grafico(card));
  }

  function grafico(card) {
    const ind = card._ind;
    const canvas = card.querySelector("canvas");
    const labels = ind.serie.map((p) => p.x);
    const valores = ind.serie.map((p) => p.y);
    const barra = ind.grafico === "barra";
    const anoAtual = String(new Date().getFullYear());
    const parcial = (x) => barra && x === anoAtual;
    const serie = cor("--series"), suave = cor("--series-soft");
    const largura = canvas.parentElement.clientWidth;

    return new Chart(canvas, {
      type: barra ? "bar" : "line",
      data: {
        labels,
        datasets: [{
          data: valores,
          backgroundColor: barra ? labels.map((x) => (parcial(x) ? suave : serie)) : serie,
          borderColor: serie, borderWidth: barra ? 0 : 2,
          borderRadius: barra ? 3 : 0, maxBarThickness: 22, categoryPercentage: 0.8, barPercentage: 0.9,
          pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2,
          pointHoverBackgroundColor: serie, pointHoverBorderColor: cor("--surface"), tension: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: 18 } },
        scales: {
          x: {
            grid: { display: false }, border: { color: cor("--rule") },
            ticks: {
              autoSkip: barra, maxRotation: 0, color: cor("--ink-3"), font: { size: 11 },
              callback(v) {
                const x = labels[v];
                if (barra) return largura < 620 ? "’" + x.slice(2) : x;
                if (!x.endsWith("-01")) return null;
                const ano = +x.slice(0, 4);
                const passo = largura < 620 ? 4 : 2;
                return ano % passo === 0 ? String(ano) : null;
              },
            },
          },
          y: {
            beginAtZero: barra,
            grid: { color: (c) => (c.tick.value === 0 ? cor("--ink-3") : cor("--grid")) },
            border: { display: false },
            ticks: { color: cor("--ink-3"), font: { size: 11 }, maxTicksLimit: 6, callback: (v) => fmt(ind.formato === "pct" ? "pct_simples" : ind.formato, v) },
          },
        },
        plugins: {
          legend: { display: false },
          annotation: { annotations: faixas(labels, largura) },
          tooltip: {
            backgroundColor: cor("--surface"), titleColor: cor("--ink"), bodyColor: cor("--ink-2"),
            borderColor: cor("--rule"), borderWidth: 1, padding: 10, displayColors: false,
            titleFont: { weight: 600 }, bodyFont: { family: "IBM Plex Mono", size: 12 },
            callbacks: {
              title: (it) => {
                const x = it[0].label;
                const quando = x.length > 4 ? `${x.slice(5, 7)}/${x.slice(0, 4)}` : x;
                return `${quando} · ${nomeGov(govDoPonto(x))}`;
              },
              label: (it) => fmt(ind.formato, it.parsed.y) + (parcial(it.label) ? " (ano incompleto)" : ""),
            },
          },
        },
      },
    });
  }

  let tRes;
  addEventListener("resize", () => { clearTimeout(tRes); tRes = setTimeout(redesenhar, 200); });
})();
