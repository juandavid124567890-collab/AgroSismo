from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect


class FincaActivaMiddleware:
    """Si desactivan la finca, sus usuarios quedan fuera aunque tengan la sesión abierta.

    El desarrollador (superusuario) nunca queda bloqueado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            usuario is not None
            and usuario.is_authenticated
            and not usuario.is_superuser
            and usuario.finca_id
            and not usuario.finca.activa
        ):
            if request.path.startswith("/api/"):
                return JsonResponse({"detalle": "La finca está desactivada."}, status=403)
            logout(request)
            return redirect("login")
        return self.get_response(request)
