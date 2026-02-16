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
        """Retrieve usage statistics via SQL aggregation (avoids loading all logs).

        Args:
            date_from: Start date filter (optional).
            date_to: End date filter (optional).
            client_id: Filter by client (optional).

        Returns:
            dict with aggregated statistics.
        """
        where_clauses = ["1=1"]
        params = []

        if date_from:
            where_clauses.append("create_date >= %s")
            params.append(date_from)
        if date_to:
            where_clauses.append("create_date <= %s")
            params.append(date_to)
        if client_id:
            where_clauses.append("client_id = %s")
            params.append(client_id)

        where_sql = " AND ".join(where_clauses)

        self.env.cr.execute(f"""
            SELECT
                COUNT(*)                                              AS total_accesses,
                COUNT(DISTINCT client_id)                             AS unique_clients,
                COUNT(DISTINCT user_id)                               AS unique_users,
                COUNT(DISTINCT ip_address)                            AS unique_ips,
                COUNT(*) FILTER (WHERE action LIKE '%%export%%')      AS total_exports,
                COALESCE(SUM(product_count), 0)                       AS total_products_exported,
                CASE WHEN COUNT(*) > 0
                     THEN ROUND(COUNT(*) FILTER (WHERE success = true) * 100.0 / COUNT(*), 1)
                     ELSE 0 END                                       AS success_rate
            FROM catalog_access_log
            WHERE {where_sql}
        """, params)
        row = self.env.cr.dictfetchone()

        # Action breakdown via grouped query
        self.env.cr.execute(f"""
            SELECT action, COUNT(*) AS cnt
            FROM catalog_access_log
            WHERE {where_sql}
            GROUP BY action
        """, params)
        action_breakdown = {r['action']: r['cnt'] for r in self.env.cr.dictfetchall()}

        return {
            'total_accesses': row['total_accesses'],
            'unique_clients': row['unique_clients'],
            'unique_users': row['unique_users'],
            'unique_ips': row['unique_ips'],
            'total_exports': row['total_exports'],
            'total_products_exported': row['total_products_exported'],
            'action_breakdown': action_breakdown,
            'success_rate': float(row['success_rate']),
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
