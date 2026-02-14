# -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
import xmlrpc.client
import json
import logging
import ssl
import base64
import threading
from odoo.orm.registry import Registry

_logger = logging.getLogger(__name__)


class _TimeoutTransport(xmlrpc.client.Transport):
    """XML-RPC Transport with configurable timeout."""
    def __init__(self, timeout=60, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """XML-RPC SafeTransport (HTTPS) with configurable timeout."""
    def __init__(self, timeout=60, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class CatalogClientConnection(models.Model):
    """
    Configuration de connexion pour synchroniser vers l'Odoo du client.
    Stocke les credentials (chiffrés) et les paramètres de mapping.
    """
    _name = 'catalog.client.connection'
    _description = 'Client Odoo Connection Configuration'
    _rec_name = 'client_id'

    # === BASIC INFO ===
    client_id = fields.Many2one(
        'catalog.client',
        string='Catalog Client',
        required=True,
        ondelete='cascade',
        index=True
    )

    # === CONNECTION SETTINGS ===
    odoo_url = fields.Char(
        'Client Odoo URL',
        required=True,
        help='Full URL of client Odoo instance (e.g., https://mycompany.odoo.com)'
    )
    database = fields.Char(
        'Database Name',
        required=True,
        help='Client database name'
    )
    api_key = fields.Char(
        'API Key',
        required=True,
        help='Client API key for authentication (stored encrypted)'
    )
    username = fields.Char(
        'Username',
        help='Alternative: username (if API key not available)'
    )

    # === STATUS ===
    is_active = fields.Boolean(
        'Active',
        default=True,
        help='If disabled, sync will not be available'
    )
    connection_status = fields.Selection([
        ('not_tested', 'Not Tested'),
        ('ok', 'Connected'),
        ('error', 'Connection Error'),
    ], string='Connection Status',
       default='not_tested',
       readonly=True
    )
    connection_error = fields.Text('Last Connection Error', readonly=True)
    last_test_date = fields.Datetime('Last Connection Test', readonly=True)
    last_sync_date = fields.Datetime('Last Sync', readonly=True)

    # === SYNC OPTIONS ===
    sync_variants = fields.Boolean(
        'Sync Product Variants',
        default=False,
        help='Sync product variants (attributes, values, and variant-specific data) '
             'to client Odoo. Only applies to direct import (XML-RPC).'
    )
    auto_create_categories = fields.Boolean(
        'Auto-create Categories',
        default=True,
        help='Automatically create missing categories in client Odoo'
    )
    include_images = fields.Boolean(
        'Include Product Images',
        default=True,
        help='Sync product images'
    )
    preserve_client_images = fields.Boolean(
        'Preserve Modified Images',
        default=True,
        help='If client has modified the image, keep their version'
    )
    verify_ssl = fields.Boolean(
        'Verify SSL Certificate',
        default=True,
        help='Disable for local development with self-signed certificates'
    )

    # === REFERENCE GENERATION ===
    reference_mode = fields.Selection([
        ('keep_original', 'Keep Original Reference'),
        ('supplier_ref', 'Use Supplier Reference'),
        ('product_id', 'Use Product ID'),
        ('custom_format', 'Custom Format'),
        ('none', 'No Reference (Empty)'),
    ], string='Reference Mode',
       default='keep_original',
       required=True,
       help='How to generate the product reference (default_code) in client Odoo'
    )
    reference_prefix = fields.Char(
        'Reference Prefix',
        help='Prefix to add before the reference (e.g., "SUP-")'
    )
    reference_suffix = fields.Char(
        'Reference Suffix',
        help='Suffix to add after the reference (e.g., "-IMP")'
    )
    reference_separator = fields.Char(
        'Separator',
        default='',
        help='Separator between prefix/reference/suffix (e.g., "-" or "_")'
    )
    reference_custom_format = fields.Char(
        'Custom Format',
        help='Custom format using placeholders: {prefix}, {ref}, {id}, {suffix}. Example: "{prefix}{ref}-{id}"'
    )

    # === SUPPLIER INFO (for invoice recognition) ===
    create_supplierinfo = fields.Boolean(
        'Create Supplier Info',
        default=True,
        help='Create product.supplierinfo records in client Odoo. '
             'This enables automatic product recognition when loading supplier invoices.'
    )
    supplier_partner_id = fields.Integer(
        'Supplier Partner ID (in client)',
        help='ID of your company (the supplier) in the client\'s Odoo. '
             'Required for creating product.supplierinfo records.'
    )
    supplier_partner_name = fields.Char(
        'Supplier Partner Name',
        readonly=True,
        help='Name of the supplier partner in client\'s Odoo (fetched automatically).'
    )
    supplierinfo_price_field = fields.Selection([
        ('list_price', 'Sales Price (from catalog)'),
        ('standard_price', 'Cost Price'),
        ('pricelist', 'Pricelist Price (client-specific)'),
    ], string='Price for Supplierinfo',
       default='list_price',
       help='Which price to use as the supplier price in product.supplierinfo'
    )
    supplierinfo_price_coefficient = fields.Float(
        'Price Coefficient',
        default=1.0,
        help='Multiply the price by this coefficient (e.g., 0.8 for 20% discount)'
    )

    # === RELATIONS ===
    field_mapping_ids = fields.One2many(
        'catalog.field.mapping',
        'connection_id',
        string='Field Mappings'
    )
    category_mapping_ids = fields.One2many(
        'catalog.category.mapping',
        'connection_id',
        string='Category Mappings'
    )
    sync_history_ids = fields.One2many(
        'catalog.sync.history',
        'connection_id',
        string='Sync History'
    )
    attribute_mapping_ids = fields.One2many(
        'catalog.attribute.mapping',
        'connection_id',
        string='Attribute Mappings'
    )
    attribute_value_mapping_ids = fields.One2many(
        'catalog.attribute.value.mapping',
        'connection_id',
        string='Attribute Value Mappings'
    )

    # === STATS ===
    total_syncs = fields.Integer('Total Syncs', compute='_compute_stats', store=True)
    last_sync_status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('error', 'Error'),
    ], string='Last Sync Status', compute='_compute_stats', store=True)

    @api.depends('sync_history_ids')
    def _compute_stats(self):
        for record in self:
            record.total_syncs = len(record.sync_history_ids)
            if record.sync_history_ids:
                last = record.sync_history_ids.sorted('create_date', reverse=True)[0]
                record.last_sync_status = last.status
            else:
                record.last_sync_status = False

    @api.constrains('odoo_url')
    def _check_odoo_url(self):
        """Validate URL format"""
        for record in self:
            if not record.odoo_url.startswith(('http://', 'https://')):
                raise ValidationError(_('Odoo URL must start with http:// or https://'))

    def _get_xmlrpc_proxy(self, endpoint, timeout=60):
        """Create XML-RPC proxy with optional SSL verification and timeout"""
        self.ensure_one()
        url = f'{self.odoo_url}/xmlrpc/2/{endpoint}'

        if not self.verify_ssl and self.odoo_url.startswith('https://'):
            ssl_context = ssl._create_unverified_context()
            transport = _TimeoutSafeTransport(timeout=timeout, context=ssl_context)
        else:
            if self.odoo_url.startswith('https://'):
                transport = _TimeoutSafeTransport(timeout=timeout)
            else:
                transport = _TimeoutTransport(timeout=timeout)
        return xmlrpc.client.ServerProxy(url, transport=transport)

    def action_test_connection(self):
        """Test connection to client Odoo"""
        self.ensure_one()
        try:
            # Connect to client Odoo
            common = self._get_xmlrpc_proxy('common')

            # Try to authenticate
            uid = common.authenticate(
                self.database,
                self.username or 'apiuser',
                self.api_key,
                {}
            )

            if not uid:
                raise UserError(_(
                    'Authentication failed.\n\n'
                    'Please verify:\n'
                    '• API Key is valid (not expired)\n'
                    '• Username is correct\n'
                    '• Database name is correct\n\n'
                    'Tip: Generate a new API Key in your Odoo:\n'
                    'Settings → Users → Your User → API Keys'
                ))

            # Test access to product.template
            models = self._get_xmlrpc_proxy('object')
            models.execute_kw(
                self.database,
                uid,
                self.api_key,
                'product.template',
                'check_access_rights',
                ['read'],
                {'raise_exception': False}
            )

            # Success
            self.write({
                'connection_status': 'ok',
                'connection_error': False,
                'last_test_date': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('Successfully connected to client Odoo'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = str(e)
            self.write({
                'connection_status': 'error',
                'connection_error': error_msg,
                'last_test_date': fields.Datetime.now(),
            })

            raise UserError(_('Connection failed: %s') % error_msg)

    def action_create_default_mappings(self):
        """Create default field and category mappings"""
        self.ensure_one()

        # Default field mappings
        # (source_field, target_field, sync_mode, default_value, default_value_apply)
        default_fields = [
            ('name', 'name', 'always', False, 'never'),
            ('default_code', 'default_code', 'create_only', False, 'never'),
            ('list_price', 'standard_price', 'always', False, 'never'),
            ('barcode', 'barcode', 'if_empty', False, 'never'),
            ('weight', 'weight', 'always', False, 'never'),
            ('volume', 'volume', 'always', False, 'never'),
            ('description_sale', 'description_purchase', 'if_empty', False, 'never'),
            # Target-only fields (replace hardcoded values in _execute_create)
            ('_none', 'type', 'create_only', 'consu', 'always'),
            ('_none', 'sale_ok', 'create_only', 'true', 'always'),
            ('_none', 'purchase_ok', 'create_only', 'true', 'always'),
            ('is_published', 'is_published', 'always', False, 'never'),
        ]

        sequence = 10
        for source, target, sync_mode, default_val, default_apply in default_fields:
            vals = {
                'connection_id': self.id,
                'source_field': source,
                'target_field': target,
                'sync_mode': sync_mode,
                'sequence': sequence,
                'default_value_apply': default_apply,
            }
            if default_val:
                vals['default_value'] = default_val
            self.env['catalog.field.mapping'].create(vals)
            sequence += 10

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Default Mappings Created'),
                'message': _('%d field mappings created') % len(default_fields),
                'type': 'success',
            }
        }

    def generate_product_reference(self, product):
        """
        Generate product reference based on connection configuration.

        Args:
            product: product.template record

        Returns:
            str: Generated reference or False
        """
        self.ensure_one()

        if self.reference_mode == 'none':
            return False

        if self.reference_mode == 'keep_original':
            # Keep the original default_code from supplier
            base_ref = product.default_code or ''
        elif self.reference_mode == 'product_id':
            # Use product ID
            base_ref = str(product.id)
        elif self.reference_mode == 'supplier_ref':
            # Use supplier reference (default_code)
            base_ref = product.default_code or ''
        elif self.reference_mode == 'custom_format':
            # Use custom format with placeholders
            if self.reference_custom_format:
                return self.reference_custom_format.format(
                    prefix=self.reference_prefix or '',
                    ref=product.default_code or '',
                    id=product.id,
                    suffix=self.reference_suffix or '',
                    separator=self.reference_separator or ''
                )
            else:
                base_ref = product.default_code or ''
        else:
            base_ref = product.default_code or ''

        # Build reference with prefix/suffix
        parts = []
        if self.reference_prefix:
            parts.append(self.reference_prefix)
        if base_ref:
            parts.append(base_ref)
        if self.reference_suffix:
            parts.append(self.reference_suffix)

        separator = self.reference_separator or ''
        return separator.join(parts) if parts else False

    def fetch_client_categories(self):
        """
        Fetch product categories from client's Odoo via XML-RPC.
        Returns list of dicts with id and name.
        """
        self.ensure_one()

        if self.connection_status != 'ok':
            raise UserError(_('Please test the connection first'))

        try:
            # Authenticate
            common = self._get_xmlrpc_proxy('common')
            uid = common.authenticate(
                self.database,
                self.username or 'apiuser',
                self.api_key,
                {}
            )

            if not uid:
                raise UserError(_('Authentication failed'))

            # Fetch categories
            models = self._get_xmlrpc_proxy('object')
            categories = models.execute_kw(
                self.database,
                uid,
                self.api_key,
                'product.category',
                'search_read',
                [[]],
                {'fields': ['id', 'name', 'complete_name'], 'limit': 1000}
            )

            return categories

        except Exception as e:
            _logger.error(f"Error fetching client categories: {e}")
            raise UserError(_('Failed to fetch categories: %s') % str(e))

    def action_search_supplier_partner(self):
        """
        Search for the supplier partner in client's Odoo.
        Searches by company name or VAT number.
        """
        self.ensure_one()

        if self.connection_status != 'ok':
            raise UserError(_('Please test the connection first'))

        try:
            # Get our company info
            company = self.env.company
            company_name = company.name
            company_vat = company.vat

            # Authenticate
            common = self._get_xmlrpc_proxy('common')
            uid = common.authenticate(
                self.database,
                self.username or 'apiuser',
                self.api_key,
                {}
            )

            if not uid:
                raise UserError(_('Authentication failed'))

            models = self._get_xmlrpc_proxy('object')

            # Search by VAT first (more reliable)
            partner_ids = []
            if company_vat:
                partner_ids = models.execute_kw(
                    self.database, uid, self.api_key,
                    'res.partner', 'search',
                    [[('vat', '=', company_vat), ('is_company', '=', True)]]
                )

            # If not found, search by name
            if not partner_ids:
                partner_ids = models.execute_kw(
                    self.database, uid, self.api_key,
                    'res.partner', 'search',
                    [[('name', 'ilike', company_name), ('is_company', '=', True)]],
                    {'limit': 5}
                )

            if partner_ids:
                # Get partner details
                partners = models.execute_kw(
                    self.database, uid, self.api_key,
                    'res.partner', 'read',
                    [partner_ids],
                    {'fields': ['id', 'name', 'vat']}
                )

                if len(partners) == 1:
                    # Single match - use it
                    self.write({
                        'supplier_partner_id': partners[0]['id'],
                        'supplier_partner_name': partners[0]['name'],
                    })
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Supplier Partner Found'),
                            'message': _('Found: %s (ID: %d)') % (partners[0]['name'], partners[0]['id']),
                            'type': 'success',
                        }
                    }
                else:
                    # Multiple matches - inform user
                    partner_list = ', '.join([f"{p['name']} (ID: {p['id']})" for p in partners])
                    raise UserError(_(
                        'Multiple partners found. Please set the ID manually:\n%s'
                    ) % partner_list)
            else:
                raise UserError(_(
                    'No partner found in client\'s Odoo matching:\n'
                    '• Name: %s\n'
                    '• VAT: %s\n\n'
                    'You can create it or set the ID manually.'
                ) % (company_name, company_vat or 'N/A'))

        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error searching supplier partner: {e}")
            raise UserError(_('Failed to search partner: %s') % str(e))

    def action_create_supplier_partner(self):
        """
        Create the supplier partner in client's Odoo using our company info.
        """
        self.ensure_one()

        if self.connection_status != 'ok':
            raise UserError(_('Please test the connection first'))

        try:
            # Get our company info
            company = self.env.company

            # Authenticate
            common = self._get_xmlrpc_proxy('common')
            uid = common.authenticate(
                self.database,
                self.username or 'apiuser',
                self.api_key,
                {}
            )

            if not uid:
                raise UserError(_('Authentication failed'))

            models = self._get_xmlrpc_proxy('object')

            # Prepare partner values
            partner_vals = {
                'name': company.name,
                'is_company': True,
                'supplier_rank': 1,  # Mark as supplier
                'customer_rank': 0,
                'vat': company.vat or False,
                'phone': company.phone or False,
                'email': company.email or False,
                'website': company.website or False,
                'street': company.street or False,
                'street2': company.street2 or False,
                'city': company.city or False,
                'zip': company.zip or False,
            }

            # Create partner
            partner_id = models.execute_kw(
                self.database, uid, self.api_key,
                'res.partner', 'create',
                [partner_vals]
            )

            self.write({
                'supplier_partner_id': partner_id,
                'supplier_partner_name': company.name,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Supplier Partner Created'),
                    'message': _('Created: %s (ID: %d)') % (company.name, partner_id),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Error creating supplier partner: {e}")
            raise UserError(_('Failed to create partner: %s') % str(e))

    def _get_supplierinfo_price(self, product, pricelist=None):
        """
        Get the price to use for product.supplierinfo based on configuration.

        Args:
            product: product.template record
            pricelist: optional product.pricelist record

        Returns:
            float: The price to use
        """
        self.ensure_one()

        if self.supplierinfo_price_field == 'standard_price':
            price = product.standard_price
        elif self.supplierinfo_price_field == 'pricelist' and pricelist:
            price = pricelist._get_product_price(product, 1.0)
        else:
            price = product.list_price

        # Apply coefficient
        if self.supplierinfo_price_coefficient:
            price = price * self.supplierinfo_price_coefficient

        return price


class CatalogFieldMapping(models.Model):
    """
    Définit comment un champ du fournisseur est mappé vers un champ client.
    Exemple: list_price (fournisseur) → standard_price (client)
    """
    _name = 'catalog.field.mapping'
    _description = 'Field Mapping Configuration'
    _order = 'sequence, id'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer('Sequence', default=10)

    # Source (fournisseur)
    source_field = fields.Selection([
        ('_none', '(No Source - Default Only)'),
        ('name', 'Product Name'),
        ('default_code', 'Internal Reference'),
        ('list_price', 'Sales Price'),
        ('standard_price', 'Cost Price'),
        ('barcode', 'Barcode'),
        ('weight', 'Weight'),
        ('volume', 'Volume'),
        ('uom_id', 'Unit of Measure'),
        ('description_sale', 'Sales Description'),
        ('description', 'Internal Notes'),
        ('description_purchase', 'Purchase Description'),
        ('categ_id', 'Category'),
        ('detailed_type', 'Product Type'),
        ('sale_ok', 'Can be Sold'),
        ('purchase_ok', 'Can be Purchased'),
        ('is_published', 'Published (Website)'),
    ], string='Supplier Field', required=True, default='_none')

    # Target (client)
    target_field = fields.Selection([
        ('name', 'Product Name'),
        ('default_code', 'Internal Reference'),
        ('list_price', 'Sales Price'),
        ('standard_price', 'Cost Price'),
        ('barcode', 'Barcode'),
        ('weight', 'Weight'),
        ('volume', 'Volume'),
        ('uom_id', 'Unit of Measure'),
        ('description_sale', 'Sales Description'),
        ('description', 'Internal Notes'),
        ('description_purchase', 'Purchase Description'),
        ('categ_id', 'Category'),
        ('detailed_type', 'Product Type'),
        ('type', 'Product Type (legacy)'),
        ('sale_ok', 'Can be Sold'),
        ('purchase_ok', 'Can be Purchased'),
        ('is_published', 'Published (Website)'),
    ], string='Client Field', required=True)

    # Sync behavior
    sync_mode = fields.Selection([
        ('create_only', 'Only on Creation'),
        ('always', 'Always Update'),
        ('if_empty', 'Only if Empty'),
        ('manual', 'Manual Approval'),
    ], string='Sync Mode',
       default='always',
       required=True,
       help='When to sync this field'
    )

    # Default value
    default_value = fields.Char(
        'Default Value',
        help='Value to use when source is empty or when apply mode is "always". '
             'For booleans: "true"/"false". For floats: "1.5". '
             'For selection: the technical key (e.g., "consu").'
    )
    default_value_apply = fields.Selection([
        ('never', 'Never'),
        ('if_source_empty', 'If Source is Empty'),
        ('always', 'Always Use Default'),
    ], string='Default Apply Mode',
       default='never',
       required=True,
       help='When to use the default value instead of the source value'
    )

    # Transformation
    apply_coefficient = fields.Boolean(
        'Apply Coefficient',
        help='Multiply value by coefficient before sync'
    )
    coefficient = fields.Float(
        'Coefficient',
        default=1.0,
        help='Value will be multiplied by this (e.g., 1.2 for 20% markup)'
    )

    is_active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('unique_mapping', 'unique(connection_id, target_field)',
         'Each target field can only be mapped once per connection!')
    ]

    # Target field type mapping for default value conversion
    TARGET_FIELD_TYPES = {
        'name': 'char',
        'default_code': 'char',
        'list_price': 'float',
        'standard_price': 'float',
        'barcode': 'char',
        'weight': 'float',
        'volume': 'float',
        'description_sale': 'text',
        'description_purchase': 'text',
        'categ_id': 'integer',
        'type': 'selection',
        'sale_ok': 'boolean',
        'purchase_ok': 'boolean',
        'is_published': 'boolean',
    }

    def _convert_default_value(self):
        """Convert the char default_value to the appropriate Python type
        for the target field."""
        self.ensure_one()
        if not self.default_value:
            return False

        field_type = self.TARGET_FIELD_TYPES.get(self.target_field, 'char')
        raw = self.default_value.strip()

        if field_type == 'float':
            try:
                return float(raw)
            except (ValueError, TypeError):
                return 0.0
        elif field_type == 'integer':
            try:
                return int(raw)
            except (ValueError, TypeError):
                return False
        elif field_type == 'boolean':
            return raw.lower() in ('true', '1', 'yes', 'oui')
        else:
            return raw

    def _resolve_value(self, product=None):
        """Resolve the effective value for this mapping given a source product.

        Args:
            product: product.template record (supplier's product), or None
                     for target-only mappings.

        Returns:
            The resolved value to sync.
        """
        self.ensure_one()
        default_val = self._convert_default_value()

        # Always use default — ignore source entirely
        if self.default_value_apply == 'always' and self.default_value:
            return default_val

        # No source field (target-only mapping) — must use default
        if self.source_field == '_none':
            return default_val if self.default_value else False

        # Read from source
        source_value = product[self.source_field] if product else False

        # Source is empty and we have a fallback default
        if self.default_value_apply == 'if_source_empty' and not source_value and self.default_value:
            return default_val

        # Apply coefficient if applicable
        if self.apply_coefficient and isinstance(source_value, (int, float)):
            source_value = source_value * self.coefficient

        return source_value


class CatalogCategoryMapping(models.Model):
    """
    Associe une catégorie du fournisseur à une catégorie dans l'Odoo client.
    Permet de mapper les catégories ou d'auto-créer si manquant.
    """
    _name = 'catalog.category.mapping'
    _description = 'Category Mapping'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Catégorie fournisseur
    supplier_category_id = fields.Many2one(
        'product.category',
        string='Supplier Category',
        required=True,
        ondelete='cascade'
    )
    supplier_category_name = fields.Char(
        related='supplier_category_id.complete_name',
        string='Supplier Category Path',
        readonly=True
    )

    # Catégorie client (External ID ou auto-créée)
    client_category_id = fields.Integer(
        'Client Category ID',
        help='ID of the category in client Odoo (if exists)'
    )
    client_category_name = fields.Char(
        'Client Category Name',
        readonly=True,
        help='Name fetched from client Odoo'
    )

    # Options
    auto_create = fields.Boolean(
        'Auto-create if Missing',
        default=True,
        help='Create category in client Odoo if it does not exist'
    )

    _sql_constraints = [
        ('unique_supplier_category', 'unique(connection_id, supplier_category_id)',
         'Each supplier category can only be mapped once per connection!')
    ]


class CatalogSyncHistory(models.Model):
    """
    Historique des synchronisations effectuées.
    Permet de tracer qui a fait quoi et quand.
    """
    _name = 'catalog.sync.history'
    _description = 'Sync History'
    _order = 'create_date desc'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade',
        index=True
    )

    # User who triggered
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)

    # Stats
    products_created = fields.Integer('Products Created', default=0)
    products_updated = fields.Integer('Products Updated', default=0)
    products_skipped = fields.Integer('Products Skipped', default=0)
    products_error = fields.Integer('Products with Errors', default=0)

    total_products = fields.Integer('Total Products', compute='_compute_total')

    @api.depends('products_created', 'products_updated', 'products_skipped', 'products_error')
    def _compute_total(self):
        for record in self:
            record.total_products = (record.products_created + record.products_updated +
                                    record.products_skipped + record.products_error)

    # Status
    status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial (with errors)'),
        ('error', 'Failed'),
    ], required=True, default='success')

    error_message = fields.Text('Error Message')

    # Details (JSON)
    details = fields.Text(
        'Sync Details',
        help='JSON with detailed changes'
    )

    # Duration
    duration = fields.Float('Duration (seconds)', help='Time taken for sync')


