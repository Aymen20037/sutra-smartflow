"""
Fonctions utilitaires pour le système de transit douanier
"""

import streamlit as st
from typing import Dict, Any, List, Optional
import math
import requests
from datetime import datetime

# ==========================================
# Devises populaires supportées
# ==========================================

POPULAR_CURRENCIES = [
    'USD', 'EUR', 'MAD', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD',
    'CNY', 'AED', 'SAR', 'QAR', 'KWD', 'TRY', 'INR', 'BRL',
    'MXN', 'ZAR', 'EGP', 'DZD', 'TND', 'NGN', 'KES', 'GHS'
]

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'MAD': 'د.م.',
    'GBP': '£',
    'JPY': '¥',
    'CHF': 'Fr',
    'CAD': 'CA$',
    'AUD': 'A$',
    'CNY': '¥',
    'AED': 'د.إ',
    'SAR': '﷼',
    'QAR': 'ر.ق',
    'KWD': 'د.ك',
    'TRY': '₺',
    'INR': '₹',
    'BRL': 'R$',
    'MXN': 'MX$',
    'ZAR': 'R',
    'EGP': 'E£',
    'DZD': 'دج',
    'TND': 'د.ت',
    'NGN': '₦',
    'KES': 'KSh',
    'GHS': 'GH₵',
}

CURRENCY_NAMES = {
    'USD': 'Dollar américain',
    'EUR': 'Euro',
    'MAD': 'Dirham marocain',
    'GBP': 'Livre sterling',
    'JPY': 'Yen japonais',
    'CHF': 'Franc suisse',
    'CAD': 'Dollar canadien',
    'AUD': 'Dollar australien',
    'CNY': 'Yuan chinois',
    'AED': 'Dirham émirati',
    'SAR': 'Riyal saoudien',
    'QAR': 'Riyal qatari',
    'KWD': 'Dinar koweïtien',
    'TRY': 'Livre turque',
    'INR': 'Roupie indienne',
    'BRL': 'Real brésilien',
    'MXN': 'Peso mexicain',
    'ZAR': 'Rand sud-africain',
    'EGP': 'Livre égyptienne',
    'DZD': 'Dinar algérien',
    'TND': 'Dinar tunisien',
    'NGN': 'Naira nigérian',
    'KES': 'Shilling kényan',
    'GHS': 'Cedi ghanéen',
}

# Taux de secours si l'API est indisponible
FALLBACK_RATES = {
    'USD': 1.0,
    'EUR': 1.08,
    'MAD': 0.10,
    'GBP': 1.27,
    'JPY': 0.0067,
    'CHF': 1.13,
    'CAD': 0.74,
    'AUD': 0.65,
    'CNY': 0.14,
    'AED': 0.27,
    'SAR': 0.27,
    'QAR': 0.27,
    'KWD': 3.26,
    'TRY': 0.031,
    'INR': 0.012,
    'BRL': 0.20,
    'MXN': 0.058,
    'ZAR': 0.054,
    'EGP': 0.021,
    'DZD': 0.0074,
    'TND': 0.32,
    'NGN': 0.00065,
    'KES': 0.0077,
    'GHS': 0.067,
}

# ==========================================
# Taux de change en temps réel
# ==========================================

@st.cache_data(ttl=3600)  # Cache 1 heure
def get_exchange_rates() -> Dict[str, float]:
    """
    Récupère les taux de change en temps réel via l'API gratuite.
    Mise en cache pendant 1 heure pour éviter les appels répétés.
    Retourne les taux par rapport à USD comme base.
    """
    try:
        response = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            # Filtrer uniquement les devises populaires
            filtered = {
                currency: rates[currency]
                for currency in POPULAR_CURRENCIES
                if currency in rates
            }
            filtered['USD'] = 1.0
            return filtered
        else:
            st.warning("⚠️ API taux de change indisponible — taux de secours utilisés.")
            return FALLBACK_RATES
    except Exception:
        st.warning("⚠️ Impossible de récupérer les taux en temps réel — taux de secours utilisés.")
        return FALLBACK_RATES


def get_rate_update_time() -> str:
    """Retourne l'heure de la dernière mise à jour des taux."""
    return datetime.now().strftime("%d/%m/%Y à %H:%M")


# ==========================================
# Conversion de devises
# ==========================================

def convert_currency(amount: float, from_currency: str, to_currency: str = 'USD') -> float:
    """
    Convertit un montant d'une devise à une autre en temps réel.
    Utilise USD comme devise pivot.
    """
    if from_currency == to_currency:
        return amount

    rates = get_exchange_rates()

    # Convertir vers USD d'abord
    rate_from = rates.get(from_currency, 1.0)
    amount_in_usd = amount / rate_from

    # Convertir USD vers la devise cible
    rate_to = rates.get(to_currency, 1.0)
    return amount_in_usd * rate_to


# ==========================================
# Calcul des droits de douane
# ==========================================

