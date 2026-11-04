// node --test src/series.test.js  (tendencia por ventas: ventana móvil, una cifra por vendedor)
const test = require("node:test");
const assert = require("node:assert");
const { salesSeries } = require("./series");

const at = (d) => new Date(d + "T12:00:00Z");

test("ventana de 7 días y días sin ventas", () => {
  const s = salesSeries([{ price: 100, seller: "a", at: at("2026-11-01") }, { price: 200, seller: "b", at: at("2026-11-03") }], "2026-10-30", "2026-11-09");
  assert.deepEqual(s.map((x) => x.day), ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09"]);
  assert.equal(s[0].median, 100);
  assert.equal(s[2].median, 150);
  assert.equal(s[2].n, 2);
  assert.equal(s[s.length - 1].median, 200);   // la del 1/11 salió de la ventana el 8/11
});

test("un vendedor que spamea ventas baratas cuenta una vez", () => {
  const sales = [...Array(10)].map(() => ({ price: 5, seller: "spam", at: at("2026-11-02") }))
    .concat([{ price: 300, seller: "x", at: at("2026-11-02") }, { price: 400, seller: "y", at: at("2026-11-02") }]);
  const [p] = salesSeries(sales, "2026-11-02", "2026-11-02");
  assert.equal(p.median, 300);
  assert.equal(p.n, 12);
  assert.equal(p.sellers, 3);
});

test("ignora precios en cero", () => {
  assert.deepEqual(salesSeries([{ price: 0, seller: "a", at: at("2026-11-02") }], "2026-11-02", "2026-11-02"), []);
});
