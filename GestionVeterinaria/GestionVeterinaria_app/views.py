from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Min       
from django.db.models.functions import ExtractHour  
from django.db.models import Q
from .forms import *
from .models import Paciente, Cita, Propietario, Veterinario
from django.urls import reverse
from datetime import datetime, time, timedelta
from django.utils import timezone


def home(request):
    return render(request, 'GestionVeterinaria_app/home.html')


def contacto(request):
    return render(request, 'GestionVeterinaria_app/contacto.html')


def nosotros(request):
    return render(request, 'GestionVeterinaria_app/nosotros.html')


@csrf_protect
def login_view(request):
    if request.method == "POST":
        u = request.POST.get("username", "").strip()
        p = request.POST.get("password", "")
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            return redirect('role-redirect')   # decide destino según rol
        messages.error(request, "Usuario o contraseña inválidos.")
    return render(request, "GestionVeterinaria_app/login.html")


def nuevo_paciente(request):
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('nuevo_paciente')
        else:
            # Mostrar errores en el mismo template
            return render(request, 'GestionVeterinaria_app/nuevopaciente.html', {'form': form})
    else:
        form = PacienteForm()
    return render(request, 'GestionVeterinaria_app/nuevopaciente.html', {'form': form})


def nuevo_propietario(request):
    if request.method == 'POST':
        form = PropietarioForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('nuevo_propietario')
    else:
        form = PropietarioForm()
    return render(request, 'GestionVeterinaria_app/nuevopropietario.html', {'form': form})


def nueva_cita(request):
    if request.method == 'POST':
        form = CitaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('nueva_cita')  # redirige por nombre de URL
    else:
        form = CitaForm()
    return render(request, 'GestionVeterinaria_app/nuevacita.html', {'form': form})


def historial_medico(request):
    paciente_id = request.GET.get('paciente')
    paciente = None
    historial_medico = []

    if paciente_id:
        paciente = get_object_or_404(Paciente, id=paciente_id)
        historial_medico = paciente.historial_medico.all()

    return render(request, 'GestionVeterinaria_app/historialmedico.html', {
        'pacientes': Paciente.objects.all(),
        'paciente': paciente,
        'historial_medico': historial_medico,
    })


@login_required
def role_redirect_view(request):
    u = request.user
    if u.groups.filter(name="administrativo").exists():
        return redirect('citas_list')   # agenda global (admin)
    if u.groups.filter(name="veterinario").exists():
        return redirect('mis_citas')    # agenda del vet
    return redirect('home')            


# ------------------------------
# Función auxiliar para alertas
# ------------------------------
def _split_hoy_maniana(qs):
    """
    Marca las citas de hoy y mañana y devuelve info para resaltarlas/contarlas.
    """
    now_local = timezone.localtime(timezone.now())
    hoy = now_local.date()
    maniana = hoy + timezone.timedelta(days=1)

    hoy_ids, maniana_ids = [], []
    for c in qs:
        d = timezone.localtime(c.fecha_hora).date()
        if d == hoy:
            hoy_ids.append(c.id)
        elif d == maniana:
            maniana_ids.append(c.id)

    return {
        "hoy_ids": hoy_ids,
        "maniana_ids": maniana_ids,
        "count_hoy": len(hoy_ids),
        "count_maniana": len(maniana_ids),
        "count_total": len(hoy_ids) + len(maniana_ids),
    }


@login_required
def citas_list(request):
    if not request.user.groups.filter(name="administrativo").exists():
        return redirect('mis_citas') 
    citas = Cita.objects.all().select_related('paciente', 'veterinario')
    alerts = _split_hoy_maniana(citas)
    return render(
        request,
        "GestionVeterinaria_app/citas_list.html",
        {"citas": citas, **alerts}
    )


@login_required
def mis_citas(request):
    """
    Muestra las citas del veterinario asociado al usuario logueado.
    Requiere que el modelo Veterinario tenga OneToOne con User usando related_name='perfil_veterinario'.
    """
    vet = getattr(request.user, 'perfil_veterinario', None)
    if vet is not None:
        citas = Cita.objects.select_related('paciente', 'veterinario').filter(veterinario=vet)
    else:
        citas = []  # usuario sin perfil de veterinario vinculado
    alerts = _split_hoy_maniana(citas)
    return render(
        request,
        "GestionVeterinaria_app/mis_citas.html",
        {"citas": citas, **alerts}
    )



