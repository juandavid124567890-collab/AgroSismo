"""Qué datos puede ver cada usuario.

Quien pertenece a una finca ve todo lo de esa finca (unidades, sismos,
afectaciones, fotos, historial y reportes). Quien aún no tiene finca asignada
conserva el comportamiento anterior: solo ve lo suyo.
"""
from django.db.models import Q


def q_unidades(usuario, prefijo=""):
    """Filtro de unidades visibles. `prefijo` sirve para filtrar desde otro modelo.

    Ejemplo: q_unidades(u, "unidad__") para afectaciones o sismos.
    """
    if getattr(usuario, "finca_id", None):
        return Q(**{f"{prefijo}finca_id": usuario.finca_id})
    return Q(**{f"{prefijo}propietario": usuario})


def unidades_de(usuario):
    from .models import UnidadAgricola

    return UnidadAgricola.objects.filter(q_unidades(usuario))


def unidad_es_accesible(usuario, unidad):
    """True si la unidad pertenece a la finca del usuario (o es suya si no tiene finca)."""
    if getattr(usuario, "finca_id", None):
        return unidad.finca_id == usuario.finca_id
    return unidad.propietario_id == usuario.pk
