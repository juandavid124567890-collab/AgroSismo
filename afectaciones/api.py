"""Puntos de acceso JSON para el modo sin conexión."""
import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import sync


def _solo_autenticados(vista):
    """Responde 401 en JSON (no redirige al login) para que el cliente sepa qué hacer."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sesión no iniciada."}, status=401)
        return vista(request, *args, **kwargs)
    return envoltura


@_solo_autenticados
@require_GET
@never_cache
@ensure_csrf_cookie
def datos_base(request):
    return JsonResponse(sync.datos_base(request.user))


@_solo_autenticados
@require_POST
def sincronizar(request):
    try:
        datos = json.loads(request.body or b"{}")
        if not isinstance(datos, dict):
            raise ValueError
        resultados = sync.procesar_lote(request.user, datos)
    except OverflowError:
        return JsonResponse({"error": "El lote es demasiado grande."}, status=413)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Formato de lote inválido."}, status=400)
    return JsonResponse({"resultados": resultados})


@_solo_autenticados
@require_POST
def subir_foto(request):
    return JsonResponse(sync.guardar_foto(request.user, request.POST, request.FILES))
