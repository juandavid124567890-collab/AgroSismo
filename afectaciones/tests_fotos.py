import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agro.models import UnidadAgricola

from .models import Afectacion, EventoSismico, Evidencia
from .tests import imagen_png

Usuario = get_user_model()
MEDIA_TEMPORAL = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class FotosPrivadasTests(TestCase):
    """Solo el dueño puede ver sus fotografías."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        finca = UnidadAgricola.objects.create(propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10"))
        evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=finca, fecha_hora=timezone.now() - timedelta(days=1)
        )
        cls.afectacion = Afectacion.objects.create(
            evento=evento, unidad=finca, elemento="CULTIVO", tipo_dano="GRIETAS",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )

    def subir_foto(self):
        self.client.force_login(self.ana)
        self.client.post(
            reverse("evidencia_agregar", args=[self.afectacion.pk]), {"imagen": imagen_png()}
        )
        return Evidencia.objects.get()

    def test_el_dueno_ve_su_foto(self):
        ev = self.subir_foto()
        r = self.client.get(reverse("evidencia_archivo", args=[ev.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertIn("private", r["Cache-Control"])
        b"".join(r.streaming_content)

    def test_otro_productor_recibe_404(self):
        ev = self.subir_foto()
        self.client.force_login(self.luis)
        r = self.client.get(reverse("evidencia_archivo", args=[ev.pk]))
        self.assertEqual(r.status_code, 404)

    def test_sin_sesion_redirige_al_login(self):
        ev = self.subir_foto()
        self.client.logout()
        r = self.client.get(reverse("evidencia_archivo", args=[ev.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_la_carpeta_media_ya_no_es_publica(self):
        ev = self.subir_foto()
        self.client.logout()
        r = self.client.get("/media/" + ev.imagen.name)
        self.assertEqual(r.status_code, 404)

    def test_el_detalle_usa_la_direccion_protegida(self):
        ev = self.subir_foto()
        r = self.client.get(reverse("afectacion_detalle", args=[self.afectacion.pk]))
        self.assertContains(r, reverse("evidencia_archivo", args=[ev.pk]))
        self.assertNotContains(r, "/media/")


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class ApiFotosTests(TestCase):
    """Fotografías tomadas sin conexión que llegan al sincronizar."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        finca = UnidadAgricola.objects.create(propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10"))
        evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=finca, fecha_hora=timezone.now() - timedelta(days=1)
        )
        cls.afectacion = Afectacion.objects.create(
            evento=evento, unidad=finca, elemento="CULTIVO", tipo_dano="GRIETAS",
            severidad="LEVE", area_afectada_ha=Decimal("1"),
        )

    def setUp(self):
        self.client.force_login(self.ana)
        self.url = reverse("api_subir_foto")

    def enviar(self, foto_id=None, afectacion_id=None, imagen=None, **extra):
        import uuid as _uuid
        datos = {
            "id": foto_id or str(_uuid.uuid4()),
            "afectacion_id": afectacion_id or str(self.afectacion.pk),
            "imagen": imagen or imagen_png(),
            "descripcion": "Grieta en el lote",
        }
        datos.update(extra)
        return self.client.post(self.url, datos)

    def test_guarda_la_foto(self):
        r = self.enviar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado"], "ok")
        ev = Evidencia.objects.get()
        self.assertEqual(ev.afectacion, self.afectacion)
        self.assertEqual(ev.descripcion, "Grieta en el lote")
        self.assertIsNotNone(ev.sincronizado_en)

    def test_reenviar_no_duplica(self):
        foto_id = "7f1b0a1e-4a63-4f43-9d9e-2f6e7a1c0b11"
        self.enviar(foto_id=foto_id)
        r = self.enviar(foto_id=foto_id)
        self.assertEqual(r.json()["estado"], "ya_existia")
        self.assertEqual(Evidencia.objects.count(), 1)

    def test_no_acepta_afectacion_ajena(self):
        self.client.force_login(self.luis)
        r = self.enviar()
        self.assertEqual(r.json()["estado"], "error")
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        falso = SimpleUploadedFile("x.png", b"no soy una imagen", content_type="image/png")
        r = self.enviar(imagen=falso)
        self.assertEqual(r.json()["estado"], "error")
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_maximo_de_fotos_por_afectacion(self):
        for _ in range(10):
            self.enviar()
        r = self.enviar()
        self.assertEqual(r.json()["estado"], "error")
        self.assertEqual(Evidencia.objects.count(), 10)

    def test_sin_sesion_responde_401(self):
        self.client.logout()
        self.assertEqual(self.enviar().status_code, 401)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_la_foto_subida_solo_la_ve_su_dueno(self):
        self.enviar()
        ev = Evidencia.objects.get()
        self.assertEqual(self.client.get(reverse("evidencia_archivo", args=[ev.pk])).status_code, 200)
        self.client.force_login(self.luis)
        self.assertEqual(self.client.get(reverse("evidencia_archivo", args=[ev.pk])).status_code, 404)
