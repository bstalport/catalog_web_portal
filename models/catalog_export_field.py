# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CatalogExportField(models.Model):
    """
    Définition des champs disponibles pour l'export catalogue.
    Permet au fournisseur de configurer quels champs produit
    seront exportables par les clients.
    """
    _name = 'catalog.export.field'
    _description = 'Catalog Export Field'
    _order = 'sequence, name'

    name = fields.Char(
        string='Field Label',
        required=True,
        translate=True,
        help='Display name shown to clients during export'
    )

    technical_name = fields.Char(
        string='Technical Name',
        required=True,
        help='Technical field name used in export (e.g., default_code, list_price)'
    )

    field_type = fields.Selection([
        ('product', 'Product Field'),
        ('computed', 'Computed Field'),
        ('relation', 'Related Field'),
    ], string='Field Type',
       default='product',
       required=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in export file columns'
    )

    is_default = fields.Boolean(
        string='Enabled by Default',
        default=True,
        help='If checked, this field is enabled by default for new configurations'
    )

    description = fields.Text(
        string='Description',
        translate=True,
        help='Description shown to supplier when configuring exports'
    )

    export_header = fields.Char(
        string='CSV Header',
        help='Column header in exported CSV (defaults to Field Label if empty)'
    )

    _sql_constraints = [
        ('technical_name_unique', 'UNIQUE(technical_name)',
         'Technical name must be unique!')
    ]

    def get_export_header(self):
        """Returns the header to use in export files"""
        self.ensure_one()
        return self.export_header or self.name
