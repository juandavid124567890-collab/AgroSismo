import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from afectaciones.models import Afectacion, EventoSismico
from agro.models import UnidadAgricola

from .models import Finca

Usuario = get_user_model()


class FincaCompartidaTests(TestCase):
    """Quienes están en la misma finca ven y registran los mismos datos."""

    @classmethod
    def setUpTestData(cls):
        cls.finca_a = Finca.objects.create(nombre="La Esperanza")
        cls.finca_b = Finca.objects.create(nombre="El Roble")
        cls.admin = Usuario.objects.create_user("ana", password="x-segura-123", finca=cls.finca_a, rol="ADMIN")
        cls.obrero = Usuario.objects.create_user("beto", password="x-segura-123", finca=cls.finca_a)
        cls.vecino = Usuario.objects.create_user("carlos", password="x-segura-123", finca=cls.finca_b)
        cls.unidad = UnidadAgricola.objects.create(propietario=cls.admin, nombre="Lote 1", area_ha=Decimal("3"))
        cls.unidad_vecino = UnidadAgricola.objects.create(propietario=cls.vecino, nombre="Lote V", area_ha=Decimal("3"))
        cls.evento = EventoSismico.objects.create(
            usuario=cls.admin, unidad=cls.unidad, fecha_hora=timezone.now() - timedelta(days=1), magnitud=Decimal("4.5")
        )
        cls.afectacion = Afectacion.objects.create(
            evento=cls.evento, unidad=cls.unidad, elemento="TERRENO", tipo_dano="GRIETAS",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )

    def test_companero_ve_las_unidades_de_la_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.get(reverse("unidades"))
        self.assertContains(r, "Lote 1")
        self.assertNotContains(r, "Lote V")

    def test_companero_ve_sismos_y_afectaciones(self):
        self.client.force_login(self.obrero)
        self.assertEqual(self.client.get(reverse("evento_detalle", args=[self.evento.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("afectacion_detalle", args=[self.afectacion.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse("eventos")), "Lote 1")

    def test_otra_finca_no_ve_nada(self):
        self.client.force_login(self.vecino)
        self.assertEqual(self.client.get(reverse("unidad_detalle", args=[self.unidad.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("evento_detalle", args=[self.evento.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("afectacion_detalle", args=[self.afectacion.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("eventos")), "Lote 1")

    def test_companero_puede_registrar_un_sismo_en_la_unidad_de_la_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.post(reverse("evento_crear"), {
            "unidad": self.unidad.pk,
            "fecha_hora": (timezone.localtime() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "magnitud": "3.8", "epicentro": "", "observaciones": "",
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(EventoSismico.objects.filter(usuario=self.obrero, unidad=self.unidad).exists())

    def test_no_puede_registrar_sismo_en_unidad_de_otra_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.post(reverse("evento_crear"), {
            "unidad": self.unidad_vecino.pk,
            "fecha_hora": (timezone.localtime() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "magnitud": "3.8", "epicentro": "", "observaciones": "",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(EventoSismico.objects.filter(unidad=self.unidad_vecino).exists())

    def test_nombre_de_unidad_no_se_repite_dentro_de_la_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.post(reverse("unidad_crear"), {
            "nombre": "lote 1", "departamento": "", "municipio": "", "vereda": "", "area_ha": "2",
        })
        self.assertContains(r, "Ya hay una unidad con ese nombre en tu finca.")

    def test_estadisticas_cuentan_los_datos_de_la_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.context["total_afectaciones"], 1)
        self.assertEqual(r.context["total_unidades"], 1)

    def test_datos_base_del_dispositivo_incluye_unidades_de_la_finca(self):
        self.client.force_login(self.obrero)
        datos = self.client.get(reverse("api_datos_base")).json()
        self.assertEqual([u["nombre"] for u in datos["unidades"]], ["Lote 1"])

    def test_sincronizar_sismo_en_unidad_de_la_finca(self):
        self.client.force_login(self.obrero)
        lote = {"eventos": [{
            "id": str(uuid.uuid4()), "unidad_id": str(self.unidad.pk),
            "fecha_hora": (timezone.now() - timedelta(hours=5)).isoformat(), "magnitud": "3.1",
        }], "afectaciones": []}
        r = self.client.post(reverse("api_sincronizar"), json.dumps(lote), content_type="application/json")
        self.assertEqual(r.json()["resultados"]["eventos"][0]["estado"], "ok")

    def test_sincronizar_en_unidad_de_otra_finca_se_rechaza(self):
        self.client.force_login(self.obrero)
        lote = {"eventos": [{
            "id": str(uuid.uuid4()), "unidad_id": str(self.unidad_vecino.pk),
            "fecha_hora": (timezone.now() - timedelta(hours=5)).isoformat(), "magnitud": "3.1",
        }], "afectaciones": []}
        r = self.client.post(reverse("api_sincronizar"), json.dumps(lote), content_type="application/json")
        self.assertEqual(r.json()["resultados"]["eventos"][0]["estado"], "error")

    def test_historial_incluye_afectaciones_de_la_finca(self):
        self.client.force_login(self.obrero)
        r = self.client.get(reverse("historial"))
        self.assertContains(r, "Lote 1")
