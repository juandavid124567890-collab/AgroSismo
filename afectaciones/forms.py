from agro.alcance import unidades_de
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from agro.models import Cultivo, UnidadAgricola

from .models import Afectacion, EventoSismico, Evidencia, Perdida


class EventoForm(forms.ModelForm):
    """Registro manual de un sismo sobre una unidad agrícola (RF-08, RF-09)."""

    magnitud = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_value=Decimal("10"),
        max_digits=3,
        decimal_places=1,
        label="Magnitud (ML)",
        help_text="Opcional. Si no la conoces, déjala vacía.",
    )

    class Meta:
        model = EventoSismico
        fields = ["unidad", "fecha_hora", "magnitud", "epicentro", "observaciones"]
        labels = {
            "unidad": "Unidad agrícola",
            "fecha_hora": "Fecha y hora del sismo",
            "epicentro": "Epicentro o referencia",
            "observaciones": "Observaciones",
        }
        widgets = {
            "fecha_hora": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidad"].queryset = unidades_de(usuario)
        self.fields["unidad"].empty_label = "Selecciona una unidad"
        self.fields["fecha_hora"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]


class AfectacionForm(forms.ModelForm):
    """Daño causado por un sismo, con una pérdida estimada opcional (RF-10, RF-11, RF-13)."""

    latitud = forms.DecimalField(
        required=False,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        max_digits=9,
        decimal_places=6,
        label="Latitud",
    )
    longitud = forms.DecimalField(
        required=False,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
        max_digits=9,
        decimal_places=6,
        label="Longitud",
    )
    perdida_cantidad = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        label="Producción perdida estimada",
    )
    perdida_unidad = forms.ChoiceField(
        required=False,
        choices=Perdida.UnidadMedida.choices,
        initial=Perdida.UnidadMedida.KG,
        label="Unidad de medida",
    )
    perdida_valor = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        label="Valor económico estimado (COP)",
        help_text="Es una estimación tuya, no una valoración técnica oficial.",
        widget=forms.NumberInput(attrs={"data-miles": "cop", "inputmode": "numeric"}),
    )

    class Meta:
        model = Afectacion
        fields = [
            "cultivo",
            "elemento",
            "tipo_dano",
            "tipo_dano_otro",
            "severidad",
            "area_afectada_ha",
            "ubicacion_texto",
            "latitud",
            "longitud",
            "observaciones",
        ]
        labels = {
            "cultivo": "Cultivo afectado",
            "elemento": "Elemento afectado",
            "tipo_dano": "Tipo de daño",
            "tipo_dano_otro": "¿Cuál otro daño?",
            "severidad": "Nivel de severidad",
            "area_afectada_ha": "Área afectada (hectáreas)",
            "ubicacion_texto": "Referencia de ubicación",
            "observaciones": "Observaciones",
        }
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 4}),
            "tipo_dano_otro": forms.TextInput(
                attrs={"maxlength": 100, "placeholder": "Ej: Pérdida de suelo fértil"}
            ),
        }

    def __init__(self, *args, evento, **kwargs):
        super().__init__(*args, **kwargs)
        self.evento = evento
        self.fields["cultivo"].queryset = Cultivo.objects.filter(unidad=evento.unidad)
        self.fields["cultivo"].empty_label = "Sin cultivo específico"
        # El UUID se asigna al crear el objeto, así que "nuevo" se reconoce por su estado.
        if not self.instance._state.adding:
            perdida = self.instance.perdidas.first()
            if perdida:
                self.initial["perdida_cantidad"] = perdida.cantidad
                self.initial["perdida_unidad"] = perdida.unidad_medida
                self.initial["perdida_valor"] = perdida.valor_estimado_cop

    def guardar_perdida(self, afectacion):
        """Crea, actualiza o elimina la pérdida estimada según lo escrito en el formulario."""
        cantidad = self.cleaned_data.get("perdida_cantidad")
        valor = self.cleaned_data.get("perdida_valor")
        perdida = afectacion.perdidas.first()
        if cantidad is None and valor is None:
            if perdida:
                perdida.delete()
            return
        if perdida is None:
            perdida = Perdida(afectacion=afectacion)
        perdida.cultivo = afectacion.cultivo
        perdida.cantidad = cantidad if cantidad is not None else Decimal("0")
        perdida.unidad_medida = self.cleaned_data.get("perdida_unidad") or Perdida.UnidadMedida.KG
        perdida.valor_estimado_cop = valor if valor is not None else Decimal("0")
        perdida.sincronizado_en = timezone.now()
        perdida.save()


class EvidenciaForm(forms.ModelForm):
    """Fotografía asociada a una afectación (RF-12)."""

    class Meta:
        model = Evidencia
        fields = ["imagen", "descripcion"]
        labels = {"imagen": "Fotografía", "descripcion": "Descripción (opcional)"}
        help_texts = {"imagen": "Formatos JPG, PNG o WEBP. Máximo 5 MB."}
        widgets = {"imagen": forms.ClearableFileInput(attrs={"accept": "image/*"})}


class HistorialFiltroForm(forms.Form):
    """Filtros del historial por fecha, unidad y severidad (RF-16)."""

    desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    unidad = forms.ModelChoiceField(
        queryset=UnidadAgricola.objects.none(),
        required=False,
        label="Unidad agrícola",
        empty_label="Todas",
    )
    severidad = forms.ChoiceField(
        required=False,
        label="Severidad",
        choices=[("", "Todas")] + list(Afectacion.Severidad.choices),
    )

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidad"].queryset = unidades_de(usuario)

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if desde and hasta and desde > hasta:
            raise ValidationError("La fecha inicial no puede ser posterior a la fecha final.")
        return datos
