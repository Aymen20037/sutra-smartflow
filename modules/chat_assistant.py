"""
Assistant IA Douanier - Interface blanche épurée
"""

import streamlit as st
from typing import Dict, Any, List

from utils.database import get_current_user_dossiers, get_documents_by_dossier, get_articles_by_document
from utils.helpers import format_currency
from utils.ai_extractor import get_groq_client


# ─── DATA HELPERS ─────────────────────────────────────────────────────────────

def _to_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_context(dossier_id: int) -> Dict[str, Any]:
    context = {
        "dossier_id": dossier_id,
        "documents": [],
        "articles": [],
        "stats": {
            "nombre_documents": 0,
            "nombre_articles": 0,
            "valeur_totale": 0,
            "montant_ht": 0,
            "montant_tva": 0,
            "valeur_totale_doc": 0,
            "valeur_articles": 0,
            "devise": "USD",
            "poids_total": 0,
            "poids_brut_total": 0,   # ← ajout
            "codes_sh": set(),
        },
    }
    documents = get_documents_by_dossier(dossier_id)
    context["documents"] = documents
    context["stats"]["nombre_documents"] = len(documents)

    montant_ht = sum(_to_float(doc.get("montant_ht", 0)) for doc in documents)
    montant_tva = sum(_to_float(doc.get("montant_tva", 0)) for doc in documents)
    valeur_totale_doc = sum(_to_float(doc.get("valeur_totale_doc", 0)) for doc in documents)
    devise = next((doc.get("devise", "") for doc in documents if doc.get("devise")), "USD")

    total_valeur_articles, total_poids, total_brut = 0, 0, 0
    all_articles, all_codes_sh = [], set()

    for doc in documents:
        for article in get_articles_by_document(doc["id"]):
            all_articles.append(article)
            total_valeur_articles += _to_float(article.get("valeur_devise", 0))
            total_poids  += article.get("poids_net", 0)
            total_brut   += article.get("poids_brut", 0)   # ← ajout
            if article.get("code_sh"):
                all_codes_sh.add(article["code_sh"])

    if valeur_totale_doc <= 0:
        valeur_totale_doc = total_valeur_articles

    context["articles"] = all_articles
    context["stats"]["nombre_articles"]   = len(all_articles)
    context["stats"]["valeur_totale"]     = valeur_totale_doc
    context["stats"]["montant_ht"]        = montant_ht
    context["stats"]["montant_tva"]       = montant_tva
    context["stats"]["valeur_totale_doc"] = valeur_totale_doc
    context["stats"]["valeur_articles"]   = total_valeur_articles
    context["stats"]["devise"]            = devise or "USD"
    context["stats"]["poids_total"]       = total_poids
    context["stats"]["poids_brut_total"]  = total_brut     # ← ajout
    context["stats"]["codes_sh"]          = list(all_codes_sh)
    return context


def detect_anomalies(context: Dict[str, Any]) -> List[str]:
    articles = context.get("articles", [])
    if not articles:
        return []
    anomalies = []
    sans_sh = [a for a in articles if not a.get("code_sh")]
    if sans_sh:
        anomalies.append(f"{len(sans_sh)} article(s) sans code SH")
    zero_qte = [a for a in articles if a.get("quantite", 0) <= 0]
    if zero_qte:
        anomalies.append(f"{len(zero_qte)} article(s) avec quantité nulle")
    for a in articles:
        val   = a.get("valeur_devise", 0)
        poids = a.get("poids_net", 0)
        if val > 10_000_000:
            anomalies.append(f"Valeur très élevée — {a.get('designation','N/A')[:30]}")
        if poids > 0 and val > 0 and (val / poids) > 100_000:
            anomalies.append(f"Ratio valeur/poids anormal — {a.get('designation','N/A')[:30]}")
    return anomalies


