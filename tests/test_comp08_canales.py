# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-02
import sys
import textwrap
from pathlib import Path

from trotamundos.dominio.puertos_notificaciones import Propuesta
from trotamundos.notificaciones.canales import descubrir

RAIZ = Path(__file__).resolve().parents[1] / "src" / "trotamundos"
CANALES = RAIZ / "notificaciones" / "canales"


def test_se_descubren_email_whatsapp_e_instagram():
    canales = descubrir()
    assert set(canales) == {"email", "whatsapp", "instagram"}
    assert all(clase().nombre == nombre for nombre, clase in canales.items())


async def test_un_canal_simulado_registra_lo_enviado_y_admite_demora_y_caida():
    email = descubrir()["email"]()
    await email.enviar("ana@mail.com", Propuesta("Hola", "Cuerpo"))
    assert email.enviados == [("ana@mail.com", Propuesta("Hola", "Cuerpo"))] and email.llamadas == 1


def test_AC_COMP_08_02_instagram_es_un_solo_archivo_y_no_cambia_nada_mas():
    # Ningún otro archivo del código menciona a Instagram: ni la composición, ni la configuración, ni los otros canales.
    menciones = [a.relative_to(RAIZ) for a in RAIZ.rglob("*.py")
                 if "instagram" in a.read_text().lower() and a.name != "instagram.py"]
    assert menciones == [], f"mencionan a Instagram: {menciones}"
    assert (CANALES / "instagram.py").exists()
    # Un canal más es un archivo más: se descubre sin editar ningún otro.
    assert {p.stem for p in CANALES.glob("*.py")} == {"__init__", "base", "email", "whatsapp", "instagram"}


def test_un_canal_nuevo_se_descubre_con_solo_agregar_su_archivo(tmp_path, monkeypatch):
    paquete = tmp_path / "canales_prueba"
    paquete.mkdir()
    (paquete / "__init__.py").write_text("")
    (paquete / "telegram.py").write_text(textwrap.dedent('''
        from trotamundos.notificaciones.canales.base import CanalSimulado, canal

        @canal("telegram")
        class CanalTelegram(CanalSimulado):
            pass
    '''))
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        assert set(descubrir("canales_prueba")) == {"telegram"}
    finally:
        sys.modules.pop("canales_prueba", None)
        sys.modules.pop("canales_prueba.telegram", None)
