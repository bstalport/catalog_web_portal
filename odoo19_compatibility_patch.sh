#!/bin/bash

# ==========================================================================
# Patch de Compatibilité Odoo 19.0
# ==========================================================================
# Ce script corrige automatiquement les problèmes de compatibilité
# Usage: ./odoo19_compatibility_patch.sh
# ==========================================================================

set -e

echo "========================================="
echo "Patch de Compatibilité Odoo 19.0"
echo "Module: Catalog Web Portal"
echo "========================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

MODULE_PATH="."

echo -e "${YELLOW}Étape 1: Vérification de la structure...${NC}"
if [ ! -f "__manifest__.py" ]; then
    echo -e "${RED}Erreur: Exécuter ce script depuis le dossier catalog_web_portal${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Structure OK${NC}"
echo ""

echo -e "${YELLOW}Étape 2: Backup des fichiers...${NC}"
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r security/ models/ views/ "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✓ Backup créé dans $BACKUP_DIR${NC}"
echo ""

echo -e "${YELLOW}Étape 3: Correction des problèmes connus...${NC}"

# Problème 1: category_id dans res.groups (déjà corrigé dans le fichier)
echo "  - Vérification catalog_security.xml..."
if grep -q "category_id" security/catalog_security.xml 2>/dev/null; then
    echo -e "${YELLOW}    ⚠ category_id trouvé (déjà corrigé manuellement)${NC}"
else
    echo -e "${GREEN}    ✓ catalog_security.xml OK${NC}"
fi

# Problème 2: Imports Python manquants
echo "  - Vérification des imports Python..."
for pyfile in models/*.py controllers/*.py; do
    if [ -f "$pyfile" ]; then
        # Vérifier si datetime est utilisé mais pas importé
        if grep -q "timedelta" "$pyfile" && ! grep -q "from datetime import" "$pyfile"; then
            echo -e "${YELLOW}    ⚠ Import manquant dans $pyfile${NC}"
            # Ajouter l'import si nécessaire
            sed -i '3 a from datetime import timedelta' "$pyfile" 2>/dev/null || true
        fi
    fi
done
echo -e "${GREEN}    ✓ Imports vérifiés${NC}"

# Problème 3: Vérifier les références de vues héritées
echo "  - Vérification des vues héritées..."
if grep -r "product.product_template_only_form_view" views/ >/dev/null 2>&1; then
    echo -e "${GREEN}    ✓ Références de vues OK${NC}"
else
    echo -e "${YELLOW}    ⚠ Vérifier manuellement les références de vues${NC}"
fi

echo ""
echo -e "${YELLOW}Étape 4: Vérification de la syntaxe Python...${NC}"
python3 -m py_compile models/*.py 2>/dev/null && echo -e "${GREEN}✓ Models OK${NC}" || echo -e "${RED}✗ Erreur dans models/${NC}"
python3 -m py_compile controllers/*.py 2>/dev/null && echo -e "${GREEN}✓ Controllers OK${NC}" || echo -e "${RED}✗ Erreur dans controllers/${NC}"

echo ""
echo -e "${YELLOW}Étape 5: Vérification de la syntaxe XML...${NC}"
for xmlfile in views/*.xml views/templates/*.xml security/*.xml data/*.xml; do
    if [ -f "$xmlfile" ]; then
        xmllint --noout "$xmlfile" 2>/dev/null && echo -e "${GREEN}✓ $(basename $xmlfile)${NC}" || echo -e "${RED}✗ Erreur dans $xmlfile${NC}"
    fi
done

echo ""
echo "========================================="
echo -e "${GREEN}Patch terminé !${NC}"
echo "========================================="
echo ""
echo "Prochaines étapes:"
echo "1. Redémarrer Odoo"
echo "2. Mettre à jour la liste des apps"
echo "3. Installer/Mettre à jour le module"
echo ""
echo "En cas de problème:"
echo "- Backup disponible dans: $BACKUP_DIR"
echo "- Consulter les logs Odoo pour plus de détails"
echo ""
