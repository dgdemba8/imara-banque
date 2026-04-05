from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

# Le modèle JournalConnexion qui va enregistrer les connexions des utilisateurs, y compris la date, l'adresse IP et le succès de la connexion.

class JournalConnexion(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    date_connexion = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    succes = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date_connexion']
        verbose_name = 'Journal de connexion'

    def __str__(self):
        return f"{self.utilisateur} - {self.date_connexion}"


class TentativeConnexion(models.Model):
    """
    Stocke les tentatives échouées par username + IP.
    Permet le blocage temporaire après 3 échecs consécutifs.
    """
    username    = models.CharField(max_length=150)
    adresse_ip  = models.GenericIPAddressField(null=True, blank=True)
    tentatives  = models.PositiveIntegerField(default=0)
    bloque_jusqu = models.DateTimeField(null=True, blank=True)
    derniere_tentative = models.DateTimeField(auto_now=True)

    DUREE_BLOCAGE  = timedelta(minutes=15)
    MAX_TENTATIVES = 3

    class Meta:
        # Un enregistrement par couple (username, ip)
        unique_together = ('username', 'adresse_ip')
        verbose_name = 'Tentative de connexion'

    def __str__(self):
        return f"{self.username} ({self.adresse_ip}) — {self.tentatives} tentative(s)"

    # ------------------------------------------------------------------
    # Les Helpers
    # ------------------------------------------------------------------

    @property
    def est_bloque(self):
        """Retourne True si le compte est actuellement bloqué."""
        if self.bloque_jusqu and timezone.now() < self.bloque_jusqu:
            return True
        return False

    @property
    def temps_restant(self):
        """Retourne le nb de secondes restantes avant déblocage (0 si non bloqué)."""
        if self.est_bloque:
            delta = self.bloque_jusqu - timezone.now()
            return max(int(delta.total_seconds()), 0)
        return 0

    def enregistrer_echec(self):
        """Incrémente le compteur et bloque si le seuil est atteint."""
        # Si le blocage précédent est expiré, on repart de zéro
        if self.bloque_jusqu and timezone.now() >= self.bloque_jusqu:
            self.tentatives = 0
            self.bloque_jusqu = None

        self.tentatives += 1

        if self.tentatives >= self.MAX_TENTATIVES:
            self.bloque_jusqu = timezone.now() + self.DUREE_BLOCAGE

        self.save()

    def reinitialiser(self):
        """Remet à zéro après une connexion réussie."""
        self.tentatives = 0
        self.bloque_jusqu = None
        self.save()

    # ------------------------------------------------------------------
    # Méthode de classe : point d'entrée unique
    # ------------------------------------------------------------------

    @classmethod
    def verifier_ou_creer(cls, username, ip):
        """
        Retourne l'objet TentativeConnexion correspondant au couple
        (username, ip), en le créant s'il n'existe pas encore.
        """
        obj, _ = cls.objects.get_or_create(
            username=username,
            adresse_ip=ip,
        )
        return obj



