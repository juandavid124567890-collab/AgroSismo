from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from agro.models import UnidadAgricola

from .models import Finca

Usuario = get_user_model()


class FincaModeloTests(TestCase):
    def test_nombre_de_finca_es_unico(self):
        Finca.objects.create(nombre="La Esperanza")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Finca.objects.create(nombre="La Esperanza")

    def test_usuarios_comparten_finca(self):
        f = Finca.objects.create(nombre="La Esperanza")
        a = Usuario.objects.create_user("ana", password="x-segura-123", finca=f, rol="ADMIN")
        b = Usuario.objects.create_user("beto", password="x-segura-123", finca=f)
        self.assertCountEqual(f.miembros.all(), [a, b])

    def test_desarrollador_es_el_superusuario(self):
        dev = Usuario.objects.create_superuser("dev", password="x-segura-123")
        otro = Usuario.objects.create_user("ana", password="x-segura-123")
        self.assertTrue(dev.es_desarrollador)
        self.assertFalse(otro.es_desarrollador)

    def test_unidad_nueva_queda_en_la_finca_de_quien_la_crea(self):
        f = Finca.objects.create(nombre="La Esperanza")
        ana = Usuario.objects.create_user("ana", password="x-segura-123", finca=f)
        u = UnidadAgricola.objects.create(propietario=ana, nombre="Lote 1", area_ha=Decimal("3"))
        self.assertEqual(u.finca, f)

    def test_unidad_de_usuario_sin_finca_queda_sin_finca(self):
        ana = Usuario.objects.create_user("ana", password="x-segura-123")
        u = UnidadAgricola.objects.create(propietario=ana, nombre="Lote 1", area_ha=Decimal("3"))
        self.assertIsNone(u.finca)


class AsignarFincasTests(TestCase):
    def ejecutar(self):
        salida = StringIO()
        call_command("asignar_fincas", stdout=salida)
        return salida.getvalue()

    def test_crea_finca_por_usuario_y_mueve_sus_unidades(self):
        ana = Usuario.objects.create_user("ana", password="x-segura-123")
        luis = Usuario.objects.create_user("luis", password="x-segura-123")
        u = UnidadAgricola.objects.create(propietario=ana, nombre="Lote 1", area_ha=Decimal("3"))
        self.ejecutar()
        ana.refresh_from_db(); luis.refresh_from_db(); u.refresh_from_db()
        self.assertEqual(ana.finca.nombre, "Finca de ana")
        self.assertEqual(luis.finca.nombre, "Finca de luis")
        self.assertEqual(u.finca, ana.finca)

    def test_se_puede_repetir_sin_duplicar(self):
        Usuario.objects.create_user("ana", password="x-segura-123")
        self.ejecutar()
        self.ejecutar()
        self.assertEqual(Finca.objects.count(), 1)

    def test_el_desarrollador_sin_unidades_no_recibe_finca(self):
        dev = Usuario.objects.create_superuser("dev", password="x-segura-123")
        self.ejecutar()
        dev.refresh_from_db()
        self.assertIsNone(dev.finca)

    def test_el_desarrollador_con_unidades_si_recibe_finca(self):
        dev = Usuario.objects.create_superuser("dev", password="x-segura-123")
        u = UnidadAgricola.objects.create(propietario=dev, nombre="Girasol", area_ha=Decimal("5"))
        self.ejecutar()
        dev.refresh_from_db(); u.refresh_from_db()
        self.assertEqual(u.finca, dev.finca)
        self.assertIsNotNone(dev.finca)