def get_suggestions() -> List[dict]:
    return [
        {"label": "Résumé du dossier",       "prompt": "Fais un résumé complet de ce dossier douanier"},
        {"label": "Liste des articles",       "prompt": "Liste tous les articles avec leurs caractéristiques"},
        {"label": "Analyse financière",       "prompt": "Analyse le montant HT, la TVA, le total TTC et la somme des lignes articles du dossier"},
        {"label": "Bilan poids & quantités",  "prompt": "Donne le bilan des poids brut, poids net et quantités"},
        {"label": "Contrôle des codes SH",    "prompt": "Vérifie et liste tous les codes SH, signale les manquants"},
        {"label": "Détecter les anomalies",   "prompt": "Identifie toutes les incohérences ou anomalies dans les données"},
    ]


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    if not context or context["stats"]["nombre_articles"] == 0:
        return "Aucun article trouvé dans ce dossier."
    devise = context["stats"].get("devise", "USD")
    parts = [
        f"Dossier ID: {context['dossier_id']}",
        f"Documents: {context['stats']['nombre_documents']}",
        f"Articles: {context['stats']['nombre_articles']}",
        f"Montant HT: {format_currency(context['stats']['montant_ht'], devise)}",
        f"TVA: {format_currency(context['stats']['montant_tva'], devise)}",
        f"Total TTC extrait du document: {format_currency(context['stats']['valeur_totale_doc'], devise)}",
        f"Somme des lignes articles: {format_currency(context['stats']['valeur_articles'], devise)}",
        f"Poids net total: {context['stats']['poids_total']:.2f} kg",
        f"Poids brut total: {context['stats']['poids_brut_total']:.2f} kg",   # ← ajout
    ]
    if context["stats"]["codes_sh"]:
        parts.append(f"Codes SH: {', '.join(context['stats']['codes_sh'])}")
    parts.append("\n--- ARTICLES ---")
    for a in context["articles"]:
        parts.append(
            f"• {a.get('designation','N/A')} | Qté: {a.get('quantite',0)} "
            f"{a.get('unite','')} | "
            f"Poids net: {a.get('poids_net',0)} kg | "
            f"Poids brut: {a.get('poids_brut',0)} kg | "   # ← ajout
            f"Valeur ligne: {format_currency(a.get('valeur_devise',0), devise)} | "
            f"Code SH: {a.get('code_sh','N/A')}"
        )
    return "\n".join(parts)


def ask_groq(messages: List[Dict[str, str]], context_str: str) -> str:
    try:
        client = get_groq_client()
        system_prompt = f"""Tu es un expert senior en transit douanier et import/export.
Tu analyses les dossiers douaniers avec précision et professionnalisme.

Contexte du dossier actif :
{context_str}

Instructions :
- Base-toi uniquement sur les données fournies
- Si une information est absente, indique-le clairement
- Sois précis, structuré et professionnel
- Utilise des tableaux ou listes si cela améliore la lisibilité"""

        api_messages = [{"role": "system", "content": system_prompt}] + messages
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=api_messages,
            temperature=0.2,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur : {str(e)}"


# ─── MAIN UI ──────────────────────────────────────────────────────────────────

