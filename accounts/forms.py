from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Finca

Usuario = get_user_model()


def _campo_finca(form, quien):
    """Solo el desarrollador elige la finca; el administrador de finca no la ve."""
    if quien is not None and quien.es_desarrollador:
        form.fields["finca"].required = False
        form.fields["finca"].empty_label = "Sin finca"
        form.fields["finca"].queryset = Finca.objects.order_by("nombre")
        form.fields["finca"].label = "Finca"
    else:
        del form.fields["finca"]


class FormaIngreso(AuthenticationForm):
    """Ingreso normal, pero bloquea a quienes pertenecen a una finca desactivada."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser and user.finca_id and not user.finca.activa:
            raise ValidationError(
                "Tu finca está desactivada. Escríbenos por WhatsApp para volver a activarla.",
                code="finca_inactiva",
            )


class ConfirmarEliminarFincaForm(forms.Form):
    """Para eliminar una finca hay que escribir su nombre exacto."""

    confirmacion = forms.CharField(label="Escribe el nombre de la finca para confirmar")

    def __init__(self, *args, finca, **kwargs):
        super().__init__(*args, **kwargs)
        self.finca = finca

    def clean_confirmacion(self):
        texto = self.cleaned_data["confirmacion"].strip()
        if texto != self.finca.nombre:
            raise ValidationError("No coincide con el nombre de la finca.")
        return texto


class FincaForm(forms.ModelForm):
    """Alta y edición de fincas. Solo el desarrollador la usa."""

    class Meta:
        model = Finca
        fields = ["nombre"]
        labels = {"nombre": "Nombre de la finca"}
        help_texts = {"nombre": "Ejemplo: Finca La Esperanza. No se puede repetir."}

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetidas = Finca.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise ValidationError("Ya existe una finca con ese nombre.")
        return nombre


class UsuarioCrearForm(forms.ModelForm):
    """Alta de cuenta por el administrador (RF-02).

    Si no se escribe contraseña, el sistema genera una que se muestra una sola vez.
    """

    clave = forms.CharField(
        label="Contraseña inicial",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "data-medidor-clave": "1"}),
        help_text="Déjala vacía y AgroSismo generará una segura que podrás copiar.",
    )

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "telefono", "rol", "finca"]
        labels = {"username": "Nombre de usuario", "first_name": "Nombres", "last_name": "Apellidos",
                  "email": "Correo electrónico", "telefono": "Teléfono", "rol": "Rol"}
        help_texts = {"username": "Solo letras, números y los signos @ . + - _ (sin espacios)."}

    def __init__(self, *args, creador=None, **kwargs):
        super().__init__(*args, **kwargs)
        _campo_finca(self, creador)
        self.fields["first_name"].required = True
        self.fields["username"].widget.attrs.update({"autocapitalize": "none", "autocomplete": "off"})

    def clean_clave(self):
        clave = self.cleaned_data.get("clave", "")
        if clave:
            try:
                validate_password(clave, Usuario(username=self.cleaned_data.get("username", "")))
            except ValidationError as e:
                raise ValidationError(e.messages)
        return clave


class UsuarioEditarForm(forms.ModelForm):
    """Edición de datos de una cuenta (RF-04). La contraseña se restablece aparte."""

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "telefono", "rol", "finca"]
        labels = {"first_name": "Nombres", "last_name": "Apellidos",
                  "email": "Correo electrónico", "telefono": "Teléfono", "rol": "Rol"}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        _campo_finca(self, editor)
        self.fields["first_name"].required = True
        if editor is not None and self.instance.pk == editor.pk:
            # Un administrador no puede quitarse a sí mismo el rol (evita quedarse sin acceso).
            self.fields["rol"].disabled = True
            self.fields["rol"].help_text = "No puedes cambiar tu propio rol."


class RecuperarClaveForm(forms.Form):
    username = forms.CharField(
        label="Nombre de usuario", max_length=150,
        widget=forms.TextInput(attrs={"autocapitalize": "none", "autocomplete": "username", "autofocus": True}),
    )
    contacto = forms.CharField(
        label="¿Cómo te podemos contactar? (opcional)", max_length=200, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Teléfono o correo"}),
    )