class CatalogSyncPreview(models.TransientModel):
    """
    Modèle transient pour générer et afficher un aperçu des changements
    avant d'exécuter la synchronisation.

    CRITIQUE: Permet au client de voir exactement ce qui va être modifié.
    """
    _name = 'catalog.sync.preview'
    _description = 'Sync Preview (Transient)'

    connection_id = fields.Many2one(
        'catalog.client.connection',
        required=True,
        ondelete='cascade'
    )

    product_ids = fields.Many2many(
        'product.template',
        string='Products to Sync'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzing', 'Analyzing...'),
        ('ready', 'Ready for Review'),
        ('executing', 'Executing...'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True)

    # Progress tracking (for background sync)
    sync_progress = fields.Integer('Progress (%)', default=0)
    sync_current = fields.Integer('Current Product', default=0)
    sync_total = fields.Integer('Total Products', default=0)
    sync_message = fields.Char('Current Status', default='')
    sync_history_id = fields.Many2one('catalog.sync.history', string='Sync Result')
    sync_error_message = fields.Text('Sync Error', default='')

    # Stats
    products_to_create = fields.Integer('Will Create', compute='_compute_stats')
    products_to_update = fields.Integer('Will Update', compute='_compute_stats')
    products_to_skip = fields.Integer('Will Skip', compute='_compute_stats')
    products_with_warnings = fields.Integer('Warnings', compute='_compute_stats')

    @api.depends('change_ids', 'change_ids.change_type', 'change_ids.has_warning')
    def _compute_stats(self):
        for record in self:
            record.products_to_create = len(record.change_ids.filtered(lambda c: c.change_type == 'create'))
            record.products_to_update = len(record.change_ids.filtered(lambda c: c.change_type == 'update'))
            record.products_to_skip = len(record.change_ids.filtered(lambda c: c.change_type == 'skip'))
            record.products_with_warnings = len(record.change_ids.filtered(lambda c: c.has_warning))

    # Changes
    change_ids = fields.One2many(
        'catalog.sync.change',
        'preview_id',
        string='Changes'
    )

    def action_generate_preview(self):
        """Analyse les produits et génère le diff"""
        self.ensure_one()

        if not self.product_ids:
            raise UserError(_('No products selected for sync'))

        self.state = 'analyzing'

        try:
            # Clear existing changes
            self.change_ids.unlink()

            # Connect to client Odoo
            connection = self.connection_id
            common = connection._get_xmlrpc_proxy('common')

            # Debug logging
            username = connection.username or 'apiuser'
            _logger.info(f"Attempting authentication - URL: {connection.odoo_url}, DB: {connection.database}, User: {username}")

            uid = common.authenticate(connection.database, username, connection.api_key, {})

            if not uid:
                _logger.error(f"Authentication failed - URL: {connection.odoo_url}, DB: {connection.database}, User: {username}")
                raise UserError(_(
                    'Authentication failed - Unable to connect to your Odoo.\n\n'
                    'Possible causes:\n'
                    '• Your API Key may be invalid or expired\n'
                    '• The Username may be incorrect\n'
                    '• The Database name may be wrong\n\n'
                    'Please:\n'
                    '1. Go to the Connection Setup page\n'
                    '2. Verify your API Key is still valid\n'
                    '3. Generate a new API Key if needed\n'
                    '4. Test the connection again'
                ))

            models = connection._get_xmlrpc_proxy('object')

            # For each product, check if exists and compute changes
            for product in self.product_ids:
                external_id = f'supplier_{connection.client_id.id}_product_{product.id}'

                # Search by external ID
                client_product_ids = models.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.template', 'search',
                    [[('default_code', '=', external_id)]]  # Simplified: use default_code as external ID
                )

                if client_product_ids:
                    # Product exists → UPDATE
                    self._create_update_change(product, client_product_ids[0], models, uid, connection)
                else:
                    # Product doesn't exist → CREATE
                    self._create_create_change(product, connection)

            self.state = 'ready'

        except Exception as e:
            _logger.error(f"Preview generation failed: {e}")
            self.state = 'draft'
            raise UserError(_('Preview generation failed: %s') % str(e))

    def _create_create_change(self, product, connection):
        """Create a change record for product creation"""
        changes = {}

        # Collect all fields to sync
        for mapping in connection.field_mapping_ids.filtered(lambda m: m.is_active):
            # Skip default_code if reference generation is configured
            if mapping.target_field == 'default_code' and connection.reference_mode != 'keep_original':
                continue

            value = mapping._resolve_value(product)

            changes[mapping.target_field] = {
                'old': None,
                'new': value
            }

        # Apply reference generation configuration
        generated_ref = connection.generate_product_reference(product)
        if generated_ref is not False:  # False means no reference (mode = 'none')
            changes['default_code'] = {
                'old': None,
                'new': generated_ref
            }

        # Variant preview data
        variant_data = []
        if connection.sync_variants:
            variant_data = self._get_variant_preview_data(product, connection)

        self.env['catalog.sync.change'].create({
            'preview_id': self.id,
            'product_id': product.id,
            'change_type': 'create',
            'field_changes': json.dumps(changes),
            'variant_changes': json.dumps(variant_data) if variant_data else False,
        })

    def _create_update_change(self, product, client_product_id, models_proxy, uid, connection):
        """Create a change record for product update"""
        # Build dynamic list of target fields to read from client
        active_mappings = connection.field_mapping_ids.filtered(lambda m: m.is_active and m.sync_mode != 'create_only')
        target_fields_to_read = list(set(
            m.target_field for m in active_mappings
            if m.target_field != 'categ_id'  # categ_id needs special handling
        ))
        if not target_fields_to_read:
            target_fields_to_read = ['name']  # fallback

        # Fetch current client product data
        client_data = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.template', 'read',
            [[client_product_id]],
            {'fields': target_fields_to_read}
        )[0]

        changes = {}
        has_changes = False

        # Compare each mapped field
        for mapping in active_mappings:
            value = mapping._resolve_value(product)

            # Get current client value
            client_value = client_data.get(mapping.target_field)

            # Check if_empty mode
            if mapping.sync_mode == 'if_empty' and client_value:
                continue

            # Check if value changed
            if value != client_value:
                changes[mapping.target_field] = {
                    'old': client_value,
                    'new': value
                }
                has_changes = True

        # Variant preview data
        variant_data = []
        if connection.sync_variants:
            variant_data = self._get_variant_preview_data(
                product, connection, models_proxy, uid, client_product_id
            )

        has_variant_changes = bool(variant_data)

        if has_changes or has_variant_changes:
            # Detect warnings (e.g., price decrease)
            warning = self._detect_warnings(changes)

            change_type = 'update' if has_changes else 'update'

            self.env['catalog.sync.change'].create({
                'preview_id': self.id,
                'product_id': product.id,
                'change_type': change_type,
                'client_product_id': client_product_id,
                'field_changes': json.dumps(changes) if changes else False,
                'variant_changes': json.dumps(variant_data) if variant_data else False,
                'has_warning': bool(warning),
                'warning_message': warning,
            })
        else:
            # No changes → skip
            self.env['catalog.sync.change'].create({
                'preview_id': self.id,
                'product_id': product.id,
                'change_type': 'skip',
                'client_product_id': client_product_id,
            })

    def _detect_warnings(self, changes):
        """Detect potential issues in changes"""
        warnings = []

        # Price decrease > 10%
        if 'standard_price' in changes:
            old = changes['standard_price']['old']
            new = changes['standard_price']['new']
            if old and new and old > 0:
                decrease_pct = ((old - new) / old) * 100
                if decrease_pct > 10:
                    warnings.append(f'Price decrease: {decrease_pct:.1f}%')

        return ' | '.join(warnings) if warnings else False

    def action_execute_sync(self):
        """Execute the synchronization based on preview"""
        self.ensure_one()

        if self.state != 'ready':
            raise UserError(_('Preview must be analyzed first'))

        self.state = 'executing'

        connection = self.connection_id
        start_time = fields.Datetime.now()

        # Statistics
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        errors = []

        try:
            # Connect to client Odoo
            common = connection._get_xmlrpc_proxy('common')
            uid = common.authenticate(connection.database, connection.username or 'apiuser', connection.api_key, {})

            if not uid:
                raise UserError(_('Authentication failed'))

            models = connection._get_xmlrpc_proxy('object')

            # Process each change (excluding those marked as excluded)
            for change in self.change_ids.filtered(lambda c: not c.is_excluded):
                try:
                    if change.change_type == 'create':
                        self._execute_create(change, models, uid, connection)
                        stats['created'] += 1

                    elif change.change_type == 'update':
                        self._execute_update(change, models, uid, connection)
                        stats['updated'] += 1

                    elif change.change_type == 'skip':
                        stats['skipped'] += 1

                except Exception as e:
                    _logger.error(f"Error syncing product {change.product_id.id}: {e}")
                    errors.append(f"{change.product_name}: {str(e)}")
                    stats['errors'] += 1

            # Calculate duration
            end_time = fields.Datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Determine status
            if stats['errors'] == 0:
                status = 'success'
            elif stats['created'] + stats['updated'] > 0:
                status = 'partial'
            else:
                status = 'error'

            # Create history record
            self.env['catalog.sync.history'].create({
                'connection_id': connection.id,
                'user_id': self.env.user.id,
                'products_created': stats['created'],
                'products_updated': stats['updated'],
                'products_skipped': stats['skipped'],
                'products_error': stats['errors'],
                'status': status,
                'error_message': '\n'.join(errors) if errors else False,
                'details': json.dumps({
                    'products': [c.product_id.name for c in self.change_ids],
                    'errors': errors,
                }),
                'duration': duration,
            })

            # Update connection
            connection.write({
                'last_sync_date': fields.Datetime.now(),
            })

            self.state = 'done'

            # Return notification
            message = _('%d products created, %d updated, %d errors') % (
                stats['created'], stats['updated'], stats['errors']
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Complete'),
                    'message': message,
                    'type': 'success' if status == 'success' else 'warning',
                    'sticky': True,
                }
            }

        except Exception as e:
            self.state = 'ready'
            raise UserError(_('Sync failed: %s') % str(e))

    def action_cancel_sync(self):
        """Request cancellation of a running background sync."""
        self.ensure_one()
        if self.state == 'executing':
            self.write({
                'state': 'cancelled',
                'sync_message': 'Cancelling...',
            })

    def action_execute_sync_background(self):
        """Launch sync in a background thread for portal usage (avoids HTTP timeout)."""
        self.ensure_one()

        if self.state != 'ready':
            raise UserError(_('Preview must be analyzed first'))

        total = len(self.change_ids.filtered(lambda c: not c.is_excluded))
        self.write({
            'state': 'executing',
            'sync_progress': 0,
            'sync_current': 0,
            'sync_total': total,
            'sync_message': 'Starting import...',
            'sync_error_message': '',
        })
        # Commit so the state is visible to other requests immediately
        self.env.cr.commit()

        # Launch background thread
        db_name = self.env.cr.dbname
        user_id = self.env.uid  # portal user who triggered the sync
        context = dict(self.env.context)
        preview_id = self.id

        thread = threading.Thread(
            target=CatalogSyncPreview._run_sync_thread,
            args=(db_name, user_id, context, preview_id),
            daemon=True
        )
        thread.start()

    @staticmethod
    def _run_sync_thread(db_name, user_id, context, preview_id):
        """Execute sync in a separate thread with its own cursor.
        Uses SUPERUSER_ID because portal users don't have access to internal models.
        user_id is the original portal user (for history tracking)."""
        try:
            registry = Registry(db_name)
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, context)
                preview = env['catalog.sync.preview'].browse(preview_id)

                if not preview.exists():
                    _logger.error("Sync thread: preview %s not found", preview_id)
                    return

                connection = preview.connection_id
                start_time = fields.Datetime.now()

                stats = {
                    'created': 0,
                    'updated': 0,
                    'skipped': 0,
                    'errors': 0,
                }
                errors = []

                try:
                    # Connect to client Odoo
                    common = connection._get_xmlrpc_proxy('common')
                    models_proxy = common  # temp
                    client_uid = common.authenticate(
                        connection.database,
                        connection.username or 'apiuser',
                        connection.api_key,
                        {}
                    )

                    if not client_uid:
                        raise UserError(_('Authentication failed'))

                    models_proxy = connection._get_xmlrpc_proxy('object')

                    changes = preview.change_ids.filtered(lambda c: not c.is_excluded)
                    total = len(changes)

                    for idx, change in enumerate(changes, 1):
                        try:
                            # Check for cancellation (re-read state from DB)
                            cr.execute(
                                "SELECT state FROM catalog_sync_preview WHERE id = %s",
                                (preview_id,)
                            )
                            row = cr.fetchone()
                            if not row or row[0] == 'cancelled':
                                _logger.info("Sync cancelled by user at product %d/%d", idx, total)
                                preview.write({
                                    'sync_message': 'Import cancelled by user',
                                })
                                cr.commit()
                                break

                            product_name = change.product_id.name or 'Unknown'

                            # Update progress
                            progress = int((idx / total) * 100) if total else 100
                            preview.write({
                                'sync_current': idx,
                                'sync_progress': progress,
                                'sync_message': f'Importing {product_name}... ({idx}/{total})',
                            })
                            cr.commit()

                            if change.change_type == 'create':
                                preview._execute_create(change, models_proxy, client_uid, connection)
                                stats['created'] += 1
                            elif change.change_type == 'update':
                                preview._execute_update(change, models_proxy, client_uid, connection)
                                stats['updated'] += 1
                            elif change.change_type == 'skip':
                                stats['skipped'] += 1

                        except Exception as e:
                            _logger.error("Error syncing product %s: %s", change.product_id.id, e)
                            errors.append(f"{change.product_name}: {str(e)}")
                            stats['errors'] += 1

                    # Check if cancelled
                    cr.execute(
                        "SELECT state FROM catalog_sync_preview WHERE id = %s",
                        (preview_id,)
                    )
                    row = cr.fetchone()
                    was_cancelled = row and row[0] == 'cancelled'

                    # Calculate duration
                    end_time = fields.Datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    # Determine status
                    if was_cancelled:
                        if stats['created'] + stats['updated'] > 0:
                            status = 'partial'
                        else:
                            status = 'error'
                    elif stats['errors'] == 0:
                        status = 'success'
                    elif stats['created'] + stats['updated'] > 0:
                        status = 'partial'
                    else:
                        status = 'error'

                    # Create history record
                    history = env['catalog.sync.history'].create({
                        'connection_id': connection.id,
                        'user_id': user_id,
                        'products_created': stats['created'],
                        'products_updated': stats['updated'],
                        'products_skipped': stats['skipped'],
                        'products_error': stats['errors'],
                        'status': status,
                        'error_message': '\n'.join(errors) if errors else (
                            'Import cancelled by user' if was_cancelled else False
                        ),
                        'details': json.dumps({
                            'products': [c.product_id.name for c in preview.change_ids],
                            'errors': errors,
                        }),
                        'duration': duration,
                    })

                    # Update connection
                    connection.write({
                        'last_sync_date': fields.Datetime.now(),
                    })

                    # Mark done with history reference
                    preview.write({
                        'state': 'done',
                        'sync_progress': 100,
                        'sync_message': 'Import cancelled by user' if was_cancelled else 'Import complete!',
                        'sync_history_id': history.id,
                    })
                    cr.commit()

                    _logger.info(
                        "Background sync complete: %d created, %d updated, %d errors",
                        stats['created'], stats['updated'], stats['errors']
                    )

                except Exception as e:
                    _logger.error("Background sync fatal error: %s", e, exc_info=True)
                    cr.rollback()
                    # Write error with a fresh read
                    preview = env['catalog.sync.preview'].browse(preview_id)
                    if preview.exists():
                        preview.write({
                            'state': 'ready',
                            'sync_error_message': str(e),
                            'sync_message': 'Import failed',
                        })
                        cr.commit()

        except Exception as e:
            _logger.error("Background sync thread crashed: %s", e, exc_info=True)

    def _execute_create(self, change, models_proxy, uid, connection):
        """Create a new product in client Odoo"""
        product = change.product_id
        external_id = f'supplier_{connection.client_id.id}_product_{product.id}'

        # Apply field mappings (including generated default_code)
        values = {}
        field_changes = json.loads(change.field_changes) if change.field_changes else {}
        for target_field, change_data in field_changes.items():
            values[target_field] = change_data['new']

        # Backward-compatible defaults for connections without type/sale_ok/purchase_ok mappings
        values.setdefault('type', 'consu')
        values.setdefault('sale_ok', True)
        values.setdefault('purchase_ok', True)
        if 'name' not in values or not values['name']:
            values['name'] = product.name

        # If no default_code was set (reference_mode = 'none'), use external_id as fallback
        # This ensures products can still be found/updated later
        if 'default_code' not in values or not values['default_code']:
            values['default_code'] = external_id

        # Handle category mapping
        if product.categ_id:
            client_category_id = self._map_category(product.categ_id, connection, models_proxy, uid)
            if client_category_id:
                values['categ_id'] = client_category_id

        # Handle image - ensure it's a proper base64 string
        if connection.include_images and product.image_1920:
            # In Odoo, image_1920 is already base64 encoded
            # We just need to ensure it's a string for XML-RPC
            image_data = product.image_1920
            if isinstance(image_data, bytes):
                # If it's bytes, decode to string
                image_data = image_data.decode('utf-8')
            values['image_1920'] = image_data

        # Log the values being sent (without image to avoid huge logs)
        log_values = {k: v for k, v in values.items() if k != 'image_1920'}
        if 'image_1920' in values:
            log_values['image_1920'] = f"<base64 image {len(values['image_1920'])} chars>"
        _logger.info(f"Creating product {product.name} with values: {log_values}")

        # Create product
        try:
            client_product_id = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.template', 'create',
                [values]
            )
            _logger.info(f"Successfully created product {product.name} in client Odoo (ID: {client_product_id})")

            # Create product.supplierinfo for invoice recognition
            if connection.create_supplierinfo and connection.supplier_partner_id:
                self._create_or_update_supplierinfo(
                    product, client_product_id, models_proxy, uid, connection
                )

            # Sync variants if enabled
            if connection.sync_variants:
                selected_variant_ids = None
                if connection.client_id.selected_variant_ids:
                    # Only variants belonging to this template
                    tmpl_variant_ids = product.product_variant_ids.ids
                    selected = connection.client_id.selected_variant_ids.filtered(
                        lambda v: v.id in tmpl_variant_ids
                    )
                    if selected:
                        selected_variant_ids = selected.ids

                self._sync_variants_to_client(
                    product, client_product_id, connection,
                    models_proxy, uid, selected_variant_ids
                )

            return client_product_id
        except Exception as e:
            _logger.error(f"Error creating product {product.name}: {e}", exc_info=True)
            raise

    def _execute_update(self, change, models_proxy, uid, connection):
        """Update existing product in client Odoo"""
        product = change.product_id
        client_product_id = change.client_product_id

        # PROTECTION: Only update if product has our external ID
        # This ensures we NEVER touch client's own products
        client_data = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.template', 'read',
            [[client_product_id]],
            {'fields': ['default_code']}
        )[0]

        expected_external_id = f'supplier_{connection.client_id.id}_product_{product.id}'
        if client_data.get('default_code') != expected_external_id:
            raise UserError(_(
                'Safety check failed: Product %s does not have our external ID. '
                'Refusing to update to prevent modifying client\'s own products.'
            ) % product.name)

        # Prepare update values
        values = {}
        field_changes = json.loads(change.field_changes) if change.field_changes else {}

        for target_field, change_data in field_changes.items():
            values[target_field] = change_data['new']

        # Handle image carefully
        if connection.include_images and connection.preserve_client_images:
            # Check if client modified the image
            client_image = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.template', 'read',
                [[client_product_id]],
                {'fields': ['image_1920']}
            )[0].get('image_1920')

            # Only update if image hasn't been modified by client
            # (This is simplified - ideally compare hashes)
            if product.image_1920 and not client_image:
                image_data = product.image_1920
                if isinstance(image_data, bytes):
                    image_data = image_data.decode('utf-8')
                values['image_1920'] = image_data
        elif connection.include_images:
            # Always update image
            if product.image_1920:
                image_data = product.image_1920
                if isinstance(image_data, bytes):
                    image_data = image_data.decode('utf-8')
                values['image_1920'] = image_data

        # Execute update
        if values:
            models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.template', 'write',
                [[client_product_id], values]
            )

            _logger.info(f"Updated product {product.name} in client Odoo (ID: {client_product_id})")

        # Update product.supplierinfo for invoice recognition
        if connection.create_supplierinfo and connection.supplier_partner_id:
            self._create_or_update_supplierinfo(
                product, client_product_id, models_proxy, uid, connection
            )

        # Sync variants if enabled
        if connection.sync_variants:
            selected_variant_ids = None
            if connection.client_id.selected_variant_ids:
                tmpl_variant_ids = product.product_variant_ids.ids
                selected = connection.client_id.selected_variant_ids.filtered(
                    lambda v: v.id in tmpl_variant_ids
                )
                if selected:
                    selected_variant_ids = selected.ids

            self._sync_variants_to_client(
                product, client_product_id, connection,
                models_proxy, uid, selected_variant_ids
            )

    def _create_or_update_supplierinfo(self, product, client_product_id, models_proxy, uid, connection):
        """
        Create or update product.supplierinfo record in client's Odoo.
        This enables automatic product recognition when loading supplier invoices.

        Args:
            product: product.template record (supplier's product)
            client_product_id: int, ID of the product in client's Odoo
            models_proxy: XML-RPC models proxy
            uid: XML-RPC user ID
            connection: catalog.client.connection record
        """
        try:
            # Get pricelist for price calculation if needed
            pricelist = connection.client_id.pricelist_id if connection.client_id else None

            # Calculate price
            price = connection._get_supplierinfo_price(product, pricelist)

            # Supplier product code = our default_code (the reference on our invoices)
            supplier_product_code = product.default_code or ''

            # Search for existing supplierinfo
            existing_ids = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.supplierinfo', 'search',
                [[
                    ('partner_id', '=', connection.supplier_partner_id),
                    ('product_tmpl_id', '=', client_product_id),
                ]]
            )

            supplierinfo_vals = {
                'partner_id': connection.supplier_partner_id,
                'product_tmpl_id': client_product_id,
                'product_code': supplier_product_code,
                'product_name': product.name,
                'price': price,
                'min_qty': 1.0,
            }

            if existing_ids:
                # Update existing
                models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.supplierinfo', 'write',
                    [existing_ids, {
                        'product_code': supplier_product_code,
                        'product_name': product.name,
                        'price': price,
                    }]
                )
                _logger.info(
                    f"Updated supplierinfo for product {product.name} "
                    f"(supplier code: {supplier_product_code}, price: {price})"
                )
            else:
                # Create new
                models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.supplierinfo', 'create',
                    [supplierinfo_vals]
                )
                _logger.info(
                    f"Created supplierinfo for product {product.name} "
                    f"(supplier code: {supplier_product_code}, price: {price})"
                )

        except Exception as e:
            # Log error but don't fail the whole sync
            _logger.warning(
                f"Failed to create/update supplierinfo for product {product.name}: {e}"
            )

    # ---- Variant sync helpers ----

    def _map_attribute(self, supplier_attr, connection, models_proxy, uid):
        """
        Map a supplier product.attribute to a client attribute ID.
        Uses cache in catalog.attribute.mapping; auto-creates if missing.

        Returns:
            int: client attribute ID, or False
        """
        mapping = connection.attribute_mapping_ids.filtered(
            lambda m: m.supplier_attribute_id == supplier_attr
        )

        if mapping and mapping[0].client_attribute_id:
            return mapping[0].client_attribute_id

        # Search by name (case-insensitive)
        client_attr_ids = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.attribute', 'search',
            [[('name', '=ilike', supplier_attr.name)]]
        )

        if client_attr_ids:
            client_attr_id = client_attr_ids[0]
            client_attr_name = supplier_attr.name
        else:
            # Auto-create attribute in client
            client_attr_id = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.attribute', 'create',
                [{'name': supplier_attr.name, 'create_variant': 'always'}]
            )
            client_attr_name = supplier_attr.name
            _logger.info(
                "Created attribute '%s' in client Odoo (ID: %s)",
                supplier_attr.name, client_attr_id
            )

        # Save/update mapping
        if mapping:
            mapping[0].write({
                'client_attribute_id': client_attr_id,
                'client_attribute_name': client_attr_name,
            })
        else:
            self.env['catalog.attribute.mapping'].create({
                'connection_id': connection.id,
                'supplier_attribute_id': supplier_attr.id,
                'client_attribute_id': client_attr_id,
                'client_attribute_name': client_attr_name,
            })

        return client_attr_id

    def _map_attribute_value(self, supplier_val, client_attr_id, connection, models_proxy, uid):
        """
        Map a supplier product.attribute.value to a client value ID.
        Uses cache in catalog.attribute.value.mapping; auto-creates if missing.

        Returns:
            int: client attribute value ID, or False
        """
        mapping = connection.attribute_value_mapping_ids.filtered(
            lambda m: m.supplier_value_id == supplier_val
        )

        if mapping and mapping[0].client_value_id:
            return mapping[0].client_value_id

        # Search by name + attribute in client
        client_val_ids = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.attribute.value', 'search',
            [[
                ('name', '=ilike', supplier_val.name),
                ('attribute_id', '=', client_attr_id),
            ]]
        )

        if client_val_ids:
            client_val_id = client_val_ids[0]
        else:
            # Auto-create value in client
            client_val_id = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.attribute.value', 'create',
                [{'name': supplier_val.name, 'attribute_id': client_attr_id}]
            )
            _logger.info(
                "Created attribute value '%s' for attribute %s in client Odoo (ID: %s)",
                supplier_val.name, client_attr_id, client_val_id
            )

        # Save/update mapping
        if mapping:
            mapping[0].write({
                'client_value_id': client_val_id,
                'client_value_name': supplier_val.name,
            })
        else:
            self.env['catalog.attribute.value.mapping'].create({
                'connection_id': connection.id,
                'supplier_value_id': supplier_val.id,
                'client_value_id': client_val_id,
                'client_value_name': supplier_val.name,
            })

        return client_val_id

    def _sync_variants_to_client(self, product, client_tmpl_id, connection,
                                  models_proxy, uid, selected_variant_ids=None):
        """
        Sync product variants from supplier template to client template.

        This creates attribute lines on the client template (which auto-generates
        product.product variants via Odoo), then writes variant-specific data
        (default_code, barcode, weight, etc.) and sets price_extra on PTAV.

        Args:
            product: supplier product.template
            client_tmpl_id: int, client product.template ID
            connection: catalog.client.connection
            models_proxy: XML-RPC object proxy
            uid: XML-RPC uid
            selected_variant_ids: optional list of supplier product.product IDs to sync
                                  (if None, sync all variants)
        """
        # Get supplier attribute lines
        attr_lines = product.attribute_line_ids.filtered(
            lambda l: l.attribute_id.create_variant in ('always', 'dynamic')
        )

        if not attr_lines:
            return

        # Filter by selected variants if specified
        supplier_variants = product.product_variant_ids
        if selected_variant_ids:
            supplier_variants = supplier_variants.filtered(
                lambda v: v.id in selected_variant_ids
            )

        if not supplier_variants:
            return

        # Determine which attribute values are actually used by selected variants
        used_ptavs = supplier_variants.mapped('product_template_attribute_value_ids')
        used_values_per_attr = {}
        for ptav in used_ptavs:
            attr = ptav.attribute_id
            if attr.id not in used_values_per_attr:
                used_values_per_attr[attr.id] = set()
            used_values_per_attr[attr.id].add(ptav.product_attribute_value_id.id)

        # Step 1: Map attributes + values, build attribute_line commands
        attr_line_commands = []
        # Map: supplier_attr_id -> {supplier_val_id -> client_val_id}
        value_map = {}
        # Map: supplier_attr_id -> client_attr_id
        attr_map = {}

        for line in attr_lines:
            supplier_attr = line.attribute_id

            # Skip attributes not used by any selected variant
            if supplier_attr.id not in used_values_per_attr:
                continue

            client_attr_id = self._map_attribute(
                supplier_attr, connection, models_proxy, uid
            )
            if not client_attr_id:
                continue

            attr_map[supplier_attr.id] = client_attr_id
            value_map[supplier_attr.id] = {}

            # Map values (only those used by selected variants)
            client_value_ids = []
            for val in line.value_ids:
                if val.id not in used_values_per_attr.get(supplier_attr.id, set()):
                    continue

                client_val_id = self._map_attribute_value(
                    val, client_attr_id, connection, models_proxy, uid
                )
                if client_val_id:
                    client_value_ids.append(client_val_id)
                    value_map[supplier_attr.id][val.id] = client_val_id

            if client_value_ids:
                # Check if attribute line already exists on client template
                existing_line_ids = models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.template.attribute.line', 'search',
                    [[
                        ('product_tmpl_id', '=', client_tmpl_id),
                        ('attribute_id', '=', client_attr_id),
                    ]]
                )

                if existing_line_ids:
                    # Update existing line — add new values (keep existing)
                    existing_line = models_proxy.execute_kw(
                        connection.database, uid, connection.api_key,
                        'product.template.attribute.line', 'read',
                        [existing_line_ids[:1]],
                        {'fields': ['value_ids']}
                    )[0]
                    merged_ids = list(set(existing_line['value_ids'] + client_value_ids))
                    models_proxy.execute_kw(
                        connection.database, uid, connection.api_key,
                        'product.template.attribute.line', 'write',
                        [existing_line_ids[:1], {'value_ids': [(6, 0, merged_ids)]}]
                    )
                else:
                    # Create new attribute line
                    attr_line_commands.append({
                        'attribute_id': client_attr_id,
                        'value_ids': [(6, 0, client_value_ids)],
                    })

        # Write new attribute lines (this triggers variant auto-generation)
        if attr_line_commands:
            models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.template', 'write',
                [[client_tmpl_id], {
                    'attribute_line_ids': [(0, 0, cmd) for cmd in attr_line_commands]
                }]
            )

        # Step 2: Match supplier variants to client variants and write specific data
        # Fetch client variants (product.product) for this template
        client_variant_ids = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.product', 'search',
            [[('product_tmpl_id', '=', client_tmpl_id)]]
        )

        if not client_variant_ids:
            return

        # Read client variant PTAV info for matching
        client_variants_data = models_proxy.execute_kw(
            connection.database, uid, connection.api_key,
            'product.product', 'read',
            [client_variant_ids],
            {'fields': ['id', 'product_template_attribute_value_ids']}
        )

        # Read client PTAVs to build value-based matching
        all_client_ptav_ids = []
        for cv in client_variants_data:
            all_client_ptav_ids.extend(cv.get('product_template_attribute_value_ids', []))

        client_ptav_data = {}
        if all_client_ptav_ids:
            ptav_records = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.template.attribute.value', 'read',
                [list(set(all_client_ptav_ids))],
                {'fields': ['id', 'attribute_id', 'product_attribute_value_id']}
            )
            for rec in ptav_records:
                client_ptav_data[rec['id']] = rec

        # Build client variant lookup: frozenset of (client_attr_id, client_val_id) -> variant data
        client_variant_lookup = {}
        for cv in client_variants_data:
            combo = set()
            for ptav_id in cv.get('product_template_attribute_value_ids', []):
                ptav_rec = client_ptav_data.get(ptav_id)
                if ptav_rec:
                    attr_id = ptav_rec['attribute_id']
                    if isinstance(attr_id, list):
                        attr_id = attr_id[0]
                    val_id = ptav_rec['product_attribute_value_id']
                    if isinstance(val_id, list):
                        val_id = val_id[0]
                    combo.add((attr_id, val_id))
            client_variant_lookup[frozenset(combo)] = cv

        # Match and write variant-specific fields
        for variant in supplier_variants:
            # Build expected client combination
            expected_combo = set()
            for ptav in variant.product_template_attribute_value_ids:
                supplier_attr_id = ptav.attribute_id.id
                supplier_val_id = ptav.product_attribute_value_id.id
                client_attr_id = attr_map.get(supplier_attr_id)
                client_val_id = value_map.get(supplier_attr_id, {}).get(supplier_val_id)
                if client_attr_id and client_val_id:
                    expected_combo.add((client_attr_id, client_val_id))

            client_variant = client_variant_lookup.get(frozenset(expected_combo))
            if not client_variant:
                _logger.warning(
                    "Could not match supplier variant %s (ID: %s) to any client variant",
                    variant.display_name, variant.id
                )
                continue

            client_variant_id = client_variant['id']

            # Write variant-specific fields
            variant_vals = {}
            if variant.default_code:
                variant_vals['default_code'] = (
                    f"supplier_{connection.client_id.id}_variant_{variant.id}"
                )
            if variant.barcode:
                variant_vals['barcode'] = variant.barcode
            if variant.weight:
                variant_vals['weight'] = variant.weight
            if variant.volume:
                variant_vals['volume'] = variant.volume

            # Variant image (only if different from template)
            if connection.include_images and variant.image_variant_1920:
                image_data = variant.image_variant_1920
                if isinstance(image_data, bytes):
                    image_data = image_data.decode('utf-8')
                variant_vals['image_variant_1920'] = image_data

            if variant_vals:
                models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.product', 'write',
                    [[client_variant_id], variant_vals]
                )

            # Set price_extra on PTAV (if supplier has price_extra)
            for ptav in variant.product_template_attribute_value_ids:
                if ptav.price_extra:
                    supplier_attr_id = ptav.attribute_id.id
                    supplier_val_id = ptav.product_attribute_value_id.id
                    client_attr_id = attr_map.get(supplier_attr_id)
                    client_val_id = value_map.get(supplier_attr_id, {}).get(supplier_val_id)
                    if client_attr_id and client_val_id:
                        # Find client PTAV
                        client_ptav_ids = models_proxy.execute_kw(
                            connection.database, uid, connection.api_key,
                            'product.template.attribute.value', 'search',
                            [[
                                ('product_tmpl_id', '=', client_tmpl_id),
                                ('attribute_id', '=', client_attr_id),
                                ('product_attribute_value_id', '=', client_val_id),
                            ]]
                        )
                        if client_ptav_ids:
                            models_proxy.execute_kw(
                                connection.database, uid, connection.api_key,
                                'product.template.attribute.value', 'write',
                                [client_ptav_ids[:1], {'price_extra': ptav.price_extra}]
                            )

        _logger.info(
            "Variant sync complete for product '%s': %d supplier variants processed",
            product.name, len(supplier_variants)
        )

    def _get_variant_preview_data(self, product, connection, models_proxy=None,
                                   uid=None, client_tmpl_id=None):
        """
        Build preview data for variants of a product template.

        Returns:
            list[dict]: variant info for preview display, each with:
                - combination: str (e.g. "Color: Red, Size: L")
                - sku: str (variant default_code)
                - price_extra: float
                - action: 'create' | 'update' | 'skip'
                - variant_id: int (supplier product.product ID)
        """
        variants = product.product_variant_ids.filtered(
            lambda v: v.product_template_attribute_value_ids
        )

        if not variants:
            return []

        # Build lookup of existing client variants (if updating)
        client_variant_skus = set()
        if client_tmpl_id and models_proxy and uid:
            try:
                client_pp_ids = models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.product', 'search',
                    [[('product_tmpl_id', '=', client_tmpl_id)]]
                )
                if client_pp_ids:
                    client_pp_data = models_proxy.execute_kw(
                        connection.database, uid, connection.api_key,
                        'product.product', 'read',
                        [client_pp_ids],
                        {'fields': ['default_code']}
                    )
                    for pp in client_pp_data:
                        if pp.get('default_code'):
                            client_variant_skus.add(pp['default_code'])
            except Exception as e:
                _logger.warning("Could not fetch client variants for preview: %s", e)

        result = []
        for variant in variants:
            combo_parts = []
            for ptav in variant.product_template_attribute_value_ids:
                combo_parts.append(f"{ptav.attribute_id.name}: {ptav.name}")
            combination = ', '.join(combo_parts)

            ext_id = f"supplier_{connection.client_id.id}_variant_{variant.id}"

            if ext_id in client_variant_skus:
                action = 'update'
            elif client_tmpl_id:
                action = 'create'  # template exists but variant is new
            else:
                action = 'create'

            price_extra = sum(
                ptav.price_extra
                for ptav in variant.product_template_attribute_value_ids
            )

            result.append({
                'variant_id': variant.id,
                'combination': combination,
                'sku': variant.default_code or '',
                'price_extra': price_extra,
                'action': action,
            })

        return result

    def _map_category(self, supplier_category, connection, models_proxy, uid):
        """Map supplier category to client category ID"""
        # Check if mapping exists
        mapping = connection.category_mapping_ids.filtered(
            lambda m: m.supplier_category_id == supplier_category
        )

        if mapping and mapping.client_category_id:
            return mapping.client_category_id

        # Auto-create if enabled
        if connection.auto_create_categories:
            # Search if category exists by name
            client_category_ids = models_proxy.execute_kw(
                connection.database, uid, connection.api_key,
                'product.category', 'search',
                [[('name', '=', supplier_category.name)]]
            )

            if client_category_ids:
                client_category_id = client_category_ids[0]
            else:
                # Create category
                client_category_id = models_proxy.execute_kw(
                    connection.database, uid, connection.api_key,
                    'product.category', 'create',
                    [{'name': supplier_category.name}]
                )

            # Save mapping
            if mapping:
                mapping.write({
                    'client_category_id': client_category_id,
                })
            else:
                self.env['catalog.category.mapping'].create({
                    'connection_id': connection.id,
                    'supplier_category_id': supplier_category.id,
                    'client_category_id': client_category_id,
                })

            return client_category_id

        return False


class CatalogSyncChange(models.TransientModel):
    """
    Détail d'un changement pour un produit dans le preview.
    Permet au client de voir exactement ce qui va changer.
    """
    _name = 'catalog.sync.change'
    _description = 'Sync Change Detail (Transient)'

    preview_id = fields.Many2one(
        'catalog.sync.preview',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one('product.template', required=True)
    product_name = fields.Char(related='product_id.name', readonly=True)
    product_ref = fields.Char(related='product_id.default_code', readonly=True)

    change_type = fields.Selection([
        ('create', 'Create New Product'),
        ('update', 'Update Existing'),
        ('skip', 'Skip (No Changes)'),
    ], required=True)

    client_product_id = fields.Integer('Client Product ID')

    # Changes (stored as JSON)
    field_changes = fields.Text('Field Changes')  # JSON: {"field": {"old": X, "new": Y}}
    variant_changes = fields.Text(
        'Variant Changes',
        help='JSON: list of variant diffs with combination, sku, price_extra, action'
    )

    # Warnings
    has_warning = fields.Boolean('Has Warning', default=False)
    warning_message = fields.Text('Warning')

    # User can exclude specific changes
    is_excluded = fields.Boolean('Exclude from Sync', default=False)
