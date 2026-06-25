import sqlite3
import os
import random
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, List, Dict, Any
import streamlit as st
import hashlib

try:
    import bcrypt
except Exception:
    bcrypt = None

# Chemin de la base de données
DB_PATH = Path(__file__).parent.parent / "transit_douanier.db"

def get_db_connection():
    """Établit une connexion à la base de données SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user')),
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table dossiers_transit
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dossiers_transit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_interne TEXT UNIQUE NOT NULL,
            statut TEXT DEFAULT 'En cours',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table documents_commerciaux
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents_commerciaux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id INTEGER NOT NULL,
            type_document TEXT NOT NULL,
            chemin_fichier TEXT NOT NULL,
            date_import TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dossier_id) REFERENCES dossiers_transit (id) ON DELETE CASCADE
        )
    ''')

    # Table articles_extraits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles_extraits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            num_ligne INTEGER NOT NULL,
            designation TEXT,
            code_sh TEXT,
            quantite REAL DEFAULT 0,
            poids_net REAL DEFAULT 0,
            valeur_devise REAL DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents_commerciaux (id) ON DELETE CASCADE
        )
    ''')

    # Table password_reset_codes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS excel_lignes_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id INTEGER DEFAULT 0,
            source_fichier TEXT DEFAULT '',
            qte REAL DEFAULT 0,
            desi TEXT DEFAULT '',
            hs TEXT DEFAULT '',
            val REAL DEFAULT 0,
            poids_net REAL DEFAULT 0,
            pn TEXT DEFAULT '',
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS excel_recap_hs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id INTEGER DEFAULT 0,
            hs TEXT DEFAULT '',
            desi TEXT DEFAULT '',
            qte_total REAL DEFAULT 0,
            val_total REAL DEFAULT 0,
            poids_net_total REAL DEFAULT 0,
            pn_liste TEXT DEFAULT '',
            nb_lignes INTEGER DEFAULT 0,
            date_calcul TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS excel_poids_packing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id INTEGER NOT NULL,
            source_fichier TEXT,
            desi TEXT,
            pn TEXT,
            qte REAL DEFAULT 0,
            poids_net REAL DEFAULT 0,
            poids_brut REAL DEFAULT 0,
            FOREIGN KEY (dossier_id) REFERENCES dossiers_transit(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

    # Ajout des nouvelles colonnes (sans casser la BD existante)
    _add_dossier_columns()
    _add_document_columns()
    _add_article_columns()
    _add_excel_columns()


def _add_dossier_columns():
    """Ajoute les colonnes manquantes a dossiers_transit."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE dossiers_transit ADD COLUMN user_id INTEGER"
        )
    except Exception:
        pass

    try:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_dossiers_user '
            'ON dossiers_transit(user_id)'
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


