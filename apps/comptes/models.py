from django.db import models
from django.contrib.auth.models import User
# from apps.journal.models import JournalConnexion # pour les logs de connexion

# Create your models here.
class Compte(models.Model):
    TYPES = [
        ('courant', 'Compte Courant'),
        ('epargne', 'Compte Épargne'),
    ]
    utilisateur    = models.ForeignKey(User, on_delete=models.CASCADE)
    numero_compte  = models.CharField(max_length=20, unique=True)
    type_compte    = models.CharField(max_length=10, choices=TYPES, default='courant')
    solde          = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_creation  = models.DateTimeField(auto_now_add=True)
    actif          = models.BooleanField(default=True)

    # Plafond journalier de virement (None = pas de limite)
    plafond_virement = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Plafond journalier de virement (FCFA)',
        help_text='Laisser vide pour aucune limite.'
    )



    class Meta:
        verbose_name = 'Compte'

    def __str__(self):
        return f"{self.numero_compte} - {self.utilisateur.username}"

    def montant_vire_aujourd_hui(self):
        """Retourne le total des virements émis aujourd'hui depuis ce compte."""
        from django.utils import timezone
        from apps.transactions.models import Transaction
        aujourd_hui = timezone.now().date()
        total = Transaction.objects.filter(
            compte_source=self,
            type_transaction='virement',
            statut=True,
            date_transaction__date=aujourd_hui,
        ).aggregate(total=models.Sum('montant'))['total']
        return total or 0


    def peut_virer(self, montant):
        """
        Vérifie si un virement du montant donné est possible
        au regard du plafond journalier.
        Retourne (True, None) ou (False, message_erreur).
        """
        if self.plafond_virement is None:
            return True, None
        deja_vire = self.montant_vire_aujourd_hui()
        if deja_vire + montant > self.plafond_virement:
            restant = max(self.plafond_virement - deja_vire, 0)
            return False, (
                f"Plafond journalier atteint. "
                f"Il vous reste {restant:,.0f} FCFA disponibles aujourd'hui "
                f"(plafond : {self.plafond_virement:,.0f} FCFA)."
            )
        return True, None