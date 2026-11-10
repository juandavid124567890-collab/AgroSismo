from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from .base import ModeloSincronizable, rango_o_nulo


class UnidadAgricola(ModeloSincronizable):
    """Finca, parcela o terreno del productor (RF-05, RF-06)."""

    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="unidades"
    )
    finca = models.ForeignKey(
        "accounts.Finca", on_delete=models.PROTECT, null=True, blank=True, related_name="unidades"
    )
    nombre = models.CharField(max_length=120)
    departamento = models.CharField(max_length=80, blank=True)
    municipio = models.CharField(max_length=80, blank=True)
    vereda = models.CharField(max_length=120, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    area_ha = models.DecimalField(
        "área (ha)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        db_table = "unidades_agricolas"
        ordering = ["nombre"]
        verbose_name = "unidad agrícola"
        verbose_name_plural = "unidades agrícolas"
        constraints = [
            models.UniqueConstraint(
                fields=["propietario", "nombre"], name="uq_unidad_propietario_nombre"
            ),
            models.CheckConstraint(condition=Q(area_ha__gt=0), name="ck_unidad_area_positiva"),
            models.CheckConstraint(
                condition=rango_o_nulo("latitud", -90, 90), name="ck_unidad_latitud"
            ),
            models.CheckConstraint(
                condition=rango_o_nulo("longitud", -180, 180), name="ck_unidad_longitud"
            ),
        ]

    def save(self, *args, **kwargs):
        # La unidad queda en la finca de quien la crea, para que sus compañeros la vean.
        if self.finca_id is None and self.propietario_id and self.propietario.finca_id:
            self.finca_id = self.propietario.finca_id
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Cultivo(ModeloSincronizable):
    """Cultivo asociado a una unidad agrícola (RF-07)."""

    unidad = models.ForeignKey(UnidadAgricola, on_delete=models.CASCADE, related_name="cultivos")
    tipo = models.CharField("tipo de cultivo", max_length=80)
    area_ha = models.DecimalField(
        "área sembrada (ha)", max_digits=10, decimal_places=2, null=True, blank=True
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "cultivos"
        ordering = ["tipo"]
        verbose_name = "cultivo"
        verbose_name_plural = "cultivos"
        constraints = [
            models.CheckConstraint(
                condition=Q(area_ha__isnull=True) | Q(area_ha__gt=0),
                name="ck_cultivo_area_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.tipo} ({self.unidad})"
