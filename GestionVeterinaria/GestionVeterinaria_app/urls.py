from django.urls import path, include
from GestionVeterinaria_app import views
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('home')), 
    path('home/', views.home, name='home'),
    path('contacto/', views.contacto, name='contacto'),
    path('nosotros/', views.nosotros, name='nosotros'),
    path('login/', views.login_view, name='login'),
    path('nuevopaciente/', views.nuevo_paciente, name='nuevo_paciente'),
    path('nuevopropietario/', views.nuevo_propietario, name='nuevo_propietario'),
    path('nuevacita/', views.nueva_cita, name='nueva_cita'),
    path('historialmedico/', views.historial_medico, name='historialmedico'),
    path("estadisticas/", views.estadisticas_view, name="estadisticas"),
    path("cita/<int:cita_id>/atender/", views.atender_cita, name="atender_cita"),
    path('buscarpaciente/', views.buscar_paciente, name='buscar_paciente'),
    path('editarpaciente/<int:paciente_id>/', views.editar_paciente, name='editar_paciente'),
    path('buscarpropietario/', views.buscar_propietario, name='buscar_propietario'),
    path('editarpropietario/<int:propietario_id>/', views.editar_propietario, name='editar_propietario'),
    path('logout/', views.logout_view, name='logout'),
    path('api/slots/', views.api_slots, name='api_slots'),
    path("cita/<int:cita_id>/editar/", views.editar_cita, name="editar_cita"),
    path("cita/<int:cita_id>/cancelar/", views.cancelar_cita, name="cancelar_cita"),

    # Redirección según rol
    path('redir/', views.role_redirect_view, name='role-redirect'),

    # Agenda global (solo administrativo)
    path('citas/', views.citas_list, name='citas_list'),

    # Agenda del veterinario logueado
    path('mis-citas/', views.mis_citas, name='mis_citas'),
]