from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.accounts.models import JournalConnexion


# Create your views here.
@login_required
def journal(request):
    connexions = JournalConnexion.objects.filter(utilisateur=request.user)
    return render(request, 'journal/journal.html', {'connexions': connexions})


