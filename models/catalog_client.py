# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import secrets
import string


class CatalogClient(models.Model):
    """
    Clients ayant accès au catalogue.
    Chaque client est lié à un partner Odoo et peut avoir un accès portal.
    """
    _name = 'catalog.client'
    _description = 'Catalog Client'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'
    
    # === BASIC INFO ===
    name = fields.Char(
        string='Client Name',
        required=True,
        tracking=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        required=True,
        tracking=True,
        ondelete='cascade',
        help='Odoo partner associated with this catalog client'
    )
    
    email = fields.Char(
        string='Email',
        related='partner_id.email',
        store=True,
        readonly=False
    )
    
    phone = fields.Char(
        string='Phone',
        related='partner_id.phone',
        store=True,
        readonly=False
    )
    
    # === ACCESS CONTROL ===
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='If unchecked, client cannot access catalog'
    )
    
    access_mode = fields.Selection([
        ('full', 'Full Catalog'),
        ('restricted', 'Restricted Products'),
        ('custom', 'Custom Product List'),
    ], string='Access Mode',
       default='full',
       required=True,
       tracking=True,
       help='Controls which products this client can see'
    )
    
    # Products accessibles (si mode != full)
    allowed_product_ids = fields.Many2many(
        'product.template',
        'catalog_client_product_rel',
        'client_id',
        'product_id',
        string='Allowed Products',
        help='Products visible to this client (when access mode is not Full)'
    )
    
    allowed_category_ids = fields.Many2many(
        'product.category',
        'catalog_client_category_rel',
        'client_id',
        'category_id',
        string='Allowed Categories',
        help='Product categories visible to this client (when access mode is Restricted)'
    )

    # === SELECTION CART ===
    selected_product_ids = fields.Many2many(
        'product.template',
        'catalog_client_selection_rel',
        'client_id',
        'product_id',
        string='Selected Products',
        help='Products currently in client\'s selection cart for export'
    )

    selected_variant_ids = fields.Many2many(
        'product.product',
        'catalog_client_variant_selection_rel',
        'client_id',
        'variant_id',
        string='Selected Variants',
        help='Specific product variants selected for sync. '
             'If empty for a template, all variants are synced.'
    )

    selected_product_count = fields.Integer(
        string='Selected Products',
        compute='_compute_selection_stats',
        store=False
    )

    # === API CREDENTIALS ===
    api_key = fields.Char(
        string='API Key',
        readonly=True,
        copy=False,
        groups='base.group_system',
        help='API key for direct Odoo import via XML-RPC'
    )
    
    api_secret = fields.Char(
        string='API Secret',
        readonly=True,
        copy=False,
        groups='base.group_system',
        help='API secret for authentication'
    )
    
    # === CUSTOM PRICING ===
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Custom Pricelist',
        tracking=True,
        help='Specific pricelist for this client. If not set, uses default prices.'
    )
    
    # === STATISTICS ===
    export_count = fields.Integer(
        string='Total Exports',
        compute='_compute_export_stats',
        store=False
    )
    
    last_export_date = fields.Datetime(
        string='Last Export',
        compute='_compute_export_stats',
        store=False
    )
    
    last_access_date = fields.Datetime(
        string='Last Access',
        compute='_compute_access_stats',
        store=False
    )
    
    total_access_count = fields.Integer(
        string='Total Accesses',
        compute='_compute_access_stats',
        store=False
    )
    
    # === NOTES ===
    notes = fields.Text(
        string='Internal Notes',
        help='Internal notes about this client (not visible to client)'
    )
    
    @api.depends('partner_id')
    def _compute_access_url(self):
        """Calcule l'URL d'accès au portail pour ce client"""
        super()._compute_access_url()
        for client in self:
            client.access_url = f'/catalog/portal'
    
    def _compute_export_stats(self):
        """Calcule les statistiques d'export"""
        if not self.ids:
            return
        Log = self.env['catalog.access.log']
        # Count exports per client in a single query
        data = Log.read_group(
            domain=[('client_id', 'in', self.ids), ('action', '=', 'export_csv')],
            fields=['client_id'],
            groupby=['client_id'],
        )
        counts = {d['client_id'][0]: d['client_id_count'] for d in data}
        # Last export dates
        last_dates = {}
        if counts:
            self.env.cr.execute("""
                SELECT client_id, MAX(create_date)
                FROM catalog_access_log
                WHERE client_id = ANY(%s) AND action = 'export_csv'
                GROUP BY client_id
            """, [list(counts.keys())])
            last_dates = dict(self.env.cr.fetchall())
        for client in self:
            client.export_count = counts.get(client.id, 0)
            client.last_export_date = last_dates.get(client.id, False)

    def _compute_access_stats(self):
        """Calcule les statistiques d'accès"""
        if not self.ids:
            return
        Log = self.env['catalog.access.log']
        data = Log.read_group(
            domain=[('client_id', 'in', self.ids), ('action', '=', 'view_catalog')],
            fields=['client_id'],
            groupby=['client_id'],
        )
        counts = {d['client_id'][0]: d['client_id_count'] for d in data}
        last_dates = {}
        if counts:
            self.env.cr.execute("""
                SELECT client_id, MAX(create_date)
                FROM catalog_access_log
                WHERE client_id = ANY(%s) AND action = 'view_catalog'
                GROUP BY client_id
            """, [list(counts.keys())])
            last_dates = dict(self.env.cr.fetchall())
        for client in self:
            client.total_access_count = counts.get(client.id, 0)
            client.last_access_date = last_dates.get(client.id, False)

    @api.depends('selected_product_ids')
    def _compute_selection_stats(self):
        """Calcule le nombre de produits sélectionnés"""
        for client in self:
            client.selected_product_count = len(client.selected_product_ids)

    @api.model
    def create(self, vals):
        """Génère automatiquement les clés API à la création"""
        client = super().create(vals)
        client._generate_api_credentials()
        
        # Créer un utilisateur portal si le partner n'en a pas
        if not client.partner_id.user_ids:
            client._create_portal_user()
        
        return client
    
    def _generate_api_credentials(self):
        """Génère des clés API uniques pour ce client"""
        for client in self:
            # Génère une clé API unique
            alphabet = string.ascii_letters + string.digits
            client.api_key = 'cat_' + ''.join(secrets.choice(alphabet) for _ in range(32))
            client.api_secret = ''.join(secrets.choice(alphabet) for _ in range(48))
    
    def action_regenerate_api_credentials(self):
        """Action pour régénérer les clés API"""
        self.ensure_one()
        self._generate_api_credentials()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API Credentials Regenerated',
                'message': 'New API credentials have been generated for this client.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _create_portal_user(self):
        """Crée un utilisateur portal pour ce client"""
        self.ensure_one()
        if not self.partner_id.email:
            raise UserError('Partner must have an email address to create portal access.')
        
        # Créer l'utilisateur portal
        portal_group = self.env.ref('base.group_portal')
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'login': self.partner_id.email,
            'partner_id': self.partner_id.id,
            'group_ids': [(6, 0, [portal_group.id])],
            'active': self.is_active,
        })

        return user
    
    def action_send_portal_invite(self):
        """Envoie (ou renvoie) l'invitation au portail"""
        self.ensure_one()
        
        user = self.partner_id.user_ids.filtered(lambda u: u.has_group('base.group_portal'))
        if not user:
            user = self._create_portal_user()
        else:
            user = user[0]
            user.action_reset_password()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Portal Invitation Sent',
                'message': f'Portal invitation has been sent to {self.email}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _get_accessible_domain(self):
        """
        Returns the domain for accessible products for this client.
        Use this instead of _get_accessible_products() when you only
        need to filter, to avoid loading all products into memory.
        """
        self.ensure_one()

        if self.access_mode == 'full':
            return [('is_published', '=', True)]
        elif self.access_mode == 'restricted':
            return [
                ('is_published', '=', True),
                ('categ_id', 'child_of', self.allowed_category_ids.ids),
            ]
        elif self.access_mode == 'custom':
            return [
                ('id', 'in', self.allowed_product_ids.ids),
                ('is_published', '=', True),
            ]
        else:
            return [('id', '=', False)]

    def _get_accessible_products(self):
        """
        Retourne les produits accessibles par ce client
        selon son mode d'accès.
        """
        self.ensure_one()
        return self.env['product.template'].search(self._get_accessible_domain())
    
    def action_view_access_logs(self):
        """Action pour voir les logs d'accès de ce client"""
        self.ensure_one()
        return {
            'name': f'Access Logs - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'catalog.access.log',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }
    
    def action_open_portal(self):
        """Ouvre le portail catalogue pour ce client"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/catalog/portal',
            'target': 'new',
        }
    
    @api.constrains('partner_id')
    def _check_unique_partner(self):
        """Un partner ne peut avoir qu'un seul accès catalogue"""
        for client in self:
            existing = self.search([
                ('partner_id', '=', client.partner_id.id),
                ('id', '!=', client.id)
            ])
            if existing:
                raise ValidationError(
                    f'Partner {client.partner_id.name} already has catalog access.'
                )
