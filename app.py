"""Riven Stock: app desktop (ventana pywebview + interfaz HTML en ui/)."""

import ctypes
import json
import logging
import sys
import threading
import traceback
import time
from datetime import datetime, timezone
from pathlib import Path

# Log de arranque: con pythonw.exe no hay consola, así que los errores (incluso de los imports de abajo) van a este archivo.
LOG_FILE = Path(__file__).parent / "riven-stock.log"
if getattr(sys, "frozen", False):   # instalado: la carpeta de la app no es escribible
    import os
    LOG_FILE = Path(os.environ.get("RIVEN_STOCK_DATA") or Path(os.environ.get("APPDATA", Path.home())) / "RivenStock") / "riven-stock.log"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
try:
    import crashes
    try:
        from updater import version_actual as _va
        import store as _st
        crashes.begin(_st.DATA_DIR, LOG_FILE, _va())   # antes de que el log se pise
    except Exception:
        pass
    logging.basicConfig(filename=LOG_FILE, filemode="w", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Arranque. Python %s en %s", sys.version.split()[0], sys.executable)
    def _hook(t, v, tb):
        logging.critical("Error sin capturar", exc_info=(t, v, tb))
        crashes.record("el programa", (t, v, tb))
    def _thook(a):
        logging.error("Error en hilo %s", a.thread, exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
        crashes.record(f"el hilo {a.thread.name if a.thread else '?'}", (a.exc_type, a.exc_value, a.exc_traceback))
    sys.excepthook = _hook
    threading.excepthook = _thook
except OSError:
    pass

import requests
import websocket
import webview

import cloud_backup
import feedback
import store
import opportunities
import stockcheck
import updater
from orders import OrderCache
from pricing import estimate
from ratelimit import QUEUE
from wfm_client import SEARCH_CAP, AuthError, WFMClient, WFMError, cheapest_ingame

# API de lectura de tendencias (Lambda en AWS, pública y solo de lectura); ver cloud/
CLOUD_API_URL = "https://2gxvgmytrqarivabthxybzfsn40iuyyw.lambda-url.us-east-1.on.aws/"

# Landing con la descarga y el tutorial para sacar el token (JWT) de warframe.market
LANDING_URL = "https://riven-stock.vercel.app"

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ICON = ROOT / "assets" / "icon.ico"
BASES = ROOT / "data" / "riven_bases.json"  # lo genera tools/derive_riven_bases.py
TITLE = "Riven Stock"


class Api:
    """Métodos que la interfaz llama con window.pywebview.api.<método>()."""

    def __init__(self):
        try:
            if store.migrate_legacy():
                logging.info("Base migrada a %s", store.DB_PATH)
            store.backup_if_due()
        except Exception:
            logging.exception("No se pudo migrar o respaldar la base")
        self.client = WFMClient()
        self._seen = {}  # id -> último contrato propio leído de la API (crudo)
        self._market = {}  # id -> contrato ajeno visto en la pestaña Mercado (crudo)
        self._online = False   # lo mantiene el hilo contador
        self._cache = OrderCache(self.client, self._wanted_weapons, str(store.DB_PATH.parent / "cache" / "order_cache.json"))

    def _rtype(self, weapon):
        return next((w.get("rivenType") for w in self.client.riven_weapons() if w["slug"] == weapon), None)

    def catalog(self):
        weapons = [
            {"slug": w["slug"], "name": w["i18n"]["en"]["name"], "type": w["rivenType"],
             "group": w.get("group"), "disposition": w.get("disposition")}
            for w in self.client.riven_weapons()
        ]
        stats = [
            {"slug": a["slug"], "name": a["i18n"]["en"]["name"], "unit": a.get("unit"),
             "positiveOnly": bool(a.get("positiveOnly")), "exclusiveTo": a.get("exclusiveTo") or [],
             "prefix": a.get("prefix"), "suffix": a.get("suffix")}
            for a in self.client.riven_attributes()
        ]
        return {
            "weapons": sorted(weapons, key=lambda w: w["name"]),
            "stats": sorted(stats, key=lambda s: s["name"]),
            # Valor base de cada stat por tipo de riven, para sugerir el orden del nombre.
            "bases": json.loads(BASES.read_text(encoding="utf-8")) if BASES.exists() else {},
        }

    # ---- Preferencias (locales) -------------------------------------------

    SETTING_KEYS = {"cloud_auto", "lang", "tracked_weapons", "auto_ingame", "mine_sort", "invisible_on_close",
                    "autodrop_enabled", "autodrop_hours", "autodrop_amount", "autodrop_floor", "tutorials",
                    "show_requests", "opp_enabled", "opp_weapons", "opp_threshold", "opp_min_gain"}

    # ---- Token de warframe.market ----
    def token_status(self):
        return {"has": bool(self.client.jwt), "help_url": LANDING_URL + "/#token"}

    def token_save(self, raw):
        """Valida el token pegado contra warframe.market y, si sirve, lo guarda en el .env."""
        t = (raw or "").strip().strip('"').strip("'")
        if t.upper().startswith("JWT="):
            t = t[4:].strip()
        if t.lower().startswith("bearer "):
            t = t[7:].strip()
        if t.count(".") != 2 or not t.startswith("eyJ") or len(t) < 60:
            return {"error": "token_format"}
        try:
            me = WFMClient(t).me()
        except AuthError:
            return {"error": "token_invalid"}
        except Exception:
            return {"error": "token_offline"}
        from wfm_client import ENV_FILE
        lineas = []
        if ENV_FILE.exists():
            lineas = [l for l in ENV_FILE.read_text(encoding="utf-8").splitlines() if not l.startswith("WFM_JWT=")]
        lineas.append(f"WFM_JWT={t}")
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(chr(10).join(lineas) + chr(10), encoding="utf-8")
        self.client.jwt = t
        return {"ok": True, "name": me.get("ingameName") or me.get("ingame_name") or me.get("slug") or ""}

    def open_url(self, url):
        if str(url).startswith("https://"):
            import webbrowser
            webbrowser.open(url)

    # ---- Actualizaciones ----
    def get_version(self):
        return updater.version_actual()

    def get_changelog(self):
        try:
            return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        except OSError:
            return ""

    def check_update(self):
        """{version, notas} si hay una versión nueva; {} si no; {error} si no se pudo consultar."""
        try:
            info = updater.buscar_actualizacion()
        except Exception as e:
            return {"error": f"No se pudo buscar actualizaciones: {e}"}
        self._update_info = info
        return {"version": info["version"], "notas": info["notas"]} if info else {}

    def install_update(self):
        info = getattr(self, "_update_info", None)
        if not info:
            return {"error": "No hay una actualización pendiente."}
        try:
            staging, nuevo = updater.preparar(info)
            updater.lanzar_aplicador(staging, nuevo)
        except Exception as e:
            return {"error": str(e)}
        # Cierra por el camino normal (queda Invisible); el aplicador espera y reemplaza.
        threading.Timer(1.0, lambda: self._window.destroy()).start()
        return {"ok": True}

    def get_settings(self):
        with store.connect() as conn:
            return store.settings(conn)

    def set_setting(self, key, value):
        if key not in self.SETTING_KEYS:
            return {"error": f"Preferencia desconocida: {key}"}
        with store.connect() as conn:
            store.set_setting(conn, key, value)
        return {"ok": True}

    # ---- Copias de seguridad locales ---------------------------------------

    def backup_info(self):
        return {"dir": str(store.DATA_DIR), "backups": store.list_backups()}

    def backup_now(self):
        try:
            p = store.make_backup(tag="-manual")
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True, "path": str(p)}

    def export_backup(self):
        """Guarda una copia de la base donde elija el usuario."""
        name = f"riven-stock-{datetime.now().strftime('%Y-%m-%d')}.db"
        dest = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name,
                                               file_types=("Base de Riven Stock (*.db)",))
        if not dest:
            return {"cancelled": True}
        dest = dest if isinstance(dest, str) else dest[0]
        try:
            Path(dest).unlink(missing_ok=True)
            store._copy_db(store.DB_PATH, dest)
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True, "path": str(dest)}

    def import_backup(self, path=None):
        """Restaura la base desde un archivo (el elegido o `path`). Deja antes un backup de seguridad."""
        if not path:
            sel = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Base de Riven Stock (*.db)",))
            if not sel:
                return {"cancelled": True}
            path = sel if isinstance(sel, str) else sel[0]
        if not store.validate_db(path):
            return {"error": "invalid_backup"}
        try:
            store.restore_db(path)
        except Exception as e:
            return {"error": str(e)}
        return {"ok": True}

    # ---- Copia en la nube (cifrada del lado del cliente) -------------------

    CLOUD_EVERY_S = 20 * 3600

    def _cloud_set(self, **kv):
        with store.connect() as conn:
            for k, v in kv.items():
                store.set_setting(conn, k, v)

    # ---- Sugerencias y reportes de bugs ----
    def feedback_state(self):
        with store.connect() as conn:
            return {"wait": feedback.wait_left(conn)}

    def feedback_logs(self):
        return feedback.read_log(LOG_FILE)

    def feedback_send(self, kind, text, contact, with_logs, shots):
        logs = feedback.read_log(LOG_FILE) if with_logs else ""
        with store.connect() as conn:
            r = feedback.send(conn, updater.version_actual(), kind, text, contact, logs, shots)
        logging.info("feedback %s -> %s", kind, r.get("error") or "ok")
        return r

    # ---- Reporte de crashes y vuelta a la versión sana ----
    def crash_state(self):
        files = crashes.pending()
        with store.connect() as conn:
            auto = bool(store.settings(conn).get("crash_auto"))
        prev = ""
        if files:
            prev = feedback.sanitize(files[-1].read_text(encoding="utf-8", errors="replace"))[:1500]
        return {"n": len(files), "auto": auto, "preview": prev, "rollback": crashes.rollback_target()}

    def crash_ui_error(self, msg):
        """Error de JavaScript no capturado (la interfaz lo manda; se ignoran repetidos)."""
        msg = str(msg)[:3000]
        key = msg[:200]
        seen = getattr(self, "_ui_seen", set())
        if key not in seen and len(seen) < 20:
            seen.add(key)
            self._ui_seen = seen
            logging.error("Error en la interfaz: %s", msg)
            crashes.record_text("la interfaz", msg)
        return {"ok": True}

    def crash_send(self, always=False):
        files = crashes.pending()
        if not files:
            return {"ok": True}
        with store.connect() as conn:
            if always:
                store.set_setting(conn, "crash_auto", True)
            r = feedback.send_crash(conn, updater.version_actual(), files, LOG_FILE)
        logging.info("crash -> %s", r.get("error") or "ok")
        if r.get("ok"):
            crashes.discard()
        return r

    def crash_discard(self):
        crashes.discard()
        return {"ok": True}

    def crash_set_auto(self, value):
        with store.connect() as conn:
            store.set_setting(conn, "crash_auto", bool(value))
        return {"ok": True}

    def rollback_do(self):
        to = crashes.rollback_target()
        if not to:
            return {"error": "No hay una versión anterior sana para volver."}
        try:
            info = updater.buscar_version(to)
            if not info:
                return {"error": f"No se encontró la versión {to} en GitHub."}
            staging, nuevo = updater.preparar(info)
            updater.lanzar_aplicador(staging, nuevo)
        except Exception as e:
            return {"error": str(e)}
        threading.Timer(1.0, lambda: self._window.destroy()).start()
        return {"ok": True}

    def cloud_info(self):
        with store.connect() as conn:
            st = store.settings(conn)
        return {"code": st.get("cloud_code"), "auto": st.get("cloud_auto", True), "last": st.get("cloud_last"),
                "active": st.get("cloud_active")}

    def cloud_enable(self):
        """Crea el código de recuperación y sube la primera copia."""
        code = cloud_backup.new_code()
        try:
            r = cloud_backup.upload(code, updater.version_actual())
        except cloud_backup.CloudError as e:
            return {"error": str(e)}
        self._cloud_set(cloud_code=code, cloud_auto=True, cloud_last=r["at"])
        return {"ok": True, "code": code, "last": r["at"]}

    def cloud_upload(self):
        code = self.cloud_info()["code"]
        if not code:
            return {"error": "no_cloud_backup"}
        try:
            r = cloud_backup.upload(code, updater.version_actual())
        except cloud_backup.CloudError as e:
            return {"error": str(e)}
        self._cloud_set(cloud_last=r["at"])
        return {"ok": True, "last": r["at"]}

    def cloud_restore(self, code):
        """Baja la copia con ese código y reemplaza los datos locales (antes deja una copia de seguridad)."""
        try:
            code = cloud_backup.normalize(code)
            tmp = cloud_backup.download_to_file(code)
        except cloud_backup.CloudError as e:
            return {"error": str(e)}
        try:
            store.restore_db(tmp)
        except Exception as e:
            return {"error": str(e)}
        finally:
            try:
                Path(tmp).unlink()
            except OSError:
                pass
        self._cloud_set(cloud_code=code, cloud_auto=True)
        return {"ok": True}

    def cloud_disable(self):
        """Borra la copia del servidor y olvida el código."""
        code = self.cloud_info()["code"]
        if code:
            try:
                cloud_backup.delete(code)
            except cloud_backup.CloudError as e:
                if str(e) != "no_cloud_backup":
                    return {"error": str(e)}
        self._cloud_set(cloud_code=None, cloud_last=None)
        return {"ok": True}

    def cloud_stats(self):
        try:
            r = cloud_backup.stats()
        except cloud_backup.CloudError:
            return {"active": self.cloud_info()["active"]}
        self._cloud_set(cloud_active=r.get("active"))
        return {"active": r.get("active"), "total": r.get("total")}

    def _cloud_loop(self):
        """Cada ~30 min: un ping diario anónimo (conteo de instalaciones activas) y la subida automática."""
        if self._stop.wait(60):
            return
        while True:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                with store.connect() as conn:
                    st = store.settings(conn)
                    iid = cloud_backup.install_id(conn)
                if st.get("cloud_ping") != today:
                    cloud_backup.ping(iid, updater.version_actual())
                    self._cloud_set(cloud_ping=today)
                    self.cloud_stats()
                last = st.get("cloud_last")
                due = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > self.CLOUD_EVERY_S
                if st.get("cloud_code") and st.get("cloud_auto", True) and due:
                    self.cloud_upload()
            except Exception:
                logging.info("Copia en la nube: se reintenta más tarde", exc_info=True)
            if self._stop.wait(1800):
                return

    def open_data_folder(self):
        import os
        os.startfile(str(store.DATA_DIR))
        return {"ok": True}

    # ---- Estado del usuario (Invisible / Online / En juego) ----------------

    def status(self):
        try:
            return {"status": self.client.get_status()}
        except WFMError as e:
            return {"error": str(e)}
        except (OSError, websocket.WebSocketException):
            return {"error": "warframe.market no responde. Se reintenta solo en un rato."}

    def set_status(self, status, minutes):
        try:
            return {"status": self.client.set_status(status, int(minutes) * 60)}
        except (WFMError, ValueError, OSError, websocket.WebSocketException) as e:
            return {"error": str(e)}

    # ---- Horas online efectivas ---------------------------------------------

    TICK_S = 60          # una muestra por minuto
    TICK_CAP_S = 120     # tope por muestra: una suspensión de la PC no suma horas
    STATUS_REFRESH_S = 300
    RENEW_BEFORE_S = 600

    def start_counter(self):
        try:
            with store.connect() as conn:
                store.purge_old(conn)
        except Exception:
            pass
        self._stop = threading.Event()
        threading.Thread(target=self._counter_loop, daemon=True).start()
        threading.Thread(target=self._drop_loop, daemon=True).start()
        threading.Thread(target=self._snapshot_loop, daemon=True).start()
        threading.Thread(target=self._opp_loop, daemon=True).start()
        threading.Thread(target=self._cloud_loop, daemon=True).start()
        self._cache.start()

    def stop_counter(self):
        if getattr(self, "_stop", None):
            self._stop.set()
        self._cache.stop()

    def _counter_loop(self):
        last = time.monotonic()
        st, st_at = None, 0.0
        while not self._stop.wait(self.TICK_S):
            now = time.monotonic()
            elapsed = min(now - last, self.TICK_CAP_S)
            last = now
            try:
                if st is None or now - st_at > self.STATUS_REFRESH_S:
                    st, st_at = self.client.get_status(), now
                until = st.get("statusUntil") if st else None
                left = (datetime.fromisoformat(until.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() if until else 0
                self._online = bool(st and st.get("status") in ("online", "ingame") and left > 0)
                if self._online:
                    with store.connect() as conn:
                        store.add_online_seconds(conn, elapsed)
                        # solo cuentan los rivens visibles: uno oculto no está a la venta
                        store.add_riven_seconds(conn, [i for i, a in list(self._seen.items()) if a.get("visible", True)], elapsed)
                    if left < self.RENEW_BEFORE_S:   # el servidor corta a las 4 h: renovar mientras la app esté abierta
                        st, st_at = self.client.set_status(st["status"], 240 * 60), now
            except Exception:
                st = None   # sin red o error de la API: no suma ese minuto y reintenta

    # ---- Caché de órdenes y baja automática ---------------------------------

    DROP_PASS_S = 300      # cada cuánto corre el motor de baja
    VIEW_MAX_AGE_S = 600   # al abrir un riven, si los datos son más viejos se vuelven a pedir
    CACHE_MAX_AGE_S = 900  # el motor no decide con órdenes más viejas que esto

    def activity(self):
        """La interfaz avisa que se está usando; el caché solo carga en idle."""
        self._cache.touch()
        return {"ok": True}

    def _wanted_weapons(self):
        """Armas de mis rivens visibles, primero las de los rivens más cerca de su umbral de horas."""
        with store.connect() as conn:
            cfg, hours = store.settings(conn), store.riven_hours(conn)
        base = cfg.get("autodrop_hours", 10)
        extra = list(cfg.get("opp_weapons") or []) if cfg.get("opp_enabled") else []
        score = {}
        for i, a in list(self._seen.items()):
            if not a.get("visible", True):
                continue
            h = hours.get(i, {})
            ratio = h.get("hours", 0) / (h.get("hours_override") or base or 1)
            w = a["item"]["weapon_url_name"]
            score[w] = max(score.get(w, 0), ratio)
        return sorted(score, key=score.get, reverse=True) + [w for w in extra if w not in score]

    SNAPSHOT_PASS_S = 120

    def _snapshot_loop(self):
        """Una foto diaria por arma (stock y favoritas), solo en idle y por la cola central."""
        while not self._stop.wait(self.SNAPSHOT_PASS_S):
            if not self._cache.idle() or QUEUE.busy():
                continue
            try:
                with store.connect() as conn:
                    tracked = store.settings(conn).get("tracked_weapons") or []
                    todo = [w for w in list(self._wanted_weapons()) + tracked if not store.snapshot_done_today(conn, w)]
                    if not todo:
                        continue
                    e = self._cache.get(todo[0], self.VIEW_MAX_AGE_S) or self._cache.load(todo[0])
                    store.save_snapshot(conn, todo[0], e.get("market", []))
            except Exception:
                self._stop.wait(60)

    OPP_PASS_S = 90

    def _opp_loop(self):
        """Mira el caché de las armas vigiladas (lo llena el caché en idle) y avisa de las publicaciones
        muy por debajo de su estimado. No hace pedidos propios."""
        while not self._stop.wait(self.OPP_PASS_S):
            try:
                with store.connect() as conn:
                    cfg = store.settings(conn)
                if not cfg.get("opp_enabled"):
                    continue
                self.scan_opportunities(cfg)
            except Exception:
                logging.info("Alertas de oportunidad: se reintenta", exc_info=True)

    def scan_opportunities(self, cfg=None):
        if cfg is None:
            with store.connect() as conn:
                cfg = store.settings(conn)
        thr, gain = cfg.get("opp_threshold", 30), cfg.get("opp_min_gain", 15)
        mine = set(self._seen)
        n_new = 0
        for w in cfg.get("opp_weapons") or []:
            e = self._cache.get(w, self.CACHE_MAX_AGE_S)
            if not e or not e.get("market"):
                continue
            for o in opportunities.find(e["market"], self._rtype(w), thr, gain, mine, weapon=w):
                text = json.dumps({"weapon": w, **o}, ensure_ascii=False)
                with store.connect() as conn:
                    if store.add_opportunity(conn, o["id"], text):
                        n_new += 1
        return n_new

    def _fill_for_position(self):
        """Carga el caché de las armas de mi stock que falten (la tabla lo pidió; no espera a que la app esté ociosa)."""
        try:
            for w in self._wanted_weapons():
                if not self._cache.get(w, self._cache.TTL_S):
                    self._cache.load(w)
                    time.sleep(self._cache.PAUSE_S)
        except Exception:
            pass
        finally:
            self._filling = False

    def stock_position_pending(self):
        return bool(getattr(self, "_filling", False))

    def stock_position(self):
        """Dónde está cada riven publicado respecto del estimado. Usa el caché; si faltan armas lo completa en segundo plano."""
        if not getattr(self, "_filling", False) and any(
                not self._cache.get(w, self._cache.TTL_S) for w in self._wanted_weapons()):
            self._filling = True
            threading.Thread(target=self._fill_for_position, daemon=True).start()
        with store.connect() as conn:
            cfg, hours = store.settings(conn), store.riven_hours(conn)
        base = cfg.get("autodrop_hours", 10)
        out = {}
        for aid, a in list(self._seen.items()):
            if not a.get("visible", True):
                continue
            w = a["item"]["weapon_url_name"]
            e = self._cache.get(w, self.CACHE_MAX_AGE_S)
            if not e or not e.get("market"):
                continue
            h = hours.get(aid) or {}
            try:
                rtype = self._rtype(w)
            except (WFMError, requests.RequestException):
                rtype = None
            pos = stockcheck.position(auction_view(a), e["market"], rtype, h.get("hours"),
                                      h.get("hours_override") or base, weapon=w)
            if pos:
                out[aid] = pos
        return out

    def market_trend(self, weapon, days=90):
        """Tendencia del arma: primero la nube (historial central de todas las armas); la foto local
        completa los días que falten y es el respaldo si la nube no responde."""
        with store.connect() as conn:
            local = store.market_trend(conn, weapon, days)
        by_day = {p["day"]: p for p in local}
        try:
            r = requests.get(CLOUD_API_URL, params={"weapon": weapon, "days": days}, timeout=6)
            r.raise_for_status()
            by_day.update({p["day"]: p for p in r.json().get("points", [])})
        except (requests.RequestException, ValueError):
            pass
        return {"points": [by_day[d] for d in sorted(by_day)]}

    def weapon_orders(self, weapon):
        """Las 7 órdenes online más baratas del arma, desde el caché (la pide solo si falta)."""
        try:
            e = self._cache.get(weapon, self.VIEW_MAX_AGE_S)
            if not e or "market" not in e or (e["market"] and "c" not in e["market"][0]):   # caché viejo sin fechas
                e = self._cache.load(weapon)
        except (WFMError, requests.RequestException) as ex:
            return {"error": str(ex)}
        for a in e["orders"]:
            self._market[a["id"]] = a   # para poder abrir su resumen al tocarla
        return {"orders": [{**auction_view(a), "seller": a["owner"]["ingame_name"], "status": a["owner"]["status"],
                            "reputation": a["owner"].get("reputation"),
                            "created": a.get("created"), "last_seen": a["owner"].get("last_seen")} for a in e["orders"][:7]],
                "age_s": int(time.time() - e["at"]), "market": e.get("market", [])}

    def notifications(self):
        with store.connect() as conn:
            items = store.notifications(conn)
        return {"items": items, "unread": sum(1 for n in items if not n["read_at"])}

    def mark_read(self, notification_id=None):
        with store.connect() as conn:
            store.mark_read(conn, notification_id)
        return self.notifications()

    def revert_drop(self, drop_id):
        """Vuelve al precio anterior a la baja y apaga la baja automática de ese riven."""
        with store.connect() as conn:
            d = store.get_drop(conn, drop_id)
        if not d or d["reverted_at"]:
            return {"error": "Esa baja ya no se puede revertir."}
        aid = d["auction_id"]
        try:
            cur = self._current(aid)
            new = self.client.update_auction(
                aid, price=d["old_price"], visible=cur["visible"], note=cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0))
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        self._seen[aid] = new
        with store.connect() as conn:
            store.log_event(conn, new, "update")
            store.add_price(conn, aid, new["buyout_price"], "revert")
            store.mark_reverted(conn, drop_id, aid)
        return {"auction": auction_view(new), **self.notifications()}

    def set_autodrop(self, auction_id, on):
        with store.connect() as conn:
            store.set_autodrop(conn, auction_id, on)
        return {"ok": True}

    def set_overrides(self, auction_id, hours=None, amount=None, floor=None):
        def num(v, cast):
            try:
                v = cast(v)
                return v if v > 0 else None
            except (TypeError, ValueError):
                return None
        with store.connect() as conn:
            store.set_overrides(conn, auction_id, num(hours, float), num(amount, int), num(floor, int))
        return {"ok": True}

    def _estimate_for(self, a, exclude_id):
        """Vista, órdenes y estimado de un contrato (guardado o borrador)."""
        weapon = a["item"]["weapon_url_name"]
        orders = self.weapon_orders(weapon)
        view = auction_view(a)
        pool = {o["id"]: o for o in orders.pop("market", [])}
        positives = [s["slug"] for s in view["stats"] if s["positive"]]
        # Consultas por stats: todos juntos y cada par; así entran las publicaciones que de verdad se parecen.
        combos = [positives] if len(positives) >= 2 else []
        if len(positives) == 3:
            combos += [[x, y] for i, x in enumerate(positives) for y in positives[i + 1:]]
        failed = False
        for c in combos:
            try:
                for o in self._cache.targeted(weapon, c):
                    pool[o["id"]] = o
            except (WFMError, requests.RequestException):
                failed = True   # sin esas consultas el estimado sale bajo: se avisa en vez de callarlo
        try:
            rtype = self._rtype(weapon)
        except (WFMError, requests.RequestException):
            rtype = None
        est = estimate(view, list(pool.values()), exclude_id=exclude_id, rtype=rtype, weapon=weapon)
        if est:   # los comparables también se abren: se reconstruye el contrato desde lo guardado
            for c in est["comps"]:
                o = pool.get(c["id"])
                if o and c["id"] not in self._market:
                    self._market[c["id"]] = slim_to_raw(o, weapon)
        if est and failed:
            est["partial"] = True
        return view, orders, est

    def estimate_draft(self, item, exclude_id=None):
        """Estimado de un riven que todavía no se publicó, con lo que hay en el formulario."""
        try:
            a = {"id": "draft", "buyout_price": 0, "item": dict(item)}
            a["item"]["attributes"] = [{"url_name": x["url_name"], "positive": bool(x["positive"]),
                                        "value": float(x["value"])} for x in item["attributes"]]
            a["item"]["re_rolls"] = int(item.get("re_rolls") or 0)
            a["item"]["mod_rank"] = int(item.get("mod_rank") or 0)
            a["item"]["mastery_level"] = int(item.get("mastery_level") or 8)
            view, orders, est = self._estimate_for(a, exclude_id or "draft")
            return {"auction": view, "estimate": est}
        except (WFMError, requests.RequestException, KeyError, ValueError) as e:
            return {"error": str(e)}

    def _from_cache(self, auction_id):
        """Reconstruye un contrato ajeno desde el caché de órdenes (sobrevive a reinicios)."""
        for w, e in list(self._cache._data.items()):
            for o in e.get("market") or []:
                if o.get("id") == auction_id:
                    a = slim_to_raw(o, w)
                    self._market[auction_id] = a
                    return a
        return None

    def riven_summary(self, auction_id):
        """Resumen de un riven: historial de precios, horas y órdenes online más baratas del caché."""
        a = self._seen.get(auction_id)
        foreign = a is None
        if foreign:
            a = self._market.get(auction_id)
            if not a:   # alerta de oportunidad: sale del caché de mercado del arma
                a = self._from_cache(auction_id)
        if not a:
            return {"error": "Riven no encontrado."}
        if foreign:
            hist, h = [], None
        else:
            with store.connect() as conn:
                hist = store.price_history(conn, auction_id)
                h = store.riven_hours(conn).get(auction_id)
        view, orders, est = self._estimate_for(a, auction_id)
        out = {"auction": view, "history": hist, "hours": h, "orders": orders, "estimate": est}
        if foreign:
            out["market"] = {"seller": a["owner"]["ingame_name"], "status": a["owner"].get("status"),
                             "reputation": a["owner"].get("reputation")}
        return out

    def _drop_loop(self):
        while not self._stop.wait(self.DROP_PASS_S):
            try:
                r = self.autodrop_pass() if self._online else "offline"
                self._log_pass(r)
            except Exception:
                self._log_pass(traceback.format_exc())

    def _log_pass(self, result):
        try:
            p = store.DB_PATH.parent / "cache" / "autodrop.log"
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"{store.now_iso()} {result}" + chr(10))
        except Exception:
            pass

    def autodrop_pass(self):
        """Una pasada: baja como mucho UN riven. Decide solo con órdenes del caché."""
        with store.connect() as conn:
            cfg, hours = store.settings(conn), store.riven_hours(conn)
        if not cfg.get("autodrop_enabled", False):
            return None
        for aid, a in sorted(self._seen.items(), key=lambda kv: kv[1]["item"]["weapon_url_name"]):
            h = hours.get(aid)
            if not a.get("visible", True) or not h or not h["autodrop_on"]:
                continue
            need = h["hours_override"] or cfg.get("autodrop_hours", 10)
            if h["hours"] < need:
                continue
            e = self._cache.get(a["item"]["weapon_url_name"], self.CACHE_MAX_AGE_S)
            if not e:
                continue   # el caché lo carga en idle; sin datos frescos no se decide
            price = a["buyout_price"]
            others = [o["buyout_price"] for o in e["orders"] if o["id"] != aid]
            amount = h["amount_override"] or cfg.get("autodrop_amount", 5)
            floor = h["floor_override"] or cfg.get("autodrop_floor", 10)
            new = max(price - amount, floor)
            if not others or price <= min(others) or new >= price:
                with store.connect() as conn:   # ya es el más barato (o está en el piso): otras N horas
                    store.reset_riven_hours(conn, aid)
                continue
            return self._apply_drop(aid, new)
        return None

    def _apply_drop(self, aid, new):
        try:
            cur = self._current(aid)
            old = cur["buyout_price"]
            if new >= old:
                return None
            upd = self.client.update_auction(
                aid, price=new, visible=cur["visible"], note=cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0))
        except (WFMError, requests.RequestException):
            return None
        self._seen[aid] = upd
        item = upd["item"]
        text = f"Bajé {item['weapon_url_name']} {item.get('name', '')} de {old} a {new} pt".replace("  ", " ")
        with store.connect() as conn:
            store.log_event(conn, upd, "update")
            store.add_price(conn, aid, new, "auto")
            store.add_drop(conn, aid, old, new, text)
            store.reset_riven_hours(conn, aid)
        return {"id": aid, "old": old, "new": new}

    def online_hours(self):
        with store.connect() as conn:
            return {"hours": store.online_seconds(conn) / 3600}

    def on_closing(self):
        """Al cerrar la app: Invisible, salvo que el usuario lo haya desactivado.
        Cancela el cierre, muestra "Cerrando…" y cierra de verdad cuando termina."""
        if getattr(self, "_closing", False):
            return getattr(self, "_close_ok", False)
        self._closing = True
        self.stop_counter()
        # El evento corre en el hilo de la interfaz: evaluar JS acá se bloquea a sí mismo.
        threading.Thread(target=self._finish_close, daemon=True).start()
        return False

    def _finish_close(self):
        try:
            self._window.evaluate_js("showClosing()")
        except Exception:
            pass
        try:
            with store.connect() as conn:
                if store.settings(conn).get("invisible_on_close", True):
                    self.client.set_status("invisible", 60)
        except Exception:
            pass   # si falla, el estado vence solo
        try:
            store.make_backup(tag="-cierre")
        except Exception:
            logging.exception("Backup al cerrar")
        try:
            with store.connect() as conn:
                st = store.settings(conn)
            if st.get("cloud_code") and st.get("cloud_auto", True):
                self.cloud_upload()
        except Exception:
            logging.info("Copia en la nube al cerrar: no se pudo", exc_info=True)
        self._close_ok = True
        self._window.destroy()

    def search(self, weapon, n=7):
        """Precio de referencia: las `n` ventas directas más baratas del arma (cualquier stat)
        de vendedores en juego."""
        try:
            found = self.client.search_direct(weapon)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        top = cheapest_ingame(found, n)
        return {
            "results": [
                {**auction_view(a), "seller": a["owner"]["ingame_name"],
                 "reputation": a["owner"].get("reputation")}
                for a in top
            ],
            # Si la búsqueda llegó al corte y no hubo `n` in game, puede haber más fuera del corte.
            "maybe_incomplete": len(found) >= SEARCH_CAP - 10 and len(top) < n,
        }

    def request_log(self, since=0):
        """Pedidos recientes a warframe.market, con nombre corto (para el panel opcional de pedidos)."""
        return QUEUE.recent(int(since or 0))

    def queue_status(self):
        """Avance de la cola de pedidos a warframe.market (para la barra de progreso)."""
        return QUEUE.status()

    def market_search(self, weapon, stats=(), n=150):
        """Pestaña Mercado: ventas directas de un arma (con esos stats positivos, si hay), de las
        más baratas a las más caras (todos los vendedores, con su estado)."""
        stats = [s for s in stats if s]
        try:
            found = self.client.search_direct(weapon, stats)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        rows = [a for a in found if a.get("visible", True) and not a.get("closed") and not a.get("private")]
        rows.sort(key=lambda a: a["buyout_price"])
        rows = rows[:n]
        for a in rows:
            self._market[a["id"]] = a
        return {"results": [{**auction_view(a), "seller": a["owner"]["ingame_name"],
                             "status": a["owner"].get("status"), "reputation": a["owner"].get("reputation")}
                            for a in rows],
                "total": len(found)}

    # ---- Mis contratos ----------------------------------------------

    def my_auctions(self):
        """Todo lo que muestra la pantalla principal: contratos abiertos (API), y del registro
        local los cerrados, los costos, el stock unveiled y lo invertido."""
        try:
            auctions = [a for a in self.client.my_auctions() if a["is_direct_sell"]]
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        auctions.sort(key=lambda a: (not a["visible"], a["item"]["weapon_url_name"]))
        self._seen = {a["id"]: a for a in auctions}
        with store.connect() as conn:
            store.sync_rivens(conn, auctions)
        return {"auctions": [auction_view(a) for a in auctions], **self.local()}

    def local(self):
        """Solo los datos locales (no llama a la API)."""
        with store.connect() as conn:
            sh = store.sale_hours(conn)
            return {
                "closed": [{**auction_view(c["auction"]), "sold_price": c["sold_price"],
                            "closed_at": c["closed_at"], "hours_online": sh.get(c["auction"]["id"])}
                           for c in store.closed_auctions(conn)],
                "costs": store.costs(conn),
                "lots": store.lots(conn),
                "invested": store.invested(conn),
                "hours": store.riven_hours(conn),
            }

    # ---- Costos y stock unveiled (solo local) ----------------------------

    def set_cost(self, auction_id, cost):
        try:
            with store.connect() as conn:
                store.set_cost(conn, auction_id, None if cost in (None, "") else float(cost))
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def add_lot(self, riven_type, quantity, cost, cost_is_total=True, note=""):
        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError("La cantidad tiene que ser al menos 1")
            total = float(cost) if cost_is_total else float(cost) * quantity
            with store.connect() as conn:
                store.add_lot(conn, riven_type, quantity, total, note)
        except (ValueError, TypeError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def discard_from_lot(self, lot_id):
        """Un riven del lote se abrió y no se va a publicar."""
        try:
            with store.connect() as conn:
                store.open_from_lot(conn, int(lot_id), None)
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def transmute(self, auction_ids, riven_type):
        """Transmutación del juego: 4 rivens publicados se cierran (sin venta) y entra al stock
        unveiled 1 riven sin abrir del tipo que salió, con el costo de los 4 sumado. Ese costo ya
        está en "invertido" por los rivens sacrificados, así que el lote no lo suma otra vez."""
        ids = list(dict.fromkeys(auction_ids or []))
        if len(ids) != 4:
            return {"error": "Hay que elegir exactamente 4 rivens"}
        if riven_type not in store.RIVEN_TYPES:
            return {"error": "Tipo de riven inválido"}
        missing = [i for i in ids if i not in self._seen]
        if missing:
            return {"error": "Algún riven ya no está en la lista: actualizá y probá de nuevo"}
        with store.connect() as conn:
            known = store.costs(conn)
        total_cost = sum(known.get(i, {}).get("cost", 0) for i in ids)
        closed = []
        for auction_id in ids:
            res = self.close(auction_id)
            if "error" in res:
                note = f" Ya se cerraron {len(closed)} antes del error." if closed else ""
                return {"error": res["error"] + note, "transmuted": closed}
            closed.append(auction_id)
        try:
            with store.connect() as conn:
                store.add_lot(conn, riven_type, 1, total_cost, "Transmutación de 4 rivens", from_transmute=True)
        except store.sqlite3.Error as e:
            return {"error": f"Se cerraron los 4 pero no se pudo cargar el stock: {e}", "transmuted": closed}
        return {**self.local(), "transmuted": closed}

    def delete_lot(self, lot_id):
        try:
            with store.connect() as conn:
                store.delete_lot(conn, int(lot_id))
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def _current(self, auction_id, fresh=True):
        """El contrato tal como está en la API. `fresh=True` lo vuelve a leer (para no pisar
        la nota u otros campos con datos viejos); `False` usa la última lectura si la hay."""
        if not fresh and auction_id in self._seen:
            return self._seen[auction_id]
        for a in self.client.my_auctions():
            if a["id"] == auction_id:
                self._seen[auction_id] = a
                return a
        raise WFMError("El contrato ya no existe en warframe.market (¿se cerró desde la web?)")

    def update(self, auction_id, price=None, visible=None, note=None):
        """Cambia precio, visibilidad y/o nota; lo que venga en None queda como está.
        (La API no permite cambiar los stats de un contrato ya publicado.)"""
        try:
            cur = self._current(auction_id)
            new = self.client.update_auction(
                auction_id,
                price=int(price) if price is not None else cur["buyout_price"],
                visible=bool(visible) if visible is not None else cur["visible"],
                note=note if note is not None else cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0),
            )
        except (WFMError, requests.RequestException, ValueError) as e:
            return {"error": str(e)}
        self._seen[auction_id] = new
        with store.connect() as conn:
            store.log_event(conn, new, "update")
            store.add_price(conn, auction_id, new["buyout_price"], "manual")
        return {"auction": auction_view(new)}

    def price_history(self, auction_id):
        with store.connect() as conn:
            return {"history": store.price_history(conn, auction_id)}

    def republish(self, auction_id, item=None, price=None, visible=None, note=None, polarity=None):
        """La API no deja editar los datos de un contrato publicado (polaridad, arma, stats, MR,
        rango, rolls, nombre): se publica uno nuevo con los datos cambiados, se cierra el viejo (sin
        ensuciar el historial de cerrados) y el costo y el vínculo con el lote pasan al nuevo.
        `item` es el del formulario; sin `item` se copia el viejo (y `polarity` lo pisa).
        Si falla la publicación, el viejo no se toca."""
        try:
            cur = self._current(auction_id)
            old = cur["item"]
            if item is None:
                item = {
                    "weapon_url_name": old["weapon_url_name"],
                    "name": old.get("name", ""),
                    "attributes": old["attributes"],
                    "mastery_level": old["mastery_level"],
                    "mod_rank": old["mod_rank"],
                    "re_rolls": old["re_rolls"],
                    "polarity": polarity or old.get("polarity"),
                }
            positives = [x for x in item["attributes"] if x["positive"]]
            negatives = [x for x in item["attributes"] if not x["positive"]]
            if not 2 <= len(positives) <= 3 or len(negatives) > 1:
                raise ValueError("Un riven tiene 2 o 3 stats positivos y como mucho 1 negativo")
            if not str(item.get("name", "")).strip():
                raise ValueError("Falta el nombre del riven")
            new = self.client.create_direct_sale(
                {
                    "weapon_url_name": item["weapon_url_name"],
                    "name": item["name"].strip(),
                    "attributes": [{"url_name": t["url_name"], "positive": bool(t["positive"]),
                                    "value": float(t["value"])} for t in item["attributes"]],
                    "mastery_level": int(item["mastery_level"]),
                    "mod_rank": int(item["mod_rank"]),
                    "re_rolls": int(item["re_rolls"]),
                    "polarity": item["polarity"],
                },
                price=int(price) if price is not None else cur["buyout_price"],
                visible=bool(visible) if visible is not None else cur.get("visible", True),
                note=note if note is not None else cur.get("note_raw", ""),
            )
        except (WFMError, requests.RequestException, ValueError, KeyError) as e:
            return {"error": str(e)}
        self._seen[new["id"]] = new
        warning = None
        try:
            self.client.close_auction(auction_id)
            self._seen.pop(auction_id, None)
        except (WFMError, requests.RequestException) as e:
            warning = f"Se publicó la nueva pero no se pudo cerrar la vieja: {e}"
        with store.connect() as conn:
            store.log_event(conn, new, "create")
            store.sync_rivens(conn, [new])
            store.add_price(conn, new["id"], new["buyout_price"], "publish")
            if warning is None:
                conn.execute("UPDATE riven_costs SET auction_id = ? WHERE auction_id = ?", (new["id"], auction_id))
                conn.execute("UPDATE lot_openings SET auction_id = ? WHERE auction_id = ?", (new["id"], auction_id))
                conn.commit()
        return {"auction": auction_view(new), "replaced": None if warning else auction_id,
                "warning": warning, **self.local()}

    def repolarize(self, auction_id, polarity, price=None, visible=None, note=None):
        return self.republish(auction_id, None, price, visible, note, polarity)

    def create(self, item, price, visible=True, note="", cost=None, lot_id=None):
        """Publica una venta directa. `item` viene del formulario del modal. `cost` y `lot_id`
        (si el riven salió de un lote del stock unveiled) se guardan solo en local."""
        try:
            positives = [a for a in item["attributes"] if a["positive"]]
            negatives = [a for a in item["attributes"] if not a["positive"]]
            if not 2 <= len(positives) <= 3 or len(negatives) > 1:
                raise ValueError("Un riven tiene 2 o 3 stats positivos y como mucho 1 negativo")
            if not item.get("name", "").strip():
                raise ValueError("Falta el nombre del riven")
            if lot_id:
                with store.connect() as conn:
                    lot = store.get_lot(conn, int(lot_id))
                if not lot or lot["remaining"] <= 0:
                    raise ValueError("Ese lote ya no tiene rivens sin abrir")
            new = self.client.create_direct_sale(
                {
                    "weapon_url_name": item["weapon_url_name"],
                    "name": item["name"].strip(),
                    "attributes": [{"url_name": a["url_name"], "positive": bool(a["positive"]),
                                    "value": float(a["value"])} for a in item["attributes"]],
                    "mastery_level": int(item["mastery_level"]),
                    "mod_rank": int(item["mod_rank"]),
                    "re_rolls": int(item["re_rolls"]),
                    "polarity": item["polarity"],
                },
                price=int(price), visible=bool(visible), note=note or "",
            )
        except (WFMError, requests.RequestException, ValueError, KeyError) as e:
            return {"error": str(e)}
        self._seen[new["id"]] = new
        with store.connect() as conn:
            store.log_event(conn, new, "create")
            if lot_id:
                store.open_from_lot(conn, int(lot_id), new["id"])
            if cost not in (None, ""):
                store.set_cost(conn, new["id"], float(cost), int(lot_id) if lot_id else None)
        return {"auction": auction_view(new), **self.local()}

    def close(self, auction_id, sold_price=None):
        """Cierra el contrato y guarda una copia local (después desaparece de la API).
        La copia sale de la última lectura (un pedido menos): para el historial alcanza."""
        try:
            cur = self._current(auction_id, fresh=False)
            self.client.close_auction(auction_id)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        self._seen.pop(auction_id, None)
        closed_at = store.now_iso()
        with store.connect() as conn:
            store.log_event(conn, {**cur, "closed": True}, "close",
                            sold_price=int(sold_price) if sold_price else None, at=closed_at)
            h = store.riven_hours(conn).get(auction_id)
            if sold_price and h:
                store.log_sale_hours(conn, auction_id, h["hours"], at=closed_at)
        return {"closed": auction_id, "closed_at": closed_at}


