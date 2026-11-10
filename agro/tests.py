from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Cultivo, UnidadAgricola

UBICACION = {"departamento": "Cauca", "municipio": "Popayán"}


Usuario = get_user_model()


class UnidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")

    def nueva(self, **extra):
        datos = dict(propietario=self.ana, nombre="Finca El Roble", area_ha=Decimal("25"))
        datos.update(extra)
        return UnidadAgricola(**datos)

    def test_unidad_valida(self):
        self.nueva().full_clean()

    def test_area_cero_o_negativa_rechazada(self):
        for area in (Decimal("0"), Decimal("-5")):
            with self.subTest(area=area), self.assertRaises(ValidationError):
                self.nueva(area_ha=area).full_clean()

    def test_area_cero_rechazada_por_la_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.nueva(area_ha=Decimal("0")).save()

    def test_nombre_unico_por_propietario(self):
        self.nueva().save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.nueva().save()

    def test_otro_propietario_puede_repetir_nombre(self):
        luis = Usuario.objects.create_user("luis", password="x-segura-123")
        self.nueva().save()
        self.nueva(propietario=luis).save()

    def test_coordenadas_fuera_de_rango_rechazadas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.nueva(latitud=Decimal("91"), longitud=Decimal("0")).save()

    def test_no_se_borra_un_usuario_con_unidades(self):
        from django.db.models import ProtectedError

        self.nueva().save()
        with self.assertRaises(ProtectedError):
            self.ana.delete()

    def test_borrar_unidad_borra_sus_cultivos(self):
        u = self.nueva()
        u.save()
        Cultivo.objects.create(unidad=u, tipo="Café")
        u.delete()
        self.assertEqual(Cultivo.objects.count(), 0)


class VistasUnidadTests(TestCase):
    """Pantallas de unidades y cultivos: cada productor solo ve lo suyo."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca_ana = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10")
        )
        cls.finca_luis = UnidadAgricola.objects.create(
            propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("5")
        )

    def setUp(self):
        self.client.force_login(self.ana)

    def test_requiere_iniciar_sesion(self):
        self.client.logout()
        r = self.client.get(reverse("unidades"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_lista_solo_muestra_las_propias(self):
        r = self.client.get(reverse("unidades"))
        self.assertContains(r, "Finca Ana")
        self.assertNotContains(r, "Finca Luis")

    def test_crear_unidad(self):
        r = self.client.post(reverse("unidad_crear"), {"nombre": "Parcela Nueva", "area_ha": "12.5", **UBICACION})
        self.assertEqual(r.status_code, 302)
        u = UnidadAgricola.objects.get(nombre="Parcela Nueva")
        self.assertEqual(u.propietario, self.ana)
        self.assertIsNotNone(u.sincronizado_en)

    def test_departamento_y_municipio_son_obligatorios(self):
        r = self.client.post(reverse("unidad_crear"), {"nombre": "Sin lugar", "area_ha": "2"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Elige el departamento.")
        self.assertContains(r, "Elige el municipio.")
        self.assertFalse(UnidadAgricola.objects.filter(nombre="Sin lugar").exists())

    def test_municipio_de_otro_departamento_se_rechaza(self):
        r = self.client.post(
            reverse("unidad_crear"),
            {"nombre": "Mal ubicada", "area_ha": "2", "departamento": "Cauca", "municipio": "Medellín"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "pertenezca a Cauca")
        self.assertFalse(UnidadAgricola.objects.filter(nombre="Mal ubicada").exists())

    def test_vereda_y_coordenadas_son_opcionales(self):
        r = self.client.post(
            reverse("unidad_crear"),
            {"nombre": "Con lugar", "area_ha": "2", **UBICACION, "vereda": "", "latitud": "", "longitud": ""},
        )
        self.assertEqual(r.status_code, 302)
        u = UnidadAgricola.objects.get(nombre="Con lugar")
        self.assertEqual((u.departamento, u.municipio), ("Cauca", "Popayán"))

    def test_el_formulario_marca_obligatorios_y_opcionales_y_trae_la_lista(self):
        r = self.client.get(reverse("unidad_crear"))
        self.assertContains(r, "son <strong>obligatorios</strong>")
        self.assertContains(r, "(opcional)")
        self.assertContains(r, 'id="divipola-datos"')
        self.assertContains(r, "Selecciona un departamento")

    def test_al_fallar_el_formulario_conserva_los_municipios_del_departamento(self):
        r = self.client.post(
            reverse("unidad_crear"),
            {"nombre": "", "area_ha": "2", "departamento": "Cauca", "municipio": "Popayán"},
        )
        self.assertContains(r, '<option value="Popayán" selected>Popayán</option>', html=True)

    def test_unidad_antigua_con_texto_libre_se_puede_editar_sin_perder_su_lugar(self):
        antigua = UnidadAgricola.objects.create(
            propietario=self.ana, nombre="Vieja", area_ha=Decimal("3"),
            departamento="cauca ", municipio="Popayan",
        )
        r = self.client.post(
            reverse("unidad_editar", args=[antigua.pk]),
            {"nombre": "Vieja renombrada", "area_ha": "3", "departamento": "cauca ", "municipio": "Popayan"},
        )
        self.assertEqual(r.status_code, 302)
        antigua.refresh_from_db()
        self.assertEqual(antigua.nombre, "Vieja renombrada")

    def test_nombre_repetido_muestra_error(self):
        r = self.client.post(reverse("unidad_crear"), {"nombre": "Finca Ana", "area_ha": "3", **UBICACION})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya hay una unidad con ese nombre")
        self.assertEqual(UnidadAgricola.objects.filter(propietario=self.ana).count(), 1)

    def test_area_cero_muestra_error(self):
        r = self.client.post(reverse("unidad_crear"), {"nombre": "Sin area", "area_ha": "0", **UBICACION})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(UnidadAgricola.objects.filter(nombre="Sin area").exists())

    def test_no_puede_ver_unidad_ajena(self):
        r = self.client.get(reverse("unidad_detalle", args=[self.finca_luis.pk]))
        self.assertEqual(r.status_code, 404)

    def test_no_puede_editar_unidad_ajena(self):
        r = self.client.post(
            reverse("unidad_editar", args=[self.finca_luis.pk]),
            {"nombre": "Robada", "area_ha": "5", **UBICACION},
        )
        self.assertEqual(r.status_code, 404)
        self.finca_luis.refresh_from_db()
        self.assertEqual(self.finca_luis.nombre, "Finca Luis")

    def test_editar_unidad_propia(self):
        r = self.client.post(
            reverse("unidad_editar", args=[self.finca_ana.pk]),
            {"nombre": "Finca Ana Grande", "area_ha": "20", **UBICACION},
        )
        self.assertEqual(r.status_code, 302)
        self.finca_ana.refresh_from_db()
        self.assertEqual(self.finca_ana.nombre, "Finca Ana Grande")

    def test_agregar_cultivo(self):
        r = self.client.post(
            reverse("cultivo_crear", args=[self.finca_ana.pk]),
            {"tipo": "Café", "area_ha": "2", "activo": "on"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.finca_ana.cultivos.filter(tipo="Café").count(), 1)

    def test_cultivo_no_puede_superar_el_area_de_la_unidad(self):
        r = self.client.post(
            reverse("cultivo_crear", args=[self.finca_ana.pk]),
            {"tipo": "Café", "area_ha": "11", "activo": "on"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cultivo.objects.count(), 0)

    def test_no_puede_agregar_cultivo_a_unidad_ajena(self):
        r = self.client.post(
            reverse("cultivo_crear", args=[self.finca_luis.pk]), {"tipo": "Café", "activo": "on"}
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Cultivo.objects.count(), 0)


class DivipolaTests(TestCase):
    def test_lista_completa_de_departamentos_y_municipios(self):
        from .divipola import DEPARTAMENTOS, municipios_de
        self.assertEqual(len(DEPARTAMENTOS), 33)
        self.assertEqual(sum(len(v) for v in DEPARTAMENTOS.values()), 1122)
        self.assertIn("Popayán", municipios_de("Cauca"))
        self.assertEqual(municipios_de("Bogotá D.C."), ["Bogotá D.C."])
        self.assertEqual(municipios_de("No existe"), [])
