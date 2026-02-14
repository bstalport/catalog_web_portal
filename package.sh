#!/bin/bash

# ==========================================================================
# Catalog Web Portal - Package Builder
# ==========================================================================
# This script packages the module for distribution
# Usage: ./package.sh [version]
# Example: ./package.sh 1.0.0
# ==========================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Version (from argument or default)
VERSION=${1:-1.0.0}
MODULE_NAME="catalog_web_portal"
BUILD_DIR="build"
DIST_DIR="dist"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Catalog Web Portal - Package Builder${NC}"
echo -e "${GREEN}Version: ${VERSION}${NC}"
echo -e "${GREEN}======================================${NC}"

# Step 1: Clean previous builds
echo -e "${YELLOW}Step 1: Cleaning previous builds...${NC}"
rm -rf ${BUILD_DIR} ${DIST_DIR}
mkdir -p ${BUILD_DIR} ${DIST_DIR}

# Step 2: Copy module files
echo -e "${YELLOW}Step 2: Copying module files...${NC}"
cp -r ${MODULE_NAME} ${BUILD_DIR}/

# Step 3: Remove unnecessary files
echo -e "${YELLOW}Step 3: Removing unnecessary files...${NC}"
cd ${BUILD_DIR}/${MODULE_NAME}

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# Remove git files
rm -rf .git .gitignore .gitattributes

# Remove IDE files
rm -rf .vscode .idea *.swp *.swo *~

# Remove OS files
find . -name ".DS_Store" -delete
find . -name "Thumbs.db" -delete

cd ../..

# Step 4: Create version file
echo -e "${YELLOW}Step 4: Creating version file...${NC}"
echo "${VERSION}" > ${BUILD_DIR}/${MODULE_NAME}/VERSION

# Step 5: Validate manifest
echo -e "${YELLOW}Step 5: Validating manifest...${NC}"
if [ ! -f "${BUILD_DIR}/${MODULE_NAME}/__manifest__.py" ]; then
    echo -e "${RED}ERROR: __manifest__.py not found!${NC}"
    exit 1
fi

# Update version in manifest
sed -i.bak "s/'version': '.*'/'version': '${VERSION}'/" ${BUILD_DIR}/${MODULE_NAME}/__manifest__.py
rm ${BUILD_DIR}/${MODULE_NAME}/__manifest__.py.bak

echo -e "${GREEN}✓ Manifest updated with version ${VERSION}${NC}"

# Step 6: Create ZIP archive
echo -e "${YELLOW}Step 6: Creating ZIP archive...${NC}"
cd ${BUILD_DIR}
ARCHIVE_NAME="${MODULE_NAME}_v${VERSION}.zip"
zip -r ../${DIST_DIR}/${ARCHIVE_NAME} ${MODULE_NAME} -q

cd ..

# Step 7: Create checksum
echo -e "${YELLOW}Step 7: Creating checksum...${NC}"
cd ${DIST_DIR}
sha256sum ${ARCHIVE_NAME} > ${ARCHIVE_NAME}.sha256
cd ..

# Step 8: Generate install instructions
echo -e "${YELLOW}Step 8: Generating install instructions...${NC}"
cat > ${DIST_DIR}/INSTALL_INSTRUCTIONS.txt << EOF
========================================
Catalog Web Portal v${VERSION}
Installation Instructions
========================================

Method 1: Via Odoo Apps (Recommended)
--------------------------------------
1. Download ${ARCHIVE_NAME}
2. Go to Odoo Apps menu
3. Click "Update Apps List"
4. Search for "Catalog Web Portal"
5. Click Install

Method 2: Manual Installation
------------------------------
1. Extract ${ARCHIVE_NAME}
2. Copy catalog_web_portal folder to your Odoo addons directory
3. Restart Odoo server
4. Update Apps List
5. Install the module

Method 3: Via Command Line
---------------------------
unzip ${ARCHIVE_NAME} -d /path/to/odoo/addons/
./odoo-bin -c odoo.conf -d database_name -i catalog_web_portal

For detailed installation guide, see INSTALL.md in the module.

Support
-------
Email: support@yourcompany.com
Docs: README.md

SHA256: $(cat ${ARCHIVE_NAME}.sha256 | cut -d' ' -f1)
========================================
EOF

# Step 9: Summary
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Package created successfully!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "📦 Package: ${DIST_DIR}/${ARCHIVE_NAME}"
echo -e "🔒 Checksum: ${DIST_DIR}/${ARCHIVE_NAME}.sha256"
echo -e "📄 Instructions: ${DIST_DIR}/INSTALL_INSTRUCTIONS.txt"
echo ""

# Get package size
PACKAGE_SIZE=$(du -h ${DIST_DIR}/${ARCHIVE_NAME} | cut -f1)
echo -e "📊 Package size: ${PACKAGE_SIZE}"
echo ""

# List package contents
echo -e "${YELLOW}Package contents:${NC}"
unzip -l ${DIST_DIR}/${ARCHIVE_NAME} | head -n 20
echo "..."
echo ""

# Final instructions
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}======================================${NC}"
echo "1. Test the package:"
echo "   unzip ${DIST_DIR}/${ARCHIVE_NAME} -d /tmp/test"
echo "   # Install in test Odoo instance"
echo ""
echo "2. Upload to Odoo Apps Store:"
echo "   https://apps.odoo.com/"
echo ""
echo "3. Distribute to customers"
echo ""
echo -e "${GREEN}Happy distributing! 🚀${NC}"
