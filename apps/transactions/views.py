from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.comptes.models import Compte
from .models import Transaction, VirementRecurrent
from decimal import Decimal, InvalidOperation


# ──────────────────────────────────────────────
# SEUIL EMAIL VIREMENT
# ──────────────────────────────────────────────

SEUIL_EMAIL_VIREMENT = 200_000  # FCFA


def _envoyer_email_virement(user, transaction):
    """
    Envoie un email de confirmation si le montant dépasse le seuil.
    Appelée juste après Transaction.objects.create(...).
    """
    from django.core.mail import send_mail

    if transaction.montant < SEUIL_EMAIL_VIREMENT:
        return

    dest_numero = (
        transaction.compte_destination.numero_compte
        if transaction.compte_destination else "—"
    )
    montant_fmt = f"{transaction.montant:,.0f}".replace(',', ' ')

    try:
        send_mail(
            subject=f'Virement de {montant_fmt} FCFA confirme - Imara Banque',
            message=(
                f"Bonjour {user.get_full_name() or user.username},\n\n"
                f"Votre virement a ete execute avec succes.\n\n"
                f"  - Montant        : {montant_fmt} FCFA\n"
                f"  - Compte source  : {transaction.compte_source.numero_compte}\n"
                f"  - Destinataire   : {dest_numero}\n"
                f"  - Motif          : {transaction.motif or '-'}\n"
                f"  - Date           : {timezone.now().strftime('%d/%m/%Y a %H:%M:%S')}\n\n"
                f"Si vous n'etes pas a l'origine de cette operation, "
                f"contactez immediatement votre conseiller bancaire.\n\n"
                f"Cordialement,\n"
                f"L'equipe Imara Banque\n"
                f"---\n"
                f"Ce message est envoye automatiquement, merci de ne pas y repondre."
            ),
            from_email='noreply@imarabanque.com',
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


# ──────────────────────────────────────────────
# HISTORIQUE
# ──────────────────────────────────────────────

@login_required
def historique(request):
    comptes = Compte.objects.filter(utilisateur=request.user, actif=True)

    # ── Récupération des filtres GET ──────────────────────────────
    filtre_compte = request.GET.get('compte', '')
    filtre_type   = request.GET.get('type', '')
    filtre_debut  = request.GET.get('date_debut', '')
    filtre_fin    = request.GET.get('date_fin', '')

    # ── Base queryset ─────────────────────────────────────────────
    transactions = (
        Transaction.objects.filter(compte_source__in=comptes) |
        Transaction.objects.filter(compte_destination__in=comptes)
    ).order_by('-date_transaction')

    # ── Application des filtres ───────────────────────────────────
    if filtre_compte:
        try:
            compte_filtre = Compte.objects.get(id=filtre_compte, utilisateur=request.user)
            transactions = transactions.filter(
                compte_source=compte_filtre
            ) | transactions.filter(
                compte_destination=compte_filtre
            )
            transactions = transactions.order_by('-date_transaction')
        except Compte.DoesNotExist:
            pass

    if filtre_type:
        transactions = transactions.filter(type_transaction=filtre_type)

    if filtre_debut:
        try:
            from datetime import datetime
            debut = datetime.strptime(filtre_debut, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__gte=debut)
        except ValueError:
            pass

    if filtre_fin:
        try:
            from datetime import datetime
            fin = datetime.strptime(filtre_fin, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__lte=fin)
        except ValueError:
            pass

    # ── Enrichissement pour annulation ────────────────────────────
    for t in transactions:
        t.peut_annuler = t.annulable and t.compte_source in comptes

    return render(request, 'transactions/historique.html', {
        'transactions' : transactions,
        'comptes'      : comptes,
        'filtre_compte': filtre_compte,
        'filtre_type'  : filtre_type,
        'filtre_debut' : filtre_debut,
        'filtre_fin'   : filtre_fin,
        'nb_resultats' : transactions.count(),
    })

# ──────────────────────────────────────────────
# VIREMENT
# ──────────────────────────────────────────────

@login_required
def virement(request):
    comptes = Compte.objects.filter(utilisateur=request.user, actif=True)

    if request.method == 'POST':
        compte_source_id   = request.POST.get('compte_source')
        numero_destination = request.POST.get('numero_destination', '').strip()
        montant_raw        = request.POST.get('montant', '').strip()
        motif              = request.POST.get('motif', '').strip()

        try:
            compte_source      = Compte.objects.get(id=compte_source_id, utilisateur=request.user)
            compte_destination = Compte.objects.get(numero_compte=numero_destination)
            montant            = Decimal(montant_raw)
        except Compte.DoesNotExist:
            messages.error(request, "Compte introuvable.")
            return render(request, 'transactions/virement.html', {'comptes': comptes})
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant invalide.")
            return render(request, 'transactions/virement.html', {'comptes': comptes})

        if compte_source == compte_destination:
            messages.error(request, "Vous ne pouvez pas virer vers le même compte.")
        elif montant <= 0:
            messages.error(request, "Le montant doit être supérieur à 0.")
        elif compte_source.solde < montant:
            messages.error(request, "Solde insuffisant.")
        else:
            ok, msg_plafond = compte_source.peut_virer(montant)
            if not ok:
                messages.error(request, msg_plafond)
            else:
                # Exécution du virement
                compte_source.solde      -= montant
                compte_destination.solde += montant
                compte_source.save()
                compte_destination.save()

                # ── Créer la transaction ──────────────────────────
                transaction = Transaction.objects.create(
                    compte_source=compte_source,
                    compte_destination=compte_destination,
                    type_transaction='virement',
                    montant=montant,
                    motif=motif,
                    statut=True,
                )

                # ── Email si montant ≥ 200 000 FCFA ──────────────
                _envoyer_email_virement(request.user, transaction)

                messages.success(
                    request,
                    f"Virement de {montant:,.0f} FCFA effectué. "
                    f"Vous avez 5 minutes pour l'annuler depuis l'historique."
                )
                return redirect('historique')

    return render(request, 'transactions/virement.html', {'comptes': comptes})


# ──────────────────────────────────────────────
# ANNULATION DE VIREMENT (fenêtre 5 min)
# ──────────────────────────────────────────────

@login_required
def annuler_virement(request, transaction_id):
    transaction = get_object_or_404(
        Transaction,
        id=transaction_id,
        compte_source__utilisateur=request.user,
        type_transaction='virement',
    )

    if not transaction.annulable:
        messages.error(request, "Ce virement ne peut plus être annulé (délai de 5 minutes dépassé).")
        return redirect('historique')

    if request.method == 'POST':
        transaction.compte_source.solde      += transaction.montant
        transaction.compte_destination.solde -= transaction.montant
        transaction.compte_source.save()
        transaction.compte_destination.save()

        transaction.annule          = True
        transaction.statut          = False
        transaction.date_annulation = timezone.now()
        transaction.save()

        messages.success(request, f"Virement de {transaction.montant:,.0f} FCFA annulé avec succès.")
        return redirect('historique')

    return render(request, 'transactions/confirmer_annulation.html', {
        'transaction': transaction,
    })


# ──────────────────────────────────────────────
# PLAFOND DE VIREMENT
# ──────────────────────────────────────────────

@login_required
def modifier_plafond(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, utilisateur=request.user, actif=True)

    if request.method == 'POST':
        valeur = request.POST.get('plafond', '').strip()
        if valeur == '':
            compte.plafond_virement = None
            compte.save()
            messages.success(request, "Plafond supprimé — aucune limite journalière.")
        else:
            try:
                plafond = Decimal(valeur)
                if plafond <= 0:
                    raise ValueError
                compte.plafond_virement = plafond
                compte.save()
                messages.success(request, f"Plafond journalier fixé à {plafond:,.0f} FCFA.")
            except (InvalidOperation, ValueError):
                messages.error(request, "Valeur invalide pour le plafond.")
        return redirect('solde')

    return render(request, 'transactions/modifier_plafond.html', {'compte': compte})


# ──────────────────────────────────────────────
# VIREMENTS RÉCURRENTS
# ──────────────────────────────────────────────

@login_required
def virements_recurrents(request):
    comptes    = Compte.objects.filter(utilisateur=request.user, actif=True)
    recurrents = VirementRecurrent.objects.filter(utilisateur=request.user).order_by('prochaine_execution')

    return render(request, 'transactions/virements_recurrents.html', {
        'comptes':    comptes,
        'recurrents': recurrents,
    })


@login_required
def creer_virement_recurrent(request):
    comptes = Compte.objects.filter(utilisateur=request.user, actif=True)

    if request.method == 'POST':
        compte_source_id   = request.POST.get('compte_source')
        numero_destination = request.POST.get('numero_destination', '').strip()
        montant_raw        = request.POST.get('montant', '').strip()
        motif              = request.POST.get('motif', '').strip()
        frequence          = request.POST.get('frequence', 'mensuel')
        date_debut_raw     = request.POST.get('date_debut')
        date_fin_raw       = request.POST.get('date_fin', '').strip()

        try:
            from datetime import date
            compte_source      = Compte.objects.get(id=compte_source_id, utilisateur=request.user)
            compte_destination = Compte.objects.get(numero_compte=numero_destination)
            montant            = Decimal(montant_raw)
            date_debut         = date.fromisoformat(date_debut_raw)
            date_fin           = date.fromisoformat(date_fin_raw) if date_fin_raw else None
        except Compte.DoesNotExist:
            messages.error(request, "Compte introuvable.")
            return render(request, 'transactions/creer_virement_recurrent.html', {'comptes': comptes})
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, "Données invalides. Vérifiez les champs.")
            return render(request, 'transactions/creer_virement_recurrent.html', {'comptes': comptes})

        if compte_source == compte_destination:
            messages.error(request, "Compte source et destination identiques.")
        elif montant <= 0:
            messages.error(request, "Le montant doit être supérieur à 0.")
        elif date_fin and date_fin < date_debut:
            messages.error(request, "La date de fin doit être postérieure à la date de début.")
        else:
            VirementRecurrent.objects.create(
                utilisateur=request.user,
                compte_source=compte_source,
                compte_destination=compte_destination,
                montant=montant,
                motif=motif,
                frequence=frequence,
                date_debut=date_debut,
                date_fin=date_fin,
                prochaine_execution=date_debut,
            )
            messages.success(request, "Virement récurrent programmé avec succès.")
            return redirect('virements_recurrents')

    return render(request, 'transactions/creer_virement_recurrent.html', {'comptes': comptes})


@login_required
def toggle_virement_recurrent(request, recurrent_id):
    virement = get_object_or_404(VirementRecurrent, id=recurrent_id, utilisateur=request.user)
    if virement.statut == 'actif':
        virement.statut = 'pause'
        messages.info(request, "Virement récurrent mis en pause.")
    elif virement.statut == 'pause':
        virement.statut = 'actif'
        messages.success(request, "Virement récurrent réactivé.")
    virement.save()
    return redirect('virements_recurrents')


@login_required
def supprimer_virement_recurrent(request, recurrent_id):
    virement = get_object_or_404(VirementRecurrent, id=recurrent_id, utilisateur=request.user)
    if request.method == 'POST':
        virement.delete()
        messages.success(request, "Virement récurrent supprimé.")
        return redirect('virements_recurrents')
    return render(request, 'transactions/supprimer_virement_recurrent.html', {'virement': virement})