"""Crea una finca para cada cuenta que todavía no tiene y mueve a ella sus unidades.

Sirve una sola vez, al pasar de "cada usuario con sus datos" a "fincas con varios
usuarios". Se puede ejecutar de nuevo sin problema: solo toca lo que falta.
Después, el desarrollador reagrupa a los usuarios en el panel de administración
(cambiando su finca) cuando varios trabajan en la misma.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Finca
from agro.models import UnidadAgricola

Usuario = get_user_model()


def nombre_libre(base):
    nombre, n = base, 2
    while Finca.objects.filter(nombre=nombre).exists():
        nombre, n = f"{base} ({n})", n + 1
    return nombre


class Command(BaseCommand):
    help = "Crea una finca para cada usuario sin finca y le asigna sus unidades agrícolas."

    @transaction.atomic
    def handle(self, *args, **opciones):
        creadas = 0
        for usuario in Usuario.objects.filter(finca__isnull=True).order_by("pk"):
            tiene_unidades = UnidadAgricola.objects.filter(propietario=usuario).exists()
            if usuario.is_superuser and not tiene_unidades:
                continue  # el desarrollador no necesita finca si no registra datos
            finca = Finca.objects.create(nombre=nombre_libre(f"Finca de {usuario.username}"))
            usuario.finca = finca
            usuario.save(update_fields=["finca"])
            creadas += 1
        movidas = 0
        for unidad in UnidadAgricola.objects.filter(finca__isnull=True).select_related("propietario"):
            if unidad.propietario.finca_id:
                UnidadAgricola.objects.filter(pk=unidad.pk).update(finca_id=unidad.propietario.finca_id)
                movidas += 1
        self.stdout.write(self.style.SUCCESS(f"Fincas creadas: {creadas}. Unidades asignadas: {movidas}."))
