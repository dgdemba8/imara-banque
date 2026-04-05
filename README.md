# Imara Banque : Plateforme bancaire en ligne

> Une application bancaire complète construite avec Django, pensée pour être sécurisée, élégante et fonctionnelle.

---

## Pour lancer le projet en local

### Prérequis
- Python 3.14
- MySQL 8
- Redis (optionnel, pour Celery)

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/dgdemba8/imara-banque.git
cd imara-banque

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Créer la base de données MySQL
mysql -u root -p
CREATE DATABASE exam_banque CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;

# 4. Copier .env.example → .env et remplir vos valeurs
cp .env.example .env

# 5. Appliquer les migrations
python manage.py migrate

# 6. Créer un superutilisateur
python manage.py createsuperuser

# 7. Lancer le serveur
python manage.py runserver

# 8. (Optionnel) Lancer Celery pour les virements récurrents
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

---

## À propos du projet

Imara Banque est une plateforme bancaire web développée avec Django 6, MySQL et Celery. Elle ambitionne d'offrir les fonctionnalités essentielles d'une banque en ligne moderne : gestion de comptes, virements, relevés PDF, journal de connexions et bien plus.

Le projet a été conçu avec une attention particulière portée à deux choses : **la sécurité** et **l'expérience utilisateur**. L'interface est sobre, élégante, cohérente du premier au dernier pixel (aux couleurs ardoise et champagne qui font l'identité visuelle d'Imara Banque).

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Django 6 + Python 3.14 |
| Base de données | MySQL 8 |
| Tâches asynchrones | Celery + Redis |
| Génération PDF | ReportLab |
| Frontend | Bootstrap 5 + Chart.js + Vanilla JS |
| Planification | django-celery-beat |

---

## Fonctionnalités

### Authentification
L'authentification se déroule en **deux étapes distinctes**, à la manière des vraies plateformes bancaires. L'utilisateur saisit d'abord son nom d'utilisateur, puis son mot de passe sur une seconde page. Cette séparation permet de vérifier l'existence du compte avant même d'exposer le champ mot de passe.

- Connexion en deux étapes (username → password)
- Affichage/masquage du mot de passe
- Trois tentatives de connexion possibles. Si le mot de passe est toujours incorrect, l'utilisateur est bloqué pendant quinze (15) minutes, au bout desquelles il pourra retenter une connexion.
- Déconnexion manuelle sécurisée
- **Déconnexion automatique après 30 minutes d'inactivité**, avec un popup de compte à rebours (5 minutes d'avertissement avant expiration)
- Le bouton "Je suis toujours là" prolonge la session via AJAX sans rechargement de page

### Gestion des comptes
Chaque utilisateur peut avoir plusieurs comptes (courant, épargne). La page "Mes Comptes" affiche en temps réel :

- Le solde disponible de chaque compte
- Le plafond journalier de virement (modifiable à tout moment)
- La date d'ouverture du compte
- Un **graphique d'évolution du solde sur 30 jours** (Chart.js), reconstruit dynamiquement à partir des transactions réelles — la courbe reflète fidèlement chaque mouvement de fonds

