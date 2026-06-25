import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, List

from dotenv import load_dotenv
from groq import Groq, InternalServerError, BadRequestError
import streamlit as st

load_dotenv()

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]


@st.cache_resource
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY introuvable dans le fichier .env")
    return Groq(api_key=api_key)


def get_default_structure() -> Dict[str, Any]:
    return {
        "numero": "",
        "date": "",
        "expediteur": {
            "nom": "",
            "adresse": "",
            "ville": "",
            "code_postal": "",
            "pays": ""
        },
        "destinataire": {
            "nom": "",
            "adresse": "",
            "ville": "",
            "code_postal": "",
            "pays": ""
        },
        "montant_ht": 0,
        "montant_tva": 0,
        "valeur_totale_doc": 0,
        "valeur_totale": 0,
        "devise": "",
        "articles": []
    }


def normalize_date(date_str: str) -> str:
    if not date_str:
        return ""
    formats = [
        "%d/%m/%Y", "%d-%m-%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d/%m/%y", "%d-%m-%y",
        "%Y/%m/%d", "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return date_str


def clean_json_response(raw_response: str) -> str:
    if not raw_response:
        return ""
    cleaned = raw_response.strip()
    for marker in ["```json", "```JSON", "```"]:
        if cleaned.startswith(marker):
            cleaned = cleaned[len(marker):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def fix_european_numbers(value) -> float:
    """
    Convertit un nombre au format européen en float.
    "3 150,00" → 3150.00
    "8 233,08" → 8233.08
    "0,50"     → 0.50
    "100,00"   → 100.00
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace('€', '').replace('$', '') \
                       .replace('\xa0', ' ').strip()
        if ',' in cleaned and '.' not in cleaned:
            cleaned = cleaned.replace(' ', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(' ', '').replace(',', '')
        try:
            return float(cleaned)
        except Exception:
            return 0.0
    return 0.0


def detect_devise(ocr_text: str) -> str:
    """
    Détecte la devise dominante dans le texte OCR.
    Retourne 'EUR', 'USD', 'MAD', etc.
    """
    text_upper = ocr_text.upper()
    # Comptage des occurrences pour déterminer la devise dominante
    count_eur = text_upper.count('EUR') + ocr_text.count('€')
    count_usd = text_upper.count('USD') + ocr_text.count('$')
    count_mad = text_upper.count('MAD')
    count_xof = text_upper.count('XOF')
    count_gbp = text_upper.count('GBP') + ocr_text.count('£')

    scores = {
        'EUR': count_eur,
        'USD': count_usd,
        'MAD': count_mad,
        'XOF': count_xof,
        'GBP': count_gbp,
    }
    best = max(scores, key=scores.get)
    # Si aucune devise trouvée, retourner chaîne vide
    if scores[best] == 0:
        return ''
    return best


def build_prompt(ocr_text: str) -> str:
    # Pré-détection de la devise en Python pour l'injecter dans le prompt
    devise_detectee = detect_devise(ocr_text)
    devise_hint = f'La devise détectée dans ce document est : {devise_detectee}' \
                  if devise_detectee else 'Détecte la devise depuis le texte.'

    return f"""Tu es un système d'extraction de données de factures commerciales et douanières.
Ta seule tâche : lire le texte et remplir le JSON avec les bonnes valeurs.

═══════════════════════════════════════
TEXTE À ANALYSER :
═══════════════════════════════════════
{ocr_text}
═══════════════════════════════════════

═══════════════════════════════════════
DEVISE — RÈGLE ABSOLUE :
═══════════════════════════════════════
{devise_hint}
Utilise EXACTEMENT cette valeur dans le champ "devise".
Ne jamais mettre "USD" si le document contient "€" ou "EUR".
Ne jamais mettre "$" — utilise toujours le code ISO : EUR, USD, MAD, XOF, GBP.

═══════════════════════════════════════
ÉTAPE 1 — IDENTIFIER LES EN-TÊTES DE COLONNES
═══════════════════════════════════════
Trouve la ligne d'en-têtes du tableau d'articles.
  DESIGNATION | QTE   | PRIX UNIT  | MONTANT
  DESCRIPTION | QTY   | UNIT PRICE | AMOUNT
  COMMODITY   | KGS   | PRICE      | TOTAL

Mémorise l'ordre exact des colonnes avant de lire les données.

═══════════════════════════════════════
ÉTAPE 2 — LIRE CHAQUE LIGNE D'ARTICLE
═══════════════════════════════════════
Assigne chaque valeur à la colonne correcte selon les en-têtes.

EXEMPLE :
  En-têtes : DESIGNATION | QTE | PRIX UNIT | MONTANT
  Données  : Article | 9 | 350,00 € | 3 150,00 €
  JSON :
    "designation":    "Article",
    "quantite":       9,
    "valeur_unitaire":350.00,
    "valeur_totale":  3150.00

EXEMPLE avec prix décimal inférieur à 1 :
  Données  : Article | 20 | 0,50 € | 100,00 €
  JSON :
    "designation":    "Article",
    "quantite":       20,
    "valeur_unitaire":0.50,
    "valeur_totale":  100.00   ← PAS 10.00, PAS 1000.00

ERREURS À ÉVITER :
  ✗ Prendre PRIX UNIT à la place de QTE
  ✗ Tronquer "100,00" en 10.00 ou "0,50" en 5.0
  ✗ Calculer un montant (toujours copier la valeur de la colonne MONTANT)

═══════════════════════════════════════
ÉTAPE 3 — FORMAT EUROPÉEN DES NOMBRES
═══════════════════════════════════════
  VIRGULE = séparateur décimal  : "350,00" → 350.00
  ESPACE  = séparateur milliers : "3 150,00" → 3150.00

Conversions :
  "3 150,00 €" → 3150.00
  "8 233,08 €" → 8233.08
  "1 011,08 €" → 1011.08
  "350,00 €"   → 350.00
  "0,50 €"     → 0.50     ← zéro virgule cinquante = 0.50
  "100,00 €"   → 100.00   ← cent euros = 100.00 (pas 10.00 !)

═══════════════════════════════════════
VALEUR TOTALE DU DOCUMENT :
═══════════════════════════════════════
Cherche et extrais separement les montants de synthese de la facture :
  "MONTANT HT", "TOTAL HT", "NET HT" -> montant_ht
  "TVA", "MONTANT TVA", "VAT" -> montant_tva
  "TOTAL TTC", "NET A PAYER", "TOTAL A PAYER" -> valeur_totale_doc

Exemple :
  "Montant HT 7 222,00 €" -> montant_ht: 7222.00
  "TVA 1 011,08 €" -> montant_tva: 1011.08
  "TOTAL TTC 8 233,08 €" -> valeur_totale_doc: 8233.08

Prends TOTAL TTC pour valeur_totale_doc si present, sinon TOTAL.
Ne pas additionner les articles — copier les valeurs du document.

═══════════════════════════════════════
COLONNES DE POIDS (packing lists) :
═══════════════════════════════════════
  N.W. / NET WEIGHT / POIDS NET   → "poids_net"
  G.W. / GROSS WEIGHT / POIDS BRUT → "poids_brut"
Si absentes → poids_net=0, poids_brut=0.

═══════════════════════════════════════
STRUCTURE JSON OBLIGATOIRE :
═══════════════════════════════════════
{{
    "numero": "",
    "date": "",
    "expediteur": {{
        "nom": "",
        "adresse": "",
        "ville": "",
        "code_postal": "",
        "pays": ""
    }},
    "destinataire": {{
        "nom": "",
        "adresse": "",
        "ville": "",
        "code_postal": "",
        "pays": ""
    }},
    "montant_ht": 0,
    "montant_tva": 0,
    "valeur_totale_doc": 0,
    "valeur_totale": 0,
    "devise": "",
    "articles": [
        {{
            "num_ligne": 1,
            "designation": "",
            "code_sh": "",
            "quantite": 0,
            "unite": "",
            "poids_net": 0,
            "poids_brut": 0,
            "valeur_unitaire": 0,
            "valeur_totale": 0,
            "origine": ""
        }}
    ]
}}

═══════════════════════════════════════
RÈGLES FINALES :
═══════════════════════════════════════
1. JSON uniquement — aucun texte avant ou après.
2. Aucun markdown, aucun bloc ```json.
3. Montants en nombres décimaux : 3150.00 et non "3 150,00".
4. Date au format YYYY-MM-DD.
5. Ne JAMAIS calculer — copie uniquement ce qui est dans le document.
6. Ne JAMAIS confondre PRIX UNIT et QTE.
7. "devise" = code ISO (EUR, USD, MAD...) — jamais de symbole ($, €).
"""


def call_groq_with_fallback(client, prompt: str) -> str:
    for model in GROQ_MODELS:
        print(f"\nEssai modèle : {model}")
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=4000
                )
                print(f"Modèle utilisé avec succès : {model}")
                return response.choices[0].message.content

            except BadRequestError as e:
                print(f"Modèle {model} indisponible : {e}")
                break

            except InternalServerError:
                wait = 2 ** attempt
                print(f"Serveur surchargé (tentative {attempt + 1}/3), attente {wait}s...")
                if attempt < 2:
                    time.sleep(wait)
                else:
                    print(f"Modèle {model} toujours indisponible après 3 tentatives.")
                    break

            except Exception as e:
                print(f"Erreur inattendue avec {model} : {e}")
                break

    raise RuntimeError("Tous les modèles Groq sont indisponibles. Réessayez plus tard.")


def extract_cusxte(ocr_text: str) -> Dict[str, Any]:
    try:
        print("\n" + "=" * 80)
        print("DEBUT EXTRACTION IA")
        print("=" * 80)

        if not ocr_text or len(ocr_text.strip()) < 20:
            print("OCR vide ou trop court")
            return get_default_structure()

        # Pré-détection devise pour correction post-traitement
        devise_python = detect_devise(ocr_text)

        client = get_groq_client()
        prompt = build_prompt(ocr_text)
        raw_response = call_groq_with_fallback(client, prompt)

        print("\nREPONSE BRUTE GROQ")
        print("-" * 80)
        print(raw_response)
        print("-" * 80)

        if not raw_response:
            print("Réponse vide")
            return get_default_structure()

        cleaned_response = clean_json_response(raw_response)

        print("\nJSON APRES NETTOYAGE")
        print("-" * 80)
        print(cleaned_response)
        print("-" * 80)

        try:
            result = json.loads(cleaned_response)
        except Exception:
            print("\nTentative récupération JSON...")
            start = cleaned_response.find("{")
            end = cleaned_response.rfind("}")
            if start == -1 or end == -1:
                return get_default_structure()
            result = json.loads(cleaned_response[start:end + 1])

        # Post-traitement date
        if result.get("date"):
            result["date"] = normalize_date(result["date"])

        if "articles" not in result:
            result["articles"] = []

        # Correction devise : si l'IA a mis un symbole ou une mauvaise devise,
        # on force la valeur détectée par Python
        if devise_python:
            devise_ia = result.get("devise", "").upper().strip()
            # Remplace les symboles par codes ISO
            symboles = {"€": "EUR", "$": "USD", "£": "GBP"}
            for sym, code in symboles.items():
                if sym in devise_ia:
                    devise_ia = code
            # Si l'IA a mis une devise incorrecte ou vide, on force
            if devise_ia not in ("EUR", "USD", "MAD", "XOF", "GBP", "DZD"):
                result["devise"] = devise_python
                print(f"Devise corrigée : '{devise_ia}' → '{devise_python}'")
            else:
                result["devise"] = devise_ia

        # Nettoyage des montants (double sécurité format européen)
        numeric_fields = ["quantite", "poids_net", "poids_brut",
                          "valeur_unitaire", "valeur_totale"]

        for article in result["articles"]:
            for key in numeric_fields:
                article[key] = fix_european_numbers(article.get(key, 0))

        # Montants de synthese du document
        result["montant_ht"] = fix_european_numbers(result.get("montant_ht", 0))
        result["montant_tva"] = fix_european_numbers(result.get("montant_tva", 0))
        result["valeur_totale_doc"] = fix_european_numbers(
            result.get("valeur_totale_doc", result.get("valeur_totale", 0))
        )
        result["valeur_totale"] = result["valeur_totale_doc"]

        print("\nRESULTAT FINAL IA")
        print("-" * 80)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 80)
        print(f"Nombre articles : {len(result.get('articles', []))}")
        print("=" * 80)

        return result

    except Exception as e:
        logging.exception("Erreur extraction IA")
        print("\nERREUR GROQ")
        print(str(e))
        return get_default_structure()


def extract_multiple_documents(ocr_texts: List[str]) -> List[Dict[str, Any]]:
    return [extract_cusxte(text) for text in ocr_texts]