def show_chat_assistant():
    st.markdown("""
    <style>
    /* ── Reset ── */
    .stApp { background: #ffffff !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }

    html, body, [class*="st-"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    [data-testid="stHorizontalBlock"] { gap: 0 !important; }

    /* ── Sidebar ── */
    .sidebar-header {
        padding: 20px 16px 14px;
        border-bottom: 1px solid #f0f0f0;
    }
    .brand {
        font-size: 15px;
        font-weight: 600;
        color: #111;
        display: flex;
        align-items: center;
        gap: 9px;
    }
    .brand-dot {
        width: 28px; height: 28px;
        background: #111;
        border-radius: 7px;
        display: flex; align-items: center; justify-content: center;
        font-size: 13px; color: #fff; flex-shrink: 0;
    }
    .section-label {
        padding: 14px 16px 6px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #aaa;
        font-weight: 600;
    }

    /* Stats */
    .stat-block {
        margin: 0 12px 10px;
        border: 1px solid #ebebeb;
        border-radius: 10px;
        overflow: hidden;
    }
    .stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 14px;
        border-bottom: 1px solid #f4f4f4;
        font-size: 12.5px;
    }
    .stat-row:last-child { border-bottom: none; }
    .stat-key { color: #999; }
    .stat-val { color: #111; font-weight: 500; font-variant-numeric: tabular-nums; }

    /* Alerts */
    .alert-block {
        margin: 0 12px 10px;
        background: #fff8f8;
        border: 1px solid #fde0e0;
        border-radius: 10px;
        padding: 10px 14px;
    }
    .alert-title {
        font-size: 11px; font-weight: 600;
        color: #e53e3e; text-transform: uppercase;
        letter-spacing: 0.5px; margin-bottom: 6px;
    }
    .alert-item {
        font-size: 12px; color: #c53030;
        padding: 2px 0; line-height: 1.4;
    }

    /* ── Main panel ── */
    .topbar {
        height: 50px;
        display: flex; align-items: center;
        padding: 0 24px;
        border-bottom: 1px solid #f0f0f0;
        gap: 10px;
    }
    .topbar-title { font-size: 14px; font-weight: 500; color: #333; }
    .topbar-badge {
        margin-left: auto;
        background: #f5f5f5;
        border: 1px solid #e8e8e8;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 12px;
        color: #666;
    }
    .status-dot {
        display: inline-block; width: 6px; height: 6px;
        background: #22c55e; border-radius: 50%;
        margin-right: 6px; vertical-align: middle;
    }

    /* Empty state */
    .empty-state {
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        padding: 56px 24px 24px; text-align: center;
    }
    .empty-icon {
        width: 50px; height: 50px;
        border-radius: 12px;
        background: #f5f5f5;
        border: 1px solid #e8e8e8;
        display: flex; align-items: center; justify-content: center;
        font-size: 22px; margin-bottom: 16px;
    }
    .empty-title { font-size: 20px; font-weight: 600; color: #111; margin-bottom: 6px; }
    .empty-sub { font-size: 13px; color: #888; line-height: 1.6; max-width: 360px; }

    /* Messages */
    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        max-width: 780px;
        margin: 0 auto !important;
        width: 100%;
    }
    [data-testid="stChatMessageContent"] p {
        color: #222 !important;
        font-size: 14px !important;
        line-height: 1.7 !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        background: #f5f5f5 !important;
        border: 1px solid #e8e8e8 !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
    }

    /* Input */
    [data-testid="stChatInput"] {
        background: #fff !important;
        border: 1px solid #ddd !important;
        border-radius: 10px !important;
        max-width: 780px !important;
        margin: 0 auto !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #999 !important;
        box-shadow: none !important;
    }
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        color: #111 !important;
        font-size: 14px !important;
    }
    [data-testid="stChatInput"] button {
        background: #111 !important;
        border-radius: 7px !important;
        color: #fff !important;
    }

    /* Selectbox */
    [data-testid="stSelectbox"] > label { display: none !important; }
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: #fff !important;
        border: 1px solid #e8e8e8 !important;
        border-radius: 8px !important;
        color: #333 !important;
        font-size: 13px !important;
    }

    /* Suggestion buttons */
    button[kind="tertiary"] {
        background: #fafafa !important;
        border: 1px solid #e8e8e8 !important;
        border-radius: 9px !important;
        color: #444 !important;
        font-size: 13px !important;
        text-align: left !important;
        padding: 10px 14px !important;
    }
    button[kind="tertiary"]:hover {
        background: #f0f0f0 !important;
        border-color: #ccc !important;
        color: #111 !important;
    }

    /* Clear button */
    button[kind="secondary"] {
        background: #fff !important;
        color: #999 !important;
        border: 1px solid #e8e8e8 !important;
        border-radius: 8px !important;
        font-size: 12px !important;
    }
    button[kind="secondary"]:hover {
        border-color: #e53e3e !important;
        color: #e53e3e !important;
    }

    .disclaimer {
        text-align: center;
        font-size: 11px;
        color: #bbb;
        padding: 6px 0 12px;
    }

    [data-testid="stSpinner"] p { color: #888 !important; font-size: 13px !important; }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-thumb { background: #ddd; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

    # ── Guard ──
    dossiers = get_current_user_dossiers()
    if not dossiers:
        st.markdown("""
        <div style="height:80vh;display:flex;flex-direction:column;
                    align-items:center;justify-content:center;gap:12px;text-align:center;">
            <div style="font-size:36px;">📂</div>
            <div style="font-size:18px;font-weight:600;color:#111;">Aucun dossier disponible</div>
            <div style="font-size:13px;color:#888;">
                Téléversez des documents depuis la page d'import pour commencer.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Session ──
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "current_dossier_id" not in st.session_state:
        st.session_state.current_dossier_id = None

    dossier_options = {f"{d['ref_interne']}  ·  ID {d['id']}": d["id"] for d in dossiers}
    if st.session_state.current_dossier_id not in dossier_options.values():
        st.session_state.current_dossier_id = list(dossier_options.values())[0]

    suggestions = get_suggestions()

    sidebar_col, main_col = st.columns([0.9, 3.8], gap="small")

    # ════════════════════════════════
    # SIDEBAR
    # ════════════════════════════════
    with sidebar_col:
        st.markdown("""
        <div class="sidebar-header">
            <div class="brand">
                <div class="brand-dot">⚓</div>
                Assistant IA
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-label">Dossier actif</div>', unsafe_allow_html=True)
        selected_label = st.selectbox(
            "dossier", options=list(dossier_options.keys()),
            index=list(dossier_options.values()).index(st.session_state.current_dossier_id)
                  if st.session_state.current_dossier_id in dossier_options.values() else 0,
            key="chat_dossier_selector", label_visibility="collapsed",
        )
        new_dossier_id = dossier_options[selected_label]

        if new_dossier_id != st.session_state.current_dossier_id:
            st.session_state.current_dossier_id = new_dossier_id
            st.session_state.chat_messages = []
            st.rerun()

        dossier_id  = st.session_state.current_dossier_id
        context     = build_context(dossier_id)
        context_str = format_context_for_prompt(context)
        anomalies   = detect_anomalies(context)

        st.markdown('<div class="section-label">Statistiques</div>', unsafe_allow_html=True)
        devise     = context["stats"].get("devise", "USD")
        ht         = format_currency(context["stats"]["montant_ht"], devise)
        tva        = format_currency(context["stats"]["montant_tva"], devise)
        total_ttc  = format_currency(context["stats"]["valeur_totale_doc"], devise)
        poids_net  = f"{context['stats']['poids_total']:.1f} kg"
        poids_brut = f"{context['stats']['poids_brut_total']:.1f} kg"   # ← ajout
        st.markdown(f"""
        <div class="stat-block">
            <div class="stat-row">
                <span class="stat-key">Documents</span>
                <span class="stat-val">{context['stats']['nombre_documents']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">Articles</span>
                <span class="stat-val">{context['stats']['nombre_articles']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">Montant HT</span>
                <span class="stat-val">{ht}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">TVA</span>
                <span class="stat-val">{tva}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">Total TTC</span>
                <span class="stat-val">{total_ttc}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">Poids net</span>
                <span class="stat-val">{poids_net}</span>
            </div>
            <div class="stat-row">
                <span class="stat-key">Poids brut</span>
                <span class="stat-val">{poids_brut}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        if anomalies:
            st.markdown('<div class="section-label">Alertes</div>', unsafe_allow_html=True)
            items = "".join(f'<div class="alert-item">· {a}</div>' for a in anomalies[:4])
            extra = (f'<div class="alert-item" style="opacity:.6">+ {len(anomalies)-4} autres</div>'
                     if len(anomalies) > 4 else "")
            st.markdown(f"""
            <div class="alert-block">
                <div class="alert-title">⚠ {len(anomalies)} anomalie(s)</div>
                {items}{extra}
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.session_state.chat_messages:
            if st.button("Effacer la conversation", key="clear_btn",
                         type="secondary", use_container_width=True):
                st.session_state.chat_messages = []
                st.rerun()

    # ════════════════════════════════
    # MAIN PANEL
    # ════════════════════════════════
    with main_col:
        dossier_short = selected_label.split("·")[0].strip()
        n_art = context["stats"]["nombre_articles"]
        st.markdown(f"""
        <div class="topbar">
            <span class="topbar-badge">
                <span class="status-dot"></span>
                {dossier_short} &nbsp;·&nbsp; {n_art} article{'s' if n_art>1 else ''}
            </span>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if not st.session_state.chat_messages:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">⚓</div>
                <div class="empty-title">Comment puis-je vous aider ?</div>
                <div class="empty-sub">
                    Posez une question sur votre dossier ou choisissez une analyse ci-dessous.
                </div>
            </div>""", unsafe_allow_html=True)

            cols = st.columns(2)
            for i, s in enumerate(suggestions):
                with cols[i % 2]:
                    if st.button(s["label"], key=f"sug_{i}",
                                 type="tertiary", use_container_width=True):
                        _send_message(s["prompt"], context_str)
        else:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"],
                                     avatar="👤" if msg["role"] == "user" else "⚓"):
                    st.markdown(msg["content"])

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        user_input = st.chat_input("Posez une question sur ce dossier…", key="chat_input_main")
        st.markdown(
            "<div class='disclaimer'>Réponses générées à partir des données du dossier uniquement.</div>",
            unsafe_allow_html=True,
        )

        if user_input:
            _send_message(user_input, context_str)


def _send_message(prompt: str, context_str: str):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_messages
        if m["role"] in ("user", "assistant")
    ]
    with st.spinner("Analyse en cours…"):
        response = ask_groq(api_messages, context_str)
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()
