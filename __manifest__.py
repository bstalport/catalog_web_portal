# -*- coding: utf-8 -*-
{
    'name': 'Catalog Web Portal - Supplier Product Sharing',
    'version': '19.0.1.1.0',
    'category': 'Sales/Sales',
    'summary': 'Share your product catalog with customers via web portal - No client installation needed',
    'description': """
Catalog Web Portal
==================

Share your product catalog with your customers through a secure web portal.
Your customers can browse, select and import your products directly into their Odoo,
even if they use Odoo Online (no module installation required on client side).

Key Features
------------
* **Secure Portal Access**: Create customer accounts with controlled access
* **Beautiful Web Interface**: Modern, responsive catalog browser
* **Easy Product Selection**: Multi-select, search, filters
* **CSV Export**: Generate Odoo-compatible import files
* **Direct Odoo Import**: Optional XML-RPC integration for automatic import
* **Access Control**: Manage what products each customer can see
* **Custom Pricing**: Set specific prices per customer
* **Analytics**: Track catalog views and exports
* **No Client Installation**: Works with Odoo Online!

Perfect For
-----------
* Suppliers/Manufacturers sharing catalogs with distributors
* Wholesalers sharing with retailers  
* B2B companies with multiple clients

Business Model
--------------
* Supplier pays (SaaS subscription)
* Client uses for FREE
* Win-win value proposition
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'portal',
        'website',
        'mail',
    ],
    'data': [
        # Security
        'security/catalog_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/export_fields.xml',
        'data/default_config.xml',

        # Views - Backend
        'views/catalog_config_views.xml',
        'views/catalog_client_views.xml',
        'views/catalog_access_log_views.xml',
        'views/catalog_sync_views.xml',
        'views/product_template_views.xml',
        'views/menu_views.xml',

        # Views - Portal/Website
        'views/templates/portal_layout.xml',
        'views/templates/portal_dashboard.xml',
        'views/templates/catalog_browser.xml',
        'views/templates/product_detail.xml',
        'views/templates/export_wizard.xml',
        'views/templates/sync_setup.xml',
        'views/templates/sync_preview.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'catalog_web_portal/static/src/css/catalog_portal.css',
            'catalog_web_portal/static/src/js/catalog_browser.js',
        ],
    },
    'demo': [],
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 99.00,
    'currency': 'EUR',
}
