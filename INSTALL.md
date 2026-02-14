# 🚀 Installation et Test du MVP Catalog Web Portal

Ce guide vous accompagne pas à pas pour installer Odoo 19.0 et tester le module Catalog Web Portal.

---

## Prérequis Système

### Matériel Minimum
- 4 GB RAM
- 10 GB espace disque libre
- Processeur double cœur

### Logiciels Requis
- **OS**: Ubuntu 22.04 LTS (recommandé) ou macOS
- **Python**: 3.10+
- **PostgreSQL**: 14+
- **Git**

---

## Option 1 : Installation Locale (Ubuntu)

### Étape 1 : Préparer le Système

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer les dépendances
sudo apt install -y \
    python3-pip python3-dev python3-venv \
    libxml2-dev libxslt1-dev \
    libldap2-dev libsasl2-dev \
    libjpeg-dev zlib1g-dev libpq-dev \
    node-less npm git wget

# Installer wkhtmltopdf (pour PDF)
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.jammy_amd64.deb
sudo dpkg -i wkhtmltox_0.12.6.1-2.jammy_amd64.deb
sudo apt install -f -y
```

### Étape 2 : Installer PostgreSQL

```bash
# Installer PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Créer un utilisateur Odoo dans PostgreSQL
sudo -u postgres createuser -s $USER

# Vérifier
psql postgres -c "SELECT version();"
```

### Étape 3 : Télécharger Odoo 19.0

```bash
# Créer un dossier pour Odoo
mkdir -p ~/odoo-dev
cd ~/odoo-dev

# Cloner Odoo 19.0 (branch master pour la dernière version)
git clone https://github.com/odoo/odoo.git --depth 1 --branch master odoo19

cd odoo19
```

### Étape 4 : Créer un Environnement Virtuel Python

```bash
# Créer l'environnement virtuel
python3 -m venv venv

# Activer l'environnement
source venv/bin/activate

# Mettre à jour pip
pip install --upgrade pip

# Installer les dépendances Odoo
pip install -r requirements.txt
```

### Étape 5 : Installer le Module Catalog Web Portal

```bash
# Créer un dossier pour les modules custom
mkdir -p ~/odoo-dev/custom-addons

# Copier le module catalog_web_portal
cp -r /path/to/catalog_web_portal ~/odoo-dev/custom-addons/

# OU cloner depuis git (si hébergé)
# cd ~/odoo-dev/custom-addons
# git clone [your-repo-url] catalog_web_portal
```

### Étape 6 : Créer la Base de Données

```bash
# Créer la base de données
createdb catalog_demo

# Note: Si erreur de permissions, exécuter :
# sudo -u postgres createdb -O $USER catalog_demo
```

### Étape 7 : Créer le Fichier de Configuration

Créer `~/odoo-dev/odoo19/odoo.conf`:

```ini
[options]
# Chemins
addons_path = ~/odoo-dev/odoo19/addons,~/odoo-dev/custom-addons
data_dir = ~/odoo-dev/odoo19/data

# Base de données
db_host = localhost
db_port = 5432
db_user = [votre_user]
db_password = False

# Serveur
http_port = 8069
workers = 2

# Logs
logfile = ~/odoo-dev/odoo19/odoo.log
log_level = info

# Développement
dev_mode = reload,xml,qweb
```

### Étape 8 : Démarrer Odoo

```bash
cd ~/odoo-dev/odoo19
source venv/bin/activate

# Démarrer avec installation du module
./odoo-bin -c odoo.conf -d catalog_demo -i catalog_web_portal --dev=all
```

**Attendez** que le serveur démarre (peut prendre 1-2 minutes au premier lancement).

Vous devriez voir :
```
INFO catalog_demo odoo.modules.loading: Modules loaded.
INFO catalog_demo odoo.service.server: HTTP service (werkzeug) running on http://0.0.0.0:8069
```

### Étape 9 : Accéder à Odoo

1. Ouvrir le navigateur : **http://localhost:8069**
2. Créer la base de données si demandé :
   - Database Name: `catalog_demo`
   - Email: `admin@example.com`
   - Password: `admin` (ou votre choix)
   - Language: `French / Français`
   - Country: `Belgium`
   - Demo data: ☑️ (Cocher pour avoir des produits de test)

3. Se connecter avec admin / admin

---

## Option 2 : Installation avec Docker (Plus Rapide)

### Prérequis
- Docker installé : https://docs.docker.com/get-docker/
- Docker Compose installé

### Méthode Rapide

Créer `docker-compose.yml`:

```yaml
version: '3.8'
services:
  web:
    image: odoo:19.0
    depends_on:
      - db
    ports:
      - "8069:8069"
    volumes:
      - odoo-web-data:/var/lib/odoo
      - ./config:/etc/odoo
      - ./custom-addons:/mnt/extra-addons
    environment:
      - HOST=db
      - USER=odoo
      - PASSWORD=odoo
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_PASSWORD=odoo
      - POSTGRES_USER=odoo
    volumes:
      - odoo-db-data:/var/lib/postgresql/data

