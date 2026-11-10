from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Finca(models.Model):
    """Grupo de trabajo: una finca (o empresa) con su administrador y sus trabajadores.

    Todos los usuarios de una misma finca comparten las unidades agrícolas, los sismos,
    las afectaciones, el historial y los reportes de esa finca. Solo el desarrollador
    (superusuario) crea fincas.
    """

    nombre = models.CharField(max_length=120, unique=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fincas"
        ordering = ["nombre"]
        verbose_name = "finca"
        verbose_name_plural = "fincas"

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    """Usuario del sistema (RF-02, RF-03, RF-04).

    Dos roles según la SRS: administrador y usuario agrícola. Las cuentas se
    desactivan con `is_active=False` (no se borran) para conservar el historial.
    """

    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        AGRICOLA = "AGRICOLA", "Usuario agrícola"

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.AGRICOLA)
    telefono = models.CharField(max_length=20, blank=True)
    finca = models.ForeignKey(
        Finca, on_delete=models.PROTECT, null=True, blank=True, related_name="miembros"
    )

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        # Un superusuario creado con createsuperuser siempre es administrador.
        if self.is_superuser:
            self.rol = self.Rol.ADMIN
        super().save(*args, **kwargs)

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN

    @property
    def es_desarrollador(self):
        """El desarrollador principal (superusuario) ve y administra todas las fincas."""
        return self.is_superuser


class ActividadAdministrativa(models.Model):
    """Bitácora de operaciones sobre cuentas (RNF-09)."""

    class Accion(models.TextChoices):
        CREAR = "CREAR", "Crear cuenta"
        ACTUALIZAR = "ACTUALIZAR", "Actualizar cuenta"
        DESACTIVAR = "DESACTIVAR", "Desactivar cuenta"
        REACTIVAR = "REACTIVAR", "Reactivar cuenta"

    administrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actividad_realizada",
    )
    usuario_objetivo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actividad_recibida",
    )
    accion = models.CharField(max_length=12, choices=Accion.choices)
    detalle = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "actividad_administrativa"
        ordering = ["-creado_en"]
        verbose_name = "actividad administrativa"
        verbose_name_plural = "actividad administrativa"

    def __str__(self):
        return f"{self.get_accion_display()} · {self.creado_en:%Y-%m-%d %H:%M}"


class SolicitudClave(models.Model):
    """Pedido de nueva contraseña hecho desde la pantalla de ingreso (RF-03, RF-04).

    Solo se guarda para cuentas existentes y activas; la respuesta al visitante es
    siempre la misma, para no revelar qué usuarios existen. No guarda contraseñas.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitudes_clave"
    )
    contacto = models.CharField("cómo contactarlo", max_length=200, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    atendida_en = models.DateTimeField(null=True, blank=True)
    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_clave_atendidas",
    )

    class Meta:
        db_table = "solicitudes_clave"
        ordering = ["creado_en"]
        verbose_name = "solicitud de contraseña"
        verbose_name_plural = "solicitudes de contraseña"

    @property
    def pendiente(self):
        return self.atendida_en is None

    def __str__(self):
        return f"Solicitud de {self.usuario} · {self.creado_en:%Y-%m-%d %H:%M}"
