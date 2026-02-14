#!/bin/bash
# Catalog Web Portal - Automatic Installation Script
# Compatible with Ubuntu/Debian and Odoo 19.0

set -e  # Exit on error

echo "================================================"
echo "Catalog Web Portal - Installation Script"
echo "Version: 19.0.1.0.0"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_warning "Please do not run this script as root"
    print_info "Run as: ./install.sh"
    exit 1
fi

# Get Odoo directory
echo "Step 1: Locate Odoo Installation"
echo "=================================="

DEFAULT_ADDONS="/opt/odoo/addons"
read -p "Enter Odoo addons directory [${DEFAULT_ADDONS}]: " ADDONS_PATH
ADDONS_PATH=${ADDONS_PATH:-$DEFAULT_ADDONS}

if [ ! -d "$ADDONS_PATH" ]; then
    print_error "Directory $ADDONS_PATH does not exist"
    print_info "Please create it first or provide correct path"
    exit 1
fi

print_success "Addons directory: $ADDONS_PATH"
echo ""

# Check if module already exists
MODULE_PATH="$ADDONS_PATH/catalog_web_portal"
if [ -d "$MODULE_PATH" ]; then
    print_warning "Module already exists at $MODULE_PATH"
    read -p "Overwrite? (y/n): " OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
        print_info "Installation cancelled"
        exit 0
    fi
    print_info "Removing existing module..."
    sudo rm -rf "$MODULE_PATH"
fi

# Copy module
echo ""
echo "Step 2: Copy Module Files"
echo "=================================="

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$CURRENT_DIR/__manifest__.py" ]; then
    print_error "Module files not found in current directory"
    print_info "Please run this script from the module root directory"
    exit 1
fi

print_info "Copying files to $MODULE_PATH..."
sudo cp -r "$CURRENT_DIR" "$MODULE_PATH"
print_success "Files copied"

# Set permissions
echo ""
echo "Step 3: Set Permissions"
echo "=================================="

print_info "Setting ownership to odoo:odoo..."
if id "odoo" &>/dev/null; then
    sudo chown -R odoo:odoo "$MODULE_PATH"
    print_success "Ownership set"
else
    print_warning "User 'odoo' not found, skipping ownership change"
fi

print_info "Setting permissions to 755..."
sudo chmod -R 755 "$MODULE_PATH"
print_success "Permissions set"

# Check Odoo service
echo ""
echo "Step 4: Restart Odoo Service"
echo "=================================="

read -p "Restart Odoo service now? (y/n): " RESTART
if [ "$RESTART" == "y" ]; then
    print_info "Restarting Odoo..."
    
    if sudo systemctl restart odoo 2>/dev/null; then
        print_success "Odoo service restarted (systemctl)"
    elif sudo service odoo restart 2>/dev/null; then
        print_success "Odoo service restarted (service)"
    else
        print_warning "Could not restart Odoo automatically"
        print_info "Please restart Odoo manually"
    fi
    
    # Wait for Odoo to start
    print_info "Waiting for Odoo to start (10 seconds)..."
    sleep 10
    print_success "Odoo should be ready"
else
    print_warning "Remember to restart Odoo manually"
fi

# Database selection
echo ""
echo "Step 5: Database Configuration"
echo "=================================="

read -p "Enter database name (or skip): " DB_NAME

if [ -z "$DB_NAME" ]; then
    print_info "Skipping database configuration"
else
    print_info "Module will be installed on database: $DB_NAME"
    print_warning "Please install via Odoo UI:"
    print_info "1. Go to Apps > Update Apps List"
    print_info "2. Search 'catalog_web_portal'"
    print_info "3. Click Install"
fi

# Summary
echo ""
echo "================================================"
echo "Installation Summary"
echo "================================================"
echo ""
print_success "Module files installed at: $MODULE_PATH"
print_success "Permissions configured"
[ "$RESTART" == "y" ] && print_success "Odoo service restarted"
echo ""
print_info "Next Steps:"
echo "  1. Login to Odoo as Administrator"
echo "  2. Go to Apps > Update Apps List"
echo "  3. Remove 'Apps' filter in search"
echo "  4. Search for 'Catalog Web Portal'"
echo "  5. Click 'Install'"
echo ""
print_info "After installation:"
echo "  - Configure: Catalog Portal > Configuration > Settings"
echo "  - Create clients: Catalog Portal > Clients"
echo "  - Publish products: Sales > Products"
echo ""
print_info "Documentation:"
echo "  - Full guide: $MODULE_PATH/README.md"
echo "  - Installation: $MODULE_PATH/INSTALL.md"
echo "  - Quick start: $MODULE_PATH/../QUICKSTART.md"
echo ""
print_success "Installation completed successfully!"
echo ""

# Optional: Open documentation
read -p "Open README in browser? (y/n): " OPEN_README
if [ "$OPEN_README" == "y" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "$MODULE_PATH/README.md" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "$MODULE_PATH/README.md" 2>/dev/null &
    else
        print_info "Could not open browser, view file at: $MODULE_PATH/README.md"
    fi
fi

echo "================================================"
echo "Thank you for using Catalog Web Portal!"
echo "Support: support@yourcompany.com"
echo "================================================"
