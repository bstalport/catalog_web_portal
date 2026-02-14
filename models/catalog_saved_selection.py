# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CatalogSavedSelection(models.Model):
    _name = 'catalog.saved.selection'
    _description = 'Saved Product Selection'
    _order = 'create_date desc'

    name = fields.Char(
        string='Selection Name',
        required=True,
        help='Name to identify this saved selection'
    )
    catalog_client_id = fields.Many2one(
        'catalog.client',
        string='Client',
        required=True,
        ondelete='cascade',
        index=True,
        help='Client who owns this selection'
    )
    product_ids = fields.Many2many(
        'product.template',
        'catalog_saved_selection_product_rel',
        'selection_id',
        'product_id',
        string='Products',
        help='Products in this saved selection'
    )
    product_count = fields.Integer(
        string='Product Count',
        compute='_compute_product_count',
        store=True
    )
    create_date = fields.Datetime(
        string='Created On',
        readonly=True
    )

    @api.depends('product_ids')
    def _compute_product_count(self):
        for selection in self:
            selection.product_count = len(selection.product_ids)

    def action_load_selection(self):
        """Load this selection into the client's current selection"""
        self.ensure_one()

        # Update client's current selection
        self.catalog_client_id.selected_product_ids = [(6, 0, self.product_ids.ids)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Selection Loaded'),
                'message': _('Selection "%s" has been loaded (%d products)') % (self.name, self.product_count),
                'type': 'success',
                'sticky': False,
            }
        }
