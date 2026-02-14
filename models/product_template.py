# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    """
    Extension du modèle product.template pour ajouter
    des fonctionnalités spécifiques au catalogue partagé.
    """
    _inherit = 'product.template'
    
    # === CATALOG PUBLISHING ===
    is_published = fields.Boolean(
        string='Published in Catalog',
        default=False,
        help='If checked, this product is visible in the shared catalog'
    )
    
    catalog_featured = fields.Boolean(
        string='Featured Product',
        default=False,
        help='Featured products appear first in catalog'
    )
    
    catalog_description = fields.Html(
        string='Catalog Description',
        help='Extended description for catalog display (if different from sales description)'
    )
    
    # === VISIBILITY CONTROL ===
    catalog_public = fields.Boolean(
        string='Public Catalog',
        default=True,
        help='If checked, visible in public (non-authenticated) catalog'
    )
    
    # === EXPORT INFO ===
    export_count = fields.Integer(
        string='Times Exported',
        compute='_compute_catalog_stats',
        store=False,
        help='Number of times this product has been exported by clients'
    )
    
    last_export_date = fields.Datetime(
        string='Last Export Date',
        compute='_compute_catalog_stats',
        store=False
    )
    
    view_count = fields.Integer(
        string='Catalog Views',
        compute='_compute_catalog_stats',
        store=False,
        help='Number of times this product has been viewed in catalog'
    )
    
    @api.depends('name')
    def _compute_catalog_stats(self):
        """Calcule les statistiques d'utilisation catalogue"""
        if not self.ids:
            return

        Log = self.env['catalog.access.log']

        # Export counts: single query via read_group on the m2m relation
        export_data = Log.read_group(
            domain=[
                ('product_ids', 'in', self.ids),
                ('action', 'in', ['export_csv', 'export_excel', 'direct_import']),
            ],
            fields=['product_ids'],
            groupby=['product_ids'],
        )
        export_counts = {d['product_ids'][0]: d['product_ids_count'] for d in export_data}

        # Last export dates: single query
        last_exports = {}
        if export_counts:
            self.env.cr.execute("""
                SELECT rel.product_id, MAX(log.create_date)
                FROM catalog_log_product_rel rel
                JOIN catalog_access_log log ON log.id = rel.log_id
                WHERE rel.product_id = ANY(%s)
                  AND log.action IN ('export_csv', 'export_excel', 'direct_import')
                GROUP BY rel.product_id
            """, [list(export_counts.keys())])
            last_exports = dict(self.env.cr.fetchall())

        # View counts: single query via read_group
        view_data = Log.read_group(
            domain=[
                ('product_ids', 'in', self.ids),
                ('action', '=', 'view_product'),
            ],
            fields=['product_ids'],
            groupby=['product_ids'],
        )
        view_counts = {d['product_ids'][0]: d['product_ids_count'] for d in view_data}

        for product in self:
            product.export_count = export_counts.get(product.id, 0)
            product.last_export_date = last_exports.get(product.id, False)
            product.view_count = view_counts.get(product.id, 0)
    
    def action_publish_catalog(self):
        """Action pour publier le(s) produit(s) dans le catalogue"""
        self.write({'is_published': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Products Published',
                'message': f'{len(self)} product(s) published in catalog',
                'type': 'success',
            }
        }
    
    def action_unpublish_catalog(self):
        """Action pour dépublier le(s) produit(s) du catalogue"""
        self.write({'is_published': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Products Unpublished',
                'message': f'{len(self)} product(s) unpublished from catalog',
                'type': 'info',
            }
        }
    
    def action_view_catalog_logs(self):
        """Action pour voir les logs d'accès de ce produit"""
        self.ensure_one()
        return {
            'name': f'Catalog Logs - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'catalog.access.log',
            'view_mode': 'list,form',
            'domain': [('product_ids', 'in', self.id)],
        }
    
    def get_catalog_data(self, pricelist=None, export_fields=None):
        """
        Retourne les données du produit formatées pour l'export catalogue.

        Args:
            pricelist: Product.Pricelist pour calculer le prix (optionnel)
            export_fields: catalog.export.field recordset (optionnel)
                          Si non fourni, utilise la config globale

        Returns:
            dict: Données du produit (seulement les champs activés)
        """
        self.ensure_one()

        # Get enabled export fields from config if not provided
        if export_fields is None:
            config = self.env['catalog.config'].get_config()
            export_fields = config.get_enabled_export_fields()

        # Build field mapping with all possible values
        if pricelist:
            price = pricelist._get_product_price(self, 1.0)
        else:
            price = self.list_price

        all_field_values = {
            'id': self.id,
            'name': self.name,
            'default_code': self.default_code or '',
            'barcode': self.barcode or '',
            'list_price': price,
            'standard_price': self.standard_price,
            'uom_name': self.uom_id.name,
            'categ_name': self.categ_id.display_name,
            'description_sale': self.description_sale or '',
            'catalog_description': self.catalog_description or self.description_sale or '',
            'weight': self.weight,
            'volume': self.volume,
            'image_url': f'/web/image/product.template/{self.id}/image_1920',
            'is_featured': self.catalog_featured,
            'type': self.type,
        }

        # Filter to only enabled fields (always include id)
        enabled_names = set(export_fields.mapped('technical_name'))
        result = {'id': self.id}
        for field_name, value in all_field_values.items():
            if field_name in enabled_names:
                result[field_name] = value

        return result
