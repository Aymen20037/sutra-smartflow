import base64
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.database import (
    delete_document,
    delete_user,
    get_admin_stats,
    get_all_documents_with_owner,
    get_all_users,
    init_database,
    set_user_active,
    update_user,
)


BASE_DIR = Path(__file__).parent.parent


def require_admin() -> bool:
    user = st.session_state.get("user", {})
    if user.get("role") != "admin":
        st.error("Acces reserve aux administrateurs.")
        return False
    return True


def _format_size(size_bytes: int) -> str:
    value = float(size_bytes or 0)
    for unit in ["o", "Ko", "Mo", "Go"]:
        if value < 1024 or unit == "Go":
            return f"{value:.1f} {unit}" if unit != "o" else f"{int(value)} {unit}"
        value /= 1024
    return "0 o"


def _apply_admin_style():
    st.markdown(
        """
        <style>
        .stApp{background-color:#F5F7FA;}
        div[data-testid="metric-container"]{
            background:white;
            padding:20px;
            border-radius:15px;
            box-shadow:0 4px 12px rgba(0,0,0,0.08);
            border-left:5px solid #1565C0;
        }
        [data-testid="stMetricValue"]{
            font-size:42px !important;
            font-weight:900 !important;
            color:#0A2540 !important;
        }
        [data-testid="stMetricLabel"]{
            font-size:18px !important;
            font-weight:700 !important;
            color:#555 !important;
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-8px); }
        }
        @keyframes shimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
        @keyframes slide-up {
          from { opacity: 0; transform: translateY(18px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .sutra-header {
          position: relative;
          background: #0A2540;
          border-radius: 20px;
          padding: 40px 44px;
          overflow: hidden;
          margin-bottom: 30px;
          cursor: default;
          transition: box-shadow 0.3s ease;
        }
        .sutra-header:hover { box-shadow: 0 0 0 2px #1E5AA8; }
        .grid-lines {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
          background-size: 40px 40px;
          border-radius: 20px;
        }
        .glow-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(60px);
          pointer-events: none;
        }
        .robot-icon {
          display: inline-block;
          font-size: 52px;
          animation: float 3.5s ease-in-out infinite;
          margin-right: 16px;
          vertical-align: middle;
          line-height: 1;
        }
        .header-title {
          display: inline;
          font-size: 48px;
          font-weight: 800;
          letter-spacing: -1.5px;
          background: linear-gradient(90deg, #ffffff 0%, #a8c8ff 50%, #ffffff 100%);
          background-size: 200% auto;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: shimmer 4s linear infinite, slide-up 0.6s ease forwards;
          vertical-align: middle;
        }
        .header-subtitle {
          margin-top: 16px;
          font-size: 17px;
          color: rgba(255,255,255,0.75);
          font-weight: 400;
          letter-spacing: 0.2px;
          animation: slide-up 0.6s ease 0.15s both;
        }
        .badge-row {
          display: flex;
          gap: 10px;
          margin-top: 22px;
          flex-wrap: wrap;
        }
        .badge {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 5px 13px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 500;
          border: 0.5px solid;
        }
        .badge-blue {
          background: rgba(30,90,168,0.25);
          border-color: rgba(56,138,221,0.4);
          color: #a8c8ff;
        }
        .badge-teal {
          background: rgba(29,158,117,0.2);
          border-color: rgba(29,158,117,0.4);
          color: #7ee0c0;
        }
        .badge-amber {
          background: rgba(186,117,23,0.2);
          border-color: rgba(239,159,39,0.4);
          color: #fac775;
        }
        .version-tag {
          position: absolute;
          top: 18px; right: 20px;
          font-size: 11px;
          color: rgba(255,255,255,0.35);
          font-weight: 500;
          letter-spacing: 0.5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="sutra-header">
          <div class="grid-lines"></div>
          <div class="glow-orb" style="width:280px;height:280px;background:rgba(30,90,168,0.18);top:-80px;right:-60px;"></div>
          <div class="glow-orb" style="width:180px;height:180px;background:rgba(29,158,117,0.1);bottom:-60px;left:60px;"></div>
          <div class="version-tag">Admin</div>
          <div style="position:relative;z-index:2;">
            <div style="line-height:1.1;">
              <span class="robot-icon">⚙</span>
              <span class="header-title">{title}</span>
            </div>
            <p class="header-subtitle">{subtitle}</p>
            <div class="badge-row">
              <div class="badge badge-blue">Controle global</div>
              <div class="badge badge-teal">Utilisateurs</div>
              <div class="badge badge-amber">Documents</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_admin_dashboard():
    if not require_admin():
        return

    init_database()
    _apply_admin_style()
    _render_header("Dashboard Admin", "Pilotage global de SUTRA SmartFlow")

    stats = get_admin_stats()
    row1 = st.columns(4)
    row1[0].metric("Utilisateurs", stats["total_users"])
    row1[1].metric("Administrateurs", stats["total_admins"])
    row1[2].metric("Comptes actifs", stats["active_users"])
    row1[3].metric("Documents", stats["total_documents"])

    row2 = st.columns(4)
    row2[0].metric("Documents valides", stats["validated_documents"])
    row2[1].metric("En attente", stats["pending_documents"])
    row2[2].metric("Rejetes", stats["rejected_documents"])
    row2[3].metric("Espace utilise", _format_size(stats["storage_used"]))

    documents = get_all_documents_with_owner()
    users = get_all_users()
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        role_df = pd.DataFrame(users)
        if role_df.empty:
            role_counts = pd.DataFrame(columns=["Role", "Nombre"])
        else:
            role_counts = role_df["role"].value_counts().reset_index()
            role_counts.columns = ["Role", "Nombre"]
        fig = px.pie(role_counts, names="Role", values="Nombre", hole=0.5, title="Repartition des roles")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        docs_df = pd.DataFrame(documents)
        if docs_df.empty:
            status_counts = pd.DataFrame(columns=["Statut", "Nombre"])
        else:
            status_counts = docs_df["dossier_statut"].fillna("Sans statut").value_counts().reset_index()
            status_counts.columns = ["Statut", "Nombre"]
        fig = px.bar(status_counts, x="Statut", y="Nombre", title="Documents par statut")
        st.plotly_chart(fig, use_container_width=True)


def show_user_management():
    if not require_admin():
        return

    init_database()
    _apply_admin_style()
    _render_header("Gestion Utilisateurs", "Recherche, roles, activation et maintenance des comptes")

    users = get_all_users()
    df = pd.DataFrame(users)
    if df.empty:
        st.info("Aucun utilisateur trouve.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    search = col1.text_input("Rechercher", placeholder="Nom ou email")
    role_filter = col2.selectbox("Role", ["Tous", "admin", "user"])
    active_filter = col3.selectbox("Statut", ["Tous", "Actif", "Inactif"])

    filtered = df.copy()
    if search:
        needle = search.strip().lower()
        filtered = filtered[
            filtered["username"].str.lower().str.contains(needle, na=False)
            | filtered["email"].str.lower().str.contains(needle, na=False)
        ]
    if role_filter != "Tous":
        filtered = filtered[filtered["role"] == role_filter]
    if active_filter != "Tous":
        filtered = filtered[filtered["is_active"] == (1 if active_filter == "Actif" else 0)]

    display_df = filtered.copy()
    display_df["Statut"] = display_df["is_active"].apply(lambda value: "Actif" if value else "Inactif")
    display_df = display_df[["id", "username", "email", "role", "Statut", "date_creation"]]
    display_df.columns = ["ID", "Nom", "Email", "Role", "Statut", "Date creation"]

    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=360,
        key="admin_users_table",
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = selection.selection.rows
    if not selected_rows:
        return

    selected = filtered.iloc[selected_rows[0]].to_dict()
    current_user_id = st.session_state.get("user", {}).get("id")

    st.subheader(f"Utilisateur #{selected['id']}")
    with st.form(f"edit_user_{selected['id']}"):
        username = st.text_input("Nom utilisateur", value=selected.get("username", ""))
        email = st.text_input("Email", value=selected.get("email", ""))
        role = st.selectbox("Role", ["user", "admin"], index=0 if selected.get("role") == "user" else 1)
        is_active = st.toggle("Compte actif", value=bool(selected.get("is_active", 1)))
        saved = st.form_submit_button("Enregistrer", type="primary")

    if saved:
        if selected["id"] == current_user_id and (role != "admin" or not is_active):
            st.error("Vous ne pouvez pas retirer vos propres droits admin ni desactiver votre compte.")
        elif update_user(int(selected["id"]), username, email, role, is_active):
            if selected["id"] == current_user_id:
                st.session_state["user"].update({"username": username, "email": email, "role": role, "is_active": 1})
            st.success("Utilisateur mis a jour.")
            st.rerun()
        else:
            st.error("Mise a jour impossible. Verifiez que l'email est unique.")

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        new_state = not bool(selected.get("is_active", 1))
        label = "Desactiver" if not new_state else "Activer"
        if st.button(label, use_container_width=True, disabled=selected["id"] == current_user_id):
            set_user_active(int(selected["id"]), new_state)
            st.success("Statut du compte mis a jour.")
            st.rerun()

    with action_col2:
        confirm = st.checkbox("Confirmer la suppression", key=f"confirm_delete_user_{selected['id']}")
        if st.button("Supprimer", use_container_width=True, disabled=selected["id"] == current_user_id or not confirm):
            if delete_user(int(selected["id"])):
                st.success("Utilisateur supprime.")
                st.rerun()
            else:
                st.error("Suppression impossible.")


def _delete_document_and_file(document_id: int, file_path: str) -> bool:
    deleted = delete_document(document_id)
    if not deleted:
        return False

    try:
        path = Path(file_path)
        uploads_dir = (BASE_DIR / "uploads").resolve()
        resolved = path.resolve()
        if resolved.exists() and uploads_dir in resolved.parents:
            resolved.unlink()
    except OSError:
        pass
    return True


def _render_document_preview(doc: dict):
    file_path = Path(doc.get("chemin_fichier") or "")
    if not file_path.exists():
        st.warning("Fichier introuvable sur le disque.")
        return

    suffix = file_path.suffix.lower()
    if suffix in [".png", ".jpg", ".jpeg"]:
        st.image(str(file_path), use_container_width=True)
    elif suffix == ".pdf":
        encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{encoded}" width="100%" height="650"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.info(f"Apercu non disponible pour {suffix or 'ce format'}.")


def show_document_management():
    if not require_admin():
        return

    init_database()
    _apply_admin_style()
    _render_header("Gestion Documents", "Vue globale, filtres, ouverture, telechargement et suppression")

    documents = get_all_documents_with_owner()
    df = pd.DataFrame(documents)
    if df.empty:
        st.info("Aucun document trouve.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    search = col1.text_input("Rechercher", placeholder="Reference, type, proprietaire")
    status_options = ["Tous"] + sorted(df["dossier_statut"].fillna("Sans statut").unique().tolist())
    type_options = ["Tous"] + sorted(df["type_document"].fillna("Sans type").unique().tolist())
    status_filter = col2.selectbox("Statut", status_options)
    type_filter = col3.selectbox("Type", type_options)

    filtered = df.copy()
    if search:
        needle = search.strip().lower()
        haystack = (
            filtered["ref_interne"].fillna("")
            + " "
            + filtered["type_document"].fillna("")
            + " "
            + filtered["owner_username"].fillna("")
            + " "
            + filtered["owner_email"].fillna("")
        ).str.lower()
        filtered = filtered[haystack.str.contains(needle, na=False)]
    if status_filter != "Tous":
        filtered = filtered[filtered["dossier_statut"].fillna("Sans statut") == status_filter]
    if type_filter != "Tous":
        filtered = filtered[filtered["type_document"].fillna("Sans type") == type_filter]

    display_df = filtered.copy()
    display_df["Proprietaire"] = display_df["owner_username"].fillna("Non assigne") + " <" + display_df["owner_email"].fillna("-") + ">"
    display_df["Taille"] = display_df["file_size"].apply(_format_size)
    display_df = display_df[
        ["id", "type_document", "ref_interne", "Proprietaire", "date_import", "dossier_statut", "Taille"]
    ]
    display_df.columns = ["ID", "Type", "Dossier", "Proprietaire", "Date", "Statut", "Taille"]

    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=390,
        key="admin_documents_table",
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = selection.selection.rows
    if not selected_rows:
        return

    doc = filtered.iloc[selected_rows[0]].to_dict()
    st.subheader(f"Document #{doc['id']}")
    info1, info2, info3 = st.columns(3)
    info1.metric("Type", doc.get("type_document") or "-")
    info2.metric("Statut", doc.get("dossier_statut") or "-")
    info3.metric("Taille", _format_size(doc.get("file_size") or 0))
    st.write(f"**Proprietaire :** {doc.get('owner_username') or 'Non assigne'} - {doc.get('owner_email') or '-'}")
    st.write(f"**Chemin :** {doc.get('chemin_fichier') or '-'}")

    file_path = Path(doc.get("chemin_fichier") or "")
    if file_path.exists():
        st.download_button(
            "Telecharger",
            data=file_path.read_bytes(),
            file_name=file_path.name,
            mime="application/octet-stream",
            use_container_width=True,
        )

    with st.expander("Ouvrir le document", expanded=False):
        _render_document_preview(doc)

    confirm = st.checkbox("Confirmer la suppression du document", key=f"confirm_delete_doc_{doc['id']}")
    if st.button("Supprimer le document", type="primary", disabled=not confirm):
        if _delete_document_and_file(int(doc["id"]), doc.get("chemin_fichier") or ""):
            st.success("Document supprime.")
            st.rerun()
        else:
            st.error("Suppression impossible.")
