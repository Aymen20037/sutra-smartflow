# Rapport d'analyse complet du projet Streamlit SUTRA SmartFlow

Date de l'analyse : 2026-06-11  

## 1. Portee de lecture effectuee

L'analyse s'appuie sur la structure reelle du dossier et sur les fichiers lus localement.

Fichiers cibles ouverts/inventories :

| Type | Nombre | Taille totale |
|---|---:|---:|
| `.py` | 729 | 9 311 207 octets |
| `.toml` | 1 | 34 octets |
| `.txt` | 8 | 15 073 octets |
| `.env` | 1 | 69 octets |

Le nombre eleve de fichiers Python vient du dossier `venv`, qui embarque principalement `pip`, `setuptools` et leurs dependances vendorees. Ces fichiers tiers ont ete ouverts dans la passe mecanique d'inventaire, mais l'analyse fonctionnelle ci-dessous porte sur le code applicatif du projet : `app.py`, `auth.py`, `modules/` et `utils/`.

Le fichier `.env` a ete lu uniquement pour ses noms de cles, conformement a la demande. Cle presente : `GROQ_API_KEY`.

## 2. Structure racine observee

Elements principaux a la racine :

| Chemin | Role observe |
|---|---|
| `app.py` | Point d'entree Streamlit, configuration UI, sidebar, navigation entre modules |
| `auth.py` | Ecran de connexion, inscription et reinitialisation de mot de passe |
| `requirements.txt` | Dependances Python attendues |
| `.env` | Configuration secrete locale, avec `GROQ_API_KEY` |
| `.streamlit/config.toml` | Configuration Streamlit, `fileWatcherType = "none"` |
| `transit_douanier.db` | Base SQLite embarquee |
| `modules/` | Pages fonctionnelles Streamlit |
| `utils/` | Couche base de donnees, OCR, IA et helpers |
| `uploads/` | Fichiers PDF/JPEG importes |
| `sutra.png`, `sutra logo.png` | Assets graphiques de marque |
| `venv/` | Environnement virtuel inclus dans le projet |
| `__pycache__/`, `modules/__pycache__/`, `utils/__pycache__/` | Caches Python generes |
| `.claude/settings.local.json` | Configuration locale Claude/OpenRouter |

Extensions presentes dans tout le dossier :

| Extension | Nombre |
|---|---:|
| `.py` | 729 |
| `.pyc` | 682 |
| `.exe` | 16 |
| `.txt` | 8 |
| `.pdf` | 6 |
| `.jpeg` | 4 |
| `.png` | 2 |
| `.toml` | 1 |
| `.json` | 1 |
| `.db` | 1 |
| `.env` | 1 |

## 3. Nature generale du projet

Le projet est une application Streamlit nommee **SUTRA SmartFlow**, orientee gestion de dossiers de transit douanier. Elle permet :

- l'authentification locale d'utilisateurs ;
- le televersement de documents douaniers ;
- l'extraction OCR du contenu de PDF/images ;
- l'extraction structuree via IA Groq ;
- la persistance dans SQLite ;
- la revision manuelle d'articles extraits ;
- l'export JSON/XML/CSV ;
- l'interrogation d'un assistant IA contextualise par dossier.

Le flux principal est :

1. `app.py` charge `.env`, configure Streamlit et exige une session utilisateur.
2. `auth.py` initialise SQLite et gere login/inscription/reinitialisation.
3. `modules/uploader.py` sauvegarde les fichiers dans `uploads/`, lance OCR puis Groq.
4. `utils/database.py` cree/alimente les tables `dossiers_transit`, `documents_commerciaux`, `articles_extraits`.
5. `modules/review.py` permet de corriger les articles.
6. `modules/export.py` genere des exports douaniers.
7. `modules/chat_assistant.py` construit un contexte dossier et interroge Groq.

## 4. Technologies et dependances

Dependances declarees dans `requirements.txt` :

- `streamlit==1.45.1`
- `numpy==1.26.4`
- `opencv-python-headless>=4.8.0`
- `pillow>=10.0.0`
- `python-dotenv>=1.0.0`
- `easyocr>=1.7.0`
- `groq>=0.5.0`
- `pymupdf>=1.24.0`
- `plotly>=5.0.0`
- `pytesseract>=0.3.10`
- `bcrypt>=4.0.0`