def calculate_customs_duties(
    valeur_en_devise: float,
    taux_douanier: float,
    tva_taux: float = 0.20,
    autres_taxe: float = 0.0
) -> Dict[str, float]:
    """
    Calcule les droits de douane et la TVA à l'importation.
    """
    droits_douane = valeur_en_devise * taux_douanier
    base_tva = valeur_en_devise + droits_douane + autres_taxe
    tva = base_tva * tva_taux
    total_a_payer = droits_douane + tva + autres_taxe

    return {
        'droits_douane': droits_douane,
        'base_tva': base_tva,
        'tva': tva,
        'autres_taxe': autres_taxe,
        'total_a_payer': total_a_payer
    }


# ==========================================
# Formatage
# ==========================================

def format_currency(amount: float, currency: str = 'USD') -> str:
    """Formate un montant numérique en chaîne avec symbole de devise."""
    symbol = CURRENCY_SYMBOLS.get(currency, '')
    return f"{symbol}{amount:,.2f}"


def get_currency_label(currency: str) -> str:
    """Retourne le label complet d'une devise : code + nom."""
    name = CURRENCY_NAMES.get(currency, currency)
    symbol = CURRENCY_SYMBOLS.get(currency, '')
    return f"{currency} ({symbol}) — {name}"


# ==========================================
# Validation
# ==========================================

def validate_sh_code(code_sh: str) -> bool:
    """
    Valide qu'un code SH est au bon format (min 6 chiffres).
    """
    if not code_sh:
        return False
    clean_code = code_sh.replace(' ', '').replace('.', '')
    return clean_code.isdigit() and len(clean_code) >= 6


# ==========================================
# Calculs articles
# ==========================================

def calculate_total_weight(articles: List[Dict[str, Any]]) -> float:
    """Calcule le poids net total d'une liste d'articles."""
    return sum(article.get('poids_net', 0) for article in articles)


def calculate_total_value(articles: List[Dict[str, Any]]) -> float:
    """Calcule la valeur totale en devise d'une liste d'articles."""
    return sum(article.get('valeur_devise', 0) for article in articles)


# ==========================================
# Statuts
# ==========================================

def get_status_color(statut: str) -> str:
    """Retourne une couleur associée au statut."""
    colors = {
        'En cours': 'blue',
        'Validé': 'green',
        'Rejeté': 'red',
        'En attente': 'orange',
        'Exporté': 'grey'
    }
    return colors.get(statut, 'grey')


def render_timeline(nb_documents: int, nb_articles: int, statut: str, exported: bool = False) -> str:
    """Retourne du HTML/CSS pour une barre de progression en 5 etapes."""
    completed_steps = [
        True,
        nb_documents > 0,
        nb_articles > 0,
        statut == "Documents téléversés",
        exported is True,
    ]
    labels = ["Créé", "Uploadé", "OCR extrait", "Révisé", "Exporté"]

    try:
        active_index = completed_steps.index(False)
    except ValueError:
        active_index = -1

    html_parts = [
        """
<style>
.sutra-timeline {
    width: 100%;
    max-width: 700px;
    margin: 18px auto 24px;
    padding: 18px 22px;
    background: #FFFFFF;
    border-radius: 18px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    font-family: 'Poppins', sans-serif;
}
.sutra-timeline-row {
    display: grid;
    grid-template-columns: 46px 1fr 46px 1fr 46px 1fr 46px 1fr 46px;
    align-items: center;
}
.sutra-timeline-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    min-width: 0;
}
.sutra-timeline-circle {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 800;
    box-shadow: 0 3px 8px rgba(0,0,0,0.14);
}
.sutra-timeline-label {
    color: #0A2540;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.2;
    text-align: center;
    white-space: normal;
}
.sutra-timeline-connector {
    height: 5px;
    border-radius: 999px;
    margin: 0 4px 22px;
}
.sutra-completed { background: #2ECC71; }
.sutra-active { background: #3498DB; }
.sutra-pending { background: #BDC3C7; }
@media (max-width: 620px) {
    .sutra-timeline {
        padding: 14px 10px;
    }
    .sutra-timeline-row {
        grid-template-columns: 36px 1fr 36px 1fr 36px 1fr 36px 1fr 36px;
    }
    .sutra-timeline-circle {
        width: 28px;
        height: 28px;
        font-size: 12px;
    }
    .sutra-timeline-label {
        font-size: 10px;
    }
}
</style>
<div class="sutra-timeline">
    <div class="sutra-timeline-row">
"""
    ]

    for index, label in enumerate(labels):
        state_class = "sutra-completed"
        if not completed_steps[index]:
            state_class = "sutra-active" if index == active_index else "sutra-pending"

        html_parts.append(
            f"""
        <div class="sutra-timeline-step">
            <div class="sutra-timeline-circle {state_class}">{index + 1}</div>
            <div class="sutra-timeline-label">{label}</div>
        </div>
"""
        )

        if index < len(labels) - 1:
            connector_class = "sutra-completed" if completed_steps[index + 1] else "sutra-pending"
            html_parts.append(f'        <div class="sutra-timeline-connector {connector_class}"></div>\n')

    html_parts.append(
        """    </div>
</div>
"""
    )

    return "".join(html_parts)