from django import forms
from .models import *
from datetime import timedelta, time, datetime
from django.utils import timezone


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ['nombre', 'apellido', 'especie', 'raza', 'sexo', 'fecha_nacimiento', 'informacion_medica', 'propietario']
    
    propietario = forms.ModelChoiceField(queryset=Propietario.objects.all(), empty_label="Seleccione un propietario", required=True)

class PropietarioForm(forms.ModelForm):
    class Meta:
        model = Propietario
        fields = ['nombre', 'apellido', 'direccion', 'telefono', 'email']

JORNADA_INICIO = time(9, 0)
JORNADA_FIN = time(18, 0)
INTERVALO_MIN = 30

def generar_slots(fecha, ocupados_set):
    """
    Genera lista de strings 'HH:MM' cada 30' entre 09:00 y 18:00, 
    excluyendo los que ya están ocupados (conjunto de strings 'HH:MM').
    """
    slots = []
    dt = datetime.combine(fecha, JORNADA_INICIO)
    fin = datetime.combine(fecha, JORNADA_FIN)
    while dt <= fin - timedelta(minutes=INTERVALO_MIN):
        s = dt.strftime("%H:%M")
        if s not in ocupados_set:
            slots.append(s)
        dt += timedelta(minutes=INTERVALO_MIN)
    return slots


class CitaForm(forms.ModelForm):
    # Campos visibles
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=True,
    )
    hora_slot = forms.ChoiceField(
        label="Horario disponible",
        choices=[],
        required=True,
    )

    # Dropdowns
    veterinario = forms.ModelChoiceField(
        queryset=Veterinario.objects.all(),
        empty_label="Seleccione un Veterinario",
        required=True,
    )
    paciente = forms.ModelChoiceField(
        queryset=Paciente.objects.all(),
        empty_label="Seleccione un Paciente",
        required=True,
    )
    administrativo = forms.ModelChoiceField(
        queryset=Administrativo.objects.all(),
        empty_label="Seleccione un Administrativo",
        required=True,
    )

    # El DateTime final (se arma en clean)
    fecha_hora = forms.DateTimeField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Cita
        fields = ["fecha_hora", "veterinario", "paciente", "administrativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        vet = None
        fecha_sel = None

        # Desde initial (cuando abrís el form)
        initial = kwargs.get("initial") or {}
        vet = initial.get("veterinario") or vet
        fecha_sel = initial.get("fecha") or fecha_sel

        # Si es POST, priorizamos lo que viene del form
        if self.is_bound:
            try:
                vet_id = int(self.data.get("veterinario") or 0)
                vet = Veterinario.objects.filter(id=vet_id).first() or vet
            except (TypeError, ValueError):
                pass

            fecha_str = self.data.get("fecha")
            if fecha_str:
                try:
                    fecha_sel = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                except ValueError:
                    fecha_sel = None

        # Si es edición (instance) y no vino nada arriba
        if (not vet or not fecha_sel) and self.instance and self.instance.pk:
            vet = vet or self.instance.veterinario
            fecha_sel = fecha_sel or timezone.localtime(self.instance.fecha_hora).date()

        # Cargar choices de horas
        if vet and fecha_sel:
            # ventana del día
            desde = datetime.combine(fecha_sel, time(0, 0))
            hasta = datetime.combine(fecha_sel, time(23, 59))
            if timezone.is_naive(desde):
                tz = timezone.get_current_timezone()
                desde = timezone.make_aware(desde, tz)
                hasta = timezone.make_aware(hasta, tz)

            # Turnos ocupados SOLO de citas programadas
            ocupadas = (
                Cita.objects.filter(
                    veterinario=vet,
                    estado="programada",
                    fecha_hora__range=(desde, hasta),
                )
                .values_list("fecha_hora", flat=True)
            )
            ocupados_set = {timezone.localtime(dt).strftime("%H:%M") for dt in ocupadas}

            disponibles = generar_slots(fecha_sel, ocupados_set)
            self.fields["hora_slot"].choices = [("", "Seleccione un horario")] + [(h, h) for h in disponibles]

            # Si estamos editando, preseleccionar el horario actual si aplica
            if self.instance and self.instance.pk:
                actual_hhmm = timezone.localtime(self.instance.fecha_hora).strftime("%H:%M")
                # Si el actual estaba ocupado "por nosotros", igual mostrémoslo
                if (actual_hhmm not in [c[0] for c in self.fields["hora_slot"].choices]):
                    self.fields["hora_slot"].choices.append((actual_hhmm, actual_hhmm))
                self.fields["hora_slot"].initial = actual_hhmm
                self.fields["fecha"].initial = fecha_sel
                self.fields["veterinario"].initial = vet
        else:
            self.fields["hora_slot"].choices = [("", "Seleccione un horario")]

    def clean(self):
        cleaned = super().clean()

        fecha = cleaned.get("fecha")
        slot = cleaned.get("hora_slot")
        vet = cleaned.get("veterinario")

        if not fecha or not slot or not vet:
            # faltan datos básicos
            return cleaned

        # Parsear HH:MM
        try:
            hh, mm = map(int, slot.split(":"))
        except Exception:
            raise ValidationError("Horario inválido.")

        # Validar rango laboral (inicio <= hora < fin, en pasos de 30')
        inicio_dt = datetime.combine(fecha, JORNADA_INICIO)
        fin_dt = datetime.combine(fecha, JORNADA_FIN) - timedelta(minutes=INTERVALO_MIN)
        dt_local = datetime.combine(fecha, time(hh, mm))

        if dt_local < inicio_dt or dt_local > fin_dt:
            raise ValidationError("Horario fuera de la jornada laboral (09:00–18:00).")

        # Asegurar tz-aware
        if timezone.is_naive(dt_local):
            dt_local = timezone.make_aware(dt_local, timezone.get_current_timezone())

        # Chequear conflicto: solo citas programadas, y excluirse si es edición
        qs = Cita.objects.filter(
            veterinario=vet,
            fecha_hora=dt_local,
            estado="programada",
        )
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Ese horario ya está ocupado para el veterinario seleccionado.")

        cleaned["fecha_hora"] = dt_local
        return cleaned



class HistorialAtencionForm(forms.ModelForm):
    class Meta:
        model = HistorialMedico
        fields = ["diagnostico", "tratamiento", "nota_veterinaria"]
        widgets = {
            "diagnostico": forms.Textarea(attrs={"rows": 3}),
            "tratamiento": forms.Textarea(attrs={"rows": 3}),
            "nota_veterinaria": forms.Textarea(attrs={"rows": 3}),
        }