Dependances utilisees dans le code mais non declarees explicitement dans `requirements.txt` :

- `pandas`, utilise dans `modules/dashboard.py` et `modules/review.py` ;
- `requests`, utilise dans `utils/helpers.py` pour les taux de change ;
- `torch`, importe dynamiquement dans `utils/ocr.py` pour detecter CUDA avant EasyOCR.

Le dossier `venv` existe, mais il semble non portable/casse sur cette machine : `venv/pyvenv.cfg` pointe vers `C:\Users\user\AppData\Local\Programs\Python\Python311`, alors que le projet est ouvert depuis `C:\Users\hp\...`. L'executable `venv\Scripts\python.exe` ne fonctionne donc pas ici.

## 5. Architecture applicative

### `app.py`

Role :

- charge `.env` depuis la racine ;
- configure la page Streamlit ;
- bloque l'acces si `st.session_state["user"]` n'existe pas ;
- injecte beaucoup de CSS ;
- affiche le logo `sutra.png` dans la sidebar ;
- affiche une carte utilisateur ;
- gere la navigation radio vers cinq pages :
  - Tableau de bord ;
  - Televersement ;
  - Revision ;
  - Export ;
  - Assistant IA.

Point notable : le bloc de deconnexion est duplique deux fois :

- premier `if logout: del st.session_state["user"]; st.rerun()`
- second bloc identique juste apres.

Le second bloc est inatteignable en pratique apres `st.rerun()`, mais il reste un doublon clair.

### `auth.py`

Role :

- appelle `init_database()` ;
- affiche trois onglets : connexion, mot de passe oublie, inscription ;
- authentifie par email/mot de passe ;
- stocke l'utilisateur connecte en session Streamlit ;
- cree les utilisateurs avec role `user` ;
- permet une reinitialisation directe du mot de passe.

Points notables :

- il n'y a pas de confirmation par email pour la reinitialisation ;
- le message d'email inconnu est volontairement neutre ;
- la politique de mot de passe se limite a 6 caracteres minimum ;
- l'inscription est ouverte, sans validation d'email ni approbation admin.

### `modules/dashboard.py`

Role :

- recupere les dossiers accessibles a l'utilisateur courant ;
- construit des graphiques Plotly :
  - repartition par statut ;
  - evolution temporelle des creations ;
- affiche une table filtree par statut.

Le dashboard gere correctement le cas sans dossier avec des DataFrames vides et des annotations "Aucune donnee disponible".

### `modules/uploader.py`

Role :

- cree le dossier `uploads/` si besoin ;
- accepte `pdf`, `png`, `jpg`, `jpeg`, `tiff` ;
- cree ou reutilise un dossier de transit ;
- sauvegarde le fichier sous forme `{hash8}_{nom_original}` ;
- detecte approximativement le type documentaire d'apres le nom de fichier ;
- appelle :
  - `extract_text_from_pdf()` pour les PDF ;
  - `extract_text_from_image()` pour les images ;
  - `extract_cusxte()` pour l'extraction IA ;
- cree un enregistrement document ;
- cree les articles extraits ;
- met le statut du dossier a `Documents televerses` si tout reussit.

Points notables :

- `validate_sh_code`, `format_currency`, `json`, `io`, `base64`, `get_articles_by_document` sont importes mais non utilises dans ce fichier ;
- `simulate_ocr_extraction()` existe encore en bas de fichier mais n'est pas appelee ;
- le typage documentaire depend seulement du nom de fichier, pas du contenu ;
- `hashlib.md5` est utilise pour prefixer les fichiers, pas pour une verification de securite ;
- les erreurs de traitement sont affichees mais pas persistees en base.

### `modules/review.py`

Role :

- selectionne automatiquement le dossier courant ou le premier dossier accessible ;
- selectionne automatiquement le document le plus recent du dossier ;
- charge les articles ;
- affiche un `st.data_editor` modifiable ;
- sauvegarde les modifications via `update_article()` ;
- affiche des totaux poids/valeur ;
- valide seulement un seuil de poids net total `MAX_WEIGHT = 1000`.

