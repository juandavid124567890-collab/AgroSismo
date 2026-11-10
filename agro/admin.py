from django.contrib import admin

from .models import Cultivo, UnidadAgricola


class CultivoInline(admin.TabularInline):
    model = Cultivo
    extra = 0


@admin.register(UnidadAgricola)
class UnidadAgricolaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "finca", "propietario", "municipio", "departamento", "area_ha")
    list_filter = ("finca",)
    search_fields = ("nombre", "municipio", "propietario__username", "finca__nombre")
    inlines = [CultivoInline]


@admin.register(Cultivo)
class CultivoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "unidad", "area_ha", "activo")
    list_filter = ("activo",)
