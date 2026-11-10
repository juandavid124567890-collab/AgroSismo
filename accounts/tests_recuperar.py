from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import ActividadAdministrativa, SolicitudClave

User = get_user_model()
CLAVE = "x-segura-123"


class RecuperarClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("root", password=CLAVE)
        cls.ana = User.objects.create_user("ana", password=CLAVE, first_name="Ana")

    def setUp(self):
        cache.clear()
        self.url = reverse("recuperar")

    def test_el_login_enlaza_a_la_pantalla_de_recuperacion(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, reverse("recuperar"))
        self.assertContains(r, "¿Olvidaste tu contraseña?")

    def test_la_pantalla_es_publica(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_crea_la_solicitud_para_una_cuenta_existente(self):
        r = self.client.post(self.url, {"username": "Ana", "contacto": "300 111 2222"})
        self.assertRedirects(r, reverse("recuperar_enviada"))
        s = SolicitudClave.objects.get()
        self.assertEqual((s.usuario, s.contacto), (self.ana, "300 111 2222"))
        self.assertTrue(s.pendiente)

    def test_la_respuesta_es_igual_si_la_cuenta_no_existe(self):
        r = self.client.post(self.url, {"username": "fantasma"})
        self.assertRedirects(r, reverse("recuperar_enviada"))
        self.assertEqual(SolicitudClave.objects.count(), 0)

    def test_no_crea_solicitud_para_cuentas_desactivadas(self):
        self.ana.is_active = False
        self.ana.save()
        r = self.client.post(self.url, {"username": "ana"})
        self.assertRedirects(r, reverse("recuperar_enviada"))
        self.assertEqual(SolicitudClave.objects.count(), 0)

    def test_no_repite_solicitudes_pendientes(self):
        for _ in range(3):
            self.client.post(self.url, {"username": "ana"})
        self.assertEqual(SolicitudClave.objects.count(), 1)

    def test_limite_de_solicitudes_por_direccion(self):
        for i in range(8):
            User.objects.create_user(f"u{i}", password=CLAVE)
            self.client.post(self.url, {"username": f"u{i}"})
        self.assertEqual(SolicitudClave.objects.count(), 5)

    def test_sin_usuario_vuelve_a_mostrar_el_formulario(self):
        r = self.client.post(self.url, {"username": ""})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Escribe tu nombre de usuario")

    def test_pagina_de_enviada(self):
        r = self.client.get(reverse("recuperar_enviada"))
        self.assertContains(r, "Solicitud recibida")


class AtenderSolicitudesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("root", password=CLAVE)
        cls.ana = User.objects.create_user("ana", password=CLAVE, first_name="Ana")
        cls.luis = User.objects.create_user("luis", password=CLAVE)

    def setUp(self):
        cache.clear()
        self.sol = SolicitudClave.objects.create(usuario=self.ana, contacto="ana@x.co")

    def test_el_administrador_ve_las_pendientes(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("usuarios"))
        self.assertContains(r, "Solicitudes de contraseña (1)")
        self.assertContains(r, "ana@x.co")
        self.assertContains(self.client.get(reverse("inicio")), "1 solicitud")

    def test_restablecer_la_clave_cierra_la_solicitud(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("usuario_clave", args=[self.ana.pk]))
        self.sol.refresh_from_db()
        self.assertFalse(self.sol.pendiente)
        self.assertEqual(self.sol.atendida_por, self.admin)
        r = self.client.get(reverse("usuarios"))
        self.assertNotContains(r, "Solicitudes de contraseña (")

    def test_descartar_no_cambia_la_clave_y_queda_en_la_bitacora(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("solicitud_descartar", args=[self.sol.pk]))
        self.assertRedirects(r, reverse("usuarios"))
        self.sol.refresh_from_db()
        self.assertFalse(self.sol.pendiente)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password(CLAVE))
        self.assertTrue(ActividadAdministrativa.objects.filter(detalle__contains="descartada").exists())

    def test_un_productor_no_puede_descartar_ni_ver_solicitudes(self):
        self.client.force_login(self.luis)
        self.assertEqual(self.client.post(reverse("solicitud_descartar", args=[self.sol.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("usuarios")).status_code, 403)
        self.sol.refresh_from_db()
        self.assertTrue(self.sol.pendiente)

    def test_descartar_solo_acepta_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("solicitud_descartar", args=[self.sol.pk])).status_code, 405)