volumes:
  odoo-web-data:
  odoo-db-data:
```

```bash
# Créer la structure
mkdir -p custom-addons config

# Copier le module
cp -r /path/to/catalog_web_portal custom-addons/

# Démarrer
docker-compose up -d

# Voir les logs
docker-compose logs -f web
```

Accéder : **http://localhost:8069**

---

## Option 3 : Odoo.sh (Cloud - Plus Simple)

### Avantages
- Pas d'installation locale
- Environnement production-ready
- Gratuit 15 jours d'essai

### Étapes

1. Aller sur https://www.odoo.sh/
2. Créer un compte
3. Créer un nouveau projet
4. Choisir Odoo 19.0
5. Uploader le module `catalog_web_portal` via l'interface
6. Activer le module depuis l'interface Odoo

---

## 🧪 Tester le Module

### Test 1 : Configuration Initiale

1. Menu : **Catalog Portal → Configuration → Settings**
2. Vérifier que la configuration par défaut est chargée
3. Personnaliser :
   - Logo (optionnel)
   - Couleur primaire
   - Message de bienvenue
4. Sauvegarder

### Test 2 : Publier des Produits

1. Menu : **Sales → Products**
2. Si données de démo : plusieurs produits existent
3. Ouvrir un produit
4. Onglet **Catalog**
5. Cocher **"Published in Catalog"**
6. Cocher **"Featured Product"** (optionnel)
7. Sauvegarder

**Répéter** pour 10-15 produits.

**Ou** action en masse :
1. Liste des produits
2. Sélectionner plusieurs produits (checkbox)
3. **Action → Publish in Catalog**

### Test 3 : Créer un Client Catalogue

1. Menu : **Catalog Portal → Clients**
2. Cliquer **Create**
3. Remplir :
   - **Name**: "Test Client ABC"
   - **Partner**: Créer "ABC Distribution" (ou choisir existant)
     - Email: `client@abc.com`
     - Phone: `+32 123 456 789`
   - **Access Mode**: Full Catalog
   - **Custom Pricelist**: (laisser vide pour l'instant)
4. Sauvegarder

### Test 4 : Envoyer l'Invitation Portal

1. Depuis le formulaire client, cliquer **"Send Portal Invitation"**
2. Un email devrait être "envoyé" (en dev, il apparaît dans les logs)
3. Pour tester sans email :
   - Menu : **Settings → Users & Companies → Users**
   - Chercher l'utilisateur `client@abc.com`
   - Cliquer dessus
   - **Action → Change Password**
   - Définir un mot de passe : `test123`

### Test 5 : Se Connecter comme Client

1. **Déconnecter** du compte admin
2. Se connecter avec :
   - Login: `client@abc.com`
   - Password: `test123`
3. Aller sur : **http://localhost:8069/catalog/portal**

Vous devriez voir :
- Message de bienvenue
- Barre de recherche
- Filtres par catégorie
- Grille de produits
- Bouton "Selection" en haut à droite

### Test 6 : Naviguer dans le Catalogue

1. **Chercher** un produit par nom
2. **Filtrer** par catégorie
3. **Trier** par prix
4. **Cliquer** sur un produit pour voir le détail
5. Cliquer **"Add to Selection"** sur plusieurs produits
6. Vérifier que le compteur "Selection" augmente

### Test 7 : Exporter en CSV

1. Cliquer sur **"Selection"** (icône panier)
2. Vérifier la liste des produits sélectionnés
3. Cocher **"Include product images"** (optionnel)
4. Cliquer **"Download CSV File"**
5. Le fichier `catalog_export_ABC_Distribution_YYYYMMDD_HHMMSS.csv` se télécharge

### Test 8 : Importer le CSV dans Odoo

**Simuler l'import côté client :**

1. Se reconnecter comme **admin**
2. Aller à : **Achats → Produits**
3. Cliquer **Favoris → Importer des enregistrements**
4. Upload le CSV téléchargé
5. Vérifier les correspondances de colonnes (normalement auto-détecté)
6. Cliquer **Importer**
7. Vérifier que les produits sont importés (ou mis à jour)

### Test 9 : Vérifier les Logs

1. Menu : **Catalog Portal → Analytics → Access Logs**
2. Vous devriez voir :
   - Action "View Catalog" quand le client a ouvert le portail
   - Action "View Product" pour chaque produit consulté
   - Action "Export CSV" pour l'export
3. Cliquer sur un log pour voir les détails

### Test 10 : Statistiques

1. Retour sur le client : **Catalog Portal → Clients**
2. Ouvrir "Test Client ABC"
3. Vérifier les statistiques dans les boutons en haut :
   - Nombre d'exports
   - Nombre d'accès
4. Menu : **Catalog Portal → Configuration → Settings**
5. Vérifier les statistiques globales :
   - Total clients
   - Clients actifs
   - Exports aujourd'hui
   - Exports ce mois

---

## ✅ Checklist de Tests Réussis

- [ ] Module installé sans erreur
- [ ] Configuration accessible et modifiable
- [ ] Produits publiables dans le catalogue
- [ ] Client créé avec succès
- [ ] Invitation portal envoyée
- [ ] Connexion client réussie
- [ ] Navigation catalogue fluide
- [ ] Recherche et filtres fonctionnels
- [ ] Ajout à la sélection opérationnel
- [ ] Export CSV génère un fichier valide
- [ ] Import CSV dans Odoo réussi
- [ ] Logs d'accès enregistrés correctement
- [ ] Statistiques affichées

---

## 🐛 Résolution de Problèmes Courants

### Erreur : Module not found

```bash
# Vérifier que le module est bien dans custom-addons
ls -la ~/odoo-dev/custom-addons/catalog_web_portal

