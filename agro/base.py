"""Piezas compartidas por los modelos que se registran desde el cliente offline."""
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class ModeloSincronizable(models.Model):
    """Base para registros que pueden nacer sin conexión (RF-20, RNF-06, RNF-12).

    - `id` es un UUID que el cliente puede generar sin hablar con el servidor.
      Reenviar el mismo registro actualiza la misma fila en lugar de duplicarla
      (sincronización idempotente, riesgo R-02).
    - `creado_en` es la hora en que el usuario creó el registro (puede venir del
      dispositivo); `actualizado_en` lo fija el servidor en cada cambio.
    - `sincronizado_en` queda vacío hasta que el servidor confirma el guardado.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(auto_now=True)
    sincronizado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


def rango_o_nulo(campo, minimo, maximo):
    """Condición de CHECK: el campo es nulo o está dentro de [minimo, maximo]."""
    return Q(**{f"{campo}__isnull": True}) | Q(
        **{f"{campo}__gte": minimo, f"{campo}__lte": maximo}
    )
