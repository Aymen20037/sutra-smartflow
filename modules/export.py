import streamlit as st
from utils.database import get_current_user_dossiers, get_dossier_by_ref, get_documents_by_dossier, get_articles_by_document
from utils.helpers import format_currency, calculate_total_weight, calculate_total_value, get_exchange_rates
import json
import csv
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime


def show_export():
    """Affiche l'interface d'export des données"""
    st.title(" Export des données pour les douanes")

    if 'current_dossier_id' not in st.session_state:
        st.warning("Aucun dossier actif. Veuillez d'abord téléverser et réviser des documents.")
        return

    dossier_id = st.session_state['current_dossier_id']
    ref_interne = st.session_state.get('current_ref_interne', 'N/A')
    allowed_dossiers = get_current_user_dossiers()
    allowed_ids = [d["id"] for d in allowed_dossiers]

    if dossier_id not in allowed_ids:
        st.error("Dossier non autorise pour cet utilisateur.")
        return

    st.info(f"Export du dossier : {ref_interne}")

    dossier = get_dossier_by_ref(ref_interne)
    if not dossier:
        st.error("Dossier introuvable.")
        return

    documents = get_documents_by_dossier(dossier_id)
    all_articles = []
    for doc in documents:
        articles = get_articles_by_document(doc['id'])
        for article in articles:
            article['document_id']     = doc['id']
            article['type_document']   = doc['type_document']
            article['numero_document'] = doc.get('numero_document', '')
            article['date_document']   = doc.get('date_document', '')
            article['devise']          = doc.get('devise', '')
            article['expediteur']      = {
                'nom':         doc.get('expediteur_nom', ''),
                'adresse':     doc.get('expediteur_adresse', ''),
                'ville':       doc.get('expediteur_ville', ''),
                'code_postal': doc.get('expediteur_code_postal', ''),
                'pays':        doc.get('expediteur_pays', '')
            }
            article['destinataire']    = {
                'nom':         doc.get('destinataire_nom', ''),
                'adresse':     doc.get('destinataire_adresse', ''),
                'ville':       doc.get('destinataire_ville', ''),
                'code_postal': doc.get('destinataire_code_postal', ''),
                'pays':        doc.get('destinataire_pays', '')
            }
        all_articles.extend(articles)

    if not all_articles:
        st.warning("Aucun article à exporter. Veuillez d'abord extraire et réviser des données.")
        return

    total_weight = calculate_total_weight(all_articles)
    financial_totals = get_document_financial_totals(documents, all_articles)
    total_value_doc = financial_totals["valeur_totale_doc"]
    total_value_mad = convert_currency(
        total_value_doc,
        financial_totals["devise"] or "USD",
        'MAD'
    )

    # ── Règles métiers ──────────────────────────────────────────────────────
    st.subheader("Vérification des règles métiers")
    col1, col2 = st.columns(2)

    with col1:
        if total_weight <= 0:
            st.error(" Le poids total est nul ou négatif. Veuillez vérifier les données.")
        elif total_weight > 2000:
            st.warning(f" Le poids total ({total_weight:.2f} kg) dépasse 2000 kg. Veuillez vérifier.")
        else:
            st.success(f" Poids total cohérent : {total_weight:.2f} kg")

    with col2:
        if total_value_doc <= 0:
            st.error(" La valeur totale est nulle ou négative. Veuillez vérifier les données.")
        else:
            st.success(
                " Total TTC cohérent : "
                f"{format_currency(total_value_doc, financial_totals['devise'])}"
            )

    # ── Récapitulatif ───────────────────────────────────────────────────────
    st.subheader("Récapitulatif de l'export")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Documents",       value=len(documents))
    with col2:
        st.metric(label="Articles",         value=len(all_articles))
    with col3:
        st.metric(label="Poids total (kg)", value=f"{total_weight:.2f}")
    with col4:
        st.metric(
            label="Valeur totale MAD",
            value=format_currency(total_value_mad, "MAD")
        )

    fin_col1, fin_col2, fin_col3 = st.columns(3)
    with fin_col1:
        st.metric("Montant HT", format_currency(financial_totals["montant_ht"], financial_totals["devise"]))
    with fin_col2:
        st.metric("TVA", format_currency(financial_totals["montant_tva"], financial_totals["devise"]))
    with fin_col3:
        st.metric("Total TTC", format_currency(total_value_doc, financial_totals["devise"]))

    # ── Format & génération ─────────────────────────────────────────────────
    st.subheader("Génération du fichier d'export")
    export_format = st.radio(
        "Choisissez le format d'export :",
        options=["JSON", "XML", "CSV"],
        horizontal=True
    )

    if st.button("🚀 Générer le fichier d'export", type="primary"):
        try:
            if export_format == "JSON":
                export_data  = prepare_json_export(
                    dossier, documents, all_articles,
                    total_weight, total_value_doc, total_value_mad,
                    financial_totals
                )
                file_content = json.dumps(export_data, indent=2, ensure_ascii=False)
                file_name    = f"export_{ref_interne}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                mime_type    = "application/json"

            elif export_format == "XML":
                file_content = prepare_xml_export(
                    dossier, documents, all_articles,
                    total_weight, total_value_doc, total_value_mad,
                    financial_totals
                )
                file_name = f"export_{ref_interne}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                mime_type = "application/xml"

            else:  # CSV
                file_content = prepare_csv_export(
                    dossier, documents, all_articles,
                    total_weight, total_value_doc, total_value_mad,
                    financial_totals
                )
                file_name = f"export_{ref_interne}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                mime_type = "text/csv"

            downloaded = st.download_button(
                label=f" Télécharger l'export {export_format}",
                data=file_content,
                file_name=file_name,
                mime=mime_type
            )
            if downloaded:
                st.session_state["last_exported_dossier"] = dossier["id"]
            st.success(f"Fichier {export_format} généré avec succès !")

        except Exception as e:
            st.error(f"Erreur lors de la génération de l'export : {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions d'export
# ═══════════════════════════════════════════════════════════════════════════════

def _to_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def get_document_financial_totals(documents, articles):
    devise = next((doc.get('devise', '') for doc in documents if doc.get('devise')), 'USD')
    montant_ht = sum(_to_float(doc.get('montant_ht', 0)) for doc in documents)
    montant_tva = sum(_to_float(doc.get('montant_tva', 0)) for doc in documents)
    valeur_totale_doc = sum(_to_float(doc.get('valeur_totale_doc', 0)) for doc in documents)

    if valeur_totale_doc <= 0:
        valeur_totale_doc = calculate_total_value(articles)

    return {
        "montant_ht": montant_ht,
        "montant_tva": montant_tva,
        "valeur_totale_doc": valeur_totale_doc,
        "devise": devise or "USD",
    }


def prepare_json_export(
    dossier,
    documents,
    articles,
    total_weight,
    total_value_doc,
    total_value_mad,
    financial_totals=None
):
    total_brut = sum(article.get('poids_brut', 0) for article in articles)

    first_doc = documents[0] if documents else {}
    financial_totals = financial_totals or get_document_financial_totals(documents, articles)

    export_data = {
        "numero":    first_doc.get('numero_document', ''),
        "date":      first_doc.get('date_document', ''),
        "expediteur": {
            "nom":         first_doc.get('expediteur_nom', ''),
            "adresse":     first_doc.get('expediteur_adresse', ''),
            "ville":       first_doc.get('expediteur_ville', ''),
            "code_postal": first_doc.get('expediteur_code_postal', ''),
            "pays":        first_doc.get('expediteur_pays', '')
        },
        "destinataire": {
            "nom":         first_doc.get('destinataire_nom', ''),
            "adresse":     first_doc.get('destinataire_adresse', ''),
            "ville":       first_doc.get('destinataire_ville', ''),
            "code_postal": first_doc.get('destinataire_code_postal', ''),
            "pays":        first_doc.get('destinataire_pays', '')
        },
        "montant_ht":        round(financial_totals["montant_ht"], 2),
        "montant_tva":       round(financial_totals["montant_tva"], 2),
        "valeur_totale_doc": round(financial_totals["valeur_totale_doc"], 2),
        "valeur_totale":     round(total_value_doc, 2),
        "devise":            financial_totals["devise"],
        "dossier": {
            "ref_interne":   dossier['ref_interne'],
            "statut":        dossier['statut'],
            "date_creation": dossier['date_creation']
        },
        "export_info": {
            "date_export": datetime.now().isoformat(),
            "version":     "1.0",
            "generateur":  "Système de Transit Douanier Streamlit"
        },
        "totaux": {
            "poids_net_kg":      round(total_weight, 2),
            "poids_brut_kg":     round(total_brut, 2),
            "montant_ht":        round(financial_totals["montant_ht"], 2),
            "montant_tva":       round(financial_totals["montant_tva"], 2),
            "total_ttc":         round(total_value_doc, 2),
            "devise":            financial_totals["devise"],
            "valeur_totale_mad": round(total_value_mad, 2)
        },
        "documents": [],
        "articles":  []
    }

    for doc in documents:
        export_data["documents"].append({
            "id":             doc['id'],
            "type":           doc['type_document'],
            "chemin_fichier": doc['chemin_fichier'],
            "date_import":    doc['date_import'],
            "montant_ht":     round(_to_float(doc.get('montant_ht', 0)), 2),
            "montant_tva":    round(_to_float(doc.get('montant_tva', 0)), 2),
            "total_ttc":      round(_to_float(doc.get('valeur_totale_doc', 0)), 2),
            "devise":         doc.get('devise', '')
        })

    for article in articles:
        q = article.get('quantite', 0)
        v = article.get('valeur_devise', 0)
        export_data["articles"].append({
            "num_ligne":       article.get('num_ligne'),
            "designation":     article.get('designation', ''),
            "code_sh":         article.get('code_sh', ''),
            "quantite":        q,
            "unite":           article.get('unite', ''),
            "poids_net":       round(article.get('poids_net', 0), 2),
            "poids_brut":      round(article.get('poids_brut', 0), 2),
            "valeur_unitaire": round(article.get('valeur_unitaire', 0), 2),
            "valeur_totale":   round(v, 2),
            "origine":         article.get('origine', '')
        })

    return export_data


def prepare_xml_export(
    dossier,
    documents,
    articles,
    total_weight,
    total_value_doc,
    total_value_mad,
    financial_totals=None
):
    total_brut = sum(article.get('poids_brut', 0) for article in articles)
    first_doc  = documents[0] if documents else {}
    financial_totals = financial_totals or get_document_financial_totals(documents, articles)

    root = ET.Element("EXPORT_DOUANIER_MAROC")

    # ── DOSSIER ─────────────────────────────────────────────────────────────
    d = ET.SubElement(root, "DOSSIER")
    ET.SubElement(d, "REF_INTERNE").text       = dossier['ref_interne']
    ET.SubElement(d, "STATUT").text            = dossier['statut']
    ET.SubElement(d, "DATE_CREATION").text     = str(dossier['date_creation'])
    ET.SubElement(d, "NUMERO_DOCUMENT").text   = first_doc.get('numero_document', '')
    ET.SubElement(d, "DATE_DOCUMENT").text     = first_doc.get('date_document', '')
    ET.SubElement(d, "DEVISE").text            = financial_totals["devise"]

    # ── EXPÉDITEUR ──────────────────────────────────────────────────────────
    exp_el = ET.SubElement(root, "EXPEDITEUR")
    ET.SubElement(exp_el, "NOM").text          = first_doc.get('expediteur_nom', '')
    ET.SubElement(exp_el, "ADRESSE").text      = first_doc.get('expediteur_adresse', '')
    ET.SubElement(exp_el, "VILLE").text        = first_doc.get('expediteur_ville', '')
    ET.SubElement(exp_el, "CODE_POSTAL").text  = first_doc.get('expediteur_code_postal', '')
    ET.SubElement(exp_el, "PAYS").text         = first_doc.get('expediteur_pays', '')

    # ── DESTINATAIRE ────────────────────────────────────────────────────────
    dest_el = ET.SubElement(root, "DESTINATAIRE")
    ET.SubElement(dest_el, "NOM").text         = first_doc.get('destinataire_nom', '')
    ET.SubElement(dest_el, "ADRESSE").text     = first_doc.get('destinataire_adresse', '')
    ET.SubElement(dest_el, "VILLE").text       = first_doc.get('destinataire_ville', '')
    ET.SubElement(dest_el, "CODE_POSTAL").text = first_doc.get('destinataire_code_postal', '')
    ET.SubElement(dest_el, "PAYS").text        = first_doc.get('destinataire_pays', '')

    # ── INFO EXPORT ─────────────────────────────────────────────────────────
    info = ET.SubElement(root, "INFO_EXPORT")
    ET.SubElement(info, "DATE_EXPORT").text    = datetime.now().isoformat()
    ET.SubElement(info, "VERSION").text        = "1.0"
    ET.SubElement(info, "GENERATEUR").text     = "Système de Transit Douanier Streamlit"

    # ── TOTAUX ──────────────────────────────────────────────────────────────
    tot = ET.SubElement(root, "TOTALS")
    ET.SubElement(tot, "POIDS_NET_KG").text      = f"{total_weight:.2f}"
    ET.SubElement(tot, "POIDS_BRUT_KG").text     = f"{total_brut:.2f}"
    ET.SubElement(tot, "MONTANT_HT").text        = f"{financial_totals['montant_ht']:.2f}"
    ET.SubElement(tot, "MONTANT_TVA").text       = f"{financial_totals['montant_tva']:.2f}"
    ET.SubElement(tot, "TOTAL_TTC").text         = f"{total_value_doc:.2f}"
    ET.SubElement(tot, "DEVISE").text            = financial_totals["devise"]
    ET.SubElement(tot, "VALEUR_TOTALE_MAD").text = f"{total_value_mad:.2f}"

    # ── DOCUMENTS ───────────────────────────────────────────────────────────
    docs_el = ET.SubElement(root, "DOCUMENTS")
    for doc in documents:
        de = ET.SubElement(docs_el, "DOCUMENT")
        ET.SubElement(de, "ID").text             = str(doc['id'])
        ET.SubElement(de, "TYPE").text           = doc['type_document']
        ET.SubElement(de, "CHEMIN_FICHIER").text = doc['chemin_fichier']
        ET.SubElement(de, "DATE_IMPORT").text    = str(doc['date_import'])
        ET.SubElement(de, "MONTANT_HT").text     = f"{_to_float(doc.get('montant_ht', 0)):.2f}"
        ET.SubElement(de, "MONTANT_TVA").text    = f"{_to_float(doc.get('montant_tva', 0)):.2f}"
        ET.SubElement(de, "TOTAL_TTC").text      = f"{_to_float(doc.get('valeur_totale_doc', 0)):.2f}"
        ET.SubElement(de, "DEVISE").text         = doc.get('devise', '')

    # ── ARTICLES ────────────────────────────────────────────────────────────
    arts_el = ET.SubElement(root, "ARTICLES")
    for article in articles:
        q  = article.get('quantite', 0)
        v  = article.get('valeur_devise', 0)
        ae = ET.SubElement(arts_el, "ARTICLE")
        ET.SubElement(ae, "DOCUMENT_ID").text        = str(article['document_id'])
        ET.SubElement(ae, "TYPE_DOCUMENT").text      = article['type_document']
        ET.SubElement(ae, "NUM_LIGNE").text          = str(article.get('num_ligne', ''))
        ET.SubElement(ae, "DESIGNATION").text        = article.get('designation', '')
        ET.SubElement(ae, "CODE_SH").text            = article.get('code_sh', '')
        ET.SubElement(ae, "QUANTITE").text           = str(q)
        ET.SubElement(ae, "UNITE").text              = article.get('unite', '')
        ET.SubElement(ae, "POIDS_NET_KG").text       = f"{article.get('poids_net', 0):.2f}"
        ET.SubElement(ae, "POIDS_BRUT").text         = f"{article.get('poids_brut', 0):.2f}"
        ET.SubElement(ae, "VALEUR_UNITAIRE").text    = f"{article.get('valeur_unitaire', 0):.2f}"
        ET.SubElement(ae, "VALEUR_TOTALE").text      = f"{v:.2f}"
        ET.SubElement(ae, "DEVISE").text             = financial_totals["devise"]
        ET.SubElement(ae, "ORIGINE").text            = article.get('origine', '')

    return minidom.parseString(ET.tostring(root, 'utf-8')).toprettyxml(indent="  ")


def prepare_csv_export(
    dossier,
    documents,
    articles,
    total_weight,
    total_value_doc,
    total_value_mad,
    financial_totals=None
):
    total_brut = sum(article.get('poids_brut', 0) for article in articles)
    first_doc  = documents[0] if documents else {}
    financial_totals = financial_totals or get_document_financial_totals(documents, articles)

    output = io.StringIO()
    output.write('\ufeff')  # BOM UTF-8 pour Excel
    w = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    SEP      = "=" * 70
    SEP_THIN = "-" * 70
    EMPTY    = [""]

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 1 — INFORMATIONS DOSSIER                       ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  INFORMATIONS DOSSIER"])
    w.writerow([SEP])
    w.writerow(["  Référence",         dossier['ref_interne']])
    w.writerow(["  Statut",            dossier['statut']])
    w.writerow(["  Date création",     dossier['date_creation']])
    w.writerow(["  Numéro document",   first_doc.get('numero_document', '')])
    w.writerow(["  Date document",     first_doc.get('date_document', '')])
    w.writerow(["  Devise",            financial_totals["devise"]])
    w.writerow(["  Date export",       datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
    w.writerow(["  Générateur",        "DouanePro — Système de Transit Douanier"])
    w.writerow([SEP])
    w.writerow(EMPTY)

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 2 — EXPÉDITEUR                                 ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  EXPÉDITEUR"])
    w.writerow([SEP])
    w.writerow(["  Nom",          first_doc.get('expediteur_nom', '')])
    w.writerow(["  Adresse",      first_doc.get('expediteur_adresse', '')])
    w.writerow(["  Ville",        first_doc.get('expediteur_ville', '')])
    w.writerow(["  Code postal",  first_doc.get('expediteur_code_postal', '')])
    w.writerow(["  Pays",         first_doc.get('expediteur_pays', '')])
    w.writerow([SEP])
    w.writerow(EMPTY)

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 3 — DESTINATAIRE                               ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  DESTINATAIRE"])
    w.writerow([SEP])
    w.writerow(["  Nom",          first_doc.get('destinataire_nom', '')])
    w.writerow(["  Adresse",      first_doc.get('destinataire_adresse', '')])
    w.writerow(["  Ville",        first_doc.get('destinataire_ville', '')])
    w.writerow(["  Code postal",  first_doc.get('destinataire_code_postal', '')])
    w.writerow(["  Pays",         first_doc.get('destinataire_pays', '')])
    w.writerow([SEP])
    w.writerow(EMPTY)

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 4 — DOCUMENTS SOURCE                           ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  DOCUMENTS SOURCE"])
    w.writerow([SEP])
    w.writerow([
        "  ID Document",
        "Type",
        "Date import",
        "Montant HT",
        "TVA",
        "Total TTC",
        "Devise",
        "Chemin fichier",
    ])
    w.writerow([SEP_THIN])
    for doc in documents:
        w.writerow([
            f"  {doc['id']}",
            doc['type_document'],
            doc['date_import'],
            f"{_to_float(doc.get('montant_ht', 0)):.2f}",
            f"{_to_float(doc.get('montant_tva', 0)):.2f}",
            f"{_to_float(doc.get('valeur_totale_doc', 0)):.2f}",
            doc.get('devise', ''),
            doc['chemin_fichier'],
        ])
    w.writerow([SEP])
    w.writerow(EMPTY)

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 5 — ARTICLES                                   ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  ARTICLES"])
    w.writerow([SEP])
    w.writerow([
        "  N° Ligne",
        "Désignation",
        "Code SH",
        "Quantité",
        "Unité",
        "Poids Net (kg)",
        "Poids Brut (kg)",
        f"Valeur Unitaire ({financial_totals['devise']})",
        f"Valeur Totale ({financial_totals['devise']})",
        "Valeur Totale (MAD)",
        "Origine",
    ])
    w.writerow([SEP_THIN])
    for article in articles:
        q     = article.get("quantite", 0)
        v_doc = article.get("valeur_devise", 0)
        v_mad = round(convert_currency(v_doc, financial_totals["devise"], "MAD"), 2)
        w.writerow([
            f"  {article.get('num_ligne')}",
            article.get("designation", ""),
            article.get("code_sh", "") or "—",
            q,
            article.get("unite", ""),
            round(article.get("poids_net", 0), 3),
            round(article.get("poids_brut", 0), 3),
            round(article.get("valeur_unitaire", 0), 4),
            f"{v_doc:.2f}",
            f"{v_mad:.2f}",
            article.get("origine", ""),
        ])
    w.writerow([SEP])
    w.writerow(EMPTY)

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 6 — TOTAUX                                     ║
    # ╚══════════════════════════════════════════════════════════╝
    w.writerow([SEP])
    w.writerow(["  TOTAUX"])
    w.writerow([SEP])
    w.writerow(["  Nombre de documents",   len(documents)])
    w.writerow(["  Nombre d'articles",     len(articles)])
    w.writerow([SEP_THIN])
    w.writerow(["  Poids net total (kg)",  f"{total_weight:.3f}"])
    w.writerow(["  Poids brut total (kg)", f"{total_brut:.3f}"])
    w.writerow(["  Montant HT",            f"{financial_totals['montant_ht']:.2f}"])
    w.writerow(["  TVA",                   f"{financial_totals['montant_tva']:.2f}"])
    w.writerow(["  Total TTC",             f"{total_value_doc:.2f}"])
    w.writerow(["  Devise",                financial_totals["devise"]])
    w.writerow(["  Valeur totale (MAD)",   f"{total_value_mad:.2f}"])
    w.writerow([SEP])

    return output.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
def convert_currency(amount: float, from_currency: str, to_currency: str = 'USD') -> float:
    EXCHANGE_RATES = {'USD': 1.0, 'EUR': 1.08, 'MAD': 0.10}

    if from_currency == to_currency:
        return amount

    amount_in_usd = (
        amount * EXCHANGE_RATES.get(from_currency, 1.0)
        if from_currency != 'USD' else amount
    )

    return (
        amount_in_usd / EXCHANGE_RATES.get(to_currency, 1.0)
        if to_currency != 'USD' else amount_in_usd
    )
