from agro.alcance import q_unidades, unidades_de
from datetime import timedelta

import secrets
from urllib.parse import quote
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.templatetags.static import static
from django.views.generic import TemplateView
from django.utils import timezone

from afectaciones.estadisticas import resumen as resumen_estadistico
from afectaciones.models import Afectacion, EventoSismico
from agro.models import UnidadAgricola

from django.db.models import Count

from .ayuda import secciones_para
from .fincas import eliminar_finca, resumen_de_finca
from .forms import ConfirmarEliminarFincaForm, FincaForm, FormaIngreso, RecuperarClaveForm, UsuarioCrearForm, UsuarioEditarForm
from .models import ActividadAdministrativa, Finca, SolicitudClave


WHATSAPP_URL = "https://wa.me/573122971645?text=" + quote(
    "Hola, me interesa usar AgroSismo en mi finca."
)


AYUDA_WHATSAPP_URL = "https://wa.me/573122971645?text=" + quote("Hola, necesito ayuda con AgroSismo.")


def ayuda(request):
    """Preguntas frecuentes y soluciones; pública, con secciones según el rol."""
    return render(request, "ayuda.html", {
        "secciones": secciones_para(request.user),
        "whatsapp_url": AYUDA_WHATSAPP_URL,
    })


def manual(request):
    """Descarga el manual de usuario en PDF (público)."""
    from django.http import FileResponse, Http404
    from django.conf import settings
    ruta = settings.BASE_DIR / "static" / "manual" / "Manual-AgroSismo.pdf"
    if not ruta.exists():
        raise Http404("Manual no disponible")
    return FileResponse(open(ruta, "rb"), as_attachment=True, filename="Manual-AgroSismo.pdf", content_type="application/pdf")


def landing(request):
    """Contenido público, sin iniciar sesión (RF-01)."""
    if request.user.is_authenticated:
        return redirect("inicio")
    return render(request, "landing.html", {"whatsapp_url": WHATSAPP_URL})


class IngresoView(LoginView):
    """Inicio de sesión con nombre de usuario y contraseña (RF-03)."""

    template_name = "accounts/login.html"
    authentication_form = FormaIngreso
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        if self.request.POST.get("recordarme"):
            self.request.session.set_expiry(60 * 60 * 24 * 30)  # 30 días
        else:
            self.request.session.set_expiry(0)  # se cierra al cerrar el navegador
        return respuesta