Limitation notable : si l'utilisateur ajoute des lignes dans `st.data_editor`, elles sont ignorees a la sauvegarde car le code fait `if idx >= len(articles): continue`. L'interface autorise donc visuellement des lignes dynamiques, mais seules les lignes existantes sont mises a jour.

### `modules/export.py`

Role :

- exige un dossier actif en session ;
- verifie que ce dossier fait partie des dossiers accessibles a l'utilisateur ;
- agrège les documents et articles ;
- calcule poids net, valeur totale USD et valeur totale MAD ;
- affiche des controles metier simples ;
- genere JSON, XML ou CSV telechargeable.

Points notables :

- le module importe `get_exchange_rates` mais ne l'utilise pas ;
- il definit son propre `convert_currency()` avec taux statiques, alors que `utils/helpers.py` contient deja une conversion avec API de taux ;
- la conversion locale utilise `{'USD': 1.0, 'EUR': 1.08, 'MAD': 0.10}` et convertit USD vers MAD par division, donc 1 USD devient 10 MAD ;
- les exports prennent souvent le premier document comme source des informations expediteur/destinataire ;
- la devise reelle extraite par document n'est pas utilisee pour recalculer les valeurs : l'export traite la somme comme USD.

### `modules/chat_assistant.py`

Role :

- construit un contexte complet d'un dossier :
  - documents ;
  - articles ;
  - nombre de documents/articles ;
  - valeur totale ;
  - poids net/brut ;
  - codes SH ;
- detecte quelques anomalies simples :
  - articles sans code SH ;
  - quantite nulle ;
  - valeur tres elevee ;
  - ratio valeur/poids anormal ;
- propose des prompts rapides ;
- interroge Groq avec `llama-3.3-70b-versatile`.

Point confirme dans le code : ligne contenant un `V` isole avant le `span` de la topbar :

```html
<div class="topbar">
V            <span class="topbar-badge">
```

Ce `V` sera rendu comme texte parasite dans l'interface.

## 6. Couche utilitaire

### `utils/database.py`

Role :

- fournit une connexion SQLite vers `transit_douanier.db` ;
- cree les tables au demarrage ;
- ajoute des colonnes manquantes par migrations `ALTER TABLE` silencieuses ;
- gere CRUD utilisateurs, dossiers, documents, articles ;
- filtre les dossiers selon l'utilisateur connecte ;
- cache `init_database()` avec `st.cache_resource`.

Securite mots de passe :

- utilise `bcrypt` si disponible ;
- fallback en SHA-256 prefixe `sha256$` si `bcrypt` n'est pas disponible ;
- accepte aussi des hashes SHA-256 historiques sans prefixe.

Points notables :

- les `ALTER TABLE` ignorent toutes les exceptions, donc une erreur autre que "colonne deja existante" serait masquee ;
- `update_article()` construit dynamiquement la clause SQL a partir des cles de `kwargs`. Dans les appels actuels, les cles sont controlees par le code, donc le risque est limite, mais la fonction serait dangereuse si exposee a des cles utilisateur ;
- aucune contrainte de cle etrangere n'est activee explicitement via `PRAGMA foreign_keys = ON`, donc les `ON DELETE CASCADE` peuvent ne pas fonctionner selon la configuration SQLite de connexion ;
- les fonctions `delete_dossier`, `delete_document`, `delete_article` existent mais aucune interface utilisateur ne les expose dans les modules lus.

### `utils/ocr.py`

Role :

- configure Tesseract sur `C:\Program Files\Tesseract-OCR\tesseract.exe` ;
- pretraite les images en niveaux de gris + autocontraste ;
- utilise Tesseract en premier ;
- bascule vers EasyOCR si Tesseract renvoie moins de 50 caracteres ou echoue ;
- pour les PDF, rend chaque page via PyMuPDF a matrice `2x2`, puis OCRise l'image.

Points notables :

- le chemin Tesseract est absolu Windows ; l'application depend donc fortement de cette installation locale ;
- EasyOCR importe `torch` mais `torch` n'est pas declare dans `requirements.txt` ;
- OCR PDF integral par image : robuste pour documents scannes, mais potentiellement lent et gourmand.

