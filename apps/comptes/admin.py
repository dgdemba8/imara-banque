from django.contrib import admin
from .models import Compte

# Register your models here.
@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = ['numero_compte', 'utilisateur', 'type_compte', 'solde', 'actif']
    list_filter = ['type_compte', 'actif']
    search_fields = ['numero_compte', 'utilisateur__username']


