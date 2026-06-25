import streamlit as st
from pathlib import Path
import time
import hashlib
import io
from utils.database import (
    create_dossier,
    get_dossier_by_ref,
    create_document,
    create_article,
    init_database,
    get_articles_by_document
)
from utils.helpers import validate_sh_code, format_currency


@st.cache_resource
def _init_db_once():
    init_database()
    return True


def show_uploader():
    """Affiche l'interface de téléversement de documents"""
    st.title(" Téléversement et extraction de documents")
    st.markdown("""
    Téléchargez vos documents douaniers (Factures Commerciales, Packing Lists, Titres de transport)
    pour extraction automatique des données par OCR/IA.
    """)

    _init_db_once()

    upload_dir = Path(__file__).parent.parent / "uploads"
    upload_dir.mkdir(exist_ok=True)

    with st.form("upload_form"):
        col1, col2 = st.columns([2, 1])

        with col1:
            ref_interne = st.text_input(
                "Référence interne du dossier (optionnel)",
                placeholder="Laisser vide pour générer une référence automatique",
                help="Cette référence permettra de retrouver le dossier plus tard"
            )

        with col2:
            st.write("")
            st.write("")
            submit_button = st.form_submit_button("🚀 Téléverser et traiter", type="primary")

        uploaded_files = st.file_uploader(
            "Glissez-déposez vos documents ici ou cliquez pour sélectionner",
            type=['pdf', 'png', 'jpg', 'jpeg', 'tiff'],
            accept_multiple_files=True,
            help="Formats acceptés : PDF, PNG, JPG, JPEG, TIFF"
        )

    if submit_button and uploaded_files:
        # ── Imports lazy — chargés seulement au clic ──────────────────────
        from utils.ocr import extract_text_from_image, extract_text_from_pdf
        from utils.ai_extractor import extract_cusxte
        from PIL import Image

        current_user = st.session_state.get("user", {})
        user_id = current_user.get("id")

        if not ref_interne:
            ref_interne = f"DOSS-{int(time.time())}"
            st.info(f"Référence interne générée : {ref_interne}")

        dossier = get_dossier_by_ref(ref_interne)
        if not dossier:
            dossier_id = create_dossier(ref_interne, "En cours de traitement", user_id=user_id)
            st.success(f"Nouveau dossier créé avec la référence : {ref_interne}")
        elif current_user.get("role") != "admin" and dossier.get("user_id") != user_id:
            st.error("Cette reference existe deja pour un autre utilisateur.")
            return
        else:
            dossier_id = dossier['id']
            st.info(f"Utilisation du dossier existant : {ref_interne}")

        st.session_state['current_dossier_id'] = dossier_id
        st.session_state['current_ref_interne'] = ref_interne

        progress_bar = st.progress(0)
        status_text = st.empty()

        processed_docs = []
        total_files = len(uploaded_files)

        for idx, uploaded_file in enumerate(uploaded_files):
            progress = (idx + 1) / total_files
            progress_bar.progress(progress)
            status_text.text(f"Traitement de {uploaded_file.name} ({idx+1}/{total_files})")

            try:
                # ── 1. Sauvegarde du fichier ────────────────────────────────
                file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()[:8]
                safe_filename = f"{file_hash}_{uploaded_file.name}"
                file_path = upload_dir / safe_filename

                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # ── 2. Détection du type de document ───────────────────────
                filename_lower = uploaded_file.name.lower()
                if 'facture' in filename_lower or 'invoice' in filename_lower:
                    doc_type = "Facture Commerciale"
                elif 'packing' in filename_lower or 'liste' in filename_lower:
                    doc_type = "Packing List"
                elif 'title' in filename_lower or 'transport' in filename_lower or 'bill of lading' in filename_lower:
                    doc_type = "Titre de Transport"
                else:
                    doc_type = "Document Divers"

                # ── 3. OCR ──────────────────────────────────────────────────
                file_extension = Path(uploaded_file.name).suffix.lower()
                if file_extension == '.pdf':
                    ocr_text = extract_text_from_pdf(file_path)
                else:
                    image = Image.open(file_path)
                    ocr_text = extract_text_from_image(image)

                # ── 4. Extraction IA ────────────────────────────────────────
                extracted_data_dict = extract_cusxte(ocr_text)

                st.success("✅ Extraction IA terminée")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Numéro document", extracted_data_dict.get("numero", ""))
                with col2:
                    st.metric(
                        "Total TTC",
                        f"{extracted_data_dict.get('valeur_totale_doc', extracted_data_dict.get('valeur_totale', 0))} "
                        f"{extracted_data_dict.get('devise', '')}"
                    )

                # ── 5. Sauvegarde document en BD (avec données IA) ──────────
                exp  = extracted_data_dict.get('expediteur', {})
                dest = extracted_data_dict.get('destinataire', {})

                document_id = create_document(
                    dossier_id=dossier_id,
                    type_document=doc_type,
                    chemin_fichier=str(file_path),
                    numero_document=extracted_data_dict.get('numero', ''),
                    date_document=extracted_data_dict.get('date', ''),
                    devise=extracted_data_dict.get('devise', ''),
                    montant_ht=extracted_data_dict.get('montant_ht', 0),
                    montant_tva=extracted_data_dict.get('montant_tva', 0),
                    valeur_totale_doc=extracted_data_dict.get(
                        'valeur_totale_doc',
                        extracted_data_dict.get('valeur_totale', 0)
                    ),
                    expediteur_nom=exp.get('nom', ''),
                    expediteur_adresse=exp.get('adresse', ''),
                    expediteur_ville=exp.get('ville', ''),
                    expediteur_code_postal=exp.get('code_postal', ''),
                    expediteur_pays=exp.get('pays', ''),
                    destinataire_nom=dest.get('nom', ''),
                    destinataire_adresse=dest.get('adresse', ''),
                    destinataire_ville=dest.get('ville', ''),
                    destinataire_code_postal=dest.get('code_postal', ''),
                    destinataire_pays=dest.get('pays', '')
                )
                st.session_state['current_document_id'] = document_id

                # ── 6. Sauvegarde des articles en BD ────────────────────────
                articles = extracted_data_dict.get('articles', [])
                for i, article in enumerate(articles):
                    create_article(
                        document_id=document_id,
                        num_ligne=article.get('num_ligne', i + 1),
                        designation=article.get('designation', ''),
                        code_sh=article.get('code_sh', ''),
                        quantite=article.get('quantite', 0),
                        poids_net=article.get('poids_net', 0),
                        valeur_devise=article.get('valeur_totale', 0),
                        poids_brut=article.get('poids_brut', 0),
                        valeur_unitaire=article.get('valeur_unitaire', 0),
                        unite=article.get('unite', ''),
                        origine=article.get('origine', '')
                    )

                processed_docs.append({
                    'name': uploaded_file.name,
                    'type': doc_type,
                    'pages': len(articles) if isinstance(articles, list) else 1,
                    'status': 'Succès'
                })

            except Exception as e:
                st.error(f"Erreur lors du traitement de {uploaded_file.name}: {str(e)}")
                processed_docs.append({
                    'name': uploaded_file.name,
                    'type': 'Erreur',
                    'pages': 0,
                    'status': f'Échec: {str(e)}'
                })

        progress_bar.empty()
        status_text.empty()

        st.subheader("Résultats du traitement")
        if processed_docs:
            results_data = []
            for doc in processed_docs:
                results_data.append({
                    "Document": doc['name'],
                    "Type": doc['type'],
                    "Pages/Lignes": doc['pages'],
                    "Statut": doc['status']
                })

            st.dataframe(
                results_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Statut": st.column_config.TextColumn(
                        "Statut",
                        help="Statut de traitement du document"
                    )
                }
            )

            if all(doc['status'] == 'Succès' for doc in processed_docs):
                from utils.database import update_dossier_statut
                update_dossier_statut(dossier_id, "Documents téléversés")
                st.success("✅ Tous les documents ont été traités avec succès !")
                st.info("Vous pouvez maintenant passer à l'onglet de révision pour vérifier et modifier les données extraites.")
            else:
                st.warning("⚠️ Certains documents ont rencontré des erreurs lors du traitement.")
        else:
            st.warning("Aucun fichier n'a été traité.")

    if 'current_dossier_id' in st.session_state:
        st.divider()
        st.subheader("Dossier actif en session")
        dossier_info = get_dossier_by_ref(st.session_state.get('current_ref_interne', ''))
        if dossier_info:
            st.write(f"**Référence :** {dossier_info['ref_interne']}")
            st.write(f"**Statut :** {dossier_info['statut']}")
            st.write(f"**Date de création :** {dossier_info['date_creation']}")


def simulate_ocr_extraction(uploaded_file, doc_type):
    import random
    num_lines = random.randint(1, 5)
    extracted_data = []
    for i in range(num_lines):
        designation = f"Article de démonstration {i+1}"
        code_sh = f"{random.randint(100000, 999999)}"
        quantite = random.randint(1, 100)
        poids_net = round(random.uniform(0.5, 50.0), 2)
        valeur_unitaire = round(random.uniform(10.0, 500.0), 2)
        valeur_devise = quantite * valeur_unitaire
        extracted_data.append({
            'num_ligne': i + 1,
            'designation': designation,
            'code_sh': code_sh,
            'quantite': quantite,
            'poids_net': poids_net,
            'valeur_devise': round(valeur_devise, 2)
        })
    return extracted_data
