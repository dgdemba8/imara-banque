from celery import shared_task
from django.utils import timezone


@shared_task
def executer_virements_recurrents():
    """
    Tâche Celery Beat — à exécuter toutes les heures (ou chaque nuit).
    Parcourt tous les VirementRecurrent actifs dont la prochaine_execution
    est aujourd'hui ou dans le passé, et les exécute.
    """
    from apps.transactions.models import VirementRecurrent
    from django.core.mail import send_mail

    aujourd_hui = timezone.now().date()

    virements_dus = VirementRecurrent.objects.filter(
        statut='actif',
        prochaine_execution__lte=aujourd_hui,
    )

    resultats = {'succes': 0, 'echecs': 0, 'details': []}

    for virement in virements_dus:
        ok, resultat = virement.executer()
        if ok:
            resultats['succes'] += 1
            resultats['details'].append(f"OK  — {virement}")

            # Notification email à l'utilisateur
            try:
                send_mail(
                    subject='Virement récurrent exécuté — Thorys Bank',
                    message=(
                        f"Bonjour {virement.utilisateur.username},\n\n"
                        f"Votre virement récurrent de {virement.montant} FCFA "
                        f"({virement.get_frequence_display()}) a été exécuté avec succès.\n\n"
                        f"Compte source      : {virement.compte_source.numero_compte}\n"
                        f"Compte destination : {virement.compte_destination.numero_compte}\n"
                        f"Motif              : {virement.motif or '—'}\n\n"
                        f"Cordialement,\nThorys Bank"
                    ),
                    from_email='noreply@thorysbank.com',
                    recipient_list=[virement.utilisateur.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        else:
            resultats['echecs'] += 1
            resultats['details'].append(f"ECHEC — {virement} : {resultat}")

            # Notification d'échec
            try:
                send_mail(
                    subject='Échec virement récurrent — Thorys Bank',
                    message=(
                        f"Bonjour {virement.utilisateur.username},\n\n"
                        f"Votre virement récurrent de {virement.montant} FCFA "
                        f"n'a pas pu être exécuté.\n\n"
                        f"Raison : {resultat}\n\n"
                        f"Veuillez vous connecter pour régulariser la situation.\n\n"
                        f"Cordialement,\nThorys Bank"
                    ),
                    from_email='noreply@thorysbank.com',
                    recipient_list=[virement.utilisateur.email],
                    fail_silently=True,
                )
            except Exception:
                pass

    return resultats
