import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "transit_douanier.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _raise_sqlite_error(action, error):
    raise RuntimeError(f"Erreur SQLite lors de {action} : {error}") from error


def init_lignes_douanieres_table():
    """Cree la table si elle n'existe pas."""
    try:
        with closing(_get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS lignes_douanieres (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        dossier_id   INTEGER DEFAULT 0,
                        qte          REAL    DEFAULT 0,
                        desi         TEXT    NOT NULL,
                        hs           TEXT    NOT NULL,
                        val          REAL    DEFAULT 0,
                        pn           TEXT    DEFAULT '',
                        date_ajout   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
    except sqlite3.Error as e:
        _raise_sqlite_error("la creation de la table lignes_douanieres", e)


def add_ligne(dossier_id=0, qte=0, desi="", hs="", val=0, pn="") -> int:
    """Insere une ligne, retourne l'id cree."""
    try:
        with closing(_get_connection()) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO lignes_douanieres (dossier_id, qte, desi, hs, val, pn)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(dossier_id or 0),
                        float(qte or 0),
                        str(desi or ""),
                        str(hs or ""),
                        float(val or 0),
                        str(pn or ""),
                    ),
                )
                return int(cursor.lastrowid)
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("l'ajout d'une ligne douaniere", e)


def get_lignes(dossier_id=None) -> list[dict]:
    try:
        with closing(_get_connection()) as conn:
            if dossier_id is None or dossier_id == 0:
                rows = conn.execute(
                    """
                    SELECT id, dossier_id, qte, desi, hs, val, pn
                    FROM lignes_douanieres
                    ORDER BY id ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, dossier_id, qte, desi, hs, val, pn
                    FROM lignes_douanieres
                    WHERE dossier_id = ?
                    ORDER BY id ASC
                    """,
                    (int(dossier_id),),
                ).fetchall()
            return [dict(row) for row in rows]
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("la lecture des lignes douanieres", e)


def update_ligne(ligne_id, qte, desi, hs, val, pn):
    """Met a jour une ligne existante par son id."""
    try:
        with closing(_get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE lignes_douanieres
                    SET qte = ?, desi = ?, hs = ?, val = ?, pn = ?
                    WHERE id = ?
                    """,
                    (
                        float(qte or 0),
                        str(desi or ""),
                        str(hs or ""),
                        float(val or 0),
                        str(pn or ""),
                        int(ligne_id),
                    ),
                )
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("la mise a jour d'une ligne douaniere", e)


def delete_ligne(ligne_id):
    """Supprime une ligne par son id."""
    try:
        with closing(_get_connection()) as conn:
            with conn:
                conn.execute(
                    "DELETE FROM lignes_douanieres WHERE id = ?",
                    (int(ligne_id),),
                )
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("la suppression d'une ligne douaniere", e)


def delete_all_lignes(dossier_id=None):
    try:
        with closing(_get_connection()) as conn:
            with conn:
                if dossier_id is None or dossier_id == 0:
                    conn.execute("DELETE FROM lignes_douanieres")
                else:
                    conn.execute(
                        "DELETE FROM lignes_douanieres WHERE dossier_id = ?",
                        (int(dossier_id),),
                    )
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("la suppression des lignes douanieres", e)


def get_recap_by_hs(dossier_id=None) -> list[dict]:
    """
    Recapitulatif groupe par code HS exact.
    Le champ hs reste toujours textuel et le GROUP BY porte sur sa valeur exacte.
    """
    try:
        with closing(_get_connection()) as conn:
            query = """
                SELECT
                    hs,
                    SUM(qte)  AS qte_total,
                    SUM(val)  AS val_total,
                    GROUP_CONCAT(CASE WHEN pn != '' THEN pn END, ' / ') AS pn_liste,
                    COUNT(*)  AS nb_lignes
                FROM lignes_douanieres
            """
            params = ()
            if dossier_id is not None and dossier_id != 0:
                query += " WHERE dossier_id = ?"
                params = (int(dossier_id),)
            query += " GROUP BY hs ORDER BY hs ASC"
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    except (sqlite3.Error, ValueError, TypeError) as e:
        _raise_sqlite_error("la generation du recapitulatif par code HS", e)
