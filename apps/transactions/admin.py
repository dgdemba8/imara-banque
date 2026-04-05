from django.contrib import admin
from .models import Transaction

# Register your models here.
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['type_transaction', 'montant', 'compte_source', 'compte_destination', 'date_transaction', 'statut']
    list_filter = ['type_transaction', 'statut']

