from django.utils import timezone
from .models import Cita

def alertas_hoy_maniana(request):
    if not request.user.is_authenticated:
        return {"glob_count_hoy": 0, "glob_count_maniana": 0, "glob_count_total": 0}

    now_local = timezone.localtime(timezone.now())
    hoy = now_local.date()
    maniana = hoy + timezone.timedelta(days=1)

    # Base queryset según rol
    qs = Cita.objects.select_related("veterinario", "paciente")
    if request.user.groups.filter(name="veterinario").exists():
        vet = getattr(request.user, 'perfil_veterinario', None)
        qs = qs.filter(veterinario=vet) if vet else qs.none()
    elif request.user.groups.filter(name="administrativo").exists():
        pass  # ve todas
    else:
        qs = qs.none()

    # Contadores
    dts = [timezone.localtime(c.fecha_hora).date() for c in qs]
    cnt_hoy = sum(1 for d in dts if d == hoy)
    cnt_man = sum(1 for d in dts if d == maniana)

    return {
        "glob_count_hoy": cnt_hoy,
        "glob_count_maniana": cnt_man,
        "glob_count_total": cnt_hoy + cnt_man,
    }
