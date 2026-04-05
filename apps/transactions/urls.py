from django.urls import path
from . import views

urlpatterns = [
    # Existants
    path('',                         views.historique,                  name='historique'),
    path('virement/',                views.virement,                    name='virement'),

    # Annulation
    path('annuler/<int:transaction_id>/', views.annuler_virement,       name='annuler_virement'),

    # Plafond
    path('plafond/<int:compte_id>/', views.modifier_plafond,            name='modifier_plafond'),

    # Récurrents
    path('recurrents/',              views.virements_recurrents,         name='virements_recurrents'),
    path('recurrents/creer/',        views.creer_virement_recurrent,     name='creer_virement_recurrent'),
    path('recurrents/<int:recurrent_id>/toggle/', views.toggle_virement_recurrent, name='toggle_virement_recurrent'),
    path('recurrents/<int:recurrent_id>/supprimer/', views.supprimer_virement_recurrent, name='supprimer_virement_recurrent'),
]