"""
utils/auth_cookie.py — Authentification persistante via cookies sécurisés.

Fonctionnalités :
    - Chiffrement/signature des données utilisateur avec Fernet (cryptographie symétrique)
    - Stockage dans un cookie navigateur via JavaScript injecté
    - Synchronisation automatique cookie → st.query_params → st.session_state
    - Résistant aux F5, rechargements, redéploiements Streamlit Cloud

Architecture :
    1. Connexion  → encrypt_user_data() → st.query_params + JS cookie
    2. Navigation → restore_session_from_cookie() lit st.query_params
    3. F5 / logo → JS lit le cookie → redirige avec ?auth_token=... → Python restaure
    4. Déconnexion → clear_auth_cookie() supprime cookie + query_params
"""

import streamlit as st
import json
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# ── Constantes ────────────────────────────────────────────────────────────────
COOKIE_NAME = "sutra_auth_token"
"""Nom du cookie et clé dans st.query_params."""


# ── Clé de chiffrement ────────────────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    """Dérive une clé Fernet valide (32 bytes, base64 URL safe) depuis le secret.

    La clé est générée par SHA256(secret) → base64 pour respecter le format
    requis par Fernet (32 bytes encodés en base64 URL safe).
    """
    try:
        secret = st.secrets["auth"]["cookie_secret_key"]
    except (KeyError, AttributeError):
        # Mode développement uniquement — toujours définir dans secrets.toml
        secret = "sutra-default-dev-secret-key-change-in-production"
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _get_cipher():
    """Retourne une instance Fernet prête à chiffrer/déchiffrer."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        st.error(
            "La bibliothèque 'cryptography' est requise. "
            "Exécutez : pip install cryptography"
        )
        st.stop()

    return Fernet(_get_fernet_key())


# ── Durée de vie ──────────────────────────────────────────────────────────────

def get_cookie_max_age_days() -> int:
    """Retourne la durée de validité du cookie (en jours) depuis secrets.toml."""
    try:
        return int(st.secrets["auth"].get("cookie_max_age_days", 30))
    except (KeyError, AttributeError, ValueError):
        return 30  # 30 jours par défaut


# ── Chiffrement / Déchiffrement ───────────────────────────────────────────────

def encrypt_user_data(user: Dict[str, Any]) -> str:
    """Chiffre les données utilisateur dans un token sécurisé.

    Seules les informations non sensibles sont stockées :
        - id, username, email, role
        - date d'expiration

    Args:
        user: Dictionnaire utilisateur (doit contenir id, username, email, role)

    Returns:
        Token chiffré (chaîne base64 URL safe)
    """
    cipher = _get_cipher()
    max_age_days = get_cookie_max_age_days()

    payload = {
        "id":      user.get("id"),
        "username": user.get("username"),
        "email":   user.get("email"),
        "role":    user.get("role"),
        "exp":     (datetime.now() + timedelta(days=max_age_days)).isoformat(),
    }
    return cipher.encrypt(json.dumps(payload).encode()).decode()


def decrypt_user_data(token: str) -> Optional[Dict[str, Any]]:
    """Déchiffre et vérifie un token de session.

    Retourne le dictionnaire utilisateur si le token est valide et non expiré.
    Retourne None si le token est invalide, altéré, ou expiré.

    Args:
        token: Token chiffré à déchiffrer

    Returns:
        Dictionnaire utilisateur ou None
    """
    if not token or not isinstance(token, str):
        return None

    try:
        cipher = _get_cipher()
        data = json.loads(cipher.decrypt(token.encode()).decode())

        # Vérification de l'expiration
        exp_str = data.get("exp", "")
        if not exp_str:
            return None
        exp = datetime.fromisoformat(exp_str)
        if datetime.now() > exp:
            return None  # Token expiré

        # Reconstruction du dictionnaire utilisateur (sans le hash)
        return {
            "id":       data.get("id"),
            "username": data.get("username"),
            "email":    data.get("email"),
            "role":     data.get("role"),
        }
    except Exception:
        return None  # Token invalide, altéré, ou erreur de déchiffrement


# ── Gestion du cookie navigateur (via JavaScript injecté) ─────────────────────

def _inject_cookie_script(action: str = "set", token: str = "") -> None:
    """Injecte un script JavaScript pour gérer le cookie navigateur.

    Le script est exécuté côté client. Il ne bloque pas le rendu Streamlit.

    Args:
        action: "set"   → écrire/créer le cookie avec le token fourni
                "clear" → supprimer le cookie
                "sync"  → lire le cookie et rediriger si non présent dans l'URL
        token:  Token à stocker (uniquement pour action="set")
    """
    max_age_seconds = get_cookie_max_age_days() * 86400

    if action == "set" and token:
        js = f"""
        <script>
        (function() {{
            var cookie = "{COOKIE_NAME}" + "=" + "{token}" +
                        "; max-age=" + {max_age_seconds} +
                        "; path=/; SameSite=Lax";
            document.cookie = cookie;
        }})();
        </script>
        """
    elif action == "clear":
        js = f"""
        <script>
        (function() {{
            document.cookie = "{COOKIE_NAME}=; max-age=0; path=/; SameSite=Lax";
        }})();
        </script>
        """
    else:  # action == "sync"
        js = f"""
        <script>
        (function() {{
            function getCookie(name) {{
                var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
                return match ? match[2] : null;
            }}
            var token = getCookie("{COOKIE_NAME}");
            var params = new URLSearchParams(window.location.search);
            if (token && !params.get("{COOKIE_NAME}")) {{
                params.set("{COOKIE_NAME}", token);
                window.location.search = params.toString();
            }}
        }})();
        </script>
        """

    st.markdown(js, unsafe_allow_html=True)


# ── API publique ──────────────────────────────────────────────────────────────

def set_auth_cookie(user: Dict[str, Any]) -> None:
    """Enregistre le token d'authentification après une connexion réussie.

    Écrit le token dans :
        1. st.query_params (visible immédiatement par Python)
        2. Cookie navigateur (persistant après F5 / rechargement)

    Args:
        user: Dictionnaire utilisateur (depuis verify_password)
    """
    token = encrypt_user_data(user)

    # 1. Stocker dans les query params (visible immédiatement par Python)
    st.query_params[COOKIE_NAME] = token

    # 2. Injecter JS pour écrire le cookie navigateur
    _inject_cookie_script(action="set", token=token)


def clear_auth_cookie() -> None:
    """Supprime le cookie d'authentification (déconnexion).

    Nettoie à la fois st.query_params et le cookie navigateur.
    """
    # 1. Supprimer des query params
    if COOKIE_NAME in st.query_params:
        del st.query_params[COOKIE_NAME]

    # 2. Injecter JS pour supprimer le cookie navigateur
    _inject_cookie_script(action="clear")


def restore_session_from_cookie() -> Optional[Dict[str, Any]]:
    """Tente de restaurer la session utilisateur depuis le cookie.

    Ordre de vérification :
        1. st.query_params (token présent dans l'URL actuelle)
        2. Cookie navigateur (via JS → redirection → nouvelle requête)

    À appeler au tout début de app.py, AVANT le check classique
    ``if "user" not in st.session_state``.

    Returns:
        Dictionnaire utilisateur si un token valide est trouvé, None sinon.
    """
    # Étape 1 : Vérifier les query params (token déjà dans l'URL)
    token = st.query_params.get(COOKIE_NAME)
    if token:
        user = decrypt_user_data(token)
        if user:
            return user

    # Étape 2 : Aucun token valide dans l'URL.
    #           Injecter JS pour lire le cookie et rediriger si nécessaire.
    _inject_cookie_script(action="sync")
    return None