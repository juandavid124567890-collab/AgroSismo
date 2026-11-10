import re

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .models import ActividadAdministrativa

User = get_user_model()
CLAVE = "x-segura-123"


def clave_mostrada(respuesta):
    """Contraseña que se le muestra una sola vez al administrador."""
    for m in get_messages(respuesta.wsgi_request):
        if "clave" in m.extra_tags:
            return re.search(r":\s(\S+)\s—", str(m)).group(1)
    return None


class GestionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("root", password=CLAVE)
        cls.ana = User.objects.create_user("ana", password=CLAVE, first_name="Ana", last_name="Pérez")
        cls.luis = User.objects.create_user("luis", password=CLAVE, first_name="Luis")

    def setUp(self):
        self.client.force_login(self.admin)

    # --- acceso ---
    def test_sin_sesion_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse("usuarios"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_un_productor_recibe_403_en_todas_las_pantallas(self):
        self.client.force_login(self.ana)
        for nombre, args in [("usuarios", []), ("usuario_crear", []), ("actividad", []),
                             ("usuario_editar", [self.luis.pk])]:
            self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 403, nombre)
        for nombre in ("usuario_estado", "usuario_clave"):
            r = self.client.post(reverse(nombre, args=[self.luis.pk]))
            self.assertEqual(r.status_code, 403, nombre)
        self.luis.refresh_from_db()
        self.assertTrue(self.luis.is_active)

    # --- lista ---
    def test_lista_con_busqueda_y_filtro(self):
        r = self.client.get(reverse("usuarios"), {"q": "ana"})
        self.assertContains(r, "@ana")
        self.assertNotContains(r, "@luis")
        self.luis.is_active = False
        self.luis.save()
        r = self.client.get(reverse("usuarios"), {"estado": "inactivos"})
        self.assertContains(r, "@luis")
        self.assertNotContains(r, "@ana")
        self.assertEqual(r.context["resumen"]["inactivos"], 1)

    # --- crear ---
    def test_crear_cuenta_genera_clave_que_funciona(self):
        r = self.client.post(reverse("usuario_crear"), {
            "username": "marta", "first_name": "Marta", "last_name": "Ruiz",
            "email": "m@x.co", "telefono": "300", "rol": "AGRICOLA", "clave": "",
        })
        self.assertRedirects(r, reverse("usuarios"))
        nueva = User.objects.get(username="marta")
        self.assertEqual(nueva.rol, "AGRICOLA")
        clave = clave_mostrada(r)
        self.assertGreaterEqual(len(clave), 10)
        self.assertTrue(nueva.check_password(clave))
        self.client.logout()
        self.assertTrue(self.client.login(username="marta", password=clave))
        log = ActividadAdministrativa.objects.get(usuario_objetivo=nueva)
        self.assertEqual((log.accion, log.administrador), ("CREAR", self.admin))

    def test_crear_con_clave_propia_debil_se_rechaza(self):
        r = self.client.post(reverse("usuario_crear"), {
            "username": "marta", "first_name": "Marta", "rol": "AGRICOLA", "clave": "12345678",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="marta").exists())

    def test_crear_con_usuario_repetido_o_invalido(self):
        for nombre in ("ana", "con espacio"):
            r = self.client.post(reverse("usuario_crear"), {
                "username": nombre, "first_name": "X", "rol": "AGRICOLA", "clave": "",
            })
            self.assertEqual(r.status_code, 200, nombre)
        self.assertEqual(User.objects.count(), 3)

    # --- editar ---
    def test_editar_datos_y_rol(self):
        r = self.client.post(reverse("usuario_editar", args=[self.ana.pk]), {
            "first_name": "Ana María", "last_name": "Pérez", "email": "", "telefono": "", "rol": "ADMIN",
        })
        self.assertRedirects(r, reverse("usuarios"))
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.first_name, self.ana.rol), ("Ana María", "ADMIN"))
        self.assertEqual(ActividadAdministrativa.objects.filter(accion="ACTUALIZAR").count(), 1)

    def test_un_administrador_no_puede_cambiar_su_propio_rol(self):
        self.client.post(reverse("usuario_editar", args=[self.admin.pk]), {
            "first_name": "Root", "last_name": "", "email": "", "telefono": "", "rol": "AGRICOLA",
        })
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, "ADMIN")

    # --- desactivar / reactivar ---
    def test_desactivar_impide_el_ingreso_y_conserva_los_datos(self):
        r = self.client.post(reverse("usuario_estado", args=[self.ana.pk]))
        self.assertRedirects(r, reverse("usuarios"))
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username="ana", password=CLAVE))
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())
        self.assertTrue(ActividadAdministrativa.objects.filter(accion="DESACTIVAR").exists())

    def test_reactivar(self):
        self.ana.is_active = False
        self.ana.save()
        self.client.post(reverse("usuario_estado", args=[self.ana.pk]))
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)
        self.assertTrue(ActividadAdministrativa.objects.filter(accion="REACTIVAR").exists())

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse("usuario_estado", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_estado_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse("usuario_estado", args=[self.ana.pk])).status_code, 405)

    # --- restablecer clave ---
    def test_restablecer_clave(self):
        r = self.client.post(reverse("usuario_clave", args=[self.ana.pk]))
        self.assertRedirects(r, reverse("usuarios"))
        nueva = clave_mostrada(r)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.check_password(CLAVE))
        self.assertTrue(self.ana.check_password(nueva))
        log = ActividadAdministrativa.objects.get(usuario_objetivo=self.ana)
        self.assertIn("restablecida", log.detalle)
        self.assertNotIn(nueva, log.detalle)  # la bitácora nunca guarda contraseñas

    # --- bitácora ---
    def test_bitacora_visible_para_el_administrador(self):
        self.client.post(reverse("usuario_estado", args=[self.ana.pk]))
        r = self.client.get(reverse("actividad"))
        self.assertContains(r, "Desactivar cuenta")
        self.assertContains(r, "@ana")

    def test_el_menu_muestra_usuarios_solo_al_administrador(self):
        self.assertContains(self.client.get(reverse("inicio")), reverse("usuarios"))
        self.client.force_login(self.ana)
        self.assertNotContains(self.client.get(reverse("inicio")), reverse("usuarios"))


class MedidorClaveTests(TestCase):
    """El formulario de nueva cuenta muestra el medidor de contraseña."""

    def setUp(self):
        self.dev = User.objects.create_superuser("dev", password=CLAVE)

    def test_formulario_carga_medidor(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("usuario_crear"))
        self.assertContains(r, "data-medidor-clave")
        self.assertContains(r, "js/clave.js")

    def test_clave_comun_se_rechaza(self):
        self.client.force_login(self.dev)
        r = self.client.post(reverse("usuario_crear"), {
            "username": "nuevo1", "first_name": "Ana", "rol": "ADMIN", "clave": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="nuevo1").exists())
