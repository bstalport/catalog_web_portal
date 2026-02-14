# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class CatalogConfig(models.Model):
    """
    Configuration globale du système de partage de catalogue.
    Un seul enregistrement (singleton) pour gérer tous les paramètres.
    """
    _name = 'catalog.config'
    _description = 'Catalog Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Configuration Name',
        default='Catalog Configuration',
        required=True,
        tracking=True
    )
    
    # === ACCESS MODES ===
    portal_access_enabled = fields.Boolean(
        string='Enable Portal Access',
        default=True,
        tracking=True,
        help='Allow customers to access catalog through secure portal'
    )
    
    # === FEATURES ===
    allow_csv_export = fields.Boolean(
        string='Allow CSV Export',
        default=True,
        tracking=True,
        help='Allow customers to export product data as CSV'
    )
    
    allow_excel_export = fields.Boolean(
        string='Allow Excel Export',
        default=True,
        tracking=True
    )
    
    allow_direct_odoo_import = fields.Boolean(
        string='Allow Direct Odoo Import',
        default=True,
        tracking=True,
        help='Allow customers to import directly via XML-RPC API'
    )

    # === SUPPLIER INFO FOR EXPORTS ===
    include_supplier_info_in_exports = fields.Boolean(
        string='Include Supplier Info in Exports',
        default=True,
        tracking=True,
        help='Include product.supplierinfo columns in CSV/Excel exports. '
             'This enables automatic product matching when clients load your invoices.'
    )
    supplier_external_id = fields.Char(
        string='Supplier External ID',
        default='catalog_supplier',
        help='External ID used for your company in CSV/Excel exports. '
             'Clients should create a partner with this external ID before importing.'
    )
    
    # === LIMITATIONS ===
    max_products_per_export = fields.Integer(
        string='Max Products per Export',
        default=1000,
        tracking=True,
        help='Maximum number of products in a single export (0 = unlimited)'
    )
    
    export_rate_limit = fields.Integer(
        string='Export Rate Limit (per hour)',
        default=10,
        tracking=True,
        help='Maximum exports per hour per user (0 = unlimited)'
    )
    
    # === PRODUCT VISIBILITY ===
    default_product_visibility = fields.Selection([
        ('all', 'All Published Products'),
        ('custom', 'Custom per Client'),
    ], string='Default Product Visibility',
       default='all',
       required=True,
       tracking=True
    )

    # === EXPORT FIELDS CONFIGURATION ===
    export_field_ids = fields.Many2many(
        'catalog.export.field',
        'catalog_config_export_field_rel',
        'config_id',
        'field_id',
        string='Export Fields',
        help='Select which product fields will be available for export by clients'
    )
    
    # === BRANDING ===
    portal_logo = fields.Binary(
        string='Portal Logo',
        help='Logo displayed in customer portal'
    )
    
    portal_primary_color = fields.Char(
        string='Primary Color',
        default='#007bff',
        help='Hex color code for portal theme'
    )
    
    portal_welcome_message = fields.Html(
        string='Welcome Message',
        default='<p>Welcome to our product catalog!</p>',
        help='Message displayed on portal home page'
    )
    
    # === CONTACT INFO ===
    support_email = fields.Char(
        string='Support Email',
        help='Email for customer support'
    )
    
    support_phone = fields.Char(
        string='Support Phone'
    )
    
    # === STATISTICS (computed) ===
    total_clients = fields.Integer(
        string='Total Clients',
        compute='_compute_statistics',
        store=False
    )
    
    active_clients = fields.Integer(
        string='Active Clients',
        compute='_compute_statistics',
        store=False
    )
    
    total_exports_today = fields.Integer(
        string='Exports Today',
        compute='_compute_statistics',
        store=False
    )
    
    total_exports_month = fields.Integer(
        string='Exports This Month',
        compute='_compute_statistics',
        store=False
    )
    
    @api.depends('portal_access_enabled')
    def _compute_statistics(self):
        """Calcule les statistiques d'utilisation"""
        for config in self:
            CatalogClient = self.env['catalog.client']
            CatalogLog = self.env['catalog.access.log']
            
            # Nombre total de clients
            config.total_clients = CatalogClient.search_count([])
            
            # Clients actifs (connectés dans les 30 derniers jours)
            thirty_days_ago = fields.Datetime.now() - timedelta(days=30)
            recent_logs = CatalogLog.search([
                ('action', '=', 'view_catalog'),
                ('create_date', '>=', thirty_days_ago)
            ])
            config.active_clients = len(recent_logs.client_id)
            
            # Exports aujourd'hui
            today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0)
            config.total_exports_today = CatalogLog.search_count([
                ('action', '=', 'export_csv'),
                ('create_date', '>=', today_start)
            ])
            
            # Exports ce mois
            month_start = fields.Datetime.now().replace(day=1, hour=0, minute=0, second=0)
            config.total_exports_month = CatalogLog.search_count([
                ('action', '=', 'export_csv'),
                ('create_date', '>=', month_start)
            ])
    
    @api.model
    def get_config(self):
        """
        Récupère la configuration singleton.
        Crée une config par défaut si elle n'existe pas.
        """
        config = self.search([], limit=1)
        if not config:
            # Get default export fields
            default_fields = self.env['catalog.export.field'].search([
                ('is_default', '=', True)
            ])
            config = self.create({
                'name': 'Catalog Configuration',
                'export_field_ids': [(6, 0, default_fields.ids)],
            })
        return config

    def get_enabled_export_fields(self):
        """
        Returns the list of enabled export field technical names.
        Falls back to default fields if none configured.
        """
        self.ensure_one()
        if self.export_field_ids:
            return self.export_field_ids.sorted('sequence')
        # Fallback to default fields
        return self.env['catalog.export.field'].search([
            ('is_default', '=', True)
        ], order='sequence')
    
    @api.constrains('max_products_per_export')
    def _check_max_products(self):
        """Validation du nombre max de produits"""
        for config in self:
            if config.max_products_per_export < 0:
                raise ValidationError('Max products per export must be >= 0')
    
    @api.constrains('portal_primary_color')
    def _check_color_format(self):
        """Validation du format de couleur hex"""
        import re
        for config in self:
            if config.portal_primary_color:
                if not re.match(r'^#[0-9A-Fa-f]{6}$', config.portal_primary_color):
                    raise ValidationError('Color must be in hex format (#RRGGBB)')
    
    def action_view_clients(self):
        """Action pour voir tous les clients"""
        self.ensure_one()
        return {
            'name': 'Catalog Clients',
            'type': 'ir.actions.act_window',
            'res_model': 'catalog.client',
            'view_mode': 'list,form',
            'domain': [],
            'context': {'default_is_active': True},
        }
    
    def action_view_logs(self):
        """Action pour voir les logs d'accès"""
        self.ensure_one()
        return {
            'name': 'Access Logs',
            'type': 'ir.actions.act_window',
            'res_model': 'catalog.access.log',
            'view_mode': 'list,form',
            'domain': [],
            'context': {},
        }
