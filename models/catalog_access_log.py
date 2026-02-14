# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CatalogAccessLog(models.Model):
    """
    Logs de tous les accès au catalogue et exports.
    Permet tracking et analytics.
    """
    _name = 'catalog.access.log'
    _description = 'Catalog Access Log'
    _order = 'create_date desc'
    _rec_name = 'action'
    
    # === BASIC INFO ===
    client_id = fields.Many2one(
        'catalog.client',
        string='Client',
        ondelete='set null',
        index=True,
        help='Client who performed the action (if authenticated)'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        ondelete='set null',
        index=True,
        help='Odoo user who performed the action'
    )
    
    ip_address = fields.Char(
        string='IP Address',
        index=True,
        help='IP address of the request'
    )
    
    # === ACTION INFO ===
    action = fields.Selection([
        ('view_catalog', 'View Catalog'),
        ('view_product', 'View Product Detail'),
        ('export_csv', 'Export CSV'),
        ('export_excel', 'Export Excel'),
        ('direct_import', 'Direct Odoo Import'),
        ('api_request', 'API Request'),
    ], string='Action',
       required=True,
       index=True
    )
    
    action_details = fields.Text(
        string='Action Details',
        help='Additional details about the action'
    )
    
    # === EXPORT SPECIFIC ===
    product_count = fields.Integer(
        string='Product Count',
        help='Number of products involved in the action'
    )
    
    product_ids = fields.Many2many(
        'product.template',
        'catalog_log_product_rel',
        'log_id',
        'product_id',
        string='Products',
        help='Products involved in this action'
    )
    
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ], string='Export Format')
    
    # === REQUEST INFO ===
    user_agent = fields.Char(
        string='User Agent',
        help='Browser/client user agent'
    )
    
    http_referer = fields.Char(
        string='HTTP Referer',
        help='Referer URL'
    )
    
    # === RESULT ===
    success = fields.Boolean(
        string='Success',
        default=True,
        help='Whether the action was successful'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error message if action failed'
    )
    
    # === COMPUTED ===
    client_name = fields.Char(
        string='Client Name',
        related='client_id.name',
        store=True
    )
    
    user_name = fields.Char(
        string='User Name',
        related='user_id.name',
        store=True
    )
    
    @api.model
    def log_action(self, action, client_id=None, user_id=None, product_ids=None, **kwargs):
        """
        Méthode helper pour créer un log facilement.
        
        Args:
            action: Type d'action (view_catalog, export_csv, etc.)
            client_id: ID du client catalog (optionnel)
            user_id: ID de l'utilisateur Odoo (optionnel)
            product_ids: Liste d'IDs de produits (optionnel)
            **kwargs: Autres champs (ip_address, export_format, etc.)
        
        Returns:
            catalog.access.log: Le log créé
        """
        vals = {
            'action': action,
            'client_id': client_id,
            'user_id': user_id,
            'product_count': len(product_ids) if product_ids else 0,
            'product_ids': [(6, 0, product_ids)] if product_ids else False,
        }
        
        # Ajouter les kwargs
        vals.update(kwargs)
        
        return self.create(vals)
    
    @api.model
    def get_statistics(self, date_from=None, date_to=None, client_id=None):
        """
        Récupère des statistiques d'utilisation.
        
        Args:
            date_from: Date de début (optionnel)
            date_to: Date de fin (optionnel)
            client_id: Filtrer par client (optionnel)
        
        Returns:
            dict: Statistiques
        """
        domain = []
        
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
        if client_id:
            domain.append(('client_id', '=', client_id))
        
        logs = self.search(domain)
        
        # Compter par type d'action
        action_counts = {}
        for action_type in self._fields['action'].selection:
            action_counts[action_type[0]] = logs.filtered(
                lambda l: l.action == action_type[0]
            ).mapped('product_count')
        
        return {
            'total_accesses': len(logs),
            'unique_clients': len(logs.mapped('client_id')),
            'unique_users': len(logs.mapped('user_id')),
            'unique_ips': len(logs.mapped('ip_address')),
            'total_exports': len(logs.filtered(lambda l: 'export' in l.action)),
            'total_products_exported': sum(logs.mapped('product_count')),
            'action_breakdown': action_counts,
            'success_rate': (
                len(logs.filtered(lambda l: l.success)) / len(logs) * 100
                if logs else 0
            ),
        }
    
    def action_view_products(self):
        """Action pour voir les produits concernés"""
        self.ensure_one()
        return {
            'name': 'Products',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.product_ids.ids)],
        }