# Vérifier addons_path dans odoo.conf
grep addons_path ~/odoo-dev/odoo19/odoo.conf
```

### Erreur : Database does not exist

```bash
# Lister les bases de données
psql -l

# Créer si nécessaire
createdb catalog_demo
```

### Erreur : Port 8069 already in use

```bash
# Trouver le processus
sudo lsof -i :8069

# Tuer le processus
kill [PID]

# Ou changer le port dans odoo.conf
http_port = 8070
```

### Erreur : Permission denied (PostgreSQL)

```bash
# Donner les droits
sudo -u postgres psql
# Dans psql :
ALTER USER [votre_user] CREATEDB;
\q
```

### Le portail affiche "No access"

**Vérifier** :
1. Client est **Active** (toggle dans le formulaire)
2. Partner a un utilisateur portal créé
3. Utilisateur portal a le bon email
4. Configuration : Portal Access Enabled = True

### Products don't appear

**Vérifier** :
1. Produits ont **"Published in Catalog"** coché
2. Client Access Mode = "Full Catalog" (pour test)
3. Rafraîchir la page (Ctrl+F5)

---

## 📝 Prochaines Étapes

Une fois le MVP testé avec succès :

1. **Personnaliser** le branding (logo, couleurs)
2. **Créer** plus de clients avec différents modes d'accès
3. **Tester** les access modes "Restricted" et "Custom"
4. **Configurer** des pricelists personnalisées
5. **Analyser** les logs pour comprendre l'usage
6. **Préparer** pour production (voir guide de déploiement)

---

## 🎓 Ressources Additionnelles

- **Odoo Documentation**: https://www.odoo.com/documentation/19.0/
- **Odoo Forum**: https://www.odoo.com/forum/help-1
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

---

## 📞 Support

Des questions ? Problèmes ?

- **Email**: support@yourcompany.com
- **GitHub Issues**: [Lien vers repo]

---

**Bon test ! 🚀**
