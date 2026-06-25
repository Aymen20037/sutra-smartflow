import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from utils.database import (
    get_current_user_dossiers,
    get_documents_by_dossier,
    get_articles_by_document,
    update_article
)

from utils.helpers import (
    validate_sh_code,
    format_currency,
    calculate_total_weight,
    render_timeline
)


def show_review():
    """Affiche l'interface de révision des données extraites"""

    st.title(" Révision et validation des données extraites")

    # ==========================================================
    # Recherche automatique du dossier
    # ==========================================================

    dossiers = get_current_user_dossiers()
    if not dossiers:
        st.warning("Aucun dossier trouvé. Veuillez d'abord téléverser des documents.")
        return

    dossier_ids = [d["id"] for d in dossiers]
    session_dossier_id = st.session_state.get("current_dossier_id")

    if session_dossier_id in dossier_ids:
        dossier_id = session_dossier_id
        dossier = next(d for d in dossiers if d["id"] == dossier_id)
        ref_interne = dossier["ref_interne"]
    else:
        dossier = dossiers[0]
        dossier_id = dossier["id"]
        ref_interne = dossier["ref_interne"]
        st.session_state["current_dossier_id"] = dossier_id
        st.session_state["current_ref_interne"] = ref_interne

    # Sélecteur de dossier
    dossier_labels = {
        f"{d['ref_interne']} (ID:{d['id']})": d["id"]
        for d in dossiers
    }
    current_label = f"{ref_interne} (ID:{dossier_id})"

    selected_label = st.selectbox(
        "Dossier",
        list(dossier_labels.keys()),
        index=list(dossier_labels.keys()).index(current_label)
        if current_label in dossier_labels else 0
    )

    if dossier_labels[selected_label] != dossier_id:
        dossier_id = dossier_labels[selected_label]
        dossier = next(d for d in dossiers if d["id"] == dossier_id)
        ref_interne = dossier["ref_interne"]
        st.session_state["current_dossier_id"] = dossier_id
        st.session_state["current_ref_interne"] = ref_interne

        if "current_document_id" in st.session_state:
            del st.session_state["current_document_id"]

        st.rerun()

    st.success(f"Dossier actif : {ref_interne}")

    # ==========================================================
    # Documents
    # ==========================================================

    documents = get_documents_by_dossier(dossier_id)

    if not documents:
        st.warning("Aucun document trouvé dans ce dossier.")
        return

    documents_sorted = sorted(documents, key=lambda d: d["id"], reverse=True)

    document_options = {
        f"{doc['type_document']} (ID:{doc['id']})": doc["id"]
        for doc in documents_sorted
    }

    session_doc_id = st.session_state.get("current_document_id")
    doc_ids = [doc["id"] for doc in documents_sorted]

    if session_doc_id in doc_ids:
        default_doc_label = next(
            label for label, did in document_options.items()
            if did == session_doc_id
        )
    else:
        default_doc_label = list(document_options.keys())[0]

    doc_select_key = f"document_selector_{dossier_id}"

    selected_doc_label = st.selectbox(
        "Sélectionnez un document",
        options=list(document_options.keys()),
        index=list(document_options.keys()).index(default_doc_label),
        key=doc_select_key
    )

    selected_doc_id = document_options[selected_doc_label]
    st.session_state["current_document_id"] = selected_doc_id

    # ── Récupérer la devise du document sélectionné ────────────────────────
    selected_doc = next(
        (doc for doc in documents_sorted if doc["id"] == selected_doc_id),
        {}
    )
    devise_doc = selected_doc.get("devise", "") or "USD"

    def _to_float(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    montant_ht = _to_float(selected_doc.get("montant_ht", 0))
    montant_tva = _to_float(selected_doc.get("montant_tva", 0))
    total_ttc = _to_float(selected_doc.get("valeur_totale_doc", 0))

    nb_articles_dossier = sum(
        len(get_articles_by_document(doc["id"]))
        for doc in documents
    )

    # ==========================================================
    # Articles
    # ==========================================================

    articles = get_articles_by_document(selected_doc_id)

    components.html(
        render_timeline(
            nb_documents=len(documents),
            nb_articles=nb_articles_dossier,
            statut=dossier["statut"],
            exported=st.session_state.get("last_exported_dossier") == dossier_id
        ),
        height=150,
        scrolling=False
    )

    if not articles:
        st.info(
            "Aucun article extrait dans ce document.\n\n"
            "Vérifiez que l'OCR et l'extraction IA fonctionnent correctement."
        )
        return

    df = pd.DataFrame(articles)

    df["num_ligne"]    = pd.to_numeric(df["num_ligne"],    errors="coerce").fillna(0).astype(int)
    df["quantite"]     = pd.to_numeric(df["quantite"],     errors="coerce").fillna(0).astype(int)
    df["poids_net"]    = pd.to_numeric(df["poids_net"],    errors="coerce").fillna(0.0)
    df["poids_brut"]   = pd.to_numeric(df["poids_brut"],   errors="coerce").fillna(0.0)
    df["valeur_devise"]= pd.to_numeric(df["valeur_devise"],errors="coerce").fillna(0.0)
    df["designation"]  = df["designation"].fillna("")
    df["code_sh"]      = df["code_sh"].fillna("")

    df = df[["num_ligne", "designation", "code_sh",
             "quantite", "poids_net", "poids_brut", "valeur_devise"]]

    st.subheader("Articles extraits")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key=f"editor_{selected_doc_id}",
        column_config={
            "num_ligne":    st.column_config.NumberColumn("Ligne", step=1, format="%.0f"),
            "designation":  st.column_config.TextColumn("Nature de la marchandise"),
            "code_sh":      st.column_config.TextColumn("Code SH"),
            "quantite":     st.column_config.NumberColumn("Quantité", step=1, format="%.0f"),
            "poids_net":    st.column_config.NumberColumn("Poids net (kg)", format="%.2f"),
            "poids_brut":   st.column_config.NumberColumn("Poids brut (kg)", format="%.2f"),
            "valeur_devise":st.column_config.NumberColumn(
                f"Valeur ({devise_doc})", format="%.2f"
            ),
        }
    )

    # ==========================================================
    # Sauvegarde
    # ==========================================================

    if st.button("Enregistrer les modifications"):
        try:
            for idx, row in edited_df.iterrows():
                if idx >= len(articles):
                    continue
                update_article(
                    articles[idx]["id"],
                    designation=str(row["designation"]),
                    code_sh=str(row["code_sh"]),
                    quantite=float(row["quantite"]),
                    poids_net=float(row["poids_net"]),
                    poids_brut=float(row["poids_brut"]),
                    valeur_devise=float(row["valeur_devise"])
                )
            st.success("Modifications enregistrées.")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur : {e}")

    # ==========================================================
    # Totaux
    # ==========================================================

    st.subheader("Résumé")

    total_weight = calculate_total_weight(edited_df.to_dict("records"))
    total_brut   = edited_df["poids_brut"].sum()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Articles", len(edited_df))
    with col2:
        st.metric("Poids net total", f"{total_weight:.2f} kg")
    with col3:
        st.metric("Poids brut total", f"{total_brut:.2f} kg")

    fin_col1, fin_col2, fin_col3 = st.columns(3)

    with fin_col1:
        st.metric("Montant HT", format_currency(montant_ht, devise_doc))
    with fin_col2:
        st.metric("TVA", format_currency(montant_tva, devise_doc))
    with fin_col3:
        st.metric("Total TTC", format_currency(total_ttc, devise_doc))

    # ==========================================================
    # Validation
    # ==========================================================

    MAX_WEIGHT = 1000

    if total_weight > MAX_WEIGHT:
        st.error(f"Poids total supérieur à {MAX_WEIGHT} kg")
    else:
        st.success(f"Poids total valide ({total_weight:.2f} kg)")

    if st.button("Passer à l'export"):
        st.info("Ouvrez maintenant l'onglet Export.")
