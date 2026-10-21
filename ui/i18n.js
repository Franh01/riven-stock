// Motor de internacionalización (es / en). Los diccionarios viven en lang_es.js y lang_en.js
// (window.LANGS.es / window.LANGS.en). Reglas:
//  - Toda función nueva se agrega con textos en ambos idiomas.
//  - Los nombres de armas, mods y stats del juego se quedan en inglés (vienen del catálogo).
//  - En el código se usa tr("clave", {params}) (el nombre t choca con variables locales).
//  - Plurales: si pasás {n}, se busca la clave "<clave>.one" (n = 1) o "<clave>.other"; si no existen, la clave sola.
(function () {
  const SUPPORTED = ["es", "en"];
  const LOCALES = { es: "es-AR", en: "en-US" };
  const dicts = window.LANGS = window.LANGS || {};
  let lang = "es";

  function detect() {
    const saved = localStorage.getItem("lang");
    if (SUPPORTED.includes(saved)) return saved;
    return String(navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en";
  }

  function lookup(key, n) {
    const d = dicts[lang] || {}, f = dicts.es || {};
    const keys = n === undefined ? [key] : [key + (n === 1 ? ".one" : ".other"), key];
    for (const k of keys) { if (k in d) return d[k]; }
    for (const k of keys) { if (k in f) return f[k]; }
    return undefined;
  }

  function t(key, params) {
    let s = lookup(key, params && params.n);
    if (s === undefined) { console.warn("i18n: falta la clave", key); return key; }
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in params ? params[k] : m));
    return s;
  }

  // Textos estáticos del HTML: data-i18n (texto), data-i18n-html (HTML), data-i18n-title, data-i18n-placeholder.
  function applyStatic(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
    root.querySelectorAll("[data-i18n-html]").forEach((el) => (el.innerHTML = t(el.dataset.i18nHtml)));
    root.querySelectorAll("[data-i18n-title]").forEach((el) => (el.title = t(el.dataset.i18nTitle)));
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => (el.placeholder = t(el.dataset.i18nPlaceholder)));
  }

  function setLang(l, persist = true) {
    if (!SUPPORTED.includes(l)) return;
    lang = l;
    if (persist) localStorage.setItem("lang", l);
    document.documentElement.lang = l;
    applyStatic();
    document.dispatchEvent(new CustomEvent("langchange", { detail: l }));
  }

  lang = detect();
  document.documentElement.lang = lang;
  window.I18N = {
    t, setLang, applyStatic, SUPPORTED,
    get lang() { return lang; },
    get locale() { return LOCALES[lang]; },
  };
  window.tr = t;
  document.addEventListener("DOMContentLoaded", () => applyStatic());
})();
