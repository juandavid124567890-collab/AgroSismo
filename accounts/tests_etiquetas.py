from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from afectaciones import pdf

User = get_user_model()


class EtiquetasFincaYUnidadTests(TestCase):
    """«Finca» es la organización; lo que se registra dentro es la «unidad agrícola»."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", password="x-segura-123")

    def test_registro_rapido_pide_la_unidad_agricola(self):
        self.client.force_login(self.ana)
        r = self.client.get(reverse("registro_rapido"))
        self.assertContains(r, "Unidad agrícola *")
        self.assertNotContains(r, 'for="unidad">Finca')

    def test_lista_de_sismos_busca_por_unidad(self):
        from datetime import timedelta
        from django.utils import timezone
        from afectaciones.models import EventoSismico
        from agro.models import UnidadAgricola

        unidad = UnidadAgricola.objects.create(propietario=self.ana, nombre="Lote Ana", area_ha=Decimal("5"))
        EventoSismico.objects.create(usuario=self.ana, unidad=unidad, fecha_hora=timezone.now() - timedelta(days=1))
        self.client.force_login(self.ana)
        r = self.client.get(reverse("eventos"))
        self.assertContains(r, "Buscar por unidad, fecha o epicentro")


class PdfConFincaTests(SimpleTestCase):
    RESUMEN = {"total": 0, "eventos": 0, "area": Decimal("0"), "valor": Decimal("0")}

    def test_el_pdf_acepta_el_nombre_de_la_finca(self):
        datos = pdf.generar_pdf("Ana", "08/11/2026", "Todos", self.RESUMEN, [], [], [], finca="Manzanares")
        self.assertTrue(datos.startswith(b"%PDF"))

    def test_el_pdf_sigue_funcionando_sin_finca(self):
        datos = pdf.generar_pdf("Ana", "08/11/2026", "Todos", self.RESUMEN, [], [], [])
        self.assertTrue(datos.startswith(b"%PDF"))
