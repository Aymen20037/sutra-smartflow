import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import base64
from auth import show_auth_page

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

st.set_page_config(
    page_title="SUTRA SmartFlow",
    page_icon="sutra logo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "user" not in st.session_state:
    show_auth_page()
    st.stop()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

/* ── Cacher TOUS les éléments Streamlit Cloud & GitHub ── */
header[data-testid="stHeader"]          { display: none !important; }
#MainMenu                                { display: none !important; }
footer                                   { display: none !important; }
[data-testid="stAppDeployButton"]        { display: none !important; }
[data-testid="stToolbar"]               { display: none !important; }
[data-testid="stStatusWidget"]          { display: none !important; }
[data-testid="stDecoration"]            { display: none !important; }
[data-testid="stDeployButton"]          { display: none !important; }
.stDeployButton                          { display: none !important; }
.stAppToolbar                            { display: none !important; }
.stAppDeployButton                       { display: none !important; }
.viewerBadge_container__r5tak           { display: none !important; }
.viewerBadge_link__qRIco                { display: none !important; }
#GithubIcon                             { display: none !important; }
iframe[title="streamlit_cloud_badge"]   { display: none !important; }
a[href*="github.com"]                   { display: none !important; }
a[href*="streamlit.io"]                 { display: none !important; }
button[title="Fork this app"]           { display: none !important; }
button[kind="header"]                   { display: none !important; }

/* ── Style général ───────────────────────────────────── */
* {
    font-family: 'Poppins', sans-serif;
}

body {
    background-color: #F8FAFC;
}

section[data-testid="stSidebar"] {
    background-color: #151A2D !important;
    color: #E0E0E0;
    margin: 16px;
    border-radius: 16px;
    overflow: hidden;
    transition: width 0.4s ease, margin 0.4s ease;
    width: 300px;
    min-width: 200px;
}

section[data-testid="stSidebar"] * {
    color: #E0E0E0 !important;
}

section[data-testid="stSidebar"] .stRadio > div > label {
    display: flex;
    align-items: center;
    padding: 12px 20px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.4s ease, transform 0.2s ease;
}

section[data-testid="stSidebar"] .stRadio > div > label:hover {
    background-color: #FFFFFF;
    color: #151A2D !important;
    transform: translateX(4px);
}

/* User card */
.user-card {
    background: linear-gradient(135deg, #1E2540 0%, #252D47 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 4px 0 8px 0;
    display: flex;
    align-items: center;
    gap: 12px;
}

.user-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4F8EF7, #A259FF);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 17px;
    font-weight: 700;
    color: #fff !important;
    flex-shrink: 0;
}

.user-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
}

.user-name {
    font-size: 14px;
    font-weight: 600;
    color: #F0F4FF !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.user-email {
    font-size: 11px;
    color: #8A93B2 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.user-role-badge {
    display: inline-block;
    margin-top: 4px;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 600;
    background: rgba(79, 142, 247, 0.15);
    color: #4F8EF7 !important;
    border: 1px solid rgba(79, 142, 247, 0.3);
    text-transform: capitalize;
}

/* Bouton déconnexion */
section[data-testid="stSidebar"] div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #EF4444 0%, #F97316 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, #DC2626 0%, #EA580C 100%) !important;
    transform: translateX(2px) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button * {
    color: #FFFFFF !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    user = st.session_state.get("user", {})

    logo_path = BASE_DIR / "sutra.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <a href="/" target="_self" style="display:block; text-align:center;">
                <img src="data:image/png;base64,{logo_b64}" width="220"
                     style="border-radius:8px;" />
            </a>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        "<div style='text-align:center; font-size:12px; color:#AAB3CC;'>Gestion des Opérations Douanières</div>",
        unsafe_allow_html=True
    )

    st.divider()

    username = user.get("username", "")
    email    = user.get("email", "")
    role     = user.get("role", "user")
    initials = "".join(p[0].upper() for p in username.split()[:2]) or "U"

    st.markdown(
        f"""
        <div class="user-card">
            <div class="user-avatar">{initials}</div>
            <div class="user-info">
                <span class="user-name">{username}</span>
                <span class="user-email">{email}</span>
                <span class="user-role-badge">⚙ {role}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    page = st.radio(
        "Navigation",
        [
            " Tableau de bord",
            " Téléversement",
            " Révision",
            " Export",
            " Assistant IA",
            " Déclaration"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    logout = st.button(
        "⎋  Déconnexion",
        key="logout",
        use_container_width=True
    )

    if logout:
        del st.session_state["user"]
        st.rerun()

    st.divider()
    st.caption("Version 1.0")
    st.caption("© SUTRA SmartFlow")

if page == " Tableau de bord":
    from modules.dashboard import show_dashboard
    show_dashboard()

elif page == " Téléversement":
    from modules.uploader import show_uploader
    show_uploader()

elif page == " Révision":
    from modules.review import show_review
    show_review()

elif page == " Export":
    from modules.export import show_export
    show_export()

elif page == " Assistant IA":
    from modules.chat_assistant import show_chat_assistant
    show_chat_assistant()

elif page == " Déclaration":
    from modules.excel_douanier import show_excel_douanier
    show_excel_douanier()