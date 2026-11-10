"""Consultas reutilizables sobre las afectaciones de un productor.

Las usan el historial (RF-15, RF-16) y, más adelante, los reportes (RF-17, RF-18),
para que ambos filtren exactamente igual.
"""
from agro.alcance import q_unidades
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Afectacion, Perdida


def filtrar_afectaciones(usuario, desde=None, hasta=None, unidad=None, severidad=""):
    """Afectaciones del usuario, filtradas por fecha del sismo, unidad y severidad.

    Las fechas se comparan como rangos de fecha y hora en la zona horaria del
    proyecto. No se usa el filtro `__date` porque en MySQL depende de tablas de
    zonas horarias que no siempre están cargadas.
    """
    consulta = Afectacion.objects.filter(q_unidades(usuario, "unidad__")).select_related(
        "evento", "unidad", "cultivo"
    )
    zona = timezone.get_current_timezone()
    if desde:
        inicio = timezone.make_aware(datetime.combine(desde, time.min), zona)
        consulta = consulta.filter(evento__fecha_hora__gte=inicio)
    if hasta:
        fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), zona)
        consulta = consulta.filter(evento__fecha_hora__lt=fin)
    if unidad:
        consulta = consulta.filter(unidad=unidad)
    if severidad:
        consulta = consulta.filter(severidad=severidad)
    return consulta


def resumen_reporte(afectaciones):
    """Totales para la vista previa y el PDF de un conjunto de afectaciones (RF-17)."""
    afectaciones = afectaciones.order_by()
    conteo_severidad = dict(afectaciones.values_list("severidad").annotate(n=Count("id")))
    por_severidad = [
        (etiqueta, conteo_severidad.get(codigo, 0), codigo.lower())
        for codigo, etiqueta in reversed(Afectacion.Severidad.choices)  # de más a menos grave
    ]
    por_unidad = list(
        afectaciones.values("unidad__nombre")
        .annotate(n=Count("id"))
        .order_by("-n", "unidad__nombre")[:5]
    )
    valor = Perdida.objects.filter(afectacion__in=afectaciones.values("pk")).aggregate(
        v=Sum("valor_estimado_cop")
    )["v"]
    return {
        "total": afectaciones.count(),
        "eventos": afectaciones.values("evento").distinct().count(),
        "area": afectaciones.aggregate(v=Sum("area_afectada_ha"))["v"] or Decimal("0"),
        "valor": valor or Decimal("0"),
        "por_severidad": por_severidad,
        "por_unidad": por_unidad,
    }


def describir_filtros(filtros):
    """Texto legible de los filtros aplicados, para el encabezado del reporte."""
    partes = []
    desde, hasta = filtros.get("desde"), filtros.get("hasta")
    if desde and hasta:
        partes.append(f"del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}")
    elif desde:
        partes.append(f"desde el {desde:%d/%m/%Y}")
    elif hasta:
        partes.append(f"hasta el {hasta:%d/%m/%Y}")
    if filtros.get("unidad"):
        partes.append(f"unidad {filtros['unidad'].nombre}")
    if filtros.get("severidad"):
        partes.append(f"severidad {Afectacion.Severidad(filtros['severidad']).label.lower()}")
    return ", ".join(partes) or "ninguno (todas las afectaciones)"
