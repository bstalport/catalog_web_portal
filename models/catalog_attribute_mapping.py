# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CatalogAttributeMapping(models.Model):
    """
    Cache le mapping entre un attribut fournisseur et un attribut dans l'Odoo client.
    Créé automatiquement lors de la synchronisation (match par nom).
    Peut être modifié manuellement pour gérer les cas de noms différents.
    """
    _name = 'catalog.attribute.mapping'
    _description = 'Attribute Mapping'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Attribut fournisseur
    supplier_attribute_id = fields.Many2one(
        'product.attribute',
        string='Supplier Attribute',
        required=True,
        ondelete='cascade'
    )
    supplier_attribute_name = fields.Char(
        related='supplier_attribute_id.name',
        string='Supplier Attribute Name',
        readonly=True
    )

    # Attribut côté client (stocké par ID car c'est un Odoo distant)
    client_attribute_id = fields.Integer(
        'Client Attribute ID',
        help='ID of the attribute in the client Odoo'
    )
    client_attribute_name = fields.Char(
        'Client Attribute Name',
        readonly=True,
        help='Name fetched from client Odoo'
    )

    auto_create = fields.Boolean(
        'Auto-create if Missing',
        default=True,
        help='Create attribute in client Odoo if it does not exist'
    )

    _sql_constraints = [
        ('unique_supplier_attribute', 'unique(connection_id, supplier_attribute_id)',
         'Each supplier attribute can only be mapped once per connection!')
    ]


class CatalogAttributeValueMapping(models.Model):
    """
    Cache le mapping entre une valeur d'attribut fournisseur et une valeur
    dans l'Odoo client. Créé automatiquement, modifiable manuellement.
    """
    _name = 'catalog.attribute.value.mapping'
    _description = 'Attribute Value Mapping'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Valeur fournisseur
    supplier_value_id = fields.Many2one(
        'product.attribute.value',
        string='Supplier Value',
        required=True,
        ondelete='cascade'
    )
    supplier_value_name = fields.Char(
        related='supplier_value_id.name',
        string='Supplier Value Name',
        readonly=True
    )
    supplier_attribute_id = fields.Many2one(
        related='supplier_value_id.attribute_id',
        string='Supplier Attribute',
        readonly=True,
        store=True
    )

    # Valeur côté client
    client_value_id = fields.Integer(
        'Client Value ID',
        help='ID of the attribute value in the client Odoo'
    )
    client_value_name = fields.Char(
        'Client Value Name',
        readonly=True
    )

    _sql_constraints = [
        ('unique_supplier_value', 'unique(connection_id, supplier_value_id)',
         'Each supplier value can only be mapped once per connection!')
    ]
