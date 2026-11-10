from .alcance import unidades_de
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .divipola import DEPARTAMENTOS
from .models import Cultivo, UnidadAgricola


class UnidadForm(forms.ModelForm):
    """Registro y edición de una unidad agrícola (RF-05, RF-06).

    Obligatorios: nombre, área, departamento y municipio.
    Opcionales: vereda y coordenadas.
    El municipio se elige de la lista oficial del departamento (DIVIPOLA).
    """

    departamento = forms.ChoiceField(
        label="Departamento",
        choices=[],
        error_messages={"required": "Elige el departamento."},
    )
    municipio = forms.CharField(
        label="Municipio",
        widget=forms.Select(choices=[]),
        error_messages={"required": "Elige el municipio."},
    )
    latitud = forms.DecimalField(
        required=False,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        max_digits=9,
        decimal_places=6,
        label="Latitud",
        help_text="Solo si conoces el punto exacto. Ejemplo: 2.441900",
    )
    longitud = forms.DecimalField(
        required=False,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
        max_digits=9,
        decimal_places=6,
        label="Longitud",
        help_text="Ejemplo: -76.606100 (en Colombia suele ser negativa).",
    )

    class Meta:
        model = UnidadAgricola
        fields = ["nombre", "area_ha", "departamento", "municipio", "vereda", "latitud", "longitud"]
        labels = {
            "nombre": "Nombre de la unidad",
            "vereda": "Vereda o sector",
            "area_ha": "Área (hectáreas)",
        }
        help_texts = {
            "nombre": "Cómo la reconoces. Ejemplo: Finca El Roble.",
            "area_ha": "Tamaño total del terreno. 1 hectárea = 10.000 m².",
            "vereda": "Si quieres, escribe la vereda donde queda.",
        }

    def __init__(self, *args, propietario, **kwargs):
        super().__init__(*args, **kwargs)
        self.propietario = propietario
        # Datos antiguos (texto libre) que no están en la lista se conservan al editar.
        guardado = (self.instance.departamento, self.instance.municipio) if self.instance.pk else ("", "")
        actual = self.data.get("departamento") if self.is_bound else guardado[0]

        deptos = list(DEPARTAMENTOS)
        if guardado[0] and guardado[0] not in deptos:
            deptos.append(guardado[0])
        self.fields["departamento"].choices = [("", "Selecciona un departamento")] + [(d, d) for d in deptos]

        municipios = list(DEPARTAMENTOS.get(actual, []))
        if guardado[1] and actual == guardado[0] and guardado[1] not in municipios:
            municipios.append(guardado[1])
        primero = "Selecciona un municipio" if municipios else "Primero elige el departamento"
        self.fields["municipio"].widget.choices = [("", primero)] + [(m, m) for m in municipios]

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetidas = unidades_de(self.propietario).filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise ValidationError("Ya hay una unidad con ese nombre en tu finca.")
        return nombre

    def clean(self):
        datos = super().clean()
        depto, mun = datos.get("departamento"), datos.get("municipio")
        if depto and mun:
            guardado = (self.instance.departamento, self.instance.municipio) if self.instance.pk else None
            if (depto, mun) != guardado and mun not in DEPARTAMENTOS.get(depto, []):
                self.add_error("municipio", f"Elige un municipio de la lista que pertenezca a {depto}.")
        return datos


class CultivoForm(forms.ModelForm):
    """Registro y edición de un cultivo de una unidad (RF-07)."""

    class Meta:
        model = Cultivo
        fields = ["tipo", "area_ha", "activo"]
        labels = {
            "tipo": "Tipo de cultivo",
            "area_ha": "Área sembrada (hectáreas)",
            "activo": "Cultivo activo",
        }
        widgets = {"tipo": forms.TextInput(attrs={"list": "tipos-cultivo"})}

    def __init__(self, *args, unidad, **kwargs):
        super().__init__(*args, **kwargs)
        self.unidad = unidad

    def clean_tipo(self):
        return self.cleaned_data["tipo"].strip()

    def clean_area_ha(self):
        area = self.cleaned_data.get("area_ha")
        if area is None:
            return area
        if area <= 0:
            raise ValidationError("El área debe ser mayor que 0.")
        if area > self.unidad.area_ha:
            raise ValidationError(
                f"El área no puede superar el área de la unidad ({self.unidad.area_ha} ha)."
            )
        return area