### `utils/ai_extractor.py`

Role :

- charge `GROQ_API_KEY` ;
- cree un client Groq ;
- construit un prompt tres strict pour extraire un JSON douanier ;
- utilise des modeles avec fallback :
  - `llama-3.3-70b-versatile`
  - `llama-3.1-8b-instant`
  - `gemma2-9b-it`
- gere les erreurs 503 avec retries exponentiels ;
- nettoie les blocs Markdown eventuels ;
- parse le JSON ;
- normalise les dates ;
- convertit certains nombres string vers float.

Points notables :

- les reponses brutes Groq, JSON nettoyes et resultats finaux sont imprimes dans la console, ce qui peut exposer des donnees documentaires sensibles dans les logs ;
- le prompt dit de ne pas calculer mais de copier les valeurs OCR, choix coherent pour eviter les hallucinations de calcul ;
- si l'OCR est vide ou trop court, la fonction retourne une structure vide par defaut.

### `utils/helpers.py`

Role :

- liste devises, symboles et noms ;
- recupere des taux via `https://api.exchangerate-api.com/v4/latest/USD` ;
- fournit des taux de secours ;
- convertit des devises ;
- calcule droits de douane/TVA ;
- formate les montants ;
- valide les codes SH ;
- calcule poids et valeurs totaux.

Points notables :

- les helpers de taux dynamiques existent, mais l'export utilise sa propre conversion statique ;
- plusieurs fonctions semblent disponibles pour une version plus avancee mais ne sont pas encore connectees a l'interface.

## 7. Base de donnees SQLite

Fichier : `transit_douanier.db`  
Taille : 73 728 octets

Tables observees :

### `users`

Colonnes :

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `username TEXT NOT NULL`
- `email TEXT UNIQUE NOT NULL`
- `password_hash TEXT NOT NULL`
- `role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user'))`
- `date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

Nombre de lignes : 3

### `dossiers_transit`

Colonnes :

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `ref_interne TEXT UNIQUE NOT NULL`
- `statut TEXT DEFAULT 'En cours'`
- `date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `user_id INTEGER`

Index : `idx_dossiers_user` sur `user_id`  
Nombre de lignes : 70

Repartition des statuts :

| Statut | Nombre |
|---|---:|
| Documents televerses | 44 |
| En cours de traitement | 26 |

Point notable : 65 dossiers ont `user_id IS NULL`. Le filtrage par utilisateur non-admin ne verra donc pas ces anciens dossiers.

### `documents_commerciaux`

Colonnes principales :

- `id`
- `dossier_id`
- `type_document`
- `chemin_fichier`
- `date_import`
- `numero_document`
- `date_document`
- `devise`
- `valeur_totale_doc`
- champs expediteur ;
- champs destinataire.

Index : `idx_documents_dossier` sur `dossier_id`  
Nombre de lignes : 67

Repartition des types :

| Type document | Nombre |
|---|---:|
| Document Divers | 34 |
| Facture Commerciale | 31 |
| Packing List | 2 |

Point notable : 46 chemins de fichiers en base pointent vers `C:\Users\user\OneDrive\Desktop\Stage project\...`, alors que le projet actuel est dans `C:\Users\hp\Downloads\Stage_sutra_v6`. Ces documents risquent donc d'etre introuvables depuis cette copie.

### `articles_extraits`

Colonnes :

- `id`
- `document_id`
- `num_ligne`
- `designation`
- `code_sh`
- `quantite`
- `poids_net`
- `valeur_devise`
- `poids_brut`
- `valeur_unitaire`
- `unite`
- `origine`

Index : `idx_articles_document` sur `document_id`  
Nombre de lignes : 212

Des donnees d'exemple historiques sont presentes, notamment des lignes nommees `Article de demonstration ...`.

## 8. Fichiers uploades

Le dossier `uploads/` contient 10 fichiers :

| Type | Nombre |
|---|---:|
| PDF | 6 |
| JPEG | 4 |

Fichiers observes :

