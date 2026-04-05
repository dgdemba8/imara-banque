from django.urls import path
from . import views

urlpatterns = [
    path('',                            views.solde,      name='solde'),
    path('releve/<int:compte_id>/pdf/', views.releve_pdf, name='releve_pdf'),
    path('releve/pdf/',                 views.releve_pdf, name='releve_pdf_tous'),
    path('releve/tous/pdf/', views.releve_pdf_tous, name='releve_pdf_tous'), #au cas ou
]


