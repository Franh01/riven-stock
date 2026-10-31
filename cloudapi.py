"""Copia en la nube y envío de ventas anónimas: métodos de Api (mixin), ver docs/ARQUITECTURA.md."""

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests

import cloud_backup
import loophealth
import store
import updater

# Calibración del estimado por arma (Lambda riven-stock-estimator, ver cloud/estimator.yml).
# Publica una vez por día un factor por arma medido contra las ventas reales.
ESTIMATOR_URL = "https://3s3sggd5nvsrvqsqeupdxhcljy0kpnmz.lambda-url.us-east-1.on.aws/"


class CloudMixin:
    CLOUD_EVERY_S = 20 * 3600
    _estimator_busy = False

    def _cloud_set(self, **kv):
        with store.connect() as conn:
            for k, v in kv.items():
                store.set_setting(conn, k, v)

    def estimator_refresh(self):
        """Lo llama pricing cuando el archivo de factores está viejo (o no está).
        Nunca frena un estimado: baja en un hilo y si falla se sigue con lo que haya."""
        if self._estimator_busy:
            return
        threading.Thread(target=self._estimator_download, daemon=True).start()

    def _estimator_download(self):
        import pricing
        self._estimator_busy = True
        try:
            r = requests.get(ESTIMATOR_URL, timeout=10)
            r.raise_for_status()
            d = r.json()
            if not isinstance(d.get("factors"), dict) or not d.get("updated"):
                return   # respuesta rara: mejor no pisar lo que ya hay
            p = pricing.factors_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            tmp.replace(p)
        except (requests.RequestException, ValueError, OSError) as e:
            logging.info("Calibración: no se pudo bajar los factores (%s)", e)
        finally:
            self._estimator_busy = False

    def cloud_info(self):
        with store.connect() as conn:
            st = store.settings(conn)
        return {"code": st.get("cloud_code"), "auto": st.get("cloud_auto", True), "last": st.get("cloud_last"),
                "active": st.get("cloud_active"), "share": st.get("share_sales") is not False}

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

    def _sales_payload(self, conn, since):
        """Ventas reales marcadas en la app desde `since`, anónimas (sin usuario ni id de contrato en claro)."""
        out = []
        for r in conn.execute("SELECT auction_id, sold_price, snapshot, at FROM auction_events "
                              "WHERE action = 'close' AND sold_price IS NOT NULL AND at > ? ORDER BY at LIMIT 50",
                              (since or "",)).fetchall():
            a = json.loads(r["snapshot"])
            item = a.get("item") or {}
            out.append({"id": hashlib.sha256(f"rs-sale:{r['auction_id']}".encode()).hexdigest(),
                        "weapon": item.get("weapon_url_name"),
                        "attrs": [[s["url_name"], s["value"], bool(s["positive"])] for s in item.get("attributes", [])],
                        "rolls": item.get("re_rolls"), "mr": item.get("mastery_level"), "rank": item.get("mod_rank"),
                        "price": a.get("buyout_price"), "sold": r["sold_price"],
                        "listed": a.get("created"), "closed": r["at"], "_at": r["at"]})
        return out

    def _share_sales(self, st, iid):
        """Si el usuario lo activó, manda las ventas nuevas (lotes de 50) y recuerda hasta dónde llegó."""
        if st.get("share_sales") is False:   # activado por defecto; solo se frena si el usuario lo apaga
            return
        since = st.get("share_sales_last")
        for _ in range(10):
            with store.connect() as conn:
                batch = self._sales_payload(conn, since)
            if not batch:
                return
            cloud_backup.send_sales(iid, updater.version_actual(), [{k: v for k, v in s.items() if k != "_at"} for s in batch])
            since = batch[-1]["_at"]
            self._cloud_set(share_sales_last=since)

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
                self._share_sales(st, iid)
                last = st.get("cloud_last")
                due = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > self.CLOUD_EVERY_S
                if st.get("cloud_code") and st.get("cloud_auto", True) and due:
                    self.cloud_upload()
                loophealth.beat("nube", 1800)
            except Exception as e:
                loophealth.beat("nube", 1800, e)
                logging.info("Copia en la nube: se reintenta más tarde", exc_info=True)
            if self._stop.wait(1800):
                return