def _add_document_columns():
    """Ajoute les colonnes manquantes à documents_commerciaux."""
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = [
        ("numero_document",          "TEXT DEFAULT ''"),
        ("date_document",            "TEXT DEFAULT ''"),
        ("devise",                   "TEXT DEFAULT ''"),
        ("montant_ht",               "REAL DEFAULT 0"),
        ("montant_tva",              "REAL DEFAULT 0"),
        ("valeur_totale_doc",        "REAL DEFAULT 0"),
        ("expediteur_nom",           "TEXT DEFAULT ''"),
        ("expediteur_adresse",       "TEXT DEFAULT ''"),
        ("expediteur_ville",         "TEXT DEFAULT ''"),
        ("expediteur_code_postal",   "TEXT DEFAULT ''"),
        ("expediteur_pays",          "TEXT DEFAULT ''"),
        ("destinataire_nom",         "TEXT DEFAULT ''"),
        ("destinataire_adresse",     "TEXT DEFAULT ''"),
        ("destinataire_ville",       "TEXT DEFAULT ''"),
        ("destinataire_code_postal", "TEXT DEFAULT ''"),
        ("destinataire_pays",        "TEXT DEFAULT ''"),
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(
                f"ALTER TABLE documents_commerciaux ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass  # colonne déjà existante

    # Index ici, connexion encore ouverte
    try:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_documents_dossier '
            'ON documents_commerciaux(dossier_id)'
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


def _add_article_columns():
    """Ajoute les colonnes manquantes à articles_extraits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = [
        ("poids_brut",      "REAL DEFAULT 0"),
        ("valeur_unitaire", "REAL DEFAULT 0"),
        ("unite",           "TEXT DEFAULT ''"),
        ("origine",         "TEXT DEFAULT ''"),
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(
                f"ALTER TABLE articles_extraits ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass  # colonne déjà existante

    # Index ici, connexion encore ouverte
    try:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_articles_document '
            'ON articles_extraits(document_id)'
        )
    except Exception:
        pass

    conn.commit()
    conn.close()  # ← fermeture APRÈS les index


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions CRUD — users
# ═══════════════════════════════════════════════════════════════════════════════

def _add_excel_columns():
    """Ajoute les colonnes manquantes aux tables Excel douanier."""
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = [
        ("excel_lignes_detail", "source_fichier", "TEXT DEFAULT ''"),
        ("excel_lignes_detail", "poids_net", "REAL DEFAULT 0"),
        ("excel_recap_hs", "desi", "TEXT DEFAULT ''"),
        ("excel_recap_hs", "poids_net_total", "REAL DEFAULT 0"),
    ]
    for table_name, col_name, col_type in columns:
        try:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass

    try:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_excel_lignes_dossier '
            'ON excel_lignes_detail(dossier_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_excel_recap_dossier '
            'ON excel_recap_hs(dossier_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_excel_packing_dossier '
            'ON excel_poids_packing(dossier_id)'
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    if bcrypt:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def _check_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("$2") and bcrypt:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            print(f"Erreur verification bcrypt: {e}")
            return False
    if password_hash.startswith("sha256$"):
        return _hash_password(password) == password_hash
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash


def create_user(username: str, email: str, password: str) -> Optional[int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO users (username, email, password_hash, role)
               VALUES (?, ?, ?, ?)''',
            (username.strip(), email.strip().lower(), _hash_password(password), "user")
        )
        user_id = cursor.lastrowid
        conn.commit()
        print(f"Utilisateur cree: {email}")
        return user_id
    except sqlite3.IntegrityError:
        print(f"Email deja utilise: {email}")
        return None
    except Exception as e:
        print(f"Erreur create_user: {e}")
        return None
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_email(email)
    if not user:
        print(f"Login echoue, utilisateur introuvable: {email}")
        return None
    if _check_password(password, user.get("password_hash", "")):
        print(f"Login reussi: {email}")
        user.pop("password_hash", None)
        return user
    print(f"Login echoue, mot de passe invalide: {email}")
    return None

def update_user_password(email: str, new_password: str) -> bool:
    """Met à jour le mot de passe d'un utilisateur par email."""
    hashed = _hash_password(new_password)  
    conn = get_db_connection()  
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hashed, email.strip().lower())  
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erreur update_user_password : {e}")
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions — password_reset_codes (vérification email)
# ═══════════════════════════════════════════════════════════════════════════════

def create_reset_code(email: str) -> str:
    """
    Génère un code à 6 chiffres, l'enregistre en BD (valide 10 minutes)
    et le retourne pour envoi par email.
    Invalide automatiquement les anciens codes non utilisés pour cet email.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Invalider les anciens codes non utilisés pour cet email
    cursor.execute(
        'UPDATE password_reset_codes SET used = 1 WHERE email = ? AND used = 0',
        (email.strip().lower(),)
    )

    code = f"{random.randint(0, 999999):06d}"
    expires_at = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
        'INSERT INTO password_reset_codes (email, code, expires_at) VALUES (?, ?, ?)',
        (email.strip().lower(), code, expires_at)
    )
    conn.commit()
    conn.close()
    return code


def verify_reset_code(email: str, code: str) -> bool:
    """
    Vérifie qu'un code est valide pour cet email :
    - existe
    - non utilisé
    - non expiré
    Retourne True/False. Ne marque PAS le code comme utilisé
    (utiliser consume_reset_code après le changement de mot de passe réussi).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT * FROM password_reset_codes
           WHERE email = ? AND code = ? AND used = 0
           ORDER BY id DESC LIMIT 1''',
        (email.strip().lower(), code.strip())
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False

    expires_at = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
    if datetime.now() > expires_at:
        return False

    return True


def consume_reset_code(email: str, code: str) -> bool:
    """Marque le code comme utilisé (à appeler après changement de mot de passe réussi)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE password_reset_codes SET used = 1
           WHERE email = ? AND code = ? AND used = 0''',
        (email.strip().lower(), code.strip())
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions CRUD — dossiers_transit
# ═══════════════════════════════════════════════════════════════════════════════

def create_dossier(ref_interne: str, statut: str = 'En cours', user_id: Optional[int] = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO dossiers_transit (ref_interne, statut, user_id) VALUES (?, ?, ?)',
        (ref_interne, statut, user_id)
    )
    dossier_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return dossier_id

def get_dossier(dossier_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dossiers_transit WHERE id = ?', (dossier_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_dossier_by_ref(ref_interne: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dossiers_transit WHERE ref_interne = ?', (ref_interne,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_dossiers(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute(
            'SELECT * FROM dossiers_transit WHERE user_id = ? ORDER BY date_creation DESC',
            (user_id,)
        )
    else:
        cursor.execute('SELECT * FROM dossiers_transit ORDER BY date_creation DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_current_user_dossiers() -> List[Dict[str, Any]]:
    user = st.session_state.get("user")
    if not user:
        return []
    if user.get("role") == "admin":
        return get_all_dossiers()
    return get_all_dossiers(user_id=user.get("id"))

def update_dossier_statut(dossier_id: int, statut: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE dossiers_transit SET statut = ? WHERE id = ?',
        (statut, dossier_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_dossier(dossier_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dossiers_transit WHERE id = ?', (dossier_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions CRUD — documents_commerciaux
# ═══════════════════════════════════════════════════════════════════════════════

def create_document(dossier_id: int, type_document: str, chemin_fichier: str,
                    numero_document: str = '', date_document: str = '', devise: str = '',
                    valeur_totale_doc: float = 0, montant_ht: float = 0,
                    montant_tva: float = 0,
                    expediteur_nom: str = '', expediteur_adresse: str = '',
                    expediteur_ville: str = '', expediteur_code_postal: str = '',
                    expediteur_pays: str = '',
                    destinataire_nom: str = '', destinataire_adresse: str = '',
                    destinataire_ville: str = '', destinataire_code_postal: str = '',
                    destinataire_pays: str = '') -> int:
    try:
        _add_document_columns()
    except Exception:
        pass

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO documents_commerciaux
           (dossier_id, type_document, chemin_fichier,
            numero_document, date_document, devise, montant_ht, montant_tva,
            valeur_totale_doc,
            expediteur_nom, expediteur_adresse, expediteur_ville,
            expediteur_code_postal, expediteur_pays,
            destinataire_nom, destinataire_adresse, destinataire_ville,
            destinataire_code_postal, destinataire_pays)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (dossier_id, type_document, chemin_fichier,
         numero_document, date_document, devise, montant_ht, montant_tva,
         valeur_totale_doc,
         expediteur_nom, expediteur_adresse, expediteur_ville,
         expediteur_code_postal, expediteur_pays,
         destinataire_nom, destinataire_adresse, destinataire_ville,
         destinataire_code_postal, destinataire_pays)
    )
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return document_id

def get_document(document_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM documents_commerciaux WHERE id = ?', (document_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_documents_by_dossier(dossier_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM documents_commerciaux WHERE dossier_id = ? ORDER BY date_import',
        (dossier_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_document(document_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM documents_commerciaux WHERE id = ?', (document_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Fonctions CRUD — articles_extraits
# ═══════════════════════════════════════════════════════════════════════════════

def create_article(document_id: int, num_ligne: int, designation: str = '',
                   code_sh: str = '', quantite: float = 0, poids_net: float = 0,
                   valeur_devise: float = 0, poids_brut: float = 0,
                   valeur_unitaire: float = 0, unite: str = '', origine: str = '') -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO articles_extraits
           (document_id, num_ligne, designation, code_sh, quantite, poids_net,
            valeur_devise, poids_brut, valeur_unitaire, unite, origine)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (document_id, num_ligne, designation, code_sh, quantite, poids_net,
         valeur_devise, poids_brut, valeur_unitaire, unite, origine)
    )
    article_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return article_id

def get_articles_by_document(document_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM articles_extraits WHERE document_id = ? ORDER BY num_ligne',
        (document_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_article(article_id: int, **kwargs) -> bool:
    if not kwargs:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    set_clause = ', '.join([f'{key} = ?' for key in kwargs.keys()])
    values = list(kwargs.values())
    values.append(article_id)
    cursor.execute(
        f'UPDATE articles_extraits SET {set_clause} WHERE id = ?',
        values
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_article(article_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM articles_extraits WHERE id = ?', (article_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ═══════════════════════════════════════════════════════════════════════════════
def _decimal_float(value, decimales=2) -> float:
    try:
        d = Decimal(str(value or 0))
        quantize_str = Decimal('0.' + '0' * decimales) if decimales > 0 else Decimal('1')
        return float(d.quantize(quantize_str, rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def get_excel_lignes(dossier_id: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT id, dossier_id, source_fichier, qte, desi, hs, val, poids_net, pn
           FROM excel_lignes_detail
           WHERE dossier_id = ?
           ORDER BY id ASC''',
        (dossier_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_excel_lignes(
    dossier_id: int,
    lignes: List[Dict[str, Any]],
    replace: bool = True
) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    if replace:
        cursor.execute('DELETE FROM excel_lignes_detail WHERE dossier_id = ?', (dossier_id,))

    cursor.executemany(
        '''INSERT INTO excel_lignes_detail
           (dossier_id, source_fichier, qte, desi, hs, val, poids_net, pn)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        [
            (
                dossier_id,
                str(ligne.get("source_fichier", "") or ""),
                _decimal_float(ligne.get("qte", 0), 3),
                str(ligne.get("desi", "") or ""),
                str(ligne.get("hs", "") or ""),
                _decimal_float(ligne.get("val", 0), 2),
                _decimal_float(ligne.get("poids_net", 0), 3),
                str(ligne.get("pn", "") or ""),
            )
            for ligne in lignes
        ]
    )
    conn.commit()
    conn.close()


def delete_excel_lignes(dossier_id: int = 0) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM excel_lignes_detail WHERE dossier_id = ?', (dossier_id,))
    cursor.execute('DELETE FROM excel_recap_hs WHERE dossier_id = ?', (dossier_id,))
    cursor.execute('DELETE FROM excel_poids_packing WHERE dossier_id = ?', (dossier_id,))
    conn.commit()
    conn.close()


def get_excel_recap(dossier_id: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT hs, desi, qte_total, val_total, poids_net_total, pn_liste, nb_lignes
           FROM excel_recap_hs
           WHERE dossier_id = ?
           ORDER BY hs ASC''',
        (dossier_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def calcule_et_sauvegarde_recap(dossier_id: int = 0) -> List[Dict[str, Any]]:
    lignes = get_excel_lignes(dossier_id)
    groupes: Dict[str, List[Dict[str, Any]]] = {}
    for ligne in lignes:
        hs = str(ligne.get("hs", "") or "")
        if hs:
            groupes.setdefault(hs, []).append(ligne)

    recap = []
    for hs in sorted(groupes.keys()):
        lignes_du_groupe = groupes[hs]
        total_qte = sum(Decimal(str(ligne.get("qte") or 0)) for ligne in lignes_du_groupe)
        total_val = sum(Decimal(str(ligne.get("val") or 0)) for ligne in lignes_du_groupe)
        total_poids = sum(
            Decimal(str(ligne.get("poids_net") or 0)) for ligne in lignes_du_groupe
        )
        pn_seen = []
        for ligne in lignes_du_groupe:
            pn = str(ligne.get("pn") or "").strip()
            if pn and pn not in pn_seen:
                pn_seen.append(pn)

        desi_recap = next(
            (str(ligne.get("desi") or "") for ligne in lignes_du_groupe if ligne.get("desi")),
            ""
        )
        recap.append({
            "hs": hs,
            "desi": desi_recap,
            "qte_total": float(total_qte.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
            "val_total": float(total_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "poids_net_total": float(
                total_poids.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            ),
            "pn_liste": " / ".join(pn_seen),
            "nb_lignes": len(lignes_du_groupe),
        })

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM excel_recap_hs WHERE dossier_id = ?', (dossier_id,))
    cursor.executemany(
        '''INSERT INTO excel_recap_hs
           (dossier_id, hs, desi, qte_total, val_total, poids_net_total, pn_liste, nb_lignes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        [
            (
                dossier_id,
                row["hs"],
                row["desi"],
                row["qte_total"],
                row["val_total"],
                row["poids_net_total"],
                row["pn_liste"],
                row["nb_lignes"],
            )
            for row in recap
        ]
    )
    conn.commit()
    conn.close()
    return recap


def save_packing_data(dossier_id: int, lignes: List[Dict[str, Any]]) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM excel_poids_packing WHERE dossier_id = ?', (dossier_id,))
    cursor.executemany(
        '''INSERT INTO excel_poids_packing
           (dossier_id, source_fichier, desi, pn, qte, poids_net, poids_brut)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        [
            (
                dossier_id,
                str(ligne.get("source_fichier", "") or ""),
                str(ligne.get("desi", "") or ""),
                str(ligne.get("pn", "") or ""),
                _decimal_float(ligne.get("qte", 0), 3),
                _decimal_float(ligne.get("poids_net", 0), 3),
                _decimal_float(ligne.get("poids_brut", 0), 3),
            )
            for ligne in lignes
        ]
    )
    conn.commit()
    conn.close()


@st.cache_resource
def init_database():
    """Initialise la base de données (à appeler une seule fois)"""
    init_db()
    return True
