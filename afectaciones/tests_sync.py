import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agro.models import Cultivo, UnidadAgricola

from .models import Afectacion, EventoSismico, Perdida

Usuario = get_user_model()


class ApiSincronizacionTests(TestCase):
    """Lote enviado por el dispositivo tras registrar sin conexión (RF-20)."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10"))
        cls.finca_luis = UnidadAgricola.objects.create(propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("10"))
        cls.cafe = Cultivo.objects.create(unidad=cls.finca, tipo="Café")

    def setUp(self):
        self.client.force_login(self.ana)
        self.url = reverse("api_sincronizar")

    def evento(self, **extra):
        d = {
            "id": str(uuid.uuid4()),
            "unidad_id": str(self.finca.pk),
            "fecha_hora": (timezone.now() - timedelta(hours=3)).isoformat(),
            "magnitud": "4.2",
            "epicentro": "Cerca del río",
        }
        d.update(extra)
        return d

    def afectacion(self, evento_id, **extra):
        d = {
            "id": str(uuid.uuid4()),
            "evento_id": str(evento_id),
            "elemento": "CULTIVO",
            "tipo_dano": "GRIETAS",
            "severidad": "MODERADA",
            "area_afectada_ha": "2.5",
            "perdida": {"cantidad": "100", "unidad_medida": "KG", "valor_estimado_cop": "300000"},
        }
        d.update(extra)
        return d

    def enviar(self, lote):
        return self.client.post(self.url, json.dumps(lote), content_type="application/json")

    def test_guarda_evento_y_afectacion_con_perdida(self):
        ev = self.evento()
        af = self.afectacion(ev["id"], cultivo_id=str(self.cafe.pk))
        r = self.enviar({"eventos": [ev], "afectaciones": [af]})
        self.assertEqual(r.status_code, 200)
        res = r.json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "ok")
        self.assertEqual(res["afectaciones"][0]["estado"], "ok")
        e = EventoSismico.objects.get(pk=ev["id"])
        self.assertEqual(e.usuario, self.ana)
        self.assertIsNotNone(e.sincronizado_en)
        a = Afectacion.objects.get(pk=af["id"])
        self.assertEqual(a.unidad, self.finca)
        self.assertEqual(a.cultivo, self.cafe)
        self.assertEqual(Perdida.objects.get(afectacion=a).valor_estimado_cop, Decimal("300000"))

    def test_reenviar_el_mismo_lote_no_duplica(self):
        ev = self.evento()
        af = self.afectacion(ev["id"])
        lote = {"eventos": [ev], "afectaciones": [af]}
        self.enviar(lote)
        r = self.enviar(lote)
        res = r.json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "ya_existia")
        self.assertEqual(res["afectaciones"][0]["estado"], "ya_existia")
        self.assertEqual(EventoSismico.objects.count(), 1)
        self.assertEqual(Afectacion.objects.count(), 1)
        self.assertEqual(Perdida.objects.count(), 1)

    def test_no_puede_usar_unidad_de_otro_productor(self):
        ev = self.evento(unidad_id=str(self.finca_luis.pk))
        res = self.enviar({"eventos": [ev]}).json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "error")
        self.assertEqual(EventoSismico.objects.count(), 0)

    def test_no_puede_tomar_el_id_de_otro_productor(self):
        ajeno = EventoSismico.objects.create(
            usuario=self.luis, unidad=self.finca_luis, fecha_hora=timezone.now() - timedelta(days=1)
        )
        ev = self.evento(id=str(ajeno.pk))
        res = self.enviar({"eventos": [ev]}).json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "error")
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.usuario, self.luis)

    def test_fecha_en_el_futuro_se_rechaza(self):
        ev = self.evento(fecha_hora=(timezone.now() + timedelta(days=2)).isoformat())
        res = self.enviar({"eventos": [ev]}).json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "error")

    def test_mismo_sismo_con_otro_id_es_conflicto_y_la_afectacion_se_reasigna(self):
        fecha = (timezone.now() - timedelta(hours=5)).isoformat()
        primero = self.evento(fecha_hora=fecha)
        self.enviar({"eventos": [primero]})
        repetido = self.evento(fecha_hora=fecha)
        af = self.afectacion(repetido["id"])
        res = self.enviar({"eventos": [repetido], "afectaciones": [af]}).json()["resultados"]
        self.assertEqual(res["eventos"][0]["estado"], "conflicto")
        self.assertEqual(res["eventos"][0]["id_existente"], primero["id"])
        self.assertEqual(res["afectaciones"][0]["estado"], "ok")
        self.assertEqual(Afectacion.objects.get(pk=af["id"]).evento_id, uuid.UUID(primero["id"]))

    def test_un_registro_invalido_no_impide_guardar_los_demas(self):
        ev = self.evento()
        buena = self.afectacion(ev["id"])
        mala = self.afectacion(ev["id"], severidad="CATASTROFICA")
        res = self.enviar({"eventos": [ev], "afectaciones": [mala, buena]}).json()["resultados"]
        self.assertEqual([x["estado"] for x in res["afectaciones"]], ["error", "ok"])
        self.assertEqual(Afectacion.objects.count(), 1)

    def test_area_mayor_que_la_unidad_se_rechaza(self):
        ev = self.evento()
        af = self.afectacion(ev["id"], area_afectada_ha="99")
        res = self.enviar({"eventos": [ev], "afectaciones": [af]}).json()["resultados"]
        self.assertEqual(res["afectaciones"][0]["estado"], "error")
        self.assertIn("area_afectada_ha", res["afectaciones"][0]["errores"])

    def test_area_no_numerica_no_rompe_el_servidor(self):
        ev = self.evento()
        for valor in ("abc", None, "NaN", ""):
            af = self.afectacion(ev["id"], area_afectada_ha=valor)
            res = self.enviar({"eventos": [ev], "afectaciones": [af]}).json()["resultados"]
            self.assertEqual(res["afectaciones"][0]["estado"], "error")

    def test_si_falla_la_perdida_no_queda_la_afectacion_a_medias(self):
        ev = self.evento()
        af = self.afectacion(ev["id"], perdida={"cantidad": "abc", "valor_estimado_cop": "1"})
        res = self.enviar({"eventos": [ev], "afectaciones": [af]}).json()["resultados"]
        self.assertEqual(res["afectaciones"][0]["estado"], "error")
        self.assertEqual(Afectacion.objects.count(), 0)

    def test_cultivo_de_otra_unidad_se_rechaza(self):
        otra = UnidadAgricola.objects.create(propietario=self.ana, nombre="Otra", area_ha=Decimal("5"))
        cultivo_otro = Cultivo.objects.create(unidad=otra, tipo="Plátano")
        ev = self.evento()
        af = self.afectacion(ev["id"], cultivo_id=str(cultivo_otro.pk))
        res = self.enviar({"eventos": [ev], "afectaciones": [af]}).json()["resultados"]
        self.assertEqual(res["afectaciones"][0]["estado"], "error")

    def test_sin_sesion_responde_401_en_json(self):
        self.client.logout()
        r = self.enviar({"eventos": []})
        self.assertEqual(r.status_code, 401)
        self.assertIn("error", r.json())

    def test_json_invalido_responde_400(self):
        r = self.client.post(self.url, "no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(self.url, "[1, 2]", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_lote_demasiado_grande_responde_413(self):
        eventos = [self.evento() for _ in range(201)]
        r = self.enviar({"eventos": eventos})
        self.assertEqual(r.status_code, 413)
        self.assertEqual(EventoSismico.objects.count(), 0)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ApiDatosBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        finca = UnidadAgricola.objects.create(propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10"))
        UnidadAgricola.objects.create(propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("4"))
        Cultivo.objects.create(unidad=finca, tipo="Café")
        Cultivo.objects.create(unidad=finca, tipo="Maíz", activo=False)

    def test_devuelve_solo_lo_del_usuario(self):
        self.client.force_login(self.ana)
        r = self.client.get(reverse("api_datos_base"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["usuario_id"], str(self.ana.pk))
        self.assertEqual([u["nombre"] for u in datos["unidades"]], ["Finca Ana"])
        self.assertEqual([c["tipo"] for c in datos["unidades"][0]["cultivos"]], ["Café"])
        self.assertIn(["GRAVE", "Grave"], datos["catalogos"]["severidades"])
        self.assertIn("csrftoken", r.cookies)

    def test_sin_sesion_responde_401(self):
        r = self.client.get(reverse("api_datos_base"))
        self.assertEqual(r.status_code, 401)
