import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from utils.database import (
    get_current_user_dossiers,
    get_documents_by_dossier,
    get_articles_by_document,
    init_database
)
from utils.helpers import render_timeline


def show_dashboard():
    """Dashboard professionnel Transit"""

    # =========================
    # CSS PROFESSIONNEL
    # =========================
    st.markdown("""
    <style>

    .stApp{
        background-color:#F5F7FA;
    }

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

    </style>
    """, unsafe_allow_html=True)

    # =========================
    # HEADER PREMIUM ANIMÉ
    # =========================
    st.markdown("""
    <style>
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-8px); }
    }
    @keyframes shimmer {
      0% { background-position: -200% center; }
      100% { background-position: 200% center; }
    }
    @keyframes pulse-ring {
      0% { transform: scale(0.95); opacity: 0.7; }
      70% { transform: scale(1.05); opacity: 0.3; }
      100% { transform: scale(0.95); opacity: 0.7; }
    }
    @keyframes particle-move {
      0% { transform: translate(0, 0) scale(1); opacity: 0.15; }
      50% { transform: translate(var(--dx), var(--dy)) scale(1.3); opacity: 0.3; }
      100% { transform: translate(0, 0) scale(1); opacity: 0.15; }
    }
    @keyframes slide-up {
      from { opacity: 0; transform: translateY(18px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes badge-in {
      from { opacity: 0; transform: scale(0.8); }
      to { opacity: 1; transform: scale(1); }
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

    .particle {
      position: absolute;
      border-radius: 50%;
      background: rgba(30, 90, 168, 0.5);
      animation: particle-move 6s ease-in-out infinite;
    }

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
      animation: badge-in 0.5s ease 0.3s both;
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
      transition: transform 0.2s, background 0.2s;
    }
    .badge:hover { transform: translateY(-2px); }
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
    .pulse-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #4cffb3;
      animation: pulse-ring 2s ease infinite;
      display: inline-block;
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

    <div class="sutra-header">
      <div class="grid-lines"></div>

      <div class="glow-orb" style="width:280px;height:280px;background:rgba(30,90,168,0.18);top:-80px;right:-60px;"></div>
      <div class="glow-orb" style="width:180px;height:180px;background:rgba(29,158,117,0.1);bottom:-60px;left:60px;"></div>

      <div class="particle" style="width:10px;height:10px;top:20%;left:72%;--dx:-18px;--dy:12px;animation-delay:0s;animation-duration:7s;"></div>
      <div class="particle" style="width:6px;height:6px;top:60%;left:85%;--dx:12px;--dy:-20px;animation-delay:1.5s;animation-duration:5.5s;"></div>
      <div class="particle" style="width:8px;height:8px;top:75%;left:60%;--dx:-10px;--dy:15px;animation-delay:3s;animation-duration:8s;"></div>
      <div class="particle" style="width:5px;height:5px;top:35%;left:90%;--dx:8px;--dy:-10px;animation-delay:2s;animation-duration:6s;"></div>

      <div class="version-tag">v2.1 · 2026</div>

      <div style="position:relative;z-index:2;">
        <div style="line-height:1.1;">
          <span class="robot-icon">🤖</span>
          <span class="header-title">SUTRA SmartFlow</span>
        </div>
        <p class="header-subtitle">
          Plateforme intelligente d'extraction OCR, IA et gestion douanière
        </p>
        <div class="badge-row">
          <div class="badge badge-blue"> AI</div>
          <div class="badge badge-teal"> OCR Hybride</div>
          <div class="badge badge-amber"> Transit douanier</div>
          <div class="badge badge-blue" style="margin-left:auto;">
            <span class="pulse-dot"></span> Actif
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # =========================
    # DATABASE
    # =========================
    init_database()

    dossiers = get_current_user_dossiers()

    # ✅ Construire un DataFrame vide avec les bonnes colonnes si aucun dossier
    if not dossiers:
        st.info(" Aucun dossier pour le moment. Commencez par téléverser un document !")
        df = pd.DataFrame(columns=["ref_interne", "statut", "date_creation"])
    else:
        df = pd.DataFrame(dossiers)

    # =========================
    # Graphiques
    # =========================

    col1, col2 = st.columns(2)

    with col1:

        if df.empty:
            statut_counts = pd.DataFrame(columns=["Statut", "Nombre"])
        else:
            statut_counts = (
                df["statut"]
                .value_counts()
                .reset_index()
            )
            statut_counts.columns = ["Statut", "Nombre"]

        fig_pie = px.pie(
            statut_counts,
            values="Nombre" if not statut_counts.empty else None,
            names="Statut" if not statut_counts.empty else None,
            hole=0.5,
            title="Répartition des Dossiers"
        )

        # ✅ Message centré si vide
        if statut_counts.empty:
            fig_pie.add_annotation(
                text="Aucune donnée disponible",
                x=0.5, y=0.5,
                font_size=16,
                showarrow=False,
                font_color="#999"
            )

        fig_pie.update_layout(height=450)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:

        if df.empty:
            evolution = pd.DataFrame(columns=["date_creation", "Nombre"])
        else:
            df["date_creation"] = pd.to_datetime(df["date_creation"])
            evolution = (
                df.groupby(df["date_creation"].dt.date)
                .size()
                .reset_index(name="Nombre")
            )

        fig_line = px.line(
            evolution,
            x="date_creation",
            y="Nombre",
            markers=True,
            title="Évolution des Créations de Dossiers"
        )

        # ✅ Message centré si vide
        if evolution.empty:
            fig_line.add_annotation(
                text="Aucune donnée disponible",
                x=0.5, y=0.5,
                font_size=16,
                showarrow=False,
                font_color="#999"
            )

        fig_line.update_layout(height=450)
        st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # =========================
    # Tableau professionnel
    # =========================

    st.subheader("Liste des Dossiers")

    statuts_disponibles = list(df["statut"].unique()) if not df.empty else []

    filtre_statut = st.selectbox(
        "Filtrer par statut",
        ["Tous"] + statuts_disponibles
    )

    if filtre_statut != "Tous":
        df = df[df["statut"] == filtre_statut]

    colonnes_affichage = ["ref_interne", "statut", "date_creation"]

    # ✅ S'assurer que les colonnes existent même si df est vide
    display_df = df.reindex(columns=colonnes_affichage).copy()

    display_df.columns = ["Référence", "Statut", "Date Création"]

    if not display_df.empty:
        display_df["Date Création"] = pd.to_datetime(
            display_df["Date Création"]
        ).dt.strftime("%d/%m/%Y %H:%M")

    selected_dossier = st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        key="dashboard_dossiers_table",
        on_select="rerun",
        selection_mode="single-row"
    )

    selected_rows = selected_dossier.selection.rows
    if selected_rows:
        dossier = df.iloc[selected_rows[0]]
        documents = get_documents_by_dossier(int(dossier["id"]))
        nb_articles = sum(
            len(get_articles_by_document(doc["id"]))
            for doc in documents
        )
        exported = st.session_state.get("last_exported_dossier") == int(dossier["id"])

        components.html(
            render_timeline(
                nb_documents=len(documents),
                nb_articles=nb_articles,
                statut=dossier["statut"],
                exported=exported
            ),
            height=150,
            scrolling=False
        )

    st.divider()