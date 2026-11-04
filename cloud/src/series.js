// Tendencia por ventas: las publicaciones se pueden inflar (cualquiera spamea avisos a 1p), las ventas no tanto.
// Por día, ventana móvil de `win` días; cada vendedor aporta una sola cifra (la mediana de sus ventas en la ventana),
// así uno que vende diez rivens baratos no arrastra la mediana.
const DAY = 86400000;

function quantile(sorted, q) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * q, i = Math.floor(pos), f = pos - i;
  return sorted[i + 1] === undefined ? sorted[i] : sorted[i] + (sorted[i + 1] - sorted[i]) * f;
}

// sales: [{price, seller, at: Date}], fromDay/toDay: "YYYY-MM-DD". Devuelve solo los días con alguna venta en la ventana.
function salesSeries(sales, fromDay, toDay, win = 7) {
  const out = [];
  const end = Date.parse(toDay + "T00:00:00Z");
  for (let t = Date.parse(fromDay + "T00:00:00Z"); t <= end; t += DAY) {
    const lo = t - (win - 1) * DAY, hi = t + DAY;
    const bySeller = new Map();
    let n = 0;
    for (const s of sales) {
      const at = +s.at;
      if (at < lo || at >= hi || !(s.price > 0)) continue;
      n += 1;
      const k = s.seller || `?${n}`;
      (bySeller.get(k) || bySeller.set(k, []).get(k)).push(s.price);
    }
    if (!n) continue;
    const per = [...bySeller.values()].map((ps) => quantile(ps.sort((a, b) => a - b), 0.5)).sort((a, b) => a - b);
    const r = (v) => Math.round(v);
    out.push({ day: new Date(t).toISOString().slice(0, 10), median: r(quantile(per, 0.5)), q1: r(quantile(per, 0.25)), q3: r(quantile(per, 0.75)), n, sellers: per.length });
  }
  return out;
}

module.exports = { salesSeries, quantile, DAY };
