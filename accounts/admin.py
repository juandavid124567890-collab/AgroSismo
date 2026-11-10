from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ActividadAdministrativa, Finca, SolicitudClave, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "finca", "rol", "is_active", "date_joined")
    list_filter = ("rol", "finca", "is_active")
    fieldsets = UserAdmin.fieldsets + (("AgroSismo", {"fields": ("rol", "finca", "telefono")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("AgroSismo", {"fields": ("rol", "finca", "telefono")}),)


@admin.register(Finca)
class FincaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa", "creada_en")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(ActividadAdministrativa)
class ActividadAdministrativaAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "accion", "administrador", "usuario_objetivo")
    list_filter = ("accion",)
    readonly_fields = ("administrador", "usuario_objetivo", "accion", "detalle", "creado_en")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SolicitudClave)
class SolicitudClaveAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "usuario", "contacto", "atendida_en", "atendida_por")
    list_filter = ("atendida_en",)
    readonly_fields = ("usuario", "contacto", "creado_en", "atendida_en", "atendida_por")

    def has_add_permission(self, request):
        return False
