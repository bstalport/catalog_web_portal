# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogConfig(TransactionCase):
    """Tests for catalog.config model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Clean any existing config for clean tests
        cls.env['catalog.config'].search([]).unlink()

    def test_get_config_creates_singleton(self):
        """Test that get_config creates a config if none exists"""
        Config = self.env['catalog.config']

        # Ensure no config exists
        self.assertFalse(Config.search([]))

        # Call get_config
        config = Config.get_config()

        # Should create one
        self.assertTrue(config)
        self.assertEqual(config.name, 'Catalog Configuration')

        # Calling again should return same record
        config2 = Config.get_config()
        self.assertEqual(config.id, config2.id)

    def test_default_values(self):
        """Test that default values are correctly set"""
        config = self.env['catalog.config'].get_config()

        self.assertTrue(config.portal_access_enabled)
        self.assertTrue(config.allow_csv_export)
        self.assertTrue(config.allow_excel_export)
        self.assertTrue(config.allow_direct_odoo_import)
        self.assertEqual(config.max_products_per_export, 1000)
        self.assertEqual(config.export_rate_limit, 10)
        self.assertEqual(config.default_product_visibility, 'all')
        self.assertEqual(config.portal_primary_color, '#007bff')

    def test_color_validation_valid(self):
        """Test that valid hex colors are accepted"""
        config = self.env['catalog.config'].get_config()

        # Valid colors
        config.portal_primary_color = '#FF0000'
        config.portal_primary_color = '#00ff00'
        config.portal_primary_color = '#123456'

    def test_color_validation_invalid(self):
        """Test that invalid colors are rejected"""
        config = self.env['catalog.config'].get_config()

        with self.assertRaises(ValidationError):
            config.portal_primary_color = 'red'

        with self.assertRaises(ValidationError):
            config.portal_primary_color = '#FFF'  # Too short

        with self.assertRaises(ValidationError):
            config.portal_primary_color = '#GGGGGG'  # Invalid chars

    def test_max_products_validation(self):
        """Test that negative max_products_per_export is rejected"""
        config = self.env['catalog.config'].get_config()

        with self.assertRaises(ValidationError):
            config.max_products_per_export = -1

        # Zero should be valid (unlimited)
        config.max_products_per_export = 0

    def test_export_fields_default(self):
        """Test that default export fields are set on new config"""
        Config = self.env['catalog.config']
        ExportField = self.env['catalog.export.field']

        # Create some default export fields if they don't exist
        if not ExportField.search([('is_default', '=', True)]):
            ExportField.create({
                'name': 'Test Field',
                'technical_name': 'test_field',
                'is_default': True,
            })

        config = Config.get_config()

        # Should have default fields
        default_fields = ExportField.search([('is_default', '=', True)])
        if default_fields:
            self.assertTrue(config.export_field_ids)

    def test_get_enabled_export_fields(self):
        """Test get_enabled_export_fields method"""
        config = self.env['catalog.config'].get_config()
        ExportField = self.env['catalog.export.field']

        # Create test fields
        field1 = ExportField.create({
            'name': 'Field 1',
            'technical_name': 'field_1',
            'sequence': 1,
        })
        field2 = ExportField.create({
            'name': 'Field 2',
            'technical_name': 'field_2',
            'sequence': 2,
        })

        # Set fields on config
        config.export_field_ids = [(6, 0, [field1.id, field2.id])]

        # Get enabled fields
        enabled = config.get_enabled_export_fields()

        self.assertEqual(len(enabled), 2)
        # Should be sorted by sequence
        self.assertEqual(enabled[0].id, field1.id)
        self.assertEqual(enabled[1].id, field2.id)

    def test_statistics_computation(self):
        """Test that statistics are computed correctly"""
        config = self.env['catalog.config'].get_config()

        # Initially should be zero
        self.assertEqual(config.total_clients, 0)
        self.assertEqual(config.active_clients, 0)
        self.assertEqual(config.total_exports_today, 0)
        self.assertEqual(config.total_exports_month, 0)

    def test_action_view_clients(self):
        """Test action_view_clients returns correct action"""
        config = self.env['catalog.config'].get_config()

        action = config.action_view_clients()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'catalog.client')
        self.assertIn('list', action['view_mode'])

    def test_action_view_logs(self):
        """Test action_view_logs returns correct action"""
        config = self.env['catalog.config'].get_config()

        action = config.action_view_logs()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'catalog.access.log')
        self.assertIn('list', action['view_mode'])

    def test_supplier_info_defaults(self):
        """Test supplier info fields have correct defaults"""
        config = self.env['catalog.config'].get_config()

        self.assertTrue(config.include_supplier_info_in_exports)
        self.assertEqual(config.supplier_external_id, 'catalog_supplier')

    def test_supplier_info_toggle(self):
        """Test toggling supplier info in exports"""
        config = self.env['catalog.config'].get_config()

        config.include_supplier_info_in_exports = False
        self.assertFalse(config.include_supplier_info_in_exports)

        config.include_supplier_info_in_exports = True
        self.assertTrue(config.include_supplier_info_in_exports)

    def test_supplier_external_id_custom(self):
        """Test setting a custom supplier external ID"""
        config = self.env['catalog.config'].get_config()

        config.supplier_external_id = 'my_company_supplier'
        self.assertEqual(config.supplier_external_id, 'my_company_supplier')

    def test_branding_fields(self):
        """Test branding fields can be set"""
        config = self.env['catalog.config'].get_config()

        config.portal_welcome_message = '<p>Welcome!</p>'
        config.support_email = 'support@test.com'
        config.support_phone = '+32123456789'

        self.assertEqual(config.support_email, 'support@test.com')
        self.assertEqual(config.support_phone, '+32123456789')

    def test_statistics_with_data(self):
        """Test statistics computation with actual data"""
        config = self.env['catalog.config'].get_config()

        # Create clients
        partner1 = self.env['res.partner'].create({
            'name': 'Stats Client 1',
            'email': 'stats1@example.com',
        })
        client1 = self.env['catalog.client'].create({
            'name': 'Stats Client 1',
            'partner_id': partner1.id,
        })

        partner2 = self.env['res.partner'].create({
            'name': 'Stats Client 2',
            'email': 'stats2@example.com',
        })
        client2 = self.env['catalog.client'].create({
            'name': 'Stats Client 2',
            'partner_id': partner2.id,
        })

        # Create access logs
        self.env['catalog.access.log'].create({
            'client_id': client1.id,
            'action': 'view_catalog',
        })
        self.env['catalog.access.log'].create({
            'client_id': client1.id,
            'action': 'export_csv',
            'product_count': 5,
        })

        config.invalidate_recordset()

        self.assertEqual(config.total_clients, 2)
        self.assertGreaterEqual(config.active_clients, 1)
        self.assertGreaterEqual(config.total_exports_today, 1)
        self.assertGreaterEqual(config.total_exports_month, 1)

    def test_allow_direct_odoo_import_default(self):
        """Test allow_direct_odoo_import defaults to True"""
        config = self.env['catalog.config'].get_config()
        self.assertTrue(config.allow_direct_odoo_import)

    def test_features_can_be_individually_disabled(self):
        """Test each export feature can be disabled independently"""
        config = self.env['catalog.config'].get_config()

        # Disable CSV only
        config.allow_csv_export = False
        self.assertFalse(config.allow_csv_export)
        self.assertTrue(config.allow_excel_export)
        self.assertTrue(config.allow_direct_odoo_import)

        # Disable Direct import only
        config.allow_csv_export = True
        config.allow_direct_odoo_import = False
        self.assertTrue(config.allow_csv_export)
        self.assertFalse(config.allow_direct_odoo_import)