@login_required
def estadisticas_view(request):
    """
    Estadísticas de los últimos 60 días:
    - Pacientes nuevos (si hay Paciente.created_at, lo usa; si no, calcula por primera cita)
    - Citas por veterinario
    - Especies más atendidas (pacientes únicos)
    - Top propietarios por cantidad de pacientes atendidos (únicos)
    - Horarios pico (citas por hora 0-23)
    """
    ahora = timezone.localtime(timezone.now())
    desde = ahora - timezone.timedelta(days=60)

    # Base: citas en los últimos 60 días
    citas_60d = (
        Cita.objects
        .select_related("veterinario", "paciente", "paciente__propietario")
        .filter(fecha_hora__gte=desde, fecha_hora__lte=ahora)
    )

    # Total de citas en la ventana (para mostrar en tarjeta)
    total_citas_60d = citas_60d.count()

    # ---------- Pacientes nuevos (últimos 60 días) ----------
    usar_created = hasattr(Paciente, "created_at")
    if usar_created:
        pacientes_nuevos_60d = Paciente.objects.filter(created_at__gte=desde).count()
    else:
        # Fallback: primera cita dentro de la ventana
        primeras = (
            Cita.objects.values("paciente_id")
            .annotate(primer_turno=Min("fecha_hora"))
            .filter(primer_turno__gte=desde, primer_turno__lte=ahora)
            .count()
        )
        pacientes_nuevos_60d = primeras

    # ---------- Citas por veterinario (conteo) ----------
    citas_por_vet = (
        citas_60d
        .values("veterinario__nombre", "veterinario__apellido")
        .annotate(total=Count("id"))
        .order_by("-total", "veterinario__apellido", "veterinario__nombre")
    )
    citas_por_vet_list = [{
        "veterinario": f"{x['veterinario__nombre']} {x['veterinario__apellido']}",
        "total": x["total"]
    } for x in citas_por_vet]

    # ---------- Especies más atendidas (pacientes únicos) ----------
    especies = (
        citas_60d
        .values("paciente__especie")
        .annotate(pacientes_unicos=Count("paciente_id", distinct=True))
        .order_by("-pacientes_unicos")[:10]
    )

    # ---------- Top propietarios (por pacientes únicos atendidos) ----------
    top_propietarios = (
        citas_60d
        .values("paciente__propietario__nombre", "paciente__propietario__apellido")
        .annotate(pacientes_atendidos=Count("paciente_id", distinct=True))
        .order_by("-pacientes_atendidos", "paciente__propietario__apellido")[:10]
    )
    top_propietarios_list = [{
        "propietario": f"{x['paciente__propietario__nombre']} {x['paciente__propietario__apellido']}",
        "pacientes_atendidos": x["pacientes_atendidos"]
    } for x in top_propietarios]

    # ---------- Horarios pico ----------
    horarios = (
        citas_60d
        .annotate(hora=ExtractHour("fecha_hora"))
        .values("hora")
        .annotate(total=Count("id"))
        .order_by("hora")
    )
    mapa_horas = {h["hora"]: h["total"] for h in horarios}
    horarios_list = [{"hora": h, "total": mapa_horas.get(h, 0)} for h in range(9, 19)]

    context = {
        "desde": desde,
        "hasta": ahora,
        "pacientes_nuevos_60d": pacientes_nuevos_60d,
        "total_citas_60d": total_citas_60d,             
        "citas_por_vet": citas_por_vet_list,
        "especies": especies,
        "top_propietarios": top_propietarios_list,
        "horarios": horarios_list,
    }
    return render(request, "GestionVeterinaria_app/estadisticas.html", context)


def _puede_gestionar_cita(user, cita):
    # Admins pueden todo; vet solo sus propias
    if user.groups.filter(name="administrativo").exists():
        return True
    vet = getattr(user, 'perfil_veterinario', None)
    return vet is not None and cita.veterinario_id == vet.id

@login_required
def editar_cita(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id)
    if not _puede_gestionar_cita(request.user, cita):
        return HttpResponseForbidden("No tenés permisos para editar esta cita.")

    if request.method == "POST":
        form = CitaForm(request.POST, instance=cita)
        if form.is_valid():
            form.save()
            messages.success(request, "La cita se actualizó correctamente.")
            # redirigir según rol
            if request.user.groups.filter(name="administrativo").exists():
                return redirect('citas_list')
            return redirect('mis_citas')
    else:
        form = CitaForm(instance=cita)

    return render(request, "GestionVeterinaria_app/editar_cita.html", {"form": form, "cita": cita})

@login_required
def cancelar_cita(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id)
    if not _puede_gestionar_cita(request.user, cita):
        return HttpResponseForbidden("No tenés permisos para cancelar esta cita.")

    if request.method == "POST":
        cita.estado = 'cancelada'
        cita.save()
        messages.success(request, "La cita fue cancelada. El horario quedó disponible.")
        if request.user.groups.filter(name="administrativo").exists():
            return redirect('citas_list')
        return redirect('mis_citas')

    # Confirmación
    return render(request, "GestionVeterinaria_app/cancelar_cita_confirm.html", {"cita": cita})