- `0287133a_Facture_Transit_Detaillee_1_Page.pdf`
- `0f5b0cb6_WhatsApp Image 2026-06-08 at 11.23.54.jpeg`
- `0fe87932_Image to PDF 20260605 11.32.54.pdf`
- `335eeaa7_liste_de_colisage_DOSS-1780489445.pdf`
- `33c36ba5_WhatsApp Image 2026-06-03 at 11.14.34.jpeg`
- `65e9ba86_WhatsApp Image 2026-06-01 at 13.43.11.jpeg`
- `73ea560c_Image to PDF 20260603 11.20.01.pdf`
- `81a42c44_SQL-(M)-CGB-2026-1204-YCL-1.pdf`
- `f150b1c9_facture_transit_DOSS-1780489445.pdf`
- `fc728800_WhatsApp Image 2026-06-01 at 12.00.38.jpeg`

Le prefixe hexagonal de 8 caracteres correspond a la logique d'upload actuelle : MD5 du contenu tronque aux 8 premiers caracteres.

## 9. Integrations externes

### Groq

Utilisation :

- extraction structuree OCR -> JSON dans `utils/ai_extractor.py` ;
- assistant conversationnel dans `modules/chat_assistant.py`.

Cle attendue :

- `GROQ_API_KEY` dans `.env`.

Modeles observes :

- Extraction : fallback entre `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `gemma2-9b-it`.
- Chat assistant : `llama-3.3-70b-versatile`.

### Tesseract OCR

Chemin configure :

- `C:\Program Files\Tesseract-OCR\tesseract.exe`

Langues :

- `fra+eng`

### EasyOCR

Utilise en fallback OCR, avec detection CUDA via `torch.cuda.is_available()`.

### PyMuPDF

Utilise pour convertir les pages PDF en images avant OCR.

### API de taux de change

`utils/helpers.py` appelle :

- `https://api.exchangerate-api.com/v4/latest/USD`

Cependant, cette conversion dynamique n'est pas utilisee par `modules/export.py`, qui possede une conversion locale statique.

### Google Fonts

`app.py` importe la police Poppins via CSS :

- `https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap`

### Configuration `.claude`

Le fichier `.claude/settings.local.json` contient des variables `ANTHROPIC_*`, dont une valeur de jeton d'authentification presente en clair. Je ne reproduis pas ce secret dans le rapport, mais sa presence dans un fichier local du projet est un point de securite important.

## 10. Gestion des utilisateurs et autorisations

Le modele d'autorisation est simple :

- un utilisateur connecte est stocke dans `st.session_state["user"]` ;
- les utilisateurs ont un role `user` ou `admin` ;
- `admin` voit tous les dossiers ;
- `user` voit seulement les dossiers dont `dossiers_transit.user_id` correspond a son `id`.

Points importants :

- les anciens dossiers sans `user_id` deviennent invisibles aux utilisateurs standards ;
- le controle d'acces est fait au niveau applicatif, pas au niveau base ;
- l'export reverifie que le dossier actif est autorise pour l'utilisateur courant ;
- l'upload empeche un utilisateur non-admin de reutiliser une reference appartenant a un autre utilisateur.

## 11. Points forts

- Architecture lisible et separee : `modules/` pour les pages, `utils/` pour les services.
- Flux metier coherent : upload -> OCR -> IA -> base -> revision -> export -> assistant.
- Persistance SQLite simple, facile a inspecter et deployer localement.
- Authentification locale avec hachage bcrypt si disponible.
- Fallback OCR Tesseract -> EasyOCR.
- Fallback multi-modeles Groq pour l'extraction.
- Gestion correcte de plusieurs cas vides dans le dashboard et la revision.
- Exports en trois formats utiles : JSON, XML, CSV.
- Assistant IA limite explicitement au contexte du dossier actif.
- Migration progressive de schema via `ALTER TABLE`, utile pour faire evoluer une base existante.

## 12. Limitations, risques et points incomplets

### Securite