def slim_to_raw(o, weapon):
    """Contrato mínimo (formato crudo de la API) a partir de un `slim`, para abrir su resumen."""
    return {"id": o["id"], "buyout_price": o["p"], "created": o.get("c"), "updated": o.get("c"),
            "item": {"weapon_url_name": weapon, "name": o.get("n") or "", "re_rolls": o["r"], "mod_rank": o.get("k"),
                     "mastery_level": o.get("m"),
                     "attributes": [{"url_name": s, "value": v, "positive": p} for s, v, p in o["s"]]},
            "owner": {"ingame_name": o.get("nm") or "?", "status": o.get("st"), "last_seen": o.get("ls")}}


def auction_view(a):
    """Lo que la interfaz necesita de un contrato."""
    item = a["item"]
    return {
        "id": a["id"],
        "price": a["buyout_price"],
        "visible": a.get("visible", True),
        "weapon": item["weapon_url_name"],
        "name": item.get("name", ""),
        "stats": [{"slug": s["url_name"], "value": s["value"], "positive": s["positive"]}
                  for s in item["attributes"]],
        "rolls": item.get("re_rolls"),
        "mr": item.get("mastery_level"),
        "rank": item.get("mod_rank"),
        "polarity": item.get("polarity"),
        "note": a.get("note_raw", ""),
        "updated": a.get("updated"),
        "created": a.get("created"),
    }


