"""Datos de una finca y eliminación completa (solo la usa el desarrollador)."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from afectaciones.models import Afectacion, Evidencia, EventoSismico, Reporte
from agro.models import UnidadAgricola

Usuario = get_user_model()


def _conjuntos(finca):
    usuarios = Usuario.objects.filter(finca=finca, is_superuser=False)
    unidades = UnidadAgricola.objects.filter(Q(finca=finca) | Q(propietario__in=usuarios))
    afectaciones = Afectacion.objects.filter(
        Q(unidad__in=unidades) | Q(evento__unidad__in=unidades) | Q(evento__usuario__in=usuarios)
    )
    eventos = EventoSismico.objects.filter(Q(unidad__in=unidades) | Q(usuario__in=usuarios))
    return usuarios, unidades, afectaciones, eventos


def resumen_de_finca(finca):
    """Cuánta información tiene la finca (para mostrarla antes de eliminar)."""
    usuarios, unidades, afectaciones, eventos = _conjuntos(finca)
    return {
        "usuarios": usuarios.count(),
        "unidades": unidades.count(),
        "sismos": eventos.count(),
        "afectaciones": afectaciones.count(),
        "fotos": Evidencia.objects.filter(afectacion__in=afectaciones).count(),
        "reportes": Reporte.objects.filter(usuario__in=usuarios).count(),
    }


def eliminar_finca(finca):
    """Borra la finca con todo lo que contiene: usuarios, unidades, sismos, afectaciones,
    fotos y reportes. No se puede deshacer. El desarrollador nunca se borra."""
    usuarios, unidades, afectaciones, eventos = _conjuntos(finca)
    archivos = [
        (e.imagen.storage, e.imagen.name)
        for e in Evidencia.objects.filter(afectacion__in=afectaciones)
        if e.imagen
    ]
    with transaction.atomic():
        Reporte.objects.filter(usuario__in=usuarios).delete()
        Afectacion.objects.filter(pk__in=list(afectaciones.values_list("pk", flat=True))).delete()
        EventoSismico.objects.filter(pk__in=list(eventos.values_list("pk", flat=True))).delete()
        UnidadAgricola.objects.filter(pk__in=list(unidades.values_list("pk", flat=True))).delete()
        Usuario.objects.filter(finca=finca, is_superuser=True).update(finca=None)
        Usuario.objects.filter(pk__in=list(usuarios.values_list("pk", flat=True))).delete()
        finca.delete()

        def borrar_fotos():
            for almacenamiento, nombre in archivos:
                try:
                    almacenamiento.delete(nombre)
                except Exception:  # la foto ya no existe o no se puede borrar: no es grave
                    pass

        transaction.on_commit(borrar_fotos)
