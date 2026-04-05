from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from .models import JournalConnexion, TentativeConnexion


def _get_ip(request):
    """Récupère l'adresse IP réelle du visiteur."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _alerter_connexions_multiples(user, ip):
    """
    Vérifie si l'utilisateur s'est connecté plusieurs fois
    en peu de temps et envoie un mail d'alerte si c'est le cas.
    Seuil : 2 connexions réussies ou plus dans les 10 dernières minutes.
    """
    fenetre = timezone.now() - timedelta(minutes=10)
    nb = JournalConnexion.objects.filter(
        utilisateur=user,
        succes=True,
        date_connexion__gte=fenetre,
    ).count()

    if nb >= 2:
        try:
            send_mail(
                subject='Connexion suspecte détectée - Imara Banque',
                message=(
                    f"Bonjour {user.get_full_name() or user.username},\n\n"
                    f"Nous avons détecté {nb + 1} connexions à votre compte "
                    f"en moins de 10 minutes.\n\n"
                    f"Détails de la dernière connexion :\n"
                    f"  • Adresse IP : {ip}\n"
                    f"  • Date       : {timezone.now().strftime('%d/%m/%Y à %H:%M:%S')}\n\n"
                    f"Si vous êtes à l'origine de toutes ces connexions, "
                    f"vous pouvez ignorer ce message.\n\n"
                    f"Dans le cas contraire, nous vous recommandons de :\n"
                    f"  1. Changer immédiatement votre mot de passe\n"
                    f"  2. Contacter votre conseiller bancaire\n\n"
                    f"Cordialement,\n"
                    f"L'équipe Imara Banque\n"
                    f"──────────────────────────────\n"
                    f"Ce message est envoyé automatiquement, merci de ne pas y répondre."
                ),
                from_email='noreply@imarabanque.com',
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 1 : Saisie du nom d'utilisateur
# ─────────────────────────────────────────────────────────────────────

def etape1_username(request):
    erreur = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        ip       = _get_ip(request)

        if User.objects.filter(username=username).exists():
            tentative = TentativeConnexion.verifier_ou_creer(username, ip)

            if tentative.est_bloque:
                request.session['bloque_username'] = username
                request.session['bloque_secondes'] = tentative.temps_restant
                return redirect('compte_bloque')

            request.session['username_temp'] = username
            return redirect('etape2_password')

        else:
            erreur = "Ce nom d'utilisateur n'existe pas."

    return render(request, 'accounts/step1_username.html', {'erreur': erreur})


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 2 : Saisie du mot de passe
# ─────────────────────────────────────────────────────────────────────

def etape2_password(request):
    username = request.session.get('username_temp')
    if not username:
        return redirect('etape1_username')

    ip        = _get_ip(request)
    tentative = TentativeConnexion.verifier_ou_creer(username, ip)

    if tentative.est_bloque:
        request.session['bloque_username'] = username
        request.session['bloque_secondes'] = tentative.temps_restant
        return redirect('compte_bloque')

    erreur               = None
    tentatives_restantes = TentativeConnexion.MAX_TENTATIVES - tentative.tentatives

    if request.method == 'POST':
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)

        if user is not None:
            # ── Connexion réussie ────────────────────────────────────
            login(request, user)

            # Enregistrer la connexion AVANT de vérifier les multiples
            # (pour que le comptage inclue celle-ci)
            JournalConnexion.objects.create(utilisateur=user, adresse_ip=ip, succes=True)

            # Vérifier connexions multiples et alerter si besoin
            _alerter_connexions_multiples(user, ip)

            tentative.reinitialiser()
            del request.session['username_temp']
            return redirect('dashboard')

        else:
            # ── Échec ────────────────────────────────────────────────
            user_obj = User.objects.get(username=username)
            JournalConnexion.objects.create(utilisateur=user_obj, adresse_ip=ip, succes=False)
            tentative.enregistrer_echec()

            if tentative.est_bloque:
                request.session['bloque_username'] = username
                request.session['bloque_secondes'] = tentative.temps_restant
                return redirect('compte_bloque')

            tentatives_restantes = TentativeConnexion.MAX_TENTATIVES - tentative.tentatives
            if tentatives_restantes == 1:
                erreur = "Mot de passe incorrect. Attention : il ne vous reste plus qu'une seule tentative avant le blocage temporaire."
            else:
                erreur = f"Mot de passe incorrect. Il vous reste {tentatives_restantes} tentative(s)."

    return render(request, 'accounts/step2_password.html', {
        'username'            : username,
        'erreur'              : erreur,
        'tentatives_restantes': tentatives_restantes,
    })


# ─────────────────────────────────────────────────────────────────────
# PAGE DE BLOCAGE
# ─────────────────────────────────────────────────────────────────────

def compte_bloque(request):
    username = request.session.get('bloque_username', '')
    secondes = request.session.get('bloque_secondes', 900)

    ip = _get_ip(request)
    if username:
        try:
            tentative = TentativeConnexion.objects.get(username=username, adresse_ip=ip)
            if not tentative.est_bloque:
                return redirect('etape1_username')
            secondes = tentative.temps_restant
        except TentativeConnexion.DoesNotExist:
            pass

    return render(request, 'accounts/compte_bloque.html', {
        'username': username,
        'secondes': secondes,
    })


# ─────────────────────────────────────────────────────────────────────
# DÉCONNEXION
# ─────────────────────────────────────────────────────────────────────

def deconnexion(request):
    logout(request)
    return redirect('etape1_username')





# ─────────────────────────────────────────────────────────────────────
# VUE REFRESH SESSION
# ─────────────────────────────────────────────────────────────────────

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

@login_required
@require_POST
def refresh_session(request):
    """
    Appelée en AJAX par le popup d'inactivité.
    Modifie la session pour forcer Django à la prolonger.
    """
    request.session.modified = True
    return JsonResponse({'status': 'ok'})