- `.claude/settings.local.json` contient un jeton en clair. Il devrait etre retire du projet, revoque si reel, et gere via variables d'environnement non versionnees.
- `.env` contient une cle Groq locale. Le rapport ne l'expose pas, mais le projet doit s'assurer que `.env` n'est jamais partage.
- Les donnees OCR/IA sont imprimees dans la console par `utils/ai_extractor.py`; cela peut exposer factures, montants, adresses, destinataires.
- Reinitialisation de mot de passe sans email ni jeton temporaire.
- Inscription ouverte sans validation d'email.
- Politique de mot de passe minimale.
- Absence apparente de protection contre bruteforce login.

### Portabilite

- `venv` non portable et actuellement casse sur ce poste.
- Chemin Tesseract absolu Windows.
- Plusieurs chemins en base pointent vers un ancien emplacement `C:\Users\user\OneDrive\Desktop\Stage project`.
- Le projet embarque `venv`, `__pycache__`, base SQLite et uploads : ce sont des artefacts d'execution plus que du code source.

### Dependances

- `pandas`, `requests` et `torch` sont utilises mais absents de `requirements.txt`.
- `opencv-python-headless` est declare mais pas observe comme utilise directement dans le code applicatif lu.
- `get_exchange_rates` est importe dans `modules/export.py` mais non utilise.

### Base de donnees

- Les cascades `ON DELETE CASCADE` risquent de ne pas s'appliquer sans `PRAGMA foreign_keys = ON`.
- Les migrations masquent toutes les exceptions.
- Les anciens dossiers sans `user_id` creent une rupture de visibilite apres introduction du filtrage utilisateur.
- Les chemins absolus stockes en base rendent la base peu portable.

### Fonctionnel

- Ajout de nouvelles lignes dans la revision ignore a la sauvegarde.
- Validation metier limitee : poids max simple, absence de controle approfondi sur devise, SH, coherence montants/quantites.
- `validate_sh_code()` existe mais n'est pas utilise dans la revision ou l'export.
- `simulate_ocr_extraction()` est du code mort.
- Le type de document est devine par le nom de fichier.
- L'export considere les valeurs comme USD meme si la devise extraite peut differer.
- `modules/export.py` duplique une logique de conversion au lieu d'utiliser `utils/helpers.py`.
- Le statut de dossier ne semble pas passer automatiquement a `Valide` ou `Exporte`.

### UI et qualite de code

- Un `V` parasite est present dans le HTML de `modules/chat_assistant.py`.
- Bloc de deconnexion duplique dans `app.py`.
- Beaucoup de CSS inline dans les fichiers Python, ce qui rend la maintenance UI plus lourde.
- Plusieurs imports inutilises.
- Certains commentaires semblent historiques ou issus d'iterations successives.

## 13. Ce qui m'a surpris ou semble notable

- Le projet contient un `venv` complet mais non fonctionnel sur cette machine. C'est tres probablement un environnement cree sur un autre poste.
- La base contient deja beaucoup de donnees : 70 dossiers, 67 documents, 212 articles.
- La majorite des dossiers n'a pas de `user_id`, ce qui entre en tension avec le filtrage utilisateur actuel.
- Les documents en base pointent souvent vers un ancien chemin absolu, tandis que des fichiers existent aussi dans `uploads/`.
- L'application possede deux mecanismes de conversion de devises : un dynamique dans `utils/helpers.py`, un statique dans `modules/export.py`.
- Le code d'extraction IA est tres detaille et prompt-engineere, plus avance que les validations metier post-extraction.
- L'assistant IA est bien contextualise mais depend des donnees deja stockees, donc il herite de toutes les erreurs OCR/IA/revision.

## 14. Synthese finale

SUTRA SmartFlow est une application Streamlit locale de gestion documentaire douaniere avec une architecture simple et comprehensible. Le coeur du produit est deja present : authentification, upload, OCR, extraction IA, revision, dashboard, export et assistant conversationnel.

Le projet est cependant dans un etat de prototype avance plutot que production : secrets locaux presents, environnement virtuel casse, chemins absolus historiques, dependances incompletes, validations metier limitees, logs sensibles et quelques incoherences de maintenance. Les fondations sont bonnes, mais les priorites avant un usage serieux seraient la securisation des secrets/logs, la portabilite de l'environnement, la correction des chemins en base, l'alignement des devises/conversions, et le durcissement des controles metier.