### Virements
- Virement entre comptes (internes ou vers n'importe quel numéro de compte)
- Vérification du solde disponible avant exécution
- Vérification du plafond journalier (paramétrable par compte)
- **Fenêtre d'annulation de 5 minutes** après chaque virement, avec compte à rebours visible dans l'historique
- **Email de confirmation automatique** pour tout virement dépassant 200 000 FCFA

### Virements récurrents
Les virements récurrents sont gérés par Celery Beat. Ils s'exécutent automatiquement en arrière-plan sans intervention de l'utilisateur. Ainsi, si l'utilisateur veut programmer en automatique le paiement d'un abonnement mensuel depuis un compte, ou le virement d'une épargne d'un compte courant vers son compte épargne, il pourra y souscrire. De ce fait, chaque mois / semaine / jour une somme prédéfinie sera transférée au compte destinataire automatiquement.

- Création d'un virement récurrent (quotidien, hebdomadaire, mensuel)
- Date de début et date de fin optionnelle
- Mise en pause / reprise à tout moment
- Suppression avec confirmation
- Notification email à chaque exécution réussie (ou en cas d'échec)
- Vérification automatique du solde et du plafond journalier avant chaque exécution

### Historique des transactions
- Vue complète de toutes les transactions du compte
- **Filtres combinables** : par compte, par type (virement / dépôt / retrait), par période (date début + date fin)
- Raccourcis de période rapide : 7 jours, 30 jours, 3 mois, 1 an
- Affichage du nombre de résultats
- Bouton d'annulation directement dans le tableau, avec compte à rebours en temps réel
- Badge de statut coloré (Succès / Annulé / Échec)

### Relevés PDF téléchargeables
Les relevés sont générés à la volée avec ReportLab, aux couleurs d'Imara Banque (bandeau ardoise, trait champagne, logo).

- Relevé par compte ou relevé global (tous comptes)
- Période paramétrable via un sélecteur de dates avec raccourcis
- Contenu : informations du compte, solde actuel, plafond, résumé chiffré (nb transactions, total débits, total crédits), tableau complet des transactions, virements récurrents (optionnel)
- Alternance de couleurs sur les lignes, débits en rouge, crédits en vert
- Pied de page horodaté

### Journal de connexions
Chaque connexion (réussie ou échouée) est enregistrée avec la date, l'heure et l'adresse IP. L'utilisateur peut consulter l'intégralité de son journal depuis le menu "Journal".

### Dashboard
Page d'accueil personnalisée après connexion, avec accès rapide aux fonctionnalités principales et un carrousel de présentation des services bancaires.

---

## Sécurité

La sécurité n'est pas une option ici, c'est une priorité architecturale. Voici ce qui a été mis en place :

### Blocage après tentatives échouées
Après **3 tentatives de mot de passe incorrectes**, l'accès est bloqué pendant **15 minutes**. Le blocage est suivi par couple `(username, adresse IP)`, ce qui signifie qu'un attaquant changeant d'IP doit recommencer le compteur. Une page de blocage dédiée affiche un compte à rebours en temps réel et se déverrouille automatiquement à l'expiration.

### Détection de connexions multiples suspectes
Si un même compte se connecte **plus de 2 fois en moins de 10 minutes**, un email d'alerte est automatiquement envoyé à l'adresse de l'utilisateur avec l'IP utilisée et l'horodatage. L'utilisateur est ainsi informé immédiatement si quelqu'un d'autre accède à son compte.

### Déconnexion automatique par inactivité
La session expire après **30 minutes sans activité**. Un popup s'affiche 5 minutes avant l'expiration (donc après 25 minutes) avec un compte à rebours. Si l'utilisateur ne réagit pas, il est déconnecté automatiquement. Toute activité sur la page (clic, scroll, frappe clavier) réinitialise le minuteur.

### Plafond journalier de virement
Chaque compte peut avoir un plafond journalier de virement, défini par l'utilisateur lui-même. Ce plafond cumule tous les virements de la journée. Si la somme des virements du jour atteint le plafond, tout nouveau virement est refusé avec un message indiquant le montant restant disponible.

### Fenêtre d'annulation sur les virements
Tout virement peut être annulé dans les **5 minutes suivant son exécution**. Passé ce délai, le virement est définitif. Cette fenêtre est affichée avec un compte à rebours dans l'historique.

### Confirmation par email pour les gros virements
Tout virement dépassant **200 000 FCFA** déclenche l'envoi automatique d'un email de confirmation au titulaire du compte, avec tous les détails de l'opération (montant, comptes, motif, horodatage).

### Protection CSRF
Tous les formulaires utilisent le token CSRF de Django. Les requêtes AJAX (refresh session) transmettent également le token dans les headers.

### Sessions sécurisées
- Durée de session limitée à 30 minutes (`SESSION_COOKIE_AGE`)
- Sessions stockées en base de données
- Toutes les vues sensibles sont protégées par `@login_required`

---

## Structure du projet

```
examproject/
├── apps/
│   ├── accounts/      # Authentification, blocage, journal de connexions
│   ├── comptes/       # Modèle Compte, solde, plafond, relevés PDF
│   ├── transactions/  # Virements, annulations, récurrents
│   ├── dashboard/     # Page d'accueil après connexion
│   └── journal/       # Historique des connexions utilisateur
├── config/            # Settings, URLs, Celery, WSGI
├── static/            # CSS, JS, images, logo
└── templates/         # Tous les templates HTML
```

---

## Dépendances principales

```
Django>=6.0
mysqlclient
celery
redis
django-celery-beat
reportlab
python-decouple
```

---

## Notes de développement

- `DEBUG = True` en développement ; passer à `False` en production
- Les pages d'erreur 404 et 500 sont personnalisées aux couleurs d'Imara Banque
- Les secrets (`SECRET_KEY`, mots de passe) sont gérés via `.env` avec `python-decouple` — ne jamais versionner le fichier `.env`
- L'envoi d'emails utilise SMTP Gmail ; configurer un mot de passe d'application dédié

---

## Auteur

Projet réalisé dans le cadre d'un examen Django par Monsieur Demba Guissé, élève ingénieur en Informatique et Télécommunications à l'École Polytechnique de Thiès.
Interface et logique métier entièrement développées from scratch.

---

*Imara Banque — Sécurisée • Simple • Rapide*