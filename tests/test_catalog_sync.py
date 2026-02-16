# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from unittest.mock import patch, MagicMock
import json


@tagged('catalog_sync', 'post_install', '-at_install')
class TestCatalogSync(TransactionCase):
    """Tests for Catalog Synchronization functionality"""

    def setUp(self):
        super().setUp()

        # Create a test partner
        self.partner = self.env['res.partner'].create({
            'name': 'Test Client',
            'email': 'client@test.com',
        })

        # Create a test catalog client
        self.catalog_client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
            'is_active': True,
        })

        # Create test products
        self.category1 = self.env['product.category'].create({
            'name': 'Electronics',
        })

        self.product1 = self.env['product.template'].create({
            'name': 'Test Product 1',
            'default_code': 'TEST001',
            'list_price': 100.0,
            'categ_id': self.category1.id,
            'type': 'consu',
        })

        self.product2 = self.env['product.template'].create({
            'name': 'Test Product 2',
            'default_code': 'TEST002',
            'list_price': 200.0,
            'categ_id': self.category1.id,
            'type': 'consu',
        })

    def test_01_connection_creation(self):
        """Test creating a client connection"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_api_key_12345',
            'username': 'test_user',
        })

        self.assertTrue(connection.id)
        self.assertEqual(connection.connection_status, 'not_tested')
        self.assertTrue(connection.is_active)
        self.assertEqual(connection.total_syncs, 0)

    def test_02_connection_url_validation(self):
        """Test URL validation on connection"""
        with self.assertRaises(ValidationError):
            self.env['catalog.client.connection'].create({
                'client_id': self.catalog_client.id,
                'odoo_url': 'invalid-url',  # Missing http://
                'database': 'test_db',
                'api_key': 'test_key',
            })

    def test_03_field_mapping_creation(self):
        """Test creating field mappings"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Create field mappings
        mapping1 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'name',
            'target_field': 'name',
            'sync_mode': 'always',
            'sequence': 10,
        })

        mapping2 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'list_price',
            'target_field': 'standard_price',
            'sync_mode': 'always',
            'apply_coefficient': True,
            'coefficient': 1.2,
            'sequence': 20,
        })

        self.assertEqual(len(connection.field_mapping_ids), 2)
        self.assertTrue(mapping2.apply_coefficient)
        self.assertEqual(mapping2.coefficient, 1.2)

    def test_04_field_mapping_unique_target(self):
        """Test that each target field can only be mapped once per connection"""
        from psycopg2 import IntegrityError
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # First mapping
        self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'name',
            'target_field': 'name',
            'sync_mode': 'always',
        })

        # Try to create duplicate target_field mapping - should fail
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['catalog.field.mapping'].create({
                    'connection_id': connection.id,
                    'source_field': 'default_code',
                    'target_field': 'name',  # Duplicate target_field
                    'sync_mode': 'always',
                })

    def test_05_category_mapping_creation(self):
        """Test creating category mappings"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        category_mapping = self.env['catalog.category.mapping'].create({
            'connection_id': connection.id,
            'supplier_category_id': self.category1.id,
            'client_category_id': 123,
            'client_category_name': 'Electronics (Client)',
            'auto_create': True,
        })

        self.assertEqual(category_mapping.supplier_category_name, 'Electronics')
        self.assertEqual(category_mapping.client_category_id, 123)

    def test_06_default_mappings_creation(self):
        """Test creating default field mappings"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Initially no mappings
        self.assertEqual(len(connection.field_mapping_ids), 0)

        # Create default mappings
        connection.action_create_default_mappings()

        # Should have created default mappings
        self.assertGreater(len(connection.field_mapping_ids), 0)

        # Check that price mapping exists and maps to standard_price
        price_mapping = connection.field_mapping_ids.filtered(
            lambda m: m.source_field == 'list_price'
        )
        self.assertTrue(price_mapping)
        self.assertEqual(price_mapping.target_field, 'standard_price')

    def test_07_sync_preview_creation(self):
        """Test creating a sync preview"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id])],
        })

        self.assertEqual(preview.state, 'draft')
        self.assertEqual(len(preview.product_ids), 2)
        self.assertEqual(preview.products_to_create, 0)  # No changes analyzed yet

    def test_08_sync_change_creation(self):
        """Test creating sync changes"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        # Create a change for product creation
        change = self.env['catalog.sync.change'].create({
            'preview_id': preview.id,
            'product_id': self.product1.id,
            'change_type': 'create',
            'field_changes': json.dumps({
                'name': {'old': None, 'new': 'Test Product 1'},
                'standard_price': {'old': None, 'new': 100.0},
            }),
        })

        self.assertEqual(change.change_type, 'create')
        self.assertEqual(change.product_name, 'Test Product 1')
        self.assertFalse(change.is_excluded)

        # Test computed stats
        preview._compute_stats()
        self.assertEqual(preview.products_to_create, 1)
        self.assertEqual(preview.products_to_update, 0)

    def test_09_sync_change_with_warning(self):
        """Test sync change with price decrease warning"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        # Test warning detection
        changes = {
            'standard_price': {'old': 100.0, 'new': 80.0}  # 20% decrease
        }
        warning = preview._detect_warnings(changes)

        self.assertTrue(warning)
        self.assertIn('Price decrease', warning)
        self.assertIn('20.0%', warning)

    def test_10_sync_change_no_warning(self):
        """Test sync change without warning (small price change)"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        # Small price change (< 10%)
        changes = {
            'standard_price': {'old': 100.0, 'new': 95.0}  # 5% decrease
        }
        warning = preview._detect_warnings(changes)

        self.assertFalse(warning)

    def test_11_sync_history_creation(self):
        """Test creating sync history"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        history = self.env['catalog.sync.history'].create({
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'products_created': 5,
            'products_updated': 3,
            'products_skipped': 2,
            'products_error': 1,
            'status': 'partial',
            'duration': 12.5,
        })

        self.assertEqual(history.total_products, 11)  # 5+3+2+1
        self.assertEqual(history.status, 'partial')
        self.assertEqual(history.duration, 12.5)

    def test_12_sync_history_status_success(self):
        """Test sync history with success status"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        history = self.env['catalog.sync.history'].create({
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'products_created': 10,
            'products_updated': 5,
            'products_error': 0,
            'status': 'success',
        })

        self.assertEqual(history.status, 'success')
        self.assertEqual(history.products_error, 0)

    def test_13_connection_stats_computation(self):
        """Test connection statistics computation"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Create some history records
        self.env['catalog.sync.history'].create({
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'products_created': 5,
            'status': 'success',
        })

        self.env['catalog.sync.history'].create({
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'products_created': 3,
            'products_error': 1,
            'status': 'partial',
        })

        connection._compute_stats()

        self.assertEqual(connection.total_syncs, 2)
        self.assertEqual(connection.last_sync_status, 'partial')  # Most recent

    def test_14_field_mapping_sequence(self):
        """Test field mapping ordering by sequence"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Create mappings out of order
        m1 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'weight',
            'target_field': 'weight',
            'sync_mode': 'always',
            'sequence': 30,
        })

        m2 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'name',
            'target_field': 'name',
            'sync_mode': 'always',
            'sequence': 10,
        })

        m3 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'list_price',
            'target_field': 'standard_price',
            'sync_mode': 'always',
            'sequence': 20,
        })

        # Check ordering
        sorted_mappings = connection.field_mapping_ids.sorted('sequence')
        self.assertEqual(sorted_mappings[0].source_field, 'name')
        self.assertEqual(sorted_mappings[1].source_field, 'list_price')
        self.assertEqual(sorted_mappings[2].source_field, 'weight')

    def test_15_external_id_format(self):
        """Test external ID format generation"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        expected_external_id = f'supplier_{self.catalog_client.id}_product_{self.product1.id}'

        # This format is used in _execute_create and _execute_update
        self.assertTrue(expected_external_id)
        self.assertIn('supplier', expected_external_id)
        self.assertIn(str(self.product1.id), expected_external_id)

    def test_16_sync_mode_validation(self):
        """Test different sync modes"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Test all sync modes using valid source/target field pairs
        mode_fields = [
            ('create_only', 'name', 'name'),
            ('always', 'default_code', 'default_code'),
            ('if_empty', 'barcode', 'barcode'),
            ('manual', 'weight', 'weight'),
        ]

        for mode, source, target in mode_fields:
            mapping = self.env['catalog.field.mapping'].create({
                'connection_id': connection.id,
                'source_field': source,
                'target_field': target,
                'sync_mode': mode,
            })
            self.assertEqual(mapping.sync_mode, mode)

    def test_17_inactive_field_mapping(self):
        """Test inactive field mappings are excluded"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Active mapping
        m1 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'name',
            'target_field': 'name',
            'sync_mode': 'always',
            'is_active': True,
        })

        # Inactive mapping
        m2 = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'list_price',
            'target_field': 'standard_price',
            'sync_mode': 'always',
            'is_active': False,
        })

        # Only active mappings should be used
        active_mappings = connection.field_mapping_ids.filtered(lambda m: m.is_active)
        self.assertEqual(len(active_mappings), 1)
        self.assertEqual(active_mappings.source_field, 'name')

    def test_18_sync_options_defaults(self):
        """Test default values for sync options"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Check defaults
        self.assertTrue(connection.is_active)
        self.assertTrue(connection.auto_create_categories)
        self.assertTrue(connection.include_images)
        self.assertTrue(connection.preserve_client_images)

    def test_19_multiple_connections_per_client(self):
        """Test that a client can have multiple connections (different instances)"""
        connection1 = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test1.odoo.com',
            'database': 'test_db_1',
            'api_key': 'key1',
        })

        connection2 = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test2.odoo.com',
            'database': 'test_db_2',
            'api_key': 'key2',
        })

        # Both should exist
        connections = self.env['catalog.client.connection'].search([
            ('client_id', '=', self.catalog_client.id)
        ])

        self.assertEqual(len(connections), 2)

    def test_20_coefficient_transformation(self):
        """Test price coefficient transformation"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        mapping = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'list_price',
            'target_field': 'standard_price',
            'sync_mode': 'always',
            'apply_coefficient': True,
            'coefficient': 1.25,  # 25% markup
        })

        # Original price
        original_price = 100.0
        # With coefficient
        expected_price = 100.0 * 1.25  # 125.0

        self.assertEqual(mapping.coefficient, 1.25)
        self.assertEqual(original_price * mapping.coefficient, expected_price)

    # ===== REFERENCE GENERATION TESTS =====

    def test_21_reference_keep_original(self):
        """Test reference generation: keep original mode"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'keep_original',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, 'TEST001')

    def test_22_reference_product_id(self):
        """Test reference generation: product ID mode"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'product_id',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, str(self.product1.id))

    def test_23_reference_none(self):
        """Test reference generation: no reference mode"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'none',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertFalse(ref)

    def test_24_reference_with_prefix(self):
        """Test reference generation with prefix"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'keep_original',
            'reference_prefix': 'SUP',
            'reference_separator': '-',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, 'SUP-TEST001')

    def test_25_reference_with_suffix(self):
        """Test reference generation with suffix"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'keep_original',
            'reference_suffix': 'IMP',
            'reference_separator': '-',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, 'TEST001-IMP')

    def test_26_reference_with_prefix_and_suffix(self):
        """Test reference generation with both prefix and suffix"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'keep_original',
            'reference_prefix': 'SUP',
            'reference_suffix': 'IMP',
            'reference_separator': '_',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, 'SUP_TEST001_IMP')

    def test_27_reference_custom_format(self):
        """Test reference generation with custom format"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'custom_format',
            'reference_custom_format': '{prefix}{ref}-{id}',
            'reference_prefix': 'CAT',
        })

        ref = connection.generate_product_reference(self.product1)

        self.assertEqual(ref, f'CATTEST001-{self.product1.id}')

    def test_28_reference_product_without_code(self):
        """Test reference generation for product without default_code"""
        product_no_code = self.env['product.template'].create({
            'name': 'No Code Product',
            'type': 'consu',
        })

        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'product_id',
        })

        ref = connection.generate_product_reference(product_no_code)

        self.assertEqual(ref, str(product_no_code.id))

    # ===== SUPPLIER INFO CONFIGURATION TESTS =====

    def test_29_supplier_info_defaults(self):
        """Test supplier info default values"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        self.assertTrue(connection.create_supplierinfo)
        self.assertEqual(connection.supplierinfo_price_field, 'list_price')
        self.assertEqual(connection.supplierinfo_price_coefficient, 1.0)

    def test_30_supplier_info_price_fields(self):
        """Test all supplier info price field options"""
        for price_field in ['list_price', 'standard_price', 'pricelist']:
            connection = self.env['catalog.client.connection'].create({
                'client_id': self.catalog_client.id,
                'odoo_url': f'https://test{price_field}.odoo.com',
                'database': 'test_db',
                'api_key': 'test_key',
                'supplierinfo_price_field': price_field,
            })
            self.assertEqual(connection.supplierinfo_price_field, price_field)

    def test_31_supplier_info_coefficient(self):
        """Test supplier info price coefficient"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://coeff.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'supplierinfo_price_coefficient': 0.8,
        })

        self.assertEqual(connection.supplierinfo_price_coefficient, 0.8)

        original_price = 100.0
        self.assertEqual(original_price * connection.supplierinfo_price_coefficient, 80.0)

    def test_32_supplier_partner_fields(self):
        """Test supplier partner ID and name fields"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://supplier.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'supplier_partner_id': 42,
            'supplier_partner_name': 'My Supplier Company',
        })

        self.assertEqual(connection.supplier_partner_id, 42)
        self.assertEqual(connection.supplier_partner_name, 'My Supplier Company')

    # ===== SYNC OPTIONS TESTS =====

    def test_33_sync_variants_option(self):
        """Test sync_variants option defaults to False"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://variants.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        self.assertFalse(connection.sync_variants)

        connection.sync_variants = True
        self.assertTrue(connection.sync_variants)

    def test_34_verify_ssl_option(self):
        """Test verify_ssl option defaults to True"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://ssl.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        self.assertTrue(connection.verify_ssl)

        connection.verify_ssl = False
        self.assertFalse(connection.verify_ssl)

    def test_35_all_reference_modes(self):
        """Test all reference mode selection values"""
        modes = ['keep_original', 'supplier_ref', 'product_id', 'custom_format', 'none']
        for mode in modes:
            connection = self.env['catalog.client.connection'].create({
                'client_id': self.catalog_client.id,
                'odoo_url': f'https://mode-{mode}.odoo.com',
                'database': 'test_db',
                'api_key': 'test_key',
                'reference_mode': mode,
            })
            self.assertEqual(connection.reference_mode, mode)

    # ===== ATTRIBUTE MAPPING INTEGRATION TESTS =====

    def test_36_attribute_mapping_on_connection(self):
        """Test attribute mappings accessible via connection"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://attr.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        attribute = self.env['product.attribute'].create({'name': 'Color'})

        self.env['catalog.attribute.mapping'].create({
            'connection_id': connection.id,
            'supplier_attribute_id': attribute.id,
            'client_attribute_id': 10,
            'client_attribute_name': 'Colour',
        })

        self.assertEqual(len(connection.attribute_mapping_ids), 1)
        self.assertEqual(connection.attribute_mapping_ids[0].client_attribute_name, 'Colour')

    def test_37_attribute_value_mapping_on_connection(self):
        """Test attribute value mappings accessible via connection"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://attrval.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        attribute = self.env['product.attribute'].create({'name': 'Size'})
        value = self.env['product.attribute.value'].create({
            'name': 'Large',
            'attribute_id': attribute.id,
        })

        self.env['catalog.attribute.value.mapping'].create({
            'connection_id': connection.id,
            'supplier_value_id': value.id,
            'client_value_id': 50,
            'client_value_name': 'L',
        })

        self.assertEqual(len(connection.attribute_value_mapping_ids), 1)
        self.assertEqual(connection.attribute_value_mapping_ids[0].client_value_name, 'L')

    def test_38_sync_history_error_status(self):
        """Test sync history with error status and error message"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://error.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        history = self.env['catalog.sync.history'].create({
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'products_created': 0,
            'products_error': 5,
            'status': 'error',
            'error_message': 'Connection timeout',
        })

        self.assertEqual(history.status, 'error')
        self.assertEqual(history.products_error, 5)
        self.assertEqual(history.error_message, 'Connection timeout')

        # Connection should reflect error status
        connection.invalidate_recordset()
        self.assertEqual(connection.last_sync_status, 'error')

    def test_39_preserve_client_images_option(self):
        """Test preserve_client_images option"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://images.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        self.assertTrue(connection.preserve_client_images)

        connection.preserve_client_images = False
        self.assertFalse(connection.preserve_client_images)

    def test_40_connection_cascade_deletes_mappings(self):
        """Test that deleting a connection cascades to all related mappings"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://cascade.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })

        # Create field mapping
        fm = self.env['catalog.field.mapping'].create({
            'connection_id': connection.id,
            'source_field': 'name',
            'target_field': 'name',
            'sync_mode': 'always',
        })

        # Create category mapping
        cat = self.env['product.category'].create({'name': 'Cascade Cat'})
        cm = self.env['catalog.category.mapping'].create({
            'connection_id': connection.id,
            'supplier_category_id': cat.id,
            'client_category_id': 1,
        })

        # Create attribute mapping
        attr = self.env['product.attribute'].create({'name': 'Cascade Attr'})
        am = self.env['catalog.attribute.mapping'].create({
            'connection_id': connection.id,
            'supplier_attribute_id': attr.id,
        })

        fm_id, cm_id, am_id = fm.id, cm.id, am.id

        connection.unlink()

        self.assertFalse(self.env['catalog.field.mapping'].browse(fm_id).exists())
        self.assertFalse(self.env['catalog.category.mapping'].browse(cm_id).exists())
        self.assertFalse(self.env['catalog.attribute.mapping'].browse(am_id).exists())

    # ===== DUPLICATE PREVENTION & CLIENT PRODUCT PROTECTION TESTS =====

    def _make_connection_with_mappings(self):
        """Helper: create a connection with default field mappings"""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'keep_original',
        })
        connection.action_create_default_mappings()
        return connection

    @patch('odoo.addons.catalog_web_portal.models.catalog_sync.CatalogClientConnection._get_xmlrpc_proxy')
    def test_41_preview_detects_existing_product_by_reference(self, mock_proxy):
        """Test that preview marks existing client products as 'update' (not 'create'),
        preventing duplicates when a product with the same reference already exists."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        # Mock XML-RPC: authentication succeeds
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1  # uid = 1
        mock_models = MagicMock()

        def proxy_router(endpoint, **kwargs):
            if endpoint == 'common':
                return mock_common
            return mock_models

        mock_proxy.side_effect = proxy_router

        # Client already has this product (matched by generated reference = default_code)
        generated_ref = connection.generate_product_reference(self.product1)
        mock_models.execute_kw.side_effect = [
            # 1st call: search by external_id pattern — no match
            [],
            # 2nd call: search by generated references — product found!
            [{'id': 999, 'default_code': generated_ref}],
            # 3rd call: read client product fields for diff
            [{'id': 999, 'name': 'Test Product 1', 'standard_price': 100.0}],
        ]

        preview.action_generate_preview()

        # Should be an UPDATE, not a CREATE (no duplicate)
        self.assertEqual(len(preview.change_ids), 1)
        change = preview.change_ids[0]
        self.assertIn(change.change_type, ('update', 'skip'))
        self.assertEqual(change.client_product_id, 999)

    @patch('odoo.addons.catalog_web_portal.models.catalog_sync.CatalogClientConnection._get_xmlrpc_proxy')
    def test_42_preview_detects_existing_product_by_external_id(self, mock_proxy):
        """Test that preview detects products by external_id fallback pattern,
        preventing duplicates even when reference_mode is 'none'."""
        connection = self.env['catalog.client.connection'].create({
            'client_id': self.catalog_client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
            'reference_mode': 'none',
        })
        connection.action_create_default_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_models = MagicMock()

        def proxy_router(endpoint, **kwargs):
            return mock_common if endpoint == 'common' else mock_models

        mock_proxy.side_effect = proxy_router

        external_id = f'supplier_{self.catalog_client.id}_product_{self.product1.id}'
        mock_models.execute_kw.side_effect = [
            # 1st call: search by external_id pattern — found
            [{'id': 500, 'default_code': external_id}],
            # 2nd call: search by generated references (none in 'none' mode) — skipped
            # but the code still does the call with an empty list, returning []
            [],
            # 3rd call: read client product fields for diff
            [{'id': 500, 'name': 'Test Product 1', 'standard_price': 100.0}],
        ]

        preview.action_generate_preview()

        self.assertEqual(len(preview.change_ids), 1)
        change = preview.change_ids[0]
        self.assertIn(change.change_type, ('update', 'skip'))
        self.assertEqual(change.client_product_id, 500)

    @patch('odoo.addons.catalog_web_portal.models.catalog_sync.CatalogClientConnection._get_xmlrpc_proxy')
    def test_43_preview_creates_new_when_not_existing(self, mock_proxy):
        """Test that preview correctly generates a 'create' change
        when the product does not exist on the client side."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_models = MagicMock()

        def proxy_router(endpoint, **kwargs):
            return mock_common if endpoint == 'common' else mock_models

        mock_proxy.side_effect = proxy_router

        # No existing products on client side
        mock_models.execute_kw.side_effect = [
            [],  # search by external_id pattern — empty
            [],  # search by generated references — empty
        ]

        preview.action_generate_preview()

        self.assertEqual(len(preview.change_ids), 1)
        self.assertEqual(preview.change_ids[0].change_type, 'create')

    def test_44_execute_update_refuses_foreign_product(self):
        """Test that _execute_update raises an error when the client product
        does not have our reference, protecting client's own products."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        # Create an update change pointing to a client product
        change = self.env['catalog.sync.change'].create({
            'preview_id': preview.id,
            'product_id': self.product1.id,
            'change_type': 'update',
            'client_product_id': 777,
            'field_changes': json.dumps({
                'name': {'old': 'Old Name', 'new': 'New Name'},
            }),
        })

        # Mock XML-RPC: client product has a different default_code (not ours)
        mock_models = MagicMock()
        mock_models.execute_kw.return_value = [
            {'id': 777, 'default_code': 'CLIENT-OWN-REF-123'}
        ]

        with self.assertRaises(UserError) as ctx:
            preview._execute_update(change, mock_models, 1, connection)

        self.assertIn('Safety check failed', str(ctx.exception))

    def test_45_execute_update_allows_our_reference(self):
        """Test that _execute_update proceeds when the product has our reference."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        change = self.env['catalog.sync.change'].create({
            'preview_id': preview.id,
            'product_id': self.product1.id,
            'change_type': 'update',
            'client_product_id': 888,
            'field_changes': json.dumps({
                'name': {'old': 'Old Name', 'new': 'Test Product 1'},
            }),
        })

        generated_ref = connection.generate_product_reference(self.product1)

        mock_models = MagicMock()
        # First call: safety check read → returns our reference
        # Second call: write → succeeds
        mock_models.execute_kw.side_effect = [
            [{'id': 888, 'default_code': generated_ref}],  # safety check
            True,  # write
        ]

        # Should not raise
        preview._execute_update(change, mock_models, 1, connection)

        # Verify write was called
        write_calls = [
            c for c in mock_models.execute_kw.call_args_list
            if len(c[0]) >= 4 and c[0][3] == 'write'
        ]
        self.assertEqual(len(write_calls), 1)

    def test_46_execute_update_allows_external_id_reference(self):
        """Test that _execute_update also accepts the external_id format."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        change = self.env['catalog.sync.change'].create({
            'preview_id': preview.id,
            'product_id': self.product1.id,
            'change_type': 'update',
            'client_product_id': 888,
            'field_changes': json.dumps({
                'name': {'old': 'Old', 'new': 'New'},
            }),
        })

        external_id = f'supplier_{self.catalog_client.id}_product_{self.product1.id}'

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            [{'id': 888, 'default_code': external_id}],  # safety check
            True,  # write
        ]

        # Should not raise
        preview._execute_update(change, mock_models, 1, connection)

    @patch('odoo.addons.catalog_web_portal.models.catalog_sync.CatalogClientConnection._get_xmlrpc_proxy')
    def test_47_sync_multiple_products_mixed_create_update(self, mock_proxy):
        """Test that preview correctly handles a mix: one product existing
        on client (update) and one new product (create), without duplicates."""
        connection = self._make_connection_with_mappings()

        preview = self.env['catalog.sync.preview'].create({
            'connection_id': connection.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id])],
        })

        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1
        mock_models = MagicMock()

        def proxy_router(endpoint, **kwargs):
            return mock_common if endpoint == 'common' else mock_models

        mock_proxy.side_effect = proxy_router

        ref1 = connection.generate_product_reference(self.product1)
        # product1 exists on client, product2 does not
        mock_models.execute_kw.side_effect = [
            # search by external_id pattern
            [],
            # search by generated references — only product1 found
            [{'id': 100, 'default_code': ref1}],
            # read client product1 fields for diff
            [{'id': 100, 'name': 'Test Product 1', 'standard_price': 100.0}],
        ]

        preview.action_generate_preview()

        changes_by_type = {}
        for c in preview.change_ids:
            changes_by_type.setdefault(c.change_type, []).append(c)

        # product2 should be created
        self.assertEqual(len(changes_by_type.get('create', [])), 1)
        create_change = changes_by_type['create'][0]
        self.assertEqual(create_change.product_id, self.product2)

        # product1 should be update or skip (already exists)
        update_or_skip = changes_by_type.get('update', []) + changes_by_type.get('skip', [])
        self.assertEqual(len(update_or_skip), 1)
        self.assertEqual(update_or_skip[0].product_id, self.product1)
