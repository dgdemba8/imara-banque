from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
from django.conf import settings
from datetime import timedelta, date, datetime
from decimal import Decimal
import json
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from .models import Compte
from apps.transactions.models import Transaction


# ─────────────────────────────────────────────────────────────────────
# VUE SOLDE + GRAPHIQUE
# ─────────────────────────────────────────────────────────────────────

@login_required
def solde(request):
    comptes = Compte.objects.filter(utilisateur=request.user, actif=True)

    aujourd_hui = timezone.now().date()
    debut       = aujourd_hui - timedelta(days=29)

    labels = [(debut + timedelta(days=i)).strftime('%d/%m') for i in range(30)]

    datasets = []
    COULEURS = [
        ('212,168,67',  '#d4a843'),
        ('45, 55, 72',  '#2d3748'),
        ('74,124,89',   '#4a7c59'),
        ('169,50,38',   '#a93226'),
    ]

    for idx, compte in enumerate(comptes):
        couleur_rgba, couleur_hex = COULEURS[idx % len(COULEURS)]

        transactions_periode = Transaction.objects.filter(
            date_transaction__date__gte=debut,
            date_transaction__date__lte=aujourd_hui,
            annule=False,
        ).filter(
            Q(compte_source=compte) | Q(compte_destination=compte)
        )

        deltas = {}
        for t in transactions_periode:
            jour = t.date_transaction.date()
            if jour not in deltas:
                deltas[jour] = Decimal('0')
            if t.compte_source_id == compte.id:
                deltas[jour] -= t.montant
            if t.compte_destination_id == compte.id:
                deltas[jour] += t.montant

        soldes_par_date = {}
        soldes_par_date[aujourd_hui] = float(compte.solde)

        for i in range(1, 30):
            jour      = aujourd_hui - timedelta(days=i)
            jour_suiv = aujourd_hui - timedelta(days=i - 1)
            delta = float(deltas.get(jour_suiv, Decimal('0')))
            soldes_par_date[jour] = round(soldes_par_date[jour_suiv] - delta, 2)

        data_points = [
            soldes_par_date.get(debut + timedelta(days=i), 0)
            for i in range(30)
        ]

        datasets.append({
            'label'           : compte.numero_compte,
            'data'            : data_points,
            'borderColor'     : couleur_hex,
            'backgroundColor' : f'rgba({couleur_rgba}, 0.08)',
            'borderWidth'     : 2,
            'pointRadius'     : 3,
            'pointHoverRadius': 6,
            'tension'         : 0.4,
            'fill'            : True,
        })

    graphique_data = json.dumps({
        'labels'  : labels,
        'datasets': datasets,
    })

    return render(request, 'comptes/solde.html', {
        'comptes'       : comptes,
        'graphique_data': graphique_data,
    })


# ─────────────────────────────────────────────────────────────────────
# HELPERS PDF
# ─────────────────────────────────────────────────────────────────────

def _libelle(transaction):
    return (transaction.motif or transaction.get_type_transaction_display())[:35]


def _entete_pdf(p, width, height, titre, sous_lignes):
    """Dessine l'en-tête Imara Banque avec logo + nom en italique."""

    # ── Bandeau ardoise ──────────────────────────────────────────
    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.rect(0, height - 2.2*cm, width, 2.2*cm, fill=1, stroke=0)

    # ── Trait champagne bas du bandeau ───────────────────────────
    p.setFillColorRGB(0.831, 0.659, 0.263)
    p.rect(0, height - 2.2*cm, width, 0.18*cm, fill=1, stroke=0)

    # ── Logo PNG ─────────────────────────────────────────────────
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        p.drawImage(
            logo_path,
            1.5*cm,
            height - 2.05*cm,
            width=1.5*cm,
            height=1.5*cm,
            preserveAspectRatio=True,
            mask='auto',          # gère la transparence PNG
        )
        nom_x = 3.3*cm            # nom décalé à droite du logo
    else:
        nom_x = 1.5*cm            # pas de logo → nom collé à gauche

    # ── "Imara Banque" en Times-Italic (proche Cormorant Garamond) ──
    p.setFont("Times-Italic", 20)
    p.setFillColorRGB(1, 1, 1)
    p.drawString(nom_x, height - 1.3*cm, "Imara Banque")

    # ── Sous-texte champagne ─────────────────────────────────────
    p.setFont("Helvetica", 7)
    p.setFillColorRGB(0.831, 0.659, 0.263)
    p.drawString(nom_x, height - 1.85*cm, "ESPACE CLIENT SÉCURISÉ")

    # ── Titre du document ────────────────────────────────────────
    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(1.5*cm, height - 3.2*cm, titre)

    # ── Trait champagne sous le titre ────────────────────────────
    p.setStrokeColorRGB(0.831, 0.659, 0.263)
    p.setLineWidth(1)
    p.line(1.5*cm, height - 3.5*cm, width - 1.5*cm, height - 3.5*cm)

    # ── Sous-lignes d'infos ──────────────────────────────────────
    y = height - 4.2*cm
    p.setFont("Helvetica", 9)
    p.setFillColorRGB(0.2, 0.2, 0.2)
    for ligne in sous_lignes:
        p.drawString(1.5*cm, y, ligne)
        y -= 0.55*cm

    return y - 0.4*cm


