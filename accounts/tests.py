from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ActividadAdministrativa, Usuario

User = get_user_model()


class UsuarioTests(TestCase):
    def test_rol_por_defecto_es_agricola(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.assertEqual(u.rol, Usuario.Rol.AGRICOLA)
        self.assertFalse(u.es_admin)

    def test_superusuario_queda_como_administrador(self):
        u = User.objects.create_superuser("root", password="x-segura-123")
        self.assertTrue(u.es_admin)

    def test_desactivar_conserva_la_cuenta(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        u.is_active = False
        u.save()
        self.assertTrue(User.objects.filter(pk=u.pk, is_active=False).exists())

    def test_bitacora_sobrevive_al_borrado_del_usuario_objetivo(self):
        admin = User.objects.create_superuser("root", password="x-segura-123")
        u = User.objects.create_user("ana", password="x-segura-123")
        ActividadAdministrativa.objects.create(
            administrador=admin, usuario_objetivo=u, accion=ActividadAdministrativa.Accion.CREAR
        )
        u.delete()
        self.assertEqual(ActividadAdministrativa.objects.count(), 1)


class InicioSesionYPwaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", password="x-segura-123")

    def test_login_muestra_opcion_mantener_sesion(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "Mantener sesión iniciada")
        self.assertContains(r, "¿Olvidaste tu contraseña?")

    def test_sin_marcar_la_sesion_termina_al_cerrar_el_navegador(self):
        self.client.post(reverse("login"), {"username": "ana", "password": "x-segura-123"})
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_marcando_la_opcion_la_sesion_dura_30_dias(self):
        self.client.post(
            reverse("login"),
            {"username": "ana", "password": "x-segura-123", "recordarme": "1"},
        )
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 30)

    def test_manifest_es_publico_y_valido(self):
        r = self.client.get(reverse("manifest"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["name"], "AgroSismo")
        self.assertEqual(datos["display"], "standalone")
        self.assertGreaterEqual(len(datos["icons"]), 2)

    def test_service_worker_se_sirve_desde_la_raiz(self):
        r = self.client.get(reverse("sw"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r["Content-Type"])
        self.assertEqual(r["Service-Worker-Allowed"], "/")

    def test_pagina_sin_conexion_es_publica(self):
        r = self.client.get(reverse("sin_conexion"))
        self.assertContains(r, "Sin conexión a internet")


class PaginaPublicaTests(TestCase):
    def test_landing_es_publica_y_tiene_las_secciones(self):
        r = self.client.get(reverse("landing"))
        self.assertEqual(r.status_code, 200)
        for texto in ("¿Qué es un evento sísmico", "Reporta una afectación en cuatro pasos",
                      "Preguntas frecuentes", "Iniciar sesión"):
            self.assertContains(r, texto)

    def test_landing_invita_a_contactar_por_whatsapp(self):
        r = self.client.get(reverse("landing"))
        self.assertContains(r, "https://wa.me/573122971645")
        self.assertContains(r, "Quiero usar AgroSismo")
        self.assertContains(r, "Empieza a proteger tu finca en 3 pasos")
        self.assertNotContains(r, "Comenzar ahora")

    def test_landing_muestra_el_carrusel_de_pantallas(self):
        r = self.client.get(reverse("landing"))
        self.assertContains(r, "pub-visor")
        self.assertContains(r, "landing/registrar.webp")

    def test_landing_redirige_si_ya_inicio_sesion(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("landing"))
        self.assertRedirects(r, reverse("inicio"))


class PanelInicioTests(TestCase):
    def test_inicio_muestra_primeros_pasos_para_un_productor_nuevo(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["pasos_hechos"], 0)
        self.assertEqual(r.context["pasos_porcentaje"], 0)
        self.assertContains(r, "Primeros pasos")

    def test_inicio_sin_afectaciones_muestra_mensaje_en_lugar_de_graficas(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("inicio"))
        self.assertFalse(r.context["est"]["hay_datos"])
        self.assertContains(r, "Aquí verás tus estadísticas")

    def test_inicio_muestra_estadisticas_solo_del_propio_usuario(self):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone
        from afectaciones.models import Afectacion, EventoSismico, Perdida
        from agro.models import UnidadAgricola
        ana = User.objects.create_user("ana", password="x-segura-123")
        luis = User.objects.create_user("luis", password="x-segura-123")

        def crear(dueno, severidad, valor):
            finca = UnidadAgricola.objects.create(propietario=dueno, nombre=f"Finca {dueno.username}", area_ha=Decimal("5"))
            ev = EventoSismico.objects.create(usuario=dueno, unidad=finca, fecha_hora=timezone.now() - timedelta(days=2))
            af = Afectacion.objects.create(evento=ev, unidad=finca, elemento="CULTIVO", tipo_dano="GRIETAS",
                                           severidad=severidad, area_afectada_ha=Decimal("2"))
            Perdida.objects.create(afectacion=af, valor_estimado_cop=Decimal(valor))

        crear(ana, "GRAVE", "1500000")
        crear(luis, "LEVE", "900000")
        self.client.force_login(ana)
        r = self.client.get(reverse("inicio"))
        est = r.context["est"]
        self.assertEqual(est["total"], 1)
        self.assertEqual([s["clave"] for s in est["severidad"]], ["GRAVE"])
        self.assertEqual(est["perdida_total"], "$1.500.000")
        self.assertEqual(est["meses_total"], 1)
        self.assertContains(r, "Severidad de los daños")
        self.assertNotContains(r, "$900.000")

    def test_inicio_marca_la_unidad_como_hecha(self):
        from decimal import Decimal
        from agro.models import UnidadAgricola
        u = User.objects.create_user("ana", password="x-segura-123")
        UnidadAgricola.objects.create(propietario=u, nombre="Finca Ana", area_ha=Decimal("5"))
        self.client.force_login(u)
        r = self.client.get(reverse("inicio"))
        self.assertTrue(r.context["paso_unidad"])
        self.assertEqual(r.context["pasos_hechos"], 1)
        self.assertEqual(r.context["pasos_porcentaje"], 33)

    def test_menu_marca_la_seccion_activa(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("historial"))
        self.assertContains(r, 'class="enlace-barra activo" href="/historial/"')


class RegistroRapidoTests(TestCase):
    def test_la_pagina_es_publica_y_no_contiene_datos_del_usuario(self):
        r = self.client.get(reverse("registro_rapido"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Registro rápido")
        self.assertNotContains(r, "csrfmiddlewaretoken")

    def test_el_service_worker_guarda_el_registro_rapido(self):
        r = self.client.get(reverse("sw"))
        self.assertContains(r, "/registro-rapido/")
        self.assertContains(r, "/static/js/rapido.js")


class SelectorMesesInicioTests(TestCase):
    def setUp(self):
        from decimal import Decimal
        from datetime import timedelta
        from django.utils import timezone
        from afectaciones.models import Afectacion, EventoSismico
        from agro.models import UnidadAgricola

        self.ana = User.objects.create_user("ana", password="x-segura-123")
        finca = UnidadAgricola.objects.create(propietario=self.ana, nombre="Finca", area_ha=Decimal("5"))
        # Un sismo de hace ~5 meses: sale en 6 y 12 meses, pero no en 3.
        ev = EventoSismico.objects.create(
            usuario=self.ana, unidad=finca, fecha_hora=timezone.now() - timedelta(days=150)
        )
        Afectacion.objects.create(
            evento=ev, unidad=finca, elemento="CULTIVO", tipo_dano="GRIETAS",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )
        self.client.force_login(self.ana)

    def meses(self, consulta=""):
        r = self.client.get(reverse("inicio") + consulta)
        return r.context["est"]

    def test_por_defecto_son_6_meses(self):
        est = self.meses()
        self.assertEqual(est["periodo"], "6")
        self.assertEqual(len(est["meses"]), 6)

    def test_se_puede_elegir_7_dias_3_y_12_meses(self):
        est7 = self.meses("?periodo=7d")
        self.assertEqual(len(est7["meses"]), 7)
        self.assertEqual(est7["meses_total"], 0)
        self.assertEqual(est7["periodo_texto"], "últimos 7 días")
        self.assertEqual(len(self.meses("?periodo=3")["meses"]), 3)
        self.assertEqual(self.meses("?periodo=3")["meses_total"], 0)
        est12 = self.meses("?periodo=12")
        self.assertEqual(len(est12["meses"]), 12)
        self.assertEqual(est12["meses_total"], 1)

    def test_valor_invalido_vuelve_a_6(self):
        self.assertEqual(self.meses("?periodo=99")["periodo"], "6")
        self.assertEqual(self.meses("?periodo=abc")["periodo"], "6")

    def test_siete_dias_cuenta_un_sismo_de_ayer(self):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone
        from afectaciones.models import Afectacion, EventoSismico
        from agro.models import UnidadAgricola

        finca = UnidadAgricola.objects.get(propietario=self.ana)
        ev = EventoSismico.objects.create(
            usuario=self.ana, unidad=finca, fecha_hora=timezone.now() - timedelta(days=1)
        )
        Afectacion.objects.create(
            evento=ev, unidad=finca, elemento="CULTIVO", tipo_dano="GRIETAS",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )
        self.assertEqual(self.meses("?periodo=7d")["meses_total"], 1)

    def test_landing_sin_la_palabra_invitacion_en_el_titulo(self):
        self.client.logout()
        r = self.client.get(reverse("landing"))
        self.assertContains(r, "Empieza a proteger tu finca en 3 pasos")