def manifest(request):
    """Datos para instalar AgroSismo como aplicación en el celular."""
    datos = {
        "name": "AgroSismo",
        "short_name": "AgroSismo",
        "description": "Registro de afectaciones sísmicas en el sector agrícola",
        "lang": "es-CO",
        "id": "/inicio/",
        "start_url": "/inicio/",
        "orientation": "any",
        "categories": ["productivity", "utilities"],
        "shortcuts": [
            {"name": "Registro rápido", "short_name": "Rápido", "url": "/registro-rapido/",
             "icons": [{"src": static("pwa/icono-192.png") + "?v=2", "sizes": "192x192", "type": "image/png"}]},
            {"name": "Registrar sismo", "short_name": "Sismo", "url": "/eventos/nuevo/",
             "icons": [{"src": static("pwa/icono-192.png") + "?v=2", "sizes": "192x192", "type": "image/png"}]},
        ],
        "scope": "/",
        "display": "standalone",
        "background_color": "#f7faf7",
        "theme_color": "#2f6f3e",
        "icons": [
            {"src": static("pwa/icono-192.png") + "?v=2", "sizes": "192x192", "type": "image/png"},
            {"src": static("pwa/icono-512.png") + "?v=2", "sizes": "512x512", "type": "image/png"},
            {"src": static("pwa/icono-maskable-512.png") + "?v=2", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(datos, content_type="application/manifest+json")


class ServiceWorkerView(TemplateView):
    """El service worker debe servirse desde la raíz para controlar todo el sitio."""

    template_name = "pwa/sw.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **kwargs):
        r = super().render_to_response(context, **kwargs)
        r["Service-Worker-Allowed"] = "/"
        r["Cache-Control"] = "no-cache"
        return r


@login_required
def inicio(request):
    """Resumen del productor: ve los datos de su finca y nada de otras fincas (RNF-04)."""
    usuario = request.user
    hace_30_dias = timezone.now() - timedelta(days=30)
    eventos = EventoSismico.objects.filter(q_unidades(usuario, "unidad__"))
    contexto = {
        "total_unidades": unidades_de(usuario).count(),
        "eventos_recientes": eventos.filter(fecha_hora__gte=hace_30_dias).count(),
        "total_afectaciones": Afectacion.objects.filter(q_unidades(usuario, "unidad__")).count(),
        "ultimo_evento": eventos.select_related("unidad").first(),
    }
    hechos = [
        contexto["total_unidades"] > 0,
        contexto["ultimo_evento"] is not None,
        contexto["total_afectaciones"] > 0,
    ]
    contexto["paso_unidad"], contexto["paso_sismo"], contexto["paso_afectacion"] = hechos
    contexto["est"] = resumen_estadistico(usuario, request.GET.get("periodo", "6"))
    contexto["pasos_hechos"] = sum(hechos)
    contexto["pasos_porcentaje"] = round(sum(hechos) * 100 / 3)
    if usuario.es_admin:
        contexto["solicitudes_pendientes"] = SolicitudClave.objects.filter(
            atendida_en__isnull=True, usuario__in=usuarios_a_cargo(usuario)
        ).count()
    return render(request, "panel/inicio.html", contexto)


# ---------------------------------------------------------------------------
# Gestión de cuentas por el administrador (RF-02, RF-04, RNF-09)
# ---------------------------------------------------------------------------
Usuario = get_user_model()
ALFABETO_CLAVE = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def solo_admin(vista):
    """Solo administradores: los demás reciben 403 (y sin sesión van al login)."""
    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if not request.user.es_admin:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


def solo_desarrollador(vista):
    """Solo el desarrollador (superusuario): los demás reciben 403."""
    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if not request.user.es_desarrollador:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


def usuarios_a_cargo(admin):
    """Cuentas que este administrador puede ver y gestionar.

    El desarrollador ve todas. El administrador de una finca ve solo a la gente de su
    finca y nunca al desarrollador. Un administrador sin finca solo ve cuentas sin finca.
    """
    if admin.es_desarrollador:
        return Usuario.objects.all()
    if admin.finca_id:
        return Usuario.objects.filter(finca_id=admin.finca_id, is_superuser=False)
    return Usuario.objects.filter(finca__isnull=True, is_superuser=False)


def generar_clave(largo=10):
    return "".join(secrets.choice(ALFABETO_CLAVE) for _ in range(largo))


def _bitacora(admin, objetivo, accion, detalle=""):
    ActividadAdministrativa.objects.create(
        administrador=admin, usuario_objetivo=objetivo, accion=accion, detalle=detalle
    )


def _mostrar_clave(request, usuario, clave):
    """La contraseña se muestra una sola vez; no se guarda en ningún otro lugar."""
    messages.add_message(
        request, messages.SUCCESS,
        f"Contraseña de «{usuario.username}»: {clave} — cópiala ahora, no se volverá a mostrar.",
        extra_tags="clave",
    )


def _cerrar_solicitudes(usuario, admin):
    SolicitudClave.objects.filter(usuario=usuario, atendida_en__isnull=True).update(
        atendida_en=timezone.now(), atendida_por=admin
    )


@solo_admin
def usuarios_lista(request):
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    base = usuarios_a_cargo(request.user)
    resumen = {
        "total": base.count(),
        "activos": base.filter(is_active=True).count(),
        "inactivos": base.filter(is_active=False).count(),
    }
    usuarios = base.select_related("finca").order_by("-date_joined")
    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if estado == "activos":
        usuarios = usuarios.filter(is_active=True)
    elif estado == "inactivos":
        usuarios = usuarios.filter(is_active=False)
    pagina = Paginator(usuarios, 15).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    solicitudes = SolicitudClave.objects.filter(
        atendida_en__isnull=True, usuario__in=base
    ).select_related("usuario")
    return render(request, "accounts/usuarios_lista.html", {
        "pagina": pagina, "q": q, "estado": estado, "resumen": resumen,
        "solicitudes": solicitudes,
        "querystring": parametros.urlencode(),
    })


@solo_admin
def usuario_crear(request):
    inicial = {}
    if request.user.es_desarrollador and request.method != "POST":
        inicial = {k: v for k, v in (("finca", request.GET.get("finca")), ("rol", request.GET.get("rol"))) if v}
    form = UsuarioCrearForm(request.POST or None, creador=request.user, initial=inicial)
    if request.method == "POST" and form.is_valid():
        usuario = form.save(commit=False)
        if not request.user.es_desarrollador:
            usuario.finca = request.user.finca
        clave = form.cleaned_data["clave"] or generar_clave()
        usuario.set_password(clave)
        usuario.save()
        _bitacora(request.user, usuario, ActividadAdministrativa.Accion.CREAR,
                  f"Rol: {usuario.get_rol_display()}")
        messages.success(request, f"Cuenta «{usuario.username}» creada.")
        _mostrar_clave(request, usuario, clave)
        return redirect("usuarios")
    return render(request, "agro/formulario.html", {
        "form": form, "titulo": "Nueva cuenta", "volver": reverse("usuarios"),
    })


@solo_admin
def usuario_editar(request, pk):
    usuario = get_object_or_404(usuarios_a_cargo(request.user), pk=pk)
    form = UsuarioEditarForm(request.POST or None, instance=usuario, editor=request.user)
    if request.method == "POST" and form.is_valid():
        cambios = ", ".join(form.changed_data)
        form.save()
        _bitacora(request.user, usuario, ActividadAdministrativa.Accion.ACTUALIZAR,
                  f"Campos: {cambios}" if cambios else "Sin cambios")
        messages.success(request, f"Cuenta «{usuario.username}» actualizada.")
        return redirect("usuarios")
    return render(request, "agro/formulario.html", {
        "form": form, "titulo": f"Editar cuenta · {usuario.username}", "volver": reverse("usuarios"),
    })


@solo_admin
@require_POST
def usuario_estado(request, pk):
    usuario = get_object_or_404(usuarios_a_cargo(request.user), pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return redirect("usuarios")
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    if usuario.is_active:
        _bitacora(request.user, usuario, ActividadAdministrativa.Accion.REACTIVAR)
        messages.success(request, f"Cuenta «{usuario.username}» reactivada.")
    else:
        _bitacora(request.user, usuario, ActividadAdministrativa.Accion.DESACTIVAR)
        messages.success(request, f"Cuenta «{usuario.username}» desactivada. Sus datos se conservan.")
    return redirect("usuarios")


@solo_admin
@require_POST
def usuario_clave(request, pk):
    usuario = get_object_or_404(usuarios_a_cargo(request.user), pk=pk)
    clave = generar_clave()
    usuario.set_password(clave)
    usuario.save(update_fields=["password"])
    _bitacora(request.user, usuario, ActividadAdministrativa.Accion.ACTUALIZAR, "Contraseña restablecida")
    _cerrar_solicitudes(usuario, request.user)
    _mostrar_clave(request, usuario, clave)
    return redirect("usuarios")


# ---------------------------------------------------------------------------
# Fincas: solo el desarrollador las crea
# ---------------------------------------------------------------------------
@solo_desarrollador
def fincas_lista(request):
    fincas = Finca.objects.annotate(
        num_usuarios=Count("miembros", distinct=True), num_unidades=Count("unidades", distinct=True)
    )
    return render(request, "accounts/fincas_lista.html", {"fincas": fincas})


@solo_desarrollador
def finca_crear(request):
    form = FincaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        finca = form.save()
        messages.success(request, f"Finca «{finca.nombre}» creada. Ahora crea a su administrador.")
        return redirect(f"{reverse('usuario_crear')}?finca={finca.pk}&rol=ADMIN")
    return render(request, "agro/formulario.html", {
        "form": form, "titulo": "Nueva finca", "volver": reverse("fincas"),
    })


@solo_desarrollador
def finca_detalle(request, pk):
    finca = get_object_or_404(Finca, pk=pk)
    miembros = Usuario.objects.filter(finca=finca).order_by("-is_active", "rol", "username")
    return render(request, "accounts/finca_detalle.html", {
        "finca": finca, "miembros": miembros, "datos": resumen_de_finca(finca),
    })


@solo_desarrollador
@require_POST
def finca_estado(request, pk):
    """Desactivar una finca deja sin acceso a todos sus usuarios; sus datos se conservan."""
    finca = get_object_or_404(Finca, pk=pk)
    finca.activa = not finca.activa
    finca.save(update_fields=["activa"])
    if finca.activa:
        _bitacora(request.user, None, ActividadAdministrativa.Accion.REACTIVAR, f"Finca «{finca.nombre}» reactivada")
        messages.success(request, f"Finca «{finca.nombre}» activada. Sus usuarios ya pueden ingresar.")
    else:
        _bitacora(request.user, None, ActividadAdministrativa.Accion.DESACTIVAR, f"Finca «{finca.nombre}» desactivada")
        messages.success(request, f"Finca «{finca.nombre}» desactivada. Sus usuarios ya no pueden ingresar y sus datos se conservan.")
    return redirect("finca_detalle", pk=finca.pk)


@solo_desarrollador
def finca_eliminar(request, pk):
    finca = get_object_or_404(Finca, pk=pk)
    form = ConfirmarEliminarFincaForm(request.POST or None, finca=finca)
    if request.method == "POST" and form.is_valid():
        nombre = finca.nombre
        resumen = resumen_de_finca(finca)
        eliminar_finca(finca)
        _bitacora(
            request.user, None, ActividadAdministrativa.Accion.DESACTIVAR,
            f"Finca «{nombre}» eliminada con {resumen['usuarios']} usuarios, {resumen['unidades']} unidades, "
            f"{resumen['sismos']} sismos y {resumen['afectaciones']} afectaciones",
        )
        messages.success(request, f"Finca «{nombre}» eliminada con todos sus datos.")
        return redirect("fincas")
    return render(request, "accounts/finca_eliminar.html", {
        "finca": finca, "form": form, "datos": resumen_de_finca(finca),
    })


@solo_desarrollador
def finca_editar(request, pk):
    finca = get_object_or_404(Finca, pk=pk)
    form = FincaForm(request.POST or None, instance=finca)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Nombre de la finca actualizado.")
        return redirect("fincas")
    return render(request, "agro/formulario.html", {
        "form": form, "titulo": f"Editar finca · {finca.nombre}", "volver": reverse("fincas"),
    })


@solo_admin
def actividad_lista(request):
    registros = ActividadAdministrativa.objects.select_related("administrador", "usuario_objetivo")
    if not request.user.es_desarrollador:
        registros = registros.filter(usuario_objetivo__in=usuarios_a_cargo(request.user))
    pagina = Paginator(registros, 25).get_page(request.GET.get("page"))
    return render(request, "accounts/actividad.html", {"pagina": pagina})


@solo_admin
@require_POST
def solicitud_descartar(request, pk):
    solicitud = get_object_or_404(
        SolicitudClave, pk=pk, atendida_en__isnull=True, usuario__in=usuarios_a_cargo(request.user)
    )
    _cerrar_solicitudes(solicitud.usuario, request.user)
    _bitacora(request.user, solicitud.usuario, ActividadAdministrativa.Accion.ACTUALIZAR,
              "Solicitud de contraseña descartada")
    messages.success(request, "Solicitud descartada.")
    return redirect("usuarios")


# ---------------------------------------------------------------------------
# Recuperar contraseña (visitante sin sesión)
# ---------------------------------------------------------------------------
MAX_SOLICITUDES_POR_HORA = 5


def _permitido_solicitar(request):
    """Límite sencillo por dirección IP para evitar abusos del formulario."""
    clave = f"recuperar:{request.META.get('REMOTE_ADDR', '')}"
    n = cache.get(clave, 0)
    if n >= MAX_SOLICITUDES_POR_HORA:
        return False
    cache.set(clave, n + 1, 3600)
    return True


def recuperar_clave(request):
    form = RecuperarClaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _permitido_solicitar(request):
            usuario = Usuario.objects.filter(
                username__iexact=form.cleaned_data["username"].strip(), is_active=True
            ).first()
            if usuario and not usuario.solicitudes_clave.filter(atendida_en__isnull=True).exists():
                SolicitudClave.objects.create(usuario=usuario, contacto=form.cleaned_data["contacto"].strip())
        # Misma respuesta exista o no la cuenta: no se revela qué usuarios existen.
        return redirect("recuperar_enviada")
    return render(request, "accounts/recuperar.html", {"form": form})


def recuperar_enviada(request):
    return render(request, "accounts/recuperar_enviada.html")
