import streamlit as st
from utils.database import (
    consume_reset_code,
    create_reset_code,
    create_user,
    get_user_by_email,
    init_database,
    update_user_password,
    verify_reset_code,
    verify_password,
)
from utils.email_sender import send_verification_code
from utils.auth_cookie import set_auth_cookie


def show_auth_page():
    init_database()

    st.markdown("""
    <style>
    [data-testid="stAppDeployButton"] {
        display: none !important;
    }          
    </style>
    """, unsafe_allow_html=True)

    left, center, right = st.columns([1, 2, 1])
    with center:
        st.image("sutra.png", use_container_width=True)
        st.caption("Connexion sécurisée")

        # ✅ 3 tabs au lieu de 2
        tab_login, tab_reset, tab_register = st.tabs([
            "Connexion",
            "Mot de passe oublié",
            "Inscription"
        ])

        with tab_login:
            show_login()
        with tab_reset:
            show_forgot_password()
        with tab_register:
            show_register()


def show_login():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", type="primary")

    if submitted:
        if not email or not password:
            st.error("Email et mot de passe requis.")
            return

        user = verify_password(email, password)
        if user:
            st.session_state["user"] = user
            # Créer le cookie d'authentification persistante
            set_auth_cookie(user)
            st.success("Connexion réussie.")
            st.rerun()
        else:
            st.error("Identifiants invalides.")


def show_forgot_password():
    st.markdown("##### Réinitialiser votre mot de passe")
    st.caption("Entrez votre email pour recevoir un code de vérification.")

    if "reset_email" not in st.session_state:
        st.session_state["reset_email"] = ""
    if "reset_code_sent" not in st.session_state:
        st.session_state["reset_code_sent"] = False

    with st.form("forgot_request_code_form"):
        email = st.text_input(
            "Email du compte",
            value=st.session_state["reset_email"],
            key="forgot_email",
        )
        request_submitted = st.form_submit_button("Envoyer le code", type="primary")

    if request_submitted:
        if not email:
            st.error("Email requis.")
            return

        normalized_email = email.strip().lower()
        user = get_user_by_email(normalized_email)
        if not user:
            # Message neutre pour ne pas révéler si l'email existe
            st.session_state["reset_email"] = normalized_email
            st.session_state["reset_code_sent"] = False
            st.warning("Si cet email est enregistré, un code de vérification sera envoyé.")
            return

        code = create_reset_code(normalized_email)
        if send_verification_code(normalized_email, code):
            st.session_state["reset_email"] = normalized_email
            st.session_state["reset_code_sent"] = True
            st.success("Code de vérification envoyé par email.")
        else:
            st.session_state["reset_code_sent"] = False
            st.error("Impossible d'envoyer le code. Vérifiez la configuration Resend.")
            return

    if not st.session_state["reset_code_sent"]:
        return

    st.markdown("##### Confirmer le code")
    st.caption("Saisissez le code reçu par email, puis choisissez un nouveau mot de passe.")

    with st.form("forgot_verify_code_form"):
        code = st.text_input("Code de vérification", max_chars=6)
        new_pass = st.text_input("Nouveau mot de passe", type="password")
        confirm = st.text_input("Confirmer le mot de passe", type="password")
        reset_submitted = st.form_submit_button("Réinitialiser", type="primary")

    if reset_submitted:
        email = st.session_state["reset_email"]

        if not code or not new_pass or not confirm:
            st.error("Tous les champs sont requis.")
            return

        if new_pass != confirm:
            st.error("Les mots de passe ne correspondent pas.")
            return

        if len(new_pass) < 6:
            st.error("Le mot de passe doit contenir au moins 6 caractères.")
            return

        if not verify_reset_code(email, code):
            st.error("Code invalide ou expiré.")
            return

        success = update_user_password(email, new_pass)
        if success:
            consume_reset_code(email, code)
            st.session_state["reset_email"] = ""
            st.session_state["reset_code_sent"] = False
            st.success("Mot de passe mis à jour. Vous pouvez vous connecter.")
        else:
            st.error("Une erreur est survenue. Réessayez.")


def show_register():
    with st.form("register_form"):
        username = st.text_input("Nom utilisateur")
        email    = st.text_input("Email", key="register_email")
        password = st.text_input("Mot de passe", type="password", key="register_password")
        confirm  = st.text_input("Confirmer le mot de passe", type="password")
        submitted = st.form_submit_button("Créer le compte", type="primary")

    if submitted:
        if not username or not email or not password or not confirm:
            st.error("Tous les champs sont requis.")
            return
        if password != confirm:
            st.error("Les mots de passe ne correspondent pas.")
            return
        if get_user_by_email(email):
            st.error("Cet email est déjà utilisé.")
            return

        user_id = create_user(username, email, password)
        if user_id:
            st.success("Compte créé. Vous pouvez vous connecter.")
        else:
            st.error("Impossible de créer le compte.")
