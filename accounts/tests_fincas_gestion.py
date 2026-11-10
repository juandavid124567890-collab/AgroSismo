import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from afectaciones.models import Afectacion, EventoSismico
from agro.models import Cultivo, UnidadAgricola

from .fincas import eliminar_finca, resumen_de_finca
from .models import ActividadAdministrativa, Finca

User = get_user_model()
CLAVE = "x-segura-123"


def datos_de_una_finca(finca, usuario, nombre_unidad):
    unidad = UnidadAgricola.objects.create(
        propietario=usuario, finca=finca, nombre=nombre_unidad, area_ha=Decimal("3"))
    Cultivo.objects.create(unidad=unidad, tipo="Café")
    evento = EventoSismico.objects.create(
        usuario=usuario, unidad=unidad, fecha_hora=timezone.now() - timedelta(days=1), magnitud=Decimal("4.5"))
    Afectacion.objects.create(
        evento=evento, unidad=unidad, elemento="TERRENO", tipo_dano="GRIETAS",
        severidad="LEVE", area_afectada_ha=Decimal("1"))
    return unidad


class GestionDeFincasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dev = User.objects.create_superuser("dev", password=CLAVE)
        cls.finca = Finca.objects.create(nombre="Manzanares")
        cls.otra = Finca.objects.create(nombre="El Roble")
        cls.admin = User.objects.create_user("ana", password=CLAVE, rol="ADMIN", finca=cls.finca)
        cls.obrero = User.objects.create_user("beto", password=CLAVE, first_name="Beto", finca=cls.finca)
        cls.vecino = User.objects.create_user("carlos", password=CLAVE, finca=cls.otra)
        datos_de_una_finca(cls.finca, cls.admin, "Girasol")
        datos_de_una_finca(cls.otra, cls.vecino, "Lote V")

    # --- ver la finca
    def test_detalle_muestra_usuarios_y_conteos(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("finca_detalle", args=[self.finca.pk]))
        self.assertContains(r, "@ana")
        self.assertContains(r, "@beto")
        self.assertNotContains(r, "@carlos")
        self.assertContains(r, "2 usuarios")

    def test_solo_el_desarrollador_ve_el_detalle(self):
        self.client.force_login(self.admin)
        for nombre in ("finca_detalle", "finca_eliminar"):
            self.assertEqual(self.client.get(reverse(nombre, args=[self.finca.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("finca_estado", args=[self.finca.pk])).status_code, 403)

    # --- desactivar
    def test_desactivar_y_reactivar(self):
        self.client.force_login(self.dev)
        self.client.post(reverse("finca_estado", args=[self.finca.pk]))
        self.finca.refresh_from_db()
        self.assertFalse(self.finca.activa)
        self.assertTrue(ActividadAdministrativa.objects.filter(detalle__contains="desactivada").exists())
        self.client.post(reverse("finca_estado", args=[self.finca.pk]))
        self.finca.refresh_from_db()
        self.assertTrue(self.finca.activa)

    def test_finca_desactivada_no_deja_ingresar(self):
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        r = self.client.post(reverse("login"), {"username": "beto", "password": CLAVE})
        self.assertContains(r, "Tu finca está desactivada")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_finca_desactivada_saca_a_quien_ya_tenia_sesion(self):
        self.client.force_login(self.obrero)
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        r = self.client.get(reverse("inicio"))
        self.assertRedirects(r, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_finca_desactivada_responde_403_a_la_api(self):
        self.client.force_login(self.obrero)
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        r = self.client.get(reverse("api_datos_base"))
        self.assertEqual(r.status_code, 403)

    def test_el_desarrollador_no_se_bloquea(self):
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        self.client.force_login(self.dev)
        self.assertEqual(self.client.get(reverse("fincas")).status_code, 200)

    def test_otras_fincas_siguen_entrando(self):
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        self.client.force_login(self.vecino)
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)

    # --- eliminar
    def test_la_pagina_de_eliminar_avisa_que_se_borra_todo(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("finca_eliminar", args=[self.finca.pk]))
        self.assertContains(r, "Esta acción no se puede deshacer")
        self.assertContains(r, "2 usuarios")
        self.assertContains(r, "1 unidad agrícola")

    def test_no_elimina_si_el_nombre_no_coincide(self):
        self.client.force_login(self.dev)
        r = self.client.post(reverse("finca_eliminar", args=[self.finca.pk]), {"confirmacion": "manzanares"})
        self.assertContains(r, "No coincide con el nombre de la finca.")
        self.assertTrue(Finca.objects.filter(pk=self.finca.pk).exists())
        self.assertTrue(User.objects.filter(username="beto").exists())

    def test_elimina_la_finca_con_todos_sus_datos_y_respeta_las_demas(self):
        self.client.force_login(self.dev)
        r = self.client.post(reverse("finca_eliminar", args=[self.finca.pk]), {"confirmacion": "Manzanares"})
        self.assertRedirects(r, reverse("fincas"))
        self.assertFalse(Finca.objects.filter(nombre="Manzanares").exists())
        self.assertFalse(User.objects.filter(username__in=["ana", "beto"]).exists())
        self.assertFalse(UnidadAgricola.objects.filter(nombre="Girasol").exists())
        self.assertEqual(EventoSismico.objects.count(), 1)
        self.assertEqual(Afectacion.objects.count(), 1)
        # la otra finca y el desarrollador quedan intactos
        self.assertTrue(User.objects.filter(username__in=["carlos", "dev"]).count() == 2)
        self.assertTrue(UnidadAgricola.objects.filter(nombre="Lote V").exists())
        self.assertTrue(ActividadAdministrativa.objects.filter(detalle__contains="eliminada").exists())

    def test_resumen_cuenta_lo_que_se_va_a_borrar(self):
        datos = resumen_de_finca(self.finca)
        self.assertEqual(datos["usuarios"], 2)
        self.assertEqual(datos["unidades"], 1)
        self.assertEqual(datos["sismos"], 1)
        self.assertEqual(datos["afectaciones"], 1)

    def test_eliminar_una_finca_vacia(self):
        vacia = Finca.objects.create(nombre="Vacía")
        eliminar_finca(vacia)
        self.assertFalse(Finca.objects.filter(nombre="Vacía").exists())

    def test_eliminar_no_borra_al_desarrollador_aunque_este_en_la_finca(self):
        User.objects.filter(pk=self.dev.pk).update(finca=self.finca)
        eliminar_finca(self.finca)
        self.dev.refresh_from_db()
        self.assertIsNone(self.dev.finca)

    def test_la_lista_muestra_si_la_finca_esta_desactivada(self):
        Finca.objects.filter(pk=self.finca.pk).update(activa=False)
        self.client.force_login(self.dev)
        self.assertContains(self.client.get(reverse("fincas")), "Desactivada")
