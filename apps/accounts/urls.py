from django.urls import path
from . import views

urlpatterns = [
    path('',          views.etape1_username, name='etape1_username'),
    path('password/', views.etape2_password, name='etape2_password'),
    path('bloque/',   views.compte_bloque,   name='compte_bloque'),
    path('deconnexion/', views.deconnexion,  name='deconnexion'),
    path('refresh-session/', views.refresh_session, name='refresh_session'),
]
