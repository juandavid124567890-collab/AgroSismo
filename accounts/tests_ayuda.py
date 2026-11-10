from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Finca, Usuario

User = get_user_model()


class AyudaTests(TestCase):
    def test_es_publica_y_tiene_whatsapp(self):
        r = self.client.get(reverse("ayuda"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "¿Cómo ingreso a AgroSismo?")
        self.assertContains(r, "https://wa.me/573122971645")
        self.assertContains(r, "Escribir por WhatsApp")

    def test_visitante_no_ve_secciones_de_administrador(self):
        r = self.client.get(reverse("ayuda"))
        self.assertNotContains(r, "Para administradores de finca")
        self.assertNotContains(r, "Para el desarrollador")

    def test_agricola_no_ve_secciones_de_administrador(self):
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("ayuda"))
        self.assertNotContains(r, "Para administradores de finca")

    def test_administrador_ve_su_seccion_pero_no_la_del_desarrollador(self):
        f = Finca.objects.create(nombre="La Esperanza")
        u = User.objects.create_user("jefe", password="x-segura-123", rol=Usuario.Rol.ADMIN, finca=f)
        self.client.force_login(u)
        r = self.client.get(reverse("ayuda"))
        self.assertContains(r, "Para administradores de finca")
        self.assertNotContains(r, "Para el desarrollador")

    def test_desarrollador_ve_todo(self):
        u = User.objects.create_superuser("root", password="x-segura-123")
        self.client.force_login(u)
        r = self.client.get(reverse("ayuda"))
        self.assertContains(r, "Para administradores de finca")
        self.assertContains(r, "Para el desarrollador")

    def test_icono_de_ayuda_en_la_barra_y_en_el_login(self):
        self.assertContains(self.client.get(reverse("login")), "¿Necesitas ayuda?")
        self.assertContains(self.client.get(reverse("landing")), f'href="{reverse("ayuda")}"')
        u = User.objects.create_user("ana", password="x-segura-123")
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse("inicio")), reverse("ayuda"))


class ManualTests(TestCase):
    def test_el_manual_se_descarga_sin_iniciar_sesion(self):
        r = self.client.get(reverse("manual"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(b"".join(r.streaming_content).startswith(b"%PDF"))

    def test_la_ayuda_enlaza_al_manual(self):
        self.assertContains(self.client.get(reverse("ayuda")), reverse("manual"))