def set_window_icon():
    """pywebview en Windows no aplica el ícono a la ventana: se lo ponemos con Win32."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd or not ICON.exists():
        return
    for size, which in ((16, 0), (32, 1)):  # ICON_SMALL, ICON_BIG
        hicon = user32.LoadImageW(None, str(ICON), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        user32.SendMessageW(hwnd, 0x80, which, hicon)  # WM_SETICON


def main():
    # Agrupa la ventana en la barra de tareas con su propio ícono, no el de Python.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("franh01.rivenstock")
    api = Api()
    api.start_counter()
    window = webview.create_window(
        TITLE, str(ROOT / "ui" / "index.html"), js_api=api,
        width=1180, height=780, min_size=(860, 580), background_color="#0c0518", maximized=True,
    )
    api._window = window
    window.events.shown += set_window_icon
    window.events.closing += api.on_closing
    webview.start()


if __name__ == "__main__":
    try:
        main()
        logging.info("Cierre normal")
        crashes.end()
    except Exception:
        logging.critical("La app no pudo arrancar", exc_info=True)
        crashes.record("el arranque", sys.exc_info())
        ctypes.windll.user32.MessageBoxW(None, "Riven Stock no pudo arrancar. Detalle en: " + str(LOG_FILE), TITLE, 0x10)
        raise
