import io
import shutil
import tempfile
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agro.models import Cultivo, UnidadAgricola

from PIL import Image

from .models import Afectacion, EventoSismico, Evidencia, Perdida, Reporte

Usuario = get_user_model()


class BaseDatos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca El Roble", area_ha=Decimal("25")
        )
        cls.otra = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Parcela San Andrés", area_ha=Decimal("10")
        )
        cls.cafe = Cultivo.objects.create(unidad=cls.finca, tipo="Café")
        cls.hace_un_dia = timezone.now() - timedelta(days=1)
        cls.evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.finca, fecha_hora=cls.hace_un_dia, magnitud=Decimal("4.2")
        )

    def afectacion(self, **extra):
        datos = dict(
            evento=self.evento,
            unidad=self.finca,
            elemento=Afectacion.Elemento.CULTIVO,
            tipo_dano=Afectacion.TipoDano.GRIETAS,
            severidad=Afectacion.Severidad.MODERADA,
            area_afectada_ha=Decimal("3"),
        )
        datos.update(extra)
        return Afectacion(**datos)


class EventoTests(BaseDatos):
    def test_no_acepta_fecha_futura(self):
        e = EventoSismico(
            usuario=self.ana, unidad=self.otra, fecha_hora=timezone.now() + timedelta(days=1)
        )
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("fecha_hora", ctx.exception.message_dict)

    def test_unidad_debe_ser_del_usuario(self):
        e = EventoSismico(usuario=self.luis, unidad=self.otra, fecha_hora=self.hace_un_dia)
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("unidad", ctx.exception.message_dict)

    def test_magnitud_fuera_de_rango_rechazada_por_la_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoSismico.objects.create(
                usuario=self.ana,
                unidad=self.otra,
                fecha_hora=self.hace_un_dia,
                magnitud=Decimal("11.0"),
            )

    def test_mismo_sismo_en_la_misma_unidad_no_se_duplica(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoSismico.objects.create(
                usuario=self.ana, unidad=self.finca, fecha_hora=self.evento.fecha_hora
            )


class SincronizacionTests(BaseDatos):
    def test_id_generado_en_el_cliente_se_conserva(self):
        uid = uuid.uuid4()
        a = self.afectacion(id=uid)
        a.save()
        self.assertEqual(Afectacion.objects.get(pk=uid).pk, uid)

    def test_reenviar_el_mismo_uuid_no_duplica(self):
        uid = uuid.uuid4()
        self.afectacion(id=uid).save()
        # Segundo envío del cliente (reintento tras una conexión interrumpida).
        Afectacion.objects.update_or_create(
            id=uid,
            defaults=dict(
                evento=self.evento,
                unidad=self.finca,
                elemento="CULTIVO",
                tipo_dano="GRIETAS",
                severidad="GRAVE",
                area_afectada_ha=Decimal("4"),
            ),
        )
        self.assertEqual(Afectacion.objects.filter(pk=uid).count(), 1)
        self.assertEqual(Afectacion.objects.get(pk=uid).severidad, "GRAVE")

    def test_sincronizado_en_empieza_vacio(self):
        a = self.afectacion()
        a.save()
        self.assertIsNone(a.sincronizado_en)


class AfectacionTests(BaseDatos):
    def test_afectacion_valida(self):
        self.afectacion(cultivo=self.cafe).full_clean()

    def test_unidad_debe_coincidir_con_la_del_evento(self):
        with self.assertRaises(ValidationError) as ctx:
            self.afectacion(unidad=self.otra).full_clean()
        self.assertIn("unidad", ctx.exception.message_dict)

    def test_cultivo_debe_ser_de_la_unidad(self):
        otro = Cultivo.objects.create(unidad=self.otra, tipo="Plátano")
        with self.assertRaises(ValidationError) as ctx:
            self.afectacion(cultivo=otro).full_clean()
        self.assertIn("cultivo", ctx.exception.message_dict)

    def test_area_afectada_no_supera_la_unidad(self):
        with self.assertRaises(ValidationError) as ctx:
            self.afectacion(area_afectada_ha=Decimal("26")).full_clean()
        self.assertIn("area_afectada_ha", ctx.exception.message_dict)

    def test_area_negativa_rechazada(self):
        with self.assertRaises(ValidationError):
            self.afectacion(area_afectada_ha=Decimal("-1")).full_clean()

    def test_severidad_invalida_rechazada(self):
        with self.assertRaises(ValidationError):
            self.afectacion(severidad="CATASTROFICA").full_clean()

    def test_latitud_fuera_de_rango_rechazada_por_la_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.afectacion(latitud=Decimal("95")).save()

    def test_borrar_evento_borra_sus_afectaciones(self):
        a = self.afectacion()
        a.save()
        self.evento.delete()
        self.assertFalse(Afectacion.objects.filter(pk=a.pk).exists())


class PerdidaTests(BaseDatos):
    def test_valor_negativo_rechazado_por_la_bd(self):
        a = self.afectacion()
        a.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Perdida.objects.create(afectacion=a, cantidad=Decimal("10"), valor_estimado_cop=Decimal("-1"))

    def test_varias_perdidas_por_afectacion(self):
        a = self.afectacion()
        a.save()
        Perdida.objects.create(afectacion=a, cantidad=Decimal("500"), valor_estimado_cop=Decimal("2500000"))
        Perdida.objects.create(afectacion=a, cantidad=Decimal("10"), unidad_medida="BULTO")
        self.assertEqual(a.perdidas.count(), 2)

    def test_cultivo_debe_ser_de_la_unidad_de_la_afectacion(self):
        a = self.afectacion()
        a.save()
        otro = Cultivo.objects.create(unidad=self.otra, tipo="Plátano")
        with self.assertRaises(ValidationError):
            Perdida(afectacion=a, cultivo=otro, cantidad=Decimal("1")).full_clean()


class ReporteTests(BaseDatos):
    def test_reporte_incluye_afectaciones(self):
        a = self.afectacion()
        a.save()
        r = Reporte.objects.create(usuario=self.ana, fecha_desde=date(2026, 8, 1), fecha_hasta=date(2026, 9, 30))
        r.afectaciones.add(a)
        self.assertEqual(list(r.afectaciones.all()), [a])
        self.assertEqual(list(a.reportes.all()), [r])

    def test_rango_de_fechas_invertido_rechazado_por_la_bd(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reporte.objects.create(
                usuario=self.ana, fecha_desde=date(2026, 9, 30), fecha_hasta=date(2026, 8, 1)
            )


class VistasEventoTests(TestCase):
    """Pantallas de sismos y afectaciones: cada productor solo ve lo suyo."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10")
        )
        cls.finca_luis = UnidadAgricola.objects.create(
            propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("5")
        )
        cls.cafe = Cultivo.objects.create(unidad=cls.finca, tipo="Café")
        cls.cafe_luis = Cultivo.objects.create(unidad=cls.finca_luis, tipo="Yuca")
        cls.ayer = timezone.now() - timedelta(days=1)
        cls.evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.finca, fecha_hora=cls.ayer
        )
        cls.evento_luis = EventoSismico.objects.create(
            usuario=cls.luis, unidad=cls.finca_luis, fecha_hora=cls.ayer
        )

    def setUp(self):
        self.client.force_login(self.ana)

    @staticmethod
    def texto_fecha(delta):
        return (timezone.localtime() + delta).strftime("%Y-%m-%dT%H:%M")

    def datos_afectacion(self, **extra):
        datos = {
            "cultivo": "",
            "elemento": "CULTIVO",
            "tipo_dano": "GRIETAS",
            "severidad": "MODERADA",
            "area_afectada_ha": "3",
        }
        datos.update(extra)
        return datos

    def test_requiere_iniciar_sesion(self):
        self.client.logout()
        r = self.client.get(reverse("eventos"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_lista_solo_muestra_los_propios(self):
        r = self.client.get(reverse("eventos"))
        self.assertContains(r, "Finca Ana")
        self.assertNotContains(r, "Finca Luis")

    def test_registrar_sismo(self):
        r = self.client.post(
            reverse("evento_crear"),
            {
                "unidad": self.finca.pk,
                "fecha_hora": self.texto_fecha(timedelta(days=-2)),
                "magnitud": "4.2",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(EventoSismico.objects.filter(usuario=self.ana).count(), 2)

    def test_sismo_con_fecha_futura_rechazado(self):
        r = self.client.post(
            reverse("evento_crear"),
            {"unidad": self.finca.pk, "fecha_hora": self.texto_fecha(timedelta(days=2))},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(EventoSismico.objects.filter(usuario=self.ana).count(), 1)

    def test_sismo_en_unidad_ajena_rechazado(self):
        r = self.client.post(
            reverse("evento_crear"),
            {"unidad": self.finca_luis.pk, "fecha_hora": self.texto_fecha(timedelta(days=-3))},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(EventoSismico.objects.filter(unidad=self.finca_luis).count(), 1)

    def test_magnitud_fuera_de_rango_rechazada(self):
        r = self.client.post(
            reverse("evento_crear"),
            {
                "unidad": self.finca.pk,
                "fecha_hora": self.texto_fecha(timedelta(days=-3)),
                "magnitud": "12",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(EventoSismico.objects.filter(usuario=self.ana).count(), 1)

    def test_no_puede_ver_sismo_ajeno(self):
        r = self.client.get(reverse("evento_detalle", args=[self.evento_luis.pk]))
        self.assertEqual(r.status_code, 404)

    def test_registrar_afectacion_con_perdida(self):
        r = self.client.post(
            reverse("afectacion_crear", args=[self.evento.pk]),
            self.datos_afectacion(
                cultivo=self.cafe.pk,
                perdida_cantidad="500",
                perdida_unidad="KG",
                perdida_valor="2500000",
            ),
        )
        self.assertEqual(r.status_code, 302)
        a = Afectacion.objects.get(evento=self.evento)
        self.assertEqual(a.unidad, self.finca)
        self.assertIsNotNone(a.sincronizado_en)
        p = a.perdidas.get()
        self.assertEqual(p.cantidad, Decimal("500"))
        self.assertEqual(p.valor_estimado_cop, Decimal("2500000"))

    def test_afectacion_sin_perdida_no_crea_perdida(self):
        self.client.post(reverse("afectacion_crear", args=[self.evento.pk]), self.datos_afectacion())
        self.assertEqual(Perdida.objects.count(), 0)

    def test_area_afectada_mayor_que_la_unidad_rechazada(self):
        r = self.client.post(
            reverse("afectacion_crear", args=[self.evento.pk]),
            self.datos_afectacion(area_afectada_ha="11"),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Afectacion.objects.count(), 0)

    def test_cultivo_de_otra_unidad_rechazado(self):
        r = self.client.post(
            reverse("afectacion_crear", args=[self.evento.pk]),
            self.datos_afectacion(cultivo=self.cafe_luis.pk),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Afectacion.objects.count(), 0)

    def test_no_puede_registrar_afectacion_en_sismo_ajeno(self):
        r = self.client.post(
            reverse("afectacion_crear", args=[self.evento_luis.pk]), self.datos_afectacion()
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Afectacion.objects.count(), 0)

    def test_editar_afectacion_actualiza_la_perdida(self):
        self.client.post(
            reverse("afectacion_crear", args=[self.evento.pk]),
            self.datos_afectacion(perdida_cantidad="10", perdida_valor="1000"),
        )
        a = Afectacion.objects.get(evento=self.evento)
        r = self.client.post(
            reverse("afectacion_editar", args=[a.pk]),
            self.datos_afectacion(severidad="GRAVE", perdida_cantidad="20", perdida_valor="2000"),
        )
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        self.assertEqual(a.severidad, "GRAVE")
        self.assertEqual(a.perdidas.count(), 1)
        self.assertEqual(a.perdidas.get().cantidad, Decimal("20"))

    def test_no_puede_ver_afectacion_ajena(self):
        ajena = Afectacion.objects.create(
            evento=self.evento_luis,
            unidad=self.finca_luis,
            elemento="TERRENO",
            tipo_dano="GRIETAS",
            severidad="LEVE",
            area_afectada_ha=Decimal("1"),
        )
        r = self.client.get(reverse("afectacion_detalle", args=[ajena.pk]))
        self.assertEqual(r.status_code, 404)


MEDIA_TEMPORAL = tempfile.mkdtemp()


def imagen_png(nombre="foto.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "green").save(buffer, format="PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class FotografiasTests(TestCase):
    """Fotos de evidencia: formato, tamaño, límite y propiedad (RF-12, riesgo R-08)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        ayer = timezone.now() - timedelta(days=1)
        cls.finca = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10")
        )
        cls.finca_luis = UnidadAgricola.objects.create(
            propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("5")
        )
        evento = EventoSismico.objects.create(usuario=cls.ana, unidad=cls.finca, fecha_hora=ayer)
        evento_luis = EventoSismico.objects.create(
            usuario=cls.luis, unidad=cls.finca_luis, fecha_hora=ayer
        )
        datos = dict(
            elemento="TERRENO", tipo_dano="GRIETAS", severidad="LEVE", area_afectada_ha=Decimal("1")
        )
        cls.afectacion = Afectacion.objects.create(evento=evento, unidad=cls.finca, **datos)
        cls.afectacion_luis = Afectacion.objects.create(
            evento=evento_luis, unidad=cls.finca_luis, **datos
        )

    def setUp(self):
        self.client.force_login(self.ana)

    def url_agregar(self, afectacion=None):
        return reverse("evidencia_agregar", args=[(afectacion or self.afectacion).pk])

    def test_agregar_fotografia_valida(self):
        r = self.client.post(
            self.url_agregar(), {"imagen": imagen_png(), "descripcion": "Grieta en el lote"}
        )
        self.assertEqual(r.status_code, 302)
        ev = Evidencia.objects.get(afectacion=self.afectacion)
        self.assertEqual(ev.descripcion, "Grieta en el lote")
        self.assertIsNotNone(ev.sincronizado_en)

    def test_archivo_que_no_es_imagen_rechazado(self):
        falso = SimpleUploadedFile("nota.png", b"esto no es una imagen", content_type="image/png")
        r = self.client.post(self.url_agregar(), {"imagen": falso})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_formato_no_permitido_rechazado(self):
        gif = SimpleUploadedFile("animacion.gif", b"GIF89a", content_type="image/gif")
        r = self.client.post(self.url_agregar(), {"imagen": gif})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evidencia.objects.count(), 0)

    @override_settings(FOTO_MAX_BYTES=10)
    def test_foto_demasiado_grande_rechazada(self):
        r = self.client.post(self.url_agregar(), {"imagen": imagen_png()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_limite_de_fotos_por_afectacion(self):
        for i in range(10):
            Evidencia.objects.create(afectacion=self.afectacion, imagen=f"evidencias/prueba{i}.png")
        r = self.client.post(self.url_agregar(), {"imagen": imagen_png()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Evidencia.objects.filter(afectacion=self.afectacion).count(), 10)

    def test_no_puede_agregar_foto_a_afectacion_ajena(self):
        r = self.client.post(self.url_agregar(self.afectacion_luis), {"imagen": imagen_png()})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_eliminar_fotografia_propia(self):
        self.client.post(self.url_agregar(), {"imagen": imagen_png()})
        ev = Evidencia.objects.get()
        r = self.client.post(reverse("evidencia_eliminar", args=[ev.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Evidencia.objects.count(), 0)

    def test_eliminar_solo_acepta_post(self):
        ev = Evidencia.objects.create(afectacion=self.afectacion, imagen="evidencias/x.png")
        r = self.client.get(reverse("evidencia_eliminar", args=[ev.pk]))
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Evidencia.objects.count(), 1)

    def test_no_puede_eliminar_foto_ajena(self):
        ev = Evidencia.objects.create(afectacion=self.afectacion_luis, imagen="evidencias/y.png")
        r = self.client.post(reverse("evidencia_eliminar", args=[ev.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Evidencia.objects.count(), 1)

    def test_el_detalle_muestra_las_fotos(self):
        self.client.post(self.url_agregar(), {"imagen": imagen_png(), "descripcion": "Vista general"})
        r = self.client.get(reverse("afectacion_detalle", args=[self.afectacion.pk]))
        self.assertContains(r, "Vista general")


class HistorialTests(TestCase):
    """Historial: filtros por fecha, unidad y severidad; solo datos propios (RF-15, RF-16)."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10")
        )
        cls.otra = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Otra Ana", area_ha=Decimal("10")
        )
        cls.finca_luis = UnidadAgricola.objects.create(
            propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("10")
        )
        ahora = timezone.now()
        cls.viejo = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.finca, fecha_hora=ahora - timedelta(days=10)
        )
        cls.reciente = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.otra, fecha_hora=ahora - timedelta(days=1)
        )
        evento_luis = EventoSismico.objects.create(
            usuario=cls.luis, unidad=cls.finca_luis, fecha_hora=ahora - timedelta(days=1)
        )
        base = dict(elemento="TERRENO", tipo_dano="GRIETAS", area_afectada_ha=Decimal("1"))
        cls.leve = Afectacion.objects.create(
            evento=cls.viejo, unidad=cls.finca, severidad="LEVE", **base
        )
        cls.grave = Afectacion.objects.create(
            evento=cls.reciente, unidad=cls.otra, severidad="GRAVE", **base
        )
        cls.ajena = Afectacion.objects.create(
            evento=evento_luis, unidad=cls.finca_luis, severidad="GRAVE", **base
        )
        Perdida.objects.create(afectacion=cls.leve, cantidad=Decimal("5"), valor_estimado_cop=Decimal("500"))
        Perdida.objects.create(afectacion=cls.grave, cantidad=Decimal("9"), valor_estimado_cop=Decimal("1000"))

    def setUp(self):
        self.client.force_login(self.ana)

    def ids(self, **filtros):
        r = self.client.get(reverse("historial"), filtros)
        self.assertEqual(r.status_code, 200)
        return {a.pk for a in r.context["pagina"]}, r

    @staticmethod
    def hace(dias):
        return (timezone.localdate() - timedelta(days=dias)).isoformat()

    def test_requiere_iniciar_sesion(self):
        self.client.logout()
        r = self.client.get(reverse("historial"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_sin_filtros_muestra_solo_las_propias(self):
        ids, _ = self.ids()
        self.assertEqual(ids, {self.leve.pk, self.grave.pk})

    def test_filtro_por_severidad(self):
        ids, _ = self.ids(severidad="GRAVE")
        self.assertEqual(ids, {self.grave.pk})

    def test_filtro_por_unidad(self):
        ids, _ = self.ids(unidad=self.finca.pk)
        self.assertEqual(ids, {self.leve.pk})

    def test_no_se_puede_filtrar_por_unidad_ajena(self):
        ids, r = self.ids(unidad=self.finca_luis.pk)
        # El filtro es inválido, así que no se aplica y nunca aparecen datos ajenos.
        self.assertNotIn(self.ajena.pk, ids)

    def test_filtro_desde(self):
        ids, _ = self.ids(desde=self.hace(3))
        self.assertEqual(ids, {self.grave.pk})

    def test_filtro_hasta(self):
        ids, _ = self.ids(hasta=self.hace(5))
        self.assertEqual(ids, {self.leve.pk})

    def test_rango_invertido_muestra_error(self):
        _, r = self.ids(desde=self.hace(1), hasta=self.hace(5))
        self.assertContains(r, "no puede ser posterior")

    def test_resumen_suma_las_perdidas(self):
        _, r = self.ids()
        self.assertEqual(r.context["resumen"]["total"], 2)
        self.assertEqual(r.context["resumen"]["valor"], Decimal("1500"))

    def test_resumen_respeta_los_filtros(self):
        _, r = self.ids(severidad="LEVE")
        self.assertEqual(r.context["resumen"]["total"], 1)
        self.assertEqual(r.context["resumen"]["valor"], Decimal("500"))


class ReportesPdfTests(TestCase):
    """Reporte: vista previa, exportación a PDF y registro del reporte (RF-17, RF-18)."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user("ana", password="x-segura-123")
        cls.luis = Usuario.objects.create_user("luis", password="x-segura-123")
        cls.finca = UnidadAgricola.objects.create(
            propietario=cls.ana, nombre="Finca Ana", area_ha=Decimal("10")
        )
        cls.finca_luis = UnidadAgricola.objects.create(
            propietario=cls.luis, nombre="Finca Luis", area_ha=Decimal("10")
        )
        ahora = timezone.now()
        evento = EventoSismico.objects.create(
            usuario=cls.ana, unidad=cls.finca, fecha_hora=ahora - timedelta(days=2)
        )
        evento_luis = EventoSismico.objects.create(
            usuario=cls.luis, unidad=cls.finca_luis, fecha_hora=ahora - timedelta(days=2)
        )
        base = dict(elemento="TERRENO", tipo_dano="GRIETAS", area_afectada_ha=Decimal("2"))
        cls.leve = Afectacion.objects.create(evento=evento, unidad=cls.finca, severidad="LEVE", **base)
        cls.grave = Afectacion.objects.create(evento=evento, unidad=cls.finca, severidad="GRAVE", **base)
        cls.ajena = Afectacion.objects.create(
            evento=evento_luis, unidad=cls.finca_luis, severidad="GRAVE", **base
        )
        Perdida.objects.create(afectacion=cls.leve, cantidad=Decimal("5"), valor_estimado_cop=Decimal("500"))
        Perdida.objects.create(afectacion=cls.grave, cantidad=Decimal("9"), valor_estimado_cop=Decimal("1000"))

    def setUp(self):
        self.client.force_login(self.ana)

    def test_requiere_iniciar_sesion(self):
        self.client.logout()
        for nombre in ("reporte",):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse("login"), r["Location"])
        r = self.client.post(reverse("reporte_pdf"), {})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reporte.objects.count(), 0)

    def test_vista_previa_con_totales_propios(self):
        r = self.client.get(reverse("reporte"))
        self.assertEqual(r.status_code, 200)
        resumen = r.context["resumen"]
        self.assertEqual(resumen["total"], 2)
        self.assertEqual(resumen["eventos"], 1)
        self.assertEqual(resumen["area"], Decimal("4"))
        self.assertEqual(resumen["valor"], Decimal("1500"))
        self.assertEqual(
            [(etiqueta, n) for etiqueta, n, _ in resumen["por_severidad"]],
            [("Grave", 1), ("Moderada", 0), ("Leve", 1)],
        )

    def test_vista_previa_respeta_los_filtros(self):
        r = self.client.get(reverse("reporte"), {"severidad": "GRAVE"})
        self.assertEqual(r.context["resumen"]["total"], 1)
        self.assertEqual(r.context["resumen"]["valor"], Decimal("1000"))

    def test_exportar_pdf(self):
        r = self.client.post(reverse("reporte_pdf"), {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_exportar_guarda_el_reporte_solo_con_datos_propios(self):
        self.client.post(reverse("reporte_pdf"), {"severidad": "GRAVE"})
        registro = Reporte.objects.get()
        self.assertEqual(registro.usuario, self.ana)
        self.assertEqual(registro.formato, "PDF")
        self.assertEqual(list(registro.afectaciones.all()), [self.grave])

    def test_exportar_solo_acepta_post(self):
        r = self.client.get(reverse("reporte_pdf"))
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Reporte.objects.count(), 0)

    def test_sin_resultados_no_genera_reporte(self):
        r = self.client.post(reverse("reporte_pdf"), {"severidad": "MODERADA"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reporte.objects.count(), 0)

    def test_filtros_invalidos_no_generan_reporte(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        hace_5 = (timezone.localdate() - timedelta(days=5)).isoformat()
        r = self.client.post(reverse("reporte_pdf"), {"desde": ayer, "hasta": hace_5})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reporte.objects.count(), 0)

    def test_unidad_ajena_no_genera_reporte(self):
        r = self.client.post(reverse("reporte_pdf"), {"unidad": self.finca_luis.pk})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reporte.objects.count(), 0)

    def test_describir_filtros(self):
        from .consultas import describir_filtros

        self.assertEqual(describir_filtros({}), "ninguno (todas las afectaciones)")
        texto = describir_filtros(
            {"desde": date(2026, 8, 1), "hasta": date(2026, 9, 30), "unidad": self.finca, "severidad": "GRAVE"}
        )
        self.assertEqual(texto, "del 01/08/2026 al 30/09/2026, unidad Finca Ana, severidad grave")

    def test_formato_de_pesos(self):
        from .pdf import formato_cop

        self.assertEqual(formato_cop(Decimal("1500000")), "$1.500.000")
        self.assertEqual(formato_cop(None), "$0")