# Si tenés la vista atender_cita, marcá la cita como atendida al guardar la atención:
@login_required
def atender_cita(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id)
    if not _puede_gestionar_cita(request.user, cita):
        return HttpResponseForbidden("No tenés permisos para atender esta cita.")

    if request.method == "POST":
        form = HistorialAtencionForm(request.POST)  # el que ya usás
        if form.is_valid():
            atencion = form.save(commit=False)
            atencion.cita = cita
            atencion.paciente = cita.paciente
            atencion.save()

            # marcar cita atendida
            cita.estado = 'atendida'
            cita.save()

            messages.success(request, "Atención registrada y cita marcada como atendida.")
            if request.user.groups.filter(name="administrativo").exists():
                return redirect('citas_list')
            return redirect('mis_citas')
    else:
        form = HistorialAtencionForm()

    return render(request, "GestionVeterinaria_app/atender_cita.html", {"form": form, "cita": cita})





@login_required
def buscar_paciente(request):
    """
    Búsqueda simple por nombre, apellido, especie, raza, o datos del propietario.
    Si hay resultados, se muestran con botón Editar.
    """
    q = request.GET.get("q", "").strip()
    resultados = []
    if q:
        resultados = (
            Paciente.objects.select_related("propietario")
            .filter(
                Q(nombre__icontains=q) |
                Q(apellido__icontains=q) |
                Q(especie__icontains=q) |
                Q(raza__icontains=q) |
                Q(propietario__nombre__icontains=q) |
                Q(propietario__apellido__icontains=q) |
                Q(propietario__email__icontains=q) |
                Q(propietario__telefono__icontains=q)
            )
            .order_by("apellido", "nombre")[:100]
        )

    return render(
        request,
        "GestionVeterinaria_app/buscar_paciente.html",
        {"q": q, "resultados": resultados},
    )


@login_required
def editar_paciente(request, paciente_id):
    """
    Edición de un paciente existente usando PacienteForm.
    """
    paciente = get_object_or_404(Paciente.objects.select_related("propietario"), pk=paciente_id)

    if request.method == "POST":
        form = PacienteForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, "Paciente actualizado correctamente.")
            # Si querés volver a la búsqueda con el nombre del paciente:
            return redirect(f"{reverse('buscar_paciente')}?q={paciente.nombre}")
    else:
        form = PacienteForm(instance=paciente)

    return render(
        request,
        "GestionVeterinaria_app/editar_paciente.html",
        {"form": form, "paciente": paciente},
    )



@login_required
def buscar_propietario(request):
    query = request.GET.get("q", "").strip()
    propietarios = Propietario.objects.all()
    if query:
        from django.db.models import Q
        propietarios = propietarios.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(email__icontains=query) |
            Q(telefono__icontains=query) |
            Q(direccion__icontains=query)
        ).order_by("apellido", "nombre")[:200]

    return render(request, "GestionVeterinaria_app/buscar_propietario.html",  # ← ruta corregida
                  {"q": query, "propietarios": propietarios})


@login_required
def editar_propietario(request, propietario_id):
    propietario = get_object_or_404(Propietario, id=propietario_id)
    if request.method == "POST":
        form = PropietarioForm(request.POST, instance=propietario)
        if form.is_valid():
            form.save()
            messages.success(request, "Propietario actualizado correctamente.")
            return redirect("buscar_propietario")
    else:
        form = PropietarioForm(instance=propietario)

    return render(request, "GestionVeterinaria_app/editar_propietario.html",  # ← ruta corregida
                  {"form": form, "propietario": propietario})



@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')



def api_slots(request):
    """
    GET /api/slots/?vet_id=ID&fecha=YYYY-MM-DD
    Devuelve: { "slots": ["09:00","09:30", ...] }
    """
    vet_id = request.GET.get("vet_id")
    fecha_str = request.GET.get("fecha")

    if not vet_id or not fecha_str:
        return JsonResponse({"slots": []})

    vet = Veterinario.objects.filter(pk=vet_id).first()
    if not vet:
        return JsonResponse({"slots": []})

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []})

    # turnos ocupados del vet en esa fecha
    desde = datetime.combine(fecha, time(0, 0))
    hasta = datetime.combine(fecha, time(23, 59))
    if timezone.is_naive(desde):
        desde = timezone.make_aware(desde, timezone.get_current_timezone())
        hasta = timezone.make_aware(hasta, timezone.get_current_timezone())

    ocupadas = (
        Cita.objects.filter(veterinario=vet, fecha_hora__range=(desde, hasta))
        .values_list("fecha_hora", flat=True)
    )
    ocupados_set = set([timezone.localtime(dt).strftime("%H:%M") for dt in ocupadas])

    slots = generar_slots(fecha, ocupados_set)
    return JsonResponse({"slots": slots})