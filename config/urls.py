from django.contrib import admin
from django.urls import path, include
from django.views.defaults import page_not_found, server_error # pour les tests d'erreurs 404 et 500

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('comptes/', include('apps.comptes.urls')),
    path('transactions/', include('apps.transactions.urls')),
    path('journal/', include('apps.journal.urls')),

    # test erreurs 404 et 500
    path('test-404/', lambda r: page_not_found(r, None)),
    path('test-500/', lambda r: server_error(r)),
]