def _pied_page(p, width, now):
    p.setStrokeColorRGB(0.88, 0.88, 0.85)
    p.setLineWidth(0.5)
    p.line(1.5*cm, 1.8*cm, width - 1.5*cm, 1.8*cm)
    p.setFont("Helvetica-Oblique", 7)
    p.setFillColorRGB(0.6, 0.6, 0.58)
    p.drawCentredString(
        width / 2, 1.2*cm,
        f"Document généré le {now.strftime('%d/%m/%Y à %H:%M')} "
        f"— Confidentiel, réservé au titulaire du compte — Imara Banque"
    )


def _entete_tableau(p, y, colonnes):
    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.rect(1.5*cm, y - 0.45*cm, 18*cm, 0.55*cm, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 8)
    for x, label in colonnes:
        p.drawString(x, y - 0.28*cm, label)
    p.setStrokeColorRGB(0.831, 0.659, 0.263)
    p.setLineWidth(0.8)
    p.line(1.5*cm, y - 0.45*cm, 19.5*cm, y - 0.45*cm)
    return y - 1.0*cm


# ─────────────────────────────────────────────────────────────────────
# RELEVÉ PDF — UN COMPTE
# ─────────────────────────────────────────────────────────────────────

@login_required
def releve_pdf(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, utilisateur=request.user, actif=True)

    date_debut_str  = request.GET.get('date_debut', '')
    date_fin_str    = request.GET.get('date_fin', '')
    avec_recurrents = request.GET.get('avec_recurrents', '1') == '1'

    try:
        date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
    except ValueError:
        date_debut = timezone.now().date() - timedelta(days=30)

    try:
        date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
    except ValueError:
        date_fin = timezone.now().date()

    transactions = Transaction.objects.filter(
        annule=False,
        date_transaction__date__gte=date_debut,
        date_transaction__date__lte=date_fin,
    ).filter(
        Q(compte_source=compte) | Q(compte_destination=compte)
    ).order_by('-date_transaction')

    now    = timezone.now()
    buffer = io.BytesIO()
    p      = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    plafond_txt = (
        f"{compte.plafond_virement:,.0f} FCFA".replace(',', ' ')
        if compte.plafond_virement else "Illimité"
    )

    sous_lignes = [
        f"Titulaire : {compte.utilisateur.get_full_name() or compte.utilisateur.username}",
        f"Compte n° : {compte.numero_compte}  —  {compte.get_type_compte_display()}",
        f"Solde actuel : {compte.solde:,.0f} FCFA".replace(',', ' '),
        f"Plafond journalier : {plafond_txt}",
        f"Période : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
    ]

    y = _entete_pdf(p, width, height, "RELEVÉ DE COMPTE", sous_lignes)

    # ── Résumé chiffré ──
    nb      = transactions.count()
    debits  = sum(t.montant for t in transactions if t.compte_source_id == compte.id)
    credits = sum(t.montant for t in transactions if t.compte_destination_id == compte.id)

    p.setFillColorRGB(0.97, 0.96, 0.94)
    p.rect(1.5*cm, y - 1*cm, 5.8*cm, 1*cm, fill=1, stroke=0)
    p.rect(7.5*cm, y - 1*cm, 5.8*cm, 1*cm, fill=1, stroke=0)
    p.rect(13.5*cm, y - 1*cm, 6*cm,   1*cm, fill=1, stroke=0)

    p.setFont("Helvetica", 7)
    p.setFillColorRGB(0.6, 0.6, 0.58)
    p.drawCentredString(4.4*cm,  y - 0.3*cm,  "TRANSACTIONS")
    p.drawCentredString(10.4*cm, y - 0.3*cm,  "TOTAL DÉBITS")
    p.drawCentredString(16.5*cm, y - 0.3*cm,  "TOTAL CRÉDITS")

    p.setFont("Helvetica-Bold", 12)
    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.drawCentredString(4.4*cm,  y - 0.75*cm, str(nb))

    p.setFillColorRGB(0.663, 0.196, 0.149)
    p.drawCentredString(10.4*cm, y - 0.75*cm,
                        f"{debits:,.0f} F".replace(',', ' '))

    p.setFillColorRGB(0.184, 0.522, 0.337)
    p.drawCentredString(16.5*cm, y - 0.75*cm,
                        f"{credits:,.0f} F".replace(',', ' '))

    y -= 1.6*cm

    colonnes = [
        (1.6*cm,  "DATE"),
        (4.5*cm,  "TYPE"),
        (7.0*cm,  "MOTIF"),
        (13.5*cm, "DÉBIT (F)"),
        (16.5*cm, "CRÉDIT (F)"),
    ]
    y = _entete_tableau(p, y, colonnes)

    p.setFont("Helvetica", 8)
    for i, t in enumerate(transactions):
        if y < 3*cm:
            _pied_page(p, width, now)
            p.showPage()
            y = height - 1.5*cm
            y = _entete_tableau(p, y, colonnes)
            p.setFont("Helvetica", 8)

        if i % 2 == 0:
            p.setFillColorRGB(0.97, 0.96, 0.94)
            p.rect(1.5*cm, y - 0.4*cm, 18*cm, 0.5*cm, fill=1, stroke=0)

        p.setFillColorRGB(0.1, 0.1, 0.1)
        p.drawString(1.6*cm, y, t.date_transaction.strftime('%d/%m/%Y %H:%M'))
        p.drawString(4.5*cm, y, t.get_type_transaction_display())
        p.drawString(7.0*cm, y, _libelle(t))

        if t.compte_source_id == compte.id:
            p.setFillColorRGB(0.663, 0.196, 0.149)
            p.drawString(13.5*cm, y, f"{t.montant:,.0f}".replace(',', ' '))
            p.setFillColorRGB(0.1, 0.1, 0.1)
            p.drawString(16.5*cm, y, "—")
        else:
            p.drawString(13.5*cm, y, "—")
            p.setFillColorRGB(0.184, 0.522, 0.337)
            p.drawString(16.5*cm, y, f"{t.montant:,.0f}".replace(',', ' '))
            p.setFillColorRGB(0.1, 0.1, 0.1)

        y -= 0.55*cm

    if not transactions:
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.6, 0.6, 0.58)
        p.drawCentredString(width / 2, y, "Aucune transaction sur la période sélectionnée.")
        y -= 0.8*cm

    if avec_recurrents:
        from apps.transactions.models import VirementRecurrent
        recurrents = VirementRecurrent.objects.filter(
            utilisateur=request.user,
            compte_source=compte,
        ).order_by('prochaine_execution')

        if recurrents.exists():
            y -= 0.5*cm
            if y < 5*cm:
                _pied_page(p, width, now)
                p.showPage()
                y = height - 1.5*cm

            p.setFont("Helvetica-Bold", 10)
            p.setFillColorRGB(0.176, 0.216, 0.282)
            p.drawString(1.5*cm, y, "VIREMENTS RÉCURRENTS")
            y -= 0.3*cm
            p.setStrokeColorRGB(0.831, 0.659, 0.263)
            p.line(1.5*cm, y, 19.5*cm, y)
            y -= 0.6*cm

            col_rec = [
                (1.6*cm,  "FRÉQUENCE"),
                (5.0*cm,  "DESTINATION"),
                (10.0*cm, "MONTANT (F)"),
                (14.0*cm, "PROCHAINE EXEC."),
                (17.5*cm, "STATUT"),
            ]
            y = _entete_tableau(p, y, col_rec)
            p.setFont("Helvetica", 8)

            statut_colors = {
                'actif':   (0.184, 0.522, 0.337),
                'pause':   (0.722, 0.573, 0.149),
                'termine': (0.663, 0.196, 0.149),
            }

            for i, v in enumerate(recurrents):
                if y < 3*cm:
                    _pied_page(p, width, now)
                    p.showPage()
                    y = height - 1.5*cm
                    y = _entete_tableau(p, y, col_rec)
                    p.setFont("Helvetica", 8)

                if i % 2 == 0:
                    p.setFillColorRGB(0.97, 0.96, 0.94)
                    p.rect(1.5*cm, y - 0.4*cm, 18*cm, 0.5*cm, fill=1, stroke=0)

                p.setFillColorRGB(0.1, 0.1, 0.1)
                p.drawString(1.6*cm,  y, v.get_frequence_display())
                p.drawString(5.0*cm,  y, v.compte_destination.numero_compte)
                p.drawString(10.0*cm, y, f"{v.montant:,.0f}".replace(',', ' '))
                p.drawString(14.0*cm, y, v.prochaine_execution.strftime('%d/%m/%Y'))

                r, g, b = statut_colors.get(v.statut, (0.1, 0.1, 0.1))
                p.setFillColorRGB(r, g, b)
                p.setFont("Helvetica-Bold", 8)
                p.drawString(17.5*cm, y, v.get_statut_display())
                p.setFont("Helvetica", 8)
                p.setFillColorRGB(0.1, 0.1, 0.1)

                y -= 0.55*cm

    _pied_page(p, width, now)
    p.save()
    buffer.seek(0)

    filename = f"releve_{compte.numero_compte}_{date_debut}_{date_fin}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────────────────────────────
