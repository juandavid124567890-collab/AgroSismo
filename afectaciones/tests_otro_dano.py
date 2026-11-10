import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from agro.models import UnidadAgricola

from .models import Afectacion, EventoSismico

Usuario = get_user_model()


class FormatoMilesTests(SimpleTestCase):
    def render(self, plantilla, valor):
        return Template("{% load formato %}" + plantilla).render(Context({"v": valor}))

    def test_cop_con_puntos(self):
        self.assertEqual(self.render("{{ v|cop }}", Decimal("1533333.00")), "$1.533.333")
        self.assertEqual(self.render("{{ v|cop }}", 233333), "$233.333")

    def test_cop_vacio_o_cero(self):
        self.assertEqual(self.render("{{ v|cop }}", None), "$0")
        self.assertEqual(self.render("{{ v|cop }}", 0), "$0")

    def test_miles_sin_signo(self):
        self.assertEqual(self.render("{{ v|miles }}", 1500000), "1.500.000")


class OtroDanoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10"))
        cls.evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.finca, fecha_hora=timezone.now() - timedelta(hours=2)
        )

    def nueva(self, **extra):
        datos = dict(
            evento=self.evento, unidad=self.finca, elemento="TERRENO", tipo_dano="OTRO",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )
        datos.update(extra)
        return Afectacion(**datos)

    def test_otro_exige_texto(self):
        with self.assertRaises(ValidationError) as ctx:
            self.nueva().full_clean()
        self.assertIn("tipo_dano_otro", ctx.exception.message_dict)

    def test_otro_con_texto_se_muestra_completo(self):
        a = self.nueva(tipo_dano_otro="  Pérdida de suelo fértil ")
        a.full_clean()
        self.assertEqual(a.tipo_dano_texto, "Otro: Pérdida de suelo fértil")

    def test_texto_se_borra_si_el_tipo_no_es_otro(self):
        a = self.nueva(tipo_dano="GRIETAS", tipo_dano_otro="algo")
        a.full_clean()
        self.assertEqual(a.tipo_dano_otro, "")
        self.assertEqual(a.tipo_dano_texto, "Grietas")

    def test_api_guarda_el_otro_dano(self):
        self.client.force_login(self.ana)
        ev = {
            "id": str(uuid.uuid4()), "unidad_id": str(self.finca.pk),
            "fecha_hora": (timezone.now() - timedelta(hours=3)).isoformat(),
        }
        af = {
            "id": str(uuid.uuid4()), "evento_id": ev["id"], "elemento": "TERRENO", "tipo_dano": "OTRO",
            "tipo_dano_otro": "Pérdida de suelo fértil", "severidad": "LEVE", "area_afectada_ha": "1",
        }
        r = self.client.post(
            reverse("api_sincronizar"), json.dumps({"eventos": [ev], "afectaciones": [af]}),
            content_type="application/json",
        )
        self.assertEqual(r.json()["resultados"]["afectaciones"][0]["estado"], "ok")
        self.assertEqual(Afectacion.objects.get(pk=af["id"]).tipo_dano_texto, "Otro: Pérdida de suelo fértil")

    def test_api_rechaza_otro_sin_texto(self):
        self.client.force_login(self.ana)
        ev = {
            "id": str(uuid.uuid4()), "unidad_id": str(self.finca.pk),
            "fecha_hora": (timezone.now() - timedelta(hours=3)).isoformat(),
        }
        af = {
            "id": str(uuid.uuid4()), "evento_id": ev["id"], "elemento": "TERRENO", "tipo_dano": "OTRO",
            "severidad": "LEVE", "area_afectada_ha": "1",
        }
        r = self.client.post(
            reverse("api_sincronizar"), json.dumps({"eventos": [ev], "afectaciones": [af]}),
            content_type="application/json",
        )
        self.assertEqual(r.json()["resultados"]["afectaciones"][0]["estado"], "error")

    def test_detalle_e_historial_muestran_el_texto(self):
        a = self.nueva(tipo_dano_otro="Pérdida de suelo fértil")
        a.full_clean()
        a.save()
        self.client.force_login(self.ana)
        self.assertContains(self.client.get(reverse("afectacion_detalle", args=[a.pk])), "Otro: Pérdida de suelo fértil")
        self.assertContains(self.client.get(reverse("historial")), "Otro: Pérdida de suelo fértil")


class FormatoHectareasTests(SimpleTestCase):
    def test_hectareas_con_dos_decimales(self):
        from .templatetags.formato import ha

        self.assertEqual(ha(Decimal("31.0200000000")), "31,02")
        self.assertEqual(ha(Decimal("4")), "4,00")
        self.assertEqual(ha(Decimal("1250.5")), "1.250,50")
        self.assertEqual(ha(None), "0,00")


class MarcaDeAguaPdfTests(SimpleTestCase):
    def test_el_pdf_se_genera_con_marca_de_agua(self):
        from . import pdf

        self.assertTrue(pdf.LOGO_MARCA.exists(), "falta static/img/logo-marca.png")
        datos = pdf.generar_pdf(
            "Ana", "07/11/2026", "Todos", {"total": 0, "eventos": 0, "area": Decimal("0"), "valor": Decimal("0")},
            [], [], [],
        )
        self.assertTrue(datos.startswith(b"%PDF"))
