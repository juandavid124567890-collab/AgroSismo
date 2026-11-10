from agro.alcance import unidad_es_accesible
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from agro.base import ModeloSincronizable, rango_o_nulo
from agro.models import Cultivo, UnidadAgricola


class EventoSismico(ModeloSincronizable):
    """Sismo registrado manualmente por el usuario (RF-08, RF-09).

    La magnitud y el epicentro son opcionales: el productor no siempre los
    conoce, y la SRS solo exige fecha, hora y unidad agrícola.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="eventos"
    )
    unidad = models.ForeignKey(
        UnidadAgricola, on_delete=models.PROTECT, related_name="eventos"
    )
    fecha_hora = models.DateTimeField("fecha y hora del sismo")
    magnitud = models.DecimalField(
        "magnitud (ML)", max_digits=3, decimal_places=1, null=True, blank=True
    )
    epicentro = models.CharField("epicentro / referencia", max_length=200, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "eventos_sismicos"
        ordering = ["-fecha_hora"]
        verbose_name = "evento sísmico"
        verbose_name_plural = "eventos sísmicos"
        indexes = [models.Index(fields=["usuario", "-fecha_hora"], name="ix_evento_usuario_fecha")]
        constraints = [
            models.CheckConstraint(
                condition=rango_o_nulo("magnitud", 0, 10), name="ck_evento_magnitud"
            ),
            # Evita duplicar el mismo sismo si se sincroniza con otro UUID.
            models.UniqueConstraint(
                fields=["unidad", "fecha_hora"], name="uq_evento_unidad_fecha"
            ),
        ]

    def clean(self):
        if self.fecha_hora and self.fecha_hora > timezone.now():
            raise ValidationError({"fecha_hora": "La fecha del sismo no puede estar en el futuro."})
        if self.unidad_id and self.usuario_id and not unidad_es_accesible(self.usuario, self.unidad):
            raise ValidationError({"unidad": "La unidad agrícola no pertenece a tu finca."})

    def __str__(self):
        return f"Sismo {timezone.localtime(self.fecha_hora):%Y-%m-%d %H:%M} · {self.unidad}"


class Afectacion(ModeloSincronizable):
    """Daño causado por un evento sísmico sobre una unidad agrícola (RF-10, RF-11)."""

    class TipoDano(models.TextChoices):
        DESLIZAMIENTO = "DESLIZAMIENTO", "Deslizamiento"
        INUNDACION = "INUNDACION", "Inundación"
        GRIETAS = "GRIETAS", "Grietas"
        HUNDIMIENTO = "HUNDIMIENTO", "Hundimiento"
        OTRO = "OTRO", "Otro"

    class Severidad(models.TextChoices):
        LEVE = "LEVE", "Leve"
        MODERADA = "MODERADA", "Moderada"
        GRAVE = "GRAVE", "Grave"

    class Elemento(models.TextChoices):
        CULTIVO = "CULTIVO", "Cultivos"
        TERRENO = "TERRENO", "Terreno"
        RIEGO = "RIEGO", "Sistema de riego"
        CERCAS = "CERCAS", "Cercas"
        BODEGA = "BODEGA", "Bodegas"
        MAQUINARIA = "MAQUINARIA", "Maquinaria o herramientas"
        VIAS = "VIAS", "Vías de acceso"
        VIVIENDA = "VIVIENDA", "Vivienda o infraestructura"

    evento = models.ForeignKey(EventoSismico, on_delete=models.CASCADE, related_name="afectaciones")
    unidad = models.ForeignKey(UnidadAgricola, on_delete=models.PROTECT, related_name="afectaciones")
    cultivo = models.ForeignKey(
        Cultivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="afectaciones"
    )
    elemento = models.CharField("elemento afectado", max_length=12, choices=Elemento.choices)
    tipo_dano = models.CharField("tipo de daño", max_length=14, choices=TipoDano.choices)
    tipo_dano_otro = models.CharField("¿cuál otro daño?", max_length=100, blank=True)
    severidad = models.CharField("nivel de severidad", max_length=9, choices=Severidad.choices)
    area_afectada_ha = models.DecimalField(
        "área afectada (ha)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ubicacion_texto = models.CharField("referencia de ubicación", max_length=200, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "afectaciones"
        ordering = ["-creado_en"]
        verbose_name = "afectación"
        verbose_name_plural = "afectaciones"
        indexes = [
            models.Index(fields=["unidad", "severidad"], name="ix_afect_unidad_severidad"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(area_afectada_ha__gte=0), name="ck_afect_area"),
            models.CheckConstraint(
                condition=rango_o_nulo("latitud", -90, 90), name="ck_afect_latitud"
            ),
            models.CheckConstraint(
                condition=rango_o_nulo("longitud", -180, 180), name="ck_afect_longitud"
            ),
        ]

    @property
    def tipo_dano_texto(self):
        """Nombre del daño; si es "Otro", muestra lo que escribió el usuario."""
        if self.tipo_dano == self.TipoDano.OTRO and self.tipo_dano_otro:
            return f"Otro: {self.tipo_dano_otro}"
        return self.get_tipo_dano_display()

    def clean(self):
        errores = {}
        self.tipo_dano_otro = (self.tipo_dano_otro or "").strip()
        if self.tipo_dano == self.TipoDano.OTRO:
            if not self.tipo_dano_otro:
                errores["tipo_dano_otro"] = "Escribe cuál es el otro daño."
        else:
            self.tipo_dano_otro = ""
        # El ER guarda la unidad también en la afectación; debe coincidir con la
        # del evento para que no existan datos contradictorios (riesgo R-06).
        if self.evento_id and self.unidad_id and self.evento.unidad_id != self.unidad_id:
            errores["unidad"] = (
                "La afectación debe registrarse sobre la misma unidad agrícola del evento sísmico."
            )
        if self.cultivo_id and self.unidad_id and self.cultivo.unidad_id != self.unidad_id:
            errores["cultivo"] = "El cultivo no pertenece a la unidad agrícola seleccionada."
        if (
            self.unidad_id
            and self.area_afectada_ha is not None
            and self.area_afectada_ha > self.unidad.area_ha
        ):
            errores["area_afectada_ha"] = "El área afectada supera el área de la unidad."
        if errores:
            raise ValidationError(errores)

    def __str__(self):
        return f"{self.get_severidad_display()} · {self.tipo_dano_texto} · {self.unidad}"


def ruta_evidencia(instancia, nombre_archivo):
    return f"evidencias/{instancia.afectacion_id}/{instancia.id}_{nombre_archivo}"


class Evidencia(ModeloSincronizable):
    """Fotografía asociada a una afectación (RF-12, RF-14)."""

    afectacion = models.ForeignKey(Afectacion, on_delete=models.CASCADE, related_name="evidencias")
    imagen = models.ImageField(
        upload_to=ruta_evidencia,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "evidencias"
        ordering = ["creado_en"]
        verbose_name = "evidencia fotográfica"
        verbose_name_plural = "evidencias fotográficas"

    def clean(self):
        limite = getattr(settings, "FOTO_MAX_BYTES", 5 * 1024 * 1024)
        if self.imagen and self.imagen.size > limite:
            raise ValidationError(
                {"imagen": f"La fotografía supera el máximo de {limite // (1024 * 1024)} MB."}
            )

    def __str__(self):
        return f"Evidencia de {self.afectacion_id}"


class Perdida(ModeloSincronizable):
    """Pérdida de producción y valor económico estimado (RF-13).

    Son estimaciones del usuario, no una valoración técnica oficial (riesgo R-21).
    Puede haber varias por afectación (por ejemplo, una por cultivo).
    """

    class UnidadMedida(models.TextChoices):
        KG = "KG", "Kilogramos"
        TON = "TON", "Toneladas"
        BULTO = "BULTO", "Bultos"
        UNIDAD = "UNIDAD", "Unidades"

    afectacion = models.ForeignKey(Afectacion, on_delete=models.CASCADE, related_name="perdidas")
    cultivo = models.ForeignKey(
        Cultivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="perdidas"
    )
    cantidad = models.DecimalField(
        "producción perdida", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    unidad_medida = models.CharField(max_length=6, choices=UnidadMedida.choices, default=UnidadMedida.KG)
    valor_estimado_cop = models.DecimalField(
        "valor económico estimado (COP)", max_digits=14, decimal_places=2, default=Decimal("0")
    )

    class Meta:
        db_table = "perdidas"
        verbose_name = "pérdida estimada"
        verbose_name_plural = "pérdidas estimadas"
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gte=0), name="ck_perdida_cantidad"),
            models.CheckConstraint(
                condition=Q(valor_estimado_cop__gte=0), name="ck_perdida_valor"
            ),
        ]

    def clean(self):
        if self.cultivo_id and self.afectacion_id and self.cultivo.unidad_id != self.afectacion.unidad_id:
            raise ValidationError({"cultivo": "El cultivo no pertenece a la unidad de la afectación."})

    def __str__(self):
        return f"{self.cantidad} {self.unidad_medida} · ${self.valor_estimado_cop:,.0f} COP"


class Reporte(models.Model):
    """Reporte generado por un usuario sobre un conjunto de afectaciones (RF-17, RF-18).

    Se guarda qué afectaciones incluyó (tabla `reporte_afectacion` del ER) para
    poder regenerar el mismo PDF más adelante. Se genera en línea, por eso usa
    un id autoincremental y no un UUID.
    """

    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reportes"
    )
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    formato = models.CharField(max_length=5, choices=Formato.choices, default=Formato.PDF)
    fecha_desde = models.DateField(null=True, blank=True)
    fecha_hasta = models.DateField(null=True, blank=True)
    afectaciones = models.ManyToManyField(
        Afectacion, related_name="reportes", db_table="reporte_afectacion", blank=True
    )

    class Meta:
        db_table = "reportes"
        ordering = ["-fecha_generacion"]
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_desde__isnull=True)
                | Q(fecha_hasta__isnull=True)
                | Q(fecha_desde__lte=F("fecha_hasta")),
                name="ck_reporte_rango_fechas",
            ),
        ]

    def __str__(self):
        return f"Reporte {self.pk} · {timezone.localtime(self.fecha_generacion):%Y-%m-%d %H:%M}"
