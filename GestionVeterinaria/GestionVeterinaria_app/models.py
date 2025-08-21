from django.db import models
from django.conf import settings
from django.utils import timezone

class Paciente(models.Model):
    SEXO_CHOICES = [
        ('M', 'Macho'),
        ('H', 'Hembra'),
    ]

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    especie = models.CharField(max_length=50)
    raza = models.CharField(max_length=50, blank=True, null=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    fecha_nacimiento = models.DateField()
    informacion_medica = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    propietario = models.ForeignKey(
        'Propietario',
        on_delete=models.CASCADE,
        related_name='pacientes'
    )

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        permissions = [
            ("view_health_stats", "Puede ver estadísticas de salud"),
            ("export_reports", "Puede exportar reportes"),
        ]
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def __str__(self):
        return f"{self.nombre} ({self.especie})"


class Propietario(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=20)
    email = models.EmailField(unique=True)

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        verbose_name = "Propietario"
        verbose_name_plural = "Propietarios"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class HistorialMedico(models.Model):
    fecha_consulta = models.DateTimeField()
    diagnostico = models.TextField()
    tratamiento = models.TextField()
    nota_veterinaria = models.TextField(blank=True, null=True)
    paciente = models.ForeignKey(
        'Paciente',
        on_delete=models.CASCADE,
        related_name='historial_medico'
    )
    cita = models.OneToOneField('Cita', on_delete=models.CASCADE, related_name='atencion', null=True, blank=True)
    
    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        verbose_name = "Historial médico"
        verbose_name_plural = "Historiales médicos"

    def __str__(self):
        return f"Consulta de {self.paciente.nombre} - {self.fecha_consulta.strftime('%Y-%m-%d')}"


class Veterinario(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=200)
    rol = models.ForeignKey('Rol', on_delete=models.CASCADE, related_name='veterinarios')

    # nuevo: vínculo 1 a 1 con el usuario del sistema
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='perfil_veterinario',
        null=True,
        blank=True,
        help_text="Usuario del sistema asociado a este veterinario (opcional)."
    )

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        verbose_name = "Veterinario"
        verbose_name_plural = "Veterinarios"

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.especialidad}"


class Administrativo(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    rol = models.ForeignKey('Rol', on_delete=models.CASCADE, related_name='personal_administrativo')
    contacto = models.CharField(max_length=150)  # Puede incluir teléfono, correo o ambos

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        verbose_name = "Administrativo"
        verbose_name_plural = "Administrativos"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Cita(models.Model):
    ESTADO_CHOICES = [
        ('programada', 'Programada'),
        ('atendida', 'Atendida'),
        ('cancelada', 'Cancelada'),
    ]

    fecha_hora = models.DateTimeField()
    veterinario = models.ForeignKey('Veterinario', on_delete=models.CASCADE, related_name='citas')
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, related_name='citas')
    administrativo = models.ForeignKey('Administrativo', on_delete=models.CASCADE, related_name='citas')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='programada')

    def __str__(self):
        return f"Cita el {self.fecha_hora} - Veterinario: {self.veterinario.nombre} {self.veterinario.apellido}"






class Rol(models.Model):
    descripcion = models.CharField(max_length=100, unique=True)

    class Meta:
        default_permissions = ("add", "change", "delete", "view")
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.descripcion