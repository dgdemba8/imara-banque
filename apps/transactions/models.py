from django.db import models
from django.utils import timezone
from datetime import timedelta
from apps.comptes.models import Compte


class Transaction(models.Model):
    TYPES = [
        ('virement', 'Virement'),
        ('depot',    'Dépôt'),
        ('retrait',  'Retrait'),
    ]
    compte_source      = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='transactions_emises')
    compte_destination = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='transactions_recues', null=True, blank=True)
    type_transaction   = models.CharField(max_length=10, choices=TYPES)
    montant            = models.DecimalField(max_digits=12, decimal_places=2)
    date_transaction   = models.DateTimeField(auto_now_add=True)
    motif              = models.CharField(max_length=255, blank=True, null=True)
    statut             = models.BooleanField(default=True)

    # Lien optionnel vers le virement récurrent qui a généré cette transaction
    virement_recurrent = models.ForeignKey(
        'VirementRecurrent',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions_generees'
    )

    # Champ pour l'annulation (délai 5 min)
    annule             = models.BooleanField(default=False)
    date_annulation    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_transaction']
        verbose_name = 'Transaction'

    def __str__(self):
        return f"{self.type_transaction} - {self.montant} FCFA - {self.date_transaction}"

    @property
    def annulable(self):
        """True si la transaction peut encore être annulée (dans les 5 minutes)."""
        if self.annule or self.type_transaction != 'virement':
            return False
        limite = self.date_transaction + timedelta(minutes=5)
        return timezone.now() <= limite

    @property
    def secondes_avant_expiration(self):
        """Secondes restantes avant la fin de la fenêtre d'annulation."""
        if not self.annulable:
            return 0
        delta = (self.date_transaction + timedelta(minutes=5)) - timezone.now()
        return max(int(delta.total_seconds()), 0)


class VirementRecurrent(models.Model):
    FREQUENCES = [
        ('quotidien', 'Quotidien'),
        ('hebdo',     'Hebdomadaire'),
        ('mensuel',   'Mensuel'),
    ]
    STATUTS = [
        ('actif',    'Actif'),
        ('pause',    'En pause'),
        ('termine',  'Terminé'),
    ]

    utilisateur        = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    compte_source      = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='virements_recurrents_source')
    compte_destination = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='virements_recurrents_dest')
    montant            = models.DecimalField(max_digits=12, decimal_places=2)
    motif              = models.CharField(max_length=255, blank=True, null=True)
    frequence          = models.CharField(max_length=10, choices=FREQUENCES, default='mensuel')
    date_debut         = models.DateField()
    date_fin           = models.DateField(null=True, blank=True, help_text='Laisser vide pour sans fin')
    prochaine_execution = models.DateField()
    statut             = models.CharField(max_length=10, choices=STATUTS, default='actif')
    date_creation      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['prochaine_execution']
        verbose_name = 'Virement récurrent'

    def __str__(self):
        return f"{self.get_frequence_display()} — {self.montant} FCFA ({self.compte_source} → {self.compte_destination})"

    def calculer_prochaine_date(self):
        """Calcule la prochaine date d'exécution après aujourd'hui."""
        from datetime import date
        base = self.prochaine_execution
        if self.frequence == 'quotidien':
            return base + timedelta(days=1)
        elif self.frequence == 'hebdo':
            return base + timedelta(weeks=1)
        elif self.frequence == 'mensuel':
            # Même jour le mois suivant
            mois = base.month + 1
            annee = base.year
            if mois > 12:
                mois = 1
                annee += 1
            import calendar
            dernier_jour = calendar.monthrange(annee, mois)[1]
            jour = min(base.day, dernier_jour)
            return base.replace(year=annee, month=mois, day=jour)

    def executer(self):
        """
        Exécute le virement récurrent :
        - Vérifie le solde et le plafond
        - Crée la Transaction
        - Met à jour la prochaine date ou termine si date_fin atteinte
        Retourne (True, transaction) ou (False, message_erreur).
        """
        from decimal import Decimal

        if self.statut != 'actif':
            return False, "Virement inactif."

        source = self.compte_source
        dest   = self.compte_destination

        # Vérification solde
        if source.solde < self.montant:
            return False, f"Solde insuffisant sur {source.numero_compte}."

        # Vérification plafond
        ok, msg = source.peut_virer(self.montant)
        if not ok:
            return False, msg

        # Exécution
        source.solde -= self.montant
        dest.solde   += self.montant
        source.save()
        dest.save()

        transaction = Transaction.objects.create(
            compte_source=source,
            compte_destination=dest,
            type_transaction='virement',
            montant=self.montant,
            motif=self.motif or f"Virement récurrent ({self.get_frequence_display()})",
            statut=True,
            virement_recurrent=self,
        )

        # Calculer la prochaine exécution
        prochaine = self.calculer_prochaine_date()
        if self.date_fin and prochaine > self.date_fin:
            self.statut = 'termine'
        else:
            self.prochaine_execution = prochaine

        self.save()
        return True, transaction