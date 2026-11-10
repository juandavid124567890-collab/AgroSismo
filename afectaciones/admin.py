from django.contrib import admin

from .models import Afectacion, EventoSismico, Evidencia, Perdida, Reporte


class EvidenciaInline(admin.TabularInline):
    model = Evidencia
    extra = 0


class PerdidaInline(admin.TabularInline):
    model = Perdida
    extra = 0


@admin.register(EventoSismico)
class EventoSismicoAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "unidad", "usuario", "magnitud")
    list_filter = ("fecha_hora",)
    search_fields = ("unidad__nombre", "usuario__username", "epicentro")


@admin.register(Afectacion)
class AfectacionAdmin(admin.ModelAdmin):
    list_display = ("unidad", "evento", "tipo_dano", "severidad", "area_afectada_ha")
    list_filter = ("severidad", "tipo_dano", "elemento")
    search_fields = ("unidad__nombre", "observaciones")
    inlines = [EvidenciaInline, PerdidaInline]


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "fecha_generacion", "formato", "fecha_desde", "fecha_hasta")
    list_filter = ("formato",)
    filter_horizontal = ("afectaciones",)
