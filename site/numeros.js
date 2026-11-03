/* Entrada monetária em pt-BR: ponto agrupa milhares, vírgula separa centavos. */
(function (root) {
  function lerValorBR(texto) {
    const s = String(texto).trim();
    if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(s)) return null;
    const n = Number(s.replace(/\./g, "").replace(",", "."));
    return Number.isFinite(n) && n > 0 && n <= Number.MAX_SAFE_INTEGER / 100 ? n : null;
  }
  if (typeof module !== "undefined") module.exports = { lerValorBR };
  else root.lerValorBR = lerValorBR;
})(globalThis);
