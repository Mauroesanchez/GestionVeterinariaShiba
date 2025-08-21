# GestionVeterinaria_app/management/commands/init_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

def add_perm(group: Group, codename: str):
    try:
        perm = Permission.objects.get(codename=codename)
        group.permissions.add(perm)
    except Permission.DoesNotExist:
        pass

class Command(BaseCommand):
    help = "Crea grupos base (veterinario, administrativo) y asigna permisos"

    def handle(self, *args, **options):
        vet_group, _ = Group.objects.get_or_create(name="veterinario")
        adm_group, _ = Group.objects.get_or_create(name="administrativo")

        modelos = ["paciente", "cita", "propietario", "historialmedico"]
        bases = ["add_", "change_", "delete_", "view_"]
        for m in modelos:
            for b in bases:
                add_perm(vet_group, f"{b}{m}")
                add_perm(adm_group, f"{b}{m}")

        # Permisos custom (definidos en models.py)
        add_perm(vet_group, "view_health_stats")
        add_perm(adm_group, "view_health_stats")
        add_perm(adm_group, "export_reports")
        add_perm(adm_group, "manage_all_appointments")

        self.stdout.write(self.style.SUCCESS("Grupos y permisos inicializados."))
