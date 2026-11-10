from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ActividadAdministrativa, Finca, SolicitudClave

User = get_user_model()
CLAVE = "x-segura-123"


class GestionPorFincaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dev = User.objects.create_superuser("dev", password=CLAVE)
        cls.finca_a = Finca.objects.create(nombre="La Esperanza")
        cls.finca_b = Finca.objects.create(nombre="El Roble")
        cls.admin_a = User.objects.create_user("ana", password=CLAVE, first_name="Ana", rol="ADMIN", finca=cls.finca_a)
        cls.obrero_a = User.objects.create_user("beto", password=CLAVE, first_name="Beto", finca=cls.finca_a)
        cls.admin_b = User.objects.create_user("carla", password=CLAVE, first_name="Carla", rol="ADMIN", finca=cls.finca_b)
        cls.obrero_b = User.objects.create_user("dario", password=CLAVE, first_name="Dario", finca=cls.finca_b)

    # --- lo que ve cada quien
    def test_admin_de_finca_solo_ve_a_su_gente(self):
        self.client.force_login(self.admin_a)
        r = self.client.get(reverse("usuarios"))
        self.assertContains(r, "@beto")
        self.assertNotContains(r, "@dario")
        self.assertNotContains(r, "@carla")

    def test_admin_de_finca_no_ve_al_desarrollador(self):
        self.client.force_login(self.admin_a)
        self.assertNotContains(self.client.get(reverse("usuarios")), "@dev")

    def test_desarrollador_ve_todas_las_cuentas(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("usuarios"))
        for nombre in ("@ana", "@beto", "@carla", "@dario"):
            self.assertContains(r, nombre)

    # --- lo que puede tocar
    def test_no_puede_editar_ni_desactivar_ni_restablecer_a_otra_finca(self):
        self.client.force_login(self.admin_a)
        self.assertEqual(self.client.get(reverse("usuario_editar", args=[self.obrero_b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("usuario_estado", args=[self.obrero_b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("usuario_clave", args=[self.obrero_b.pk])).status_code, 404)
        self.obrero_b.refresh_from_db()
        self.assertTrue(self.obrero_b.is_active)

    def test_no_puede_tocar_al_desarrollador(self):
        self.client.force_login(self.admin_a)
        self.assertEqual(self.client.get(reverse("usuario_editar", args=[self.dev.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("usuario_clave", args=[self.dev.pk])).status_code, 404)

    def test_puede_gestionar_a_su_propia_gente(self):
        self.client.force_login(self.admin_a)
        r = self.client.post(reverse("usuario_estado", args=[self.obrero_a.pk]))
        self.assertEqual(r.status_code, 302)
        self.obrero_a.refresh_from_db()
        self.assertFalse(self.obrero_a.is_active)

    # --- crear cuentas
    def test_cuenta_creada_por_admin_de_finca_queda_en_su_finca(self):
        self.client.force_login(self.admin_a)
        r = self.client.get(reverse("usuario_crear"))
        self.assertNotContains(r, 'name="finca"')
        self.client.post(reverse("usuario_crear"), {
            "username": "nuevo", "first_name": "Nuevo", "last_name": "", "email": "",
            "telefono": "", "rol": "AGRICOLA", "clave": "",
        })
        self.assertEqual(User.objects.get(username="nuevo").finca, self.finca_a)

    def test_admin_de_finca_no_puede_mandar_una_finca_ajena(self):
        self.client.force_login(self.admin_a)
        self.client.post(reverse("usuario_crear"), {
            "username": "intruso", "first_name": "X", "rol": "AGRICOLA", "clave": "",
            "finca": self.finca_b.pk,
        })
        self.assertEqual(User.objects.get(username="intruso").finca, self.finca_a)

    def test_desarrollador_crea_administrador_para_una_finca(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("usuario_crear"), {"finca": self.finca_b.pk, "rol": "ADMIN"})
        self.assertContains(r, 'name="finca"')
        self.client.post(reverse("usuario_crear"), {
            "username": "jefe", "first_name": "Jefe", "rol": "ADMIN", "clave": "",
            "finca": self.finca_b.pk,
        })
        jefe = User.objects.get(username="jefe")
        self.assertEqual(jefe.finca, self.finca_b)
        self.assertTrue(jefe.es_admin)

    # --- solicitudes y bitácora
    def test_solicitudes_de_clave_solo_las_de_mi_finca(self):
        SolicitudClave.objects.create(usuario=self.obrero_a)
        s_b = SolicitudClave.objects.create(usuario=self.obrero_b)
        self.client.force_login(self.admin_a)
        r = self.client.get(reverse("usuarios"))
        self.assertContains(r, "@beto")
        self.assertEqual(self.client.post(reverse("solicitud_descartar", args=[s_b.pk])).status_code, 404)

    def test_bitacora_solo_muestra_cuentas_de_mi_finca(self):
        ActividadAdministrativa.objects.create(
            administrador=self.admin_a, usuario_objetivo=self.obrero_a, accion="CREAR")
        ActividadAdministrativa.objects.create(
            administrador=self.admin_b, usuario_objetivo=self.obrero_b, accion="CREAR")
        self.client.force_login(self.admin_a)
        r = self.client.get(reverse("actividad"))
        self.assertContains(r, "@beto")
        self.assertNotContains(r, "@dario")


class FincasDesarrolladorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dev = User.objects.create_superuser("dev", password=CLAVE)
        cls.finca = Finca.objects.create(nombre="La Esperanza")
        cls.admin = User.objects.create_user("ana", password=CLAVE, rol="ADMIN", finca=cls.finca)
        cls.obrero = User.objects.create_user("beto", password=CLAVE, finca=cls.finca)

    def test_solo_el_desarrollador_entra_a_fincas(self):
        for quien in (self.admin, self.obrero):
            self.client.force_login(quien)
            for nombre, args in (("fincas", []), ("finca_crear", []), ("finca_editar", [self.finca.pk])):
                self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 403)

    def test_sin_sesion_va_al_login(self):
        r = self.client.get(reverse("fincas"))
        self.assertEqual(r.status_code, 302)

    def test_lista_muestra_conteos(self):
        self.client.force_login(self.dev)
        r = self.client.get(reverse("fincas"))
        self.assertContains(r, "La Esperanza")
        self.assertContains(r, "2 usuarios")

    def test_crear_finca_lleva_a_crear_su_administrador(self):
        self.client.force_login(self.dev)
        r = self.client.post(reverse("finca_crear"), {"nombre": "El Roble"})
        nueva = Finca.objects.get(nombre="El Roble")
        self.assertRedirects(r, f"{reverse('usuario_crear')}?finca={nueva.pk}&rol=ADMIN")

    def test_nombre_de_finca_repetido_se_rechaza(self):
        self.client.force_login(self.dev)
        r = self.client.post(reverse("finca_crear"), {"nombre": "la esperanza"})
        self.assertContains(r, "Ya existe una finca con ese nombre.")
        self.assertEqual(Finca.objects.count(), 1)

    def test_renombrar_finca(self):
        self.client.force_login(self.dev)
        self.client.post(reverse("finca_editar", args=[self.finca.pk]), {"nombre": "Nueva Esperanza"})
        self.finca.refresh_from_db()
        self.assertEqual(self.finca.nombre, "Nueva Esperanza")

    def test_menu_fincas_solo_para_el_desarrollador(self):
        self.client.force_login(self.dev)
        self.assertContains(self.client.get(reverse("inicio")), reverse("fincas"))
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("inicio")), reverse("fincas"))