# RELEVÉ PDF — TOUS COMPTES
# ─────────────────────────────────────────────────────────────────────

@login_required
def releve_pdf_tous(request):
    comptes = Compte.objects.filter(utilisateur=request.user, actif=True)
    if not comptes.exists():
        return HttpResponse("Aucun compte trouvé.", status=404)

    date_debut_str  = request.GET.get('date_debut', '')
    date_fin_str    = request.GET.get('date_fin', '')
    avec_recurrents = request.GET.get('avec_recurrents', '1') == '1'

    try:
        date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
    except ValueError:
        date_debut = timezone.now().date() - timedelta(days=30)

    try:
        date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
    except ValueError:
        date_fin = timezone.now().date()

    now    = timezone.now()
    buffer = io.BytesIO()
    p      = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    sous_lignes = [
        f"Client : {request.user.get_full_name() or request.user.username}",
        f"Période : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
        f"Nombre de comptes : {comptes.count()}",
    ]

    y = _entete_pdf(p, width, height, "RELEVÉ GLOBAL — TOUS MES COMPTES", sous_lignes)

    solde_total = sum(float(c.solde) for c in comptes)

    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.5*cm, y, "SYNTHÈSE DES COMPTES")
    y -= 0.3*cm
    p.setStrokeColorRGB(0.831, 0.659, 0.263)
    p.line(1.5*cm, y, 19.5*cm, y)
    y -= 0.6*cm

    col_comptes = [
        (1.6*cm,  "N° COMPTE"),
        (7.0*cm,  "TYPE"),
        (11.0*cm, "SOLDE (F)"),
        (15.0*cm, "PLAFOND / JOUR"),
        (18.0*cm, "OUVERTURE"),
    ]
    y = _entete_tableau(p, y, col_comptes)
    p.setFont("Helvetica", 8)

    for i, compte in enumerate(comptes):
        if i % 2 == 0:
            p.setFillColorRGB(0.97, 0.96, 0.94)
            p.rect(1.5*cm, y - 0.4*cm, 18*cm, 0.5*cm, fill=1, stroke=0)

        p.setFillColorRGB(0.1, 0.1, 0.1)
        p.drawString(1.6*cm, y, compte.numero_compte)
        p.drawString(7.0*cm, y, compte.get_type_compte_display())

        p.setFillColorRGB(0.184, 0.522, 0.337)
        p.setFont("Helvetica-Bold", 8)
        p.drawString(11.0*cm, y, f"{compte.solde:,.0f}".replace(',', ' '))

        p.setFont("Helvetica", 8)
        p.setFillColorRGB(0.1, 0.1, 0.1)
        plafond = (f"{compte.plafond_virement:,.0f}".replace(',', ' ')
                   if compte.plafond_virement else "Illimité")
        p.drawString(15.0*cm, y, plafond)
        p.drawString(18.0*cm, y, compte.date_creation.strftime('%d/%m/%Y'))

        y -= 0.55*cm

    y -= 0.2*cm
    p.setStrokeColorRGB(0.831, 0.659, 0.263)
    p.line(1.5*cm, y, 19.5*cm, y)
    y -= 0.5*cm
    p.setFont("Helvetica-Bold", 10)
    p.setFillColorRGB(0.176, 0.216, 0.282)
    p.drawString(1.6*cm, y, "SOLDE GLOBAL")
    p.setFillColorRGB(0.184, 0.522, 0.337)
    p.drawString(11.0*cm, y, f"{solde_total:,.0f} F".replace(',', ' '))
    y -= 1.2*cm

    for compte in comptes:
        if y < 6*cm:
            _pied_page(p, width, now)
            p.showPage()
            y = height - 1.5*cm

        p.setFont("Helvetica-Bold", 10)
        p.setFillColorRGB(0.176, 0.216, 0.282)
        p.drawString(1.5*cm, y, f"Transactions — {compte.numero_compte} ({compte.get_type_compte_display()})")
        y -= 0.3*cm
        p.setStrokeColorRGB(0.831, 0.659, 0.263)
        p.line(1.5*cm, y, 19.5*cm, y)
        y -= 0.6*cm

        transactions = Transaction.objects.filter(
            annule=False,
            date_transaction__date__gte=date_debut,
            date_transaction__date__lte=date_fin,
        ).filter(
            Q(compte_source=compte) | Q(compte_destination=compte)
        ).order_by('-date_transaction')

        if not transactions.exists():
            p.setFont("Helvetica-Oblique", 8)
            p.setFillColorRGB(0.6, 0.6, 0.58)
            p.drawString(1.6*cm, y, "Aucune transaction sur la période.")
            y -= 0.8*cm
            continue

        colonnes = [
            (1.6*cm,  "DATE"),
            (4.5*cm,  "TYPE"),
            (7.0*cm,  "MOTIF"),
            (13.5*cm, "DÉBIT (F)"),
            (16.5*cm, "CRÉDIT (F)"),
        ]
        y = _entete_tableau(p, y, colonnes)
        p.setFont("Helvetica", 8)

        for i, t in enumerate(transactions):
            if y < 3*cm:
                _pied_page(p, width, now)
                p.showPage()
                y = height - 1.5*cm
                y = _entete_tableau(p, y, colonnes)
                p.setFont("Helvetica", 8)

            if i % 2 == 0:
                p.setFillColorRGB(0.97, 0.96, 0.94)
                p.rect(1.5*cm, y - 0.4*cm, 18*cm, 0.5*cm, fill=1, stroke=0)

            p.setFillColorRGB(0.1, 0.1, 0.1)
            p.drawString(1.6*cm, y, t.date_transaction.strftime('%d/%m/%Y %H:%M'))
            p.drawString(4.5*cm, y, t.get_type_transaction_display())
            p.drawString(7.0*cm, y, _libelle(t))

            if t.compte_source_id == compte.id:
                p.setFillColorRGB(0.663, 0.196, 0.149)
                p.drawString(13.5*cm, y, f"{t.montant:,.0f}".replace(',', ' '))
                p.setFillColorRGB(0.1, 0.1, 0.1)
                p.drawString(16.5*cm, y, "—")
            else:
                p.drawString(13.5*cm, y, "—")
                p.setFillColorRGB(0.184, 0.522, 0.337)
                p.drawString(16.5*cm, y, f"{t.montant:,.0f}".replace(',', ' '))
                p.setFillColorRGB(0.1, 0.1, 0.1)

            y -= 0.55*cm

        y -= 0.6*cm

    _pied_page(p, width, now)
    p.save()
    buffer.seek(0)

    filename = f"releve_global_{date_debut}_{date_fin}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response