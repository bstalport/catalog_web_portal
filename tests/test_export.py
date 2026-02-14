# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogExportField(TransactionCase):
    """Tests for catalog.export.field model"""

    def test_export_field_creation(self):
        """Test basic export field creation"""
        field = self.env['catalog.export.field'].create({
            'name': 'Test Field',
            'technical_name': 'test_field_unique',
            'field_type': 'product',
        })

        self.assertTrue(field)
        self.assertEqual(field.name, 'Test Field')
        self.assertEqual(field.technical_name, 'test_field_unique')
        self.assertEqual(field.sequence, 10)  # Default

    def test_export_field_unique_technical_name(self):
        """Test that technical_name must be unique"""
        self.env['catalog.export.field'].create({
            'name': 'Field 1',
            'technical_name': 'unique_tech_name',
        })

        from psycopg2 import IntegrityError
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['catalog.export.field'].create({
                    'name': 'Field 2',
                    'technical_name': 'unique_tech_name',  # Duplicate
                })

    def test_get_export_header(self):
        """Test get_export_header returns correct header"""
        # With explicit header
        field1 = self.env['catalog.export.field'].create({
            'name': 'Product Name',
            'technical_name': 'name_header_test',
            'export_header': 'product_name',
        })
        self.assertEqual(field1.get_export_header(), 'product_name')

        # Without explicit header (fallback to name)
        field2 = self.env['catalog.export.field'].create({
            'name': 'Barcode',
            'technical_name': 'barcode_header_test',
        })
        self.assertEqual(field2.get_export_header(), 'Barcode')

    def test_field_type_selection(self):
        """Test all field types can be created"""
        types = ['product', 'computed', 'relation']

        for field_type in types:
            field = self.env['catalog.export.field'].create({
                'name': f'Field {field_type}',
                'technical_name': f'field_{field_type}_test',
                'field_type': field_type,
            })
            self.assertEqual(field.field_type, field_type)

    def test_default_is_default(self):
        """Test is_default field default value"""
        field = self.env['catalog.export.field'].create({
            'name': 'Test',
            'technical_name': 'default_test_field',
        })
        self.assertTrue(field.is_default)

    def test_sequence_ordering(self):
        """Test fields are ordered by sequence"""
        field1 = self.env['catalog.export.field'].create({
            'name': 'Field 1',
            'technical_name': 'seq_field_1',
            'sequence': 20,
        })
        field2 = self.env['catalog.export.field'].create({
            'name': 'Field 2',
            'technical_name': 'seq_field_2',
            'sequence': 10,
        })
        field3 = self.env['catalog.export.field'].create({
            'name': 'Field 3',
            'technical_name': 'seq_field_3',
            'sequence': 15,
        })

        fields = self.env['catalog.export.field'].search([
            ('technical_name', 'in', ['seq_field_1', 'seq_field_2', 'seq_field_3'])
        ])

        # Should be ordered: field2 (10), field3 (15), field1 (20)
        self.assertEqual(fields[0].id, field2.id)
        self.assertEqual(fields[1].id, field3.id)
        self.assertEqual(fields[2].id, field1.id)


@tagged('post_install', '-at_install', 'catalog')
class TestExportIntegration(TransactionCase):
    """Integration tests for export functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['catalog.config'].get_config()

        cls.category = cls.env['product.category'].create({
            'name': 'Export Test Category',
        })

        cls.product = cls.env['product.template'].create({
            'name': 'Export Test Product',
            'default_code': 'EXP001',
            'barcode': '9876543210123',
            'list_price': 250.0,
            'categ_id': cls.category.id,
            'weight': 2.5,
            'volume': 1.0,
            'description_sale': 'Export test description',
            'is_published': True,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Export Test Partner',
            'email': 'export@example.com',
        })

        cls.client = cls.env['catalog.client'].create({
            'name': 'Export Test Client',
            'partner_id': cls.partner.id,
        })

    def test_export_with_configured_fields(self):
        """Test that export respects configured fields"""
        ExportField = self.env['catalog.export.field']

        # Enable only name and price
        name_field = ExportField.search([('technical_name', '=', 'name')], limit=1)
        price_field = ExportField.search([('technical_name', '=', 'list_price')], limit=1)

        if not name_field:
            name_field = ExportField.create({
                'name': 'Name',
                'technical_name': 'name',
            })
        if not price_field:
            price_field = ExportField.create({
                'name': 'Price',
                'technical_name': 'list_price',
            })

        self.config.export_field_ids = [(6, 0, [name_field.id, price_field.id])]

        data = self.product.get_catalog_data()

        # Should have id, name, price
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('list_price', data)
        # Should NOT have barcode, weight, etc
        self.assertNotIn('barcode', data)
        self.assertNotIn('weight', data)

    def test_export_all_standard_fields(self):
        """Test export with all standard fields enabled"""
        ExportField = self.env['catalog.export.field']

        # Get or create all standard fields
        standard_fields = [
            ('name', 'Name'),
            ('default_code', 'Internal Reference'),
            ('barcode', 'Barcode'),
            ('list_price', 'Sales Price'),
            ('uom_name', 'Unit of Measure'),
            ('categ_name', 'Category'),
            ('weight', 'Weight'),
            ('volume', 'Volume'),
        ]

        field_ids = []
        for tech_name, name in standard_fields:
            field = ExportField.search([('technical_name', '=', tech_name)], limit=1)
            if not field:
                field = ExportField.create({
                    'name': name,
                    'technical_name': tech_name,
                })
            field_ids.append(field.id)

        self.config.export_field_ids = [(6, 0, field_ids)]

        data = self.product.get_catalog_data()

        # All fields should be present
        self.assertEqual(data['name'], 'Export Test Product')
        self.assertEqual(data['default_code'], 'EXP001')
        self.assertEqual(data['barcode'], '9876543210123')
        self.assertEqual(data['list_price'], 250.0)
        self.assertEqual(data['weight'], 2.5)
        self.assertEqual(data['volume'], 1.0)

    def test_export_with_client_pricelist(self):
        """Test export uses client pricelist"""
        # Create a pricelist with special price
        pricelist = self.env['product.pricelist'].create({
            'name': 'Client Special Pricelist',
        })
        self.env['product.pricelist.item'].create({
            'pricelist_id': pricelist.id,
            'compute_price': 'fixed',
            'fixed_price': 175.0,
            'applied_on': '1_product',
            'product_tmpl_id': self.product.id,
        })

        self.client.pricelist_id = pricelist

        # Enable price field
        ExportField = self.env['catalog.export.field']
        price_field = ExportField.search([('technical_name', '=', 'list_price')], limit=1)
        if not price_field:
            price_field = ExportField.create({
                'name': 'Price',
                'technical_name': 'list_price',
            })
        self.config.export_field_ids = [(6, 0, [price_field.id])]

        data = self.product.get_catalog_data(pricelist=pricelist)

        self.assertEqual(data['list_price'], 175.0)

    def test_client_accessible_products_for_export(self):
        """Test client can only export accessible products"""
        # Create another product not accessible
        other_category = self.env['product.category'].create({
            'name': 'Other Category',
        })
        other_product = self.env['product.template'].create({
            'name': 'Other Product',
            'is_published': True,
            'categ_id': other_category.id,
        })

        # Set client to restricted mode
        self.client.access_mode = 'restricted'
        self.client.allowed_category_ids = [(6, 0, [self.category.id])]

        accessible = self.client._get_accessible_products()

        self.assertIn(self.product, accessible)
        self.assertNotIn(other_product, accessible)

    def test_export_limits_configuration(self):
        """Test export limits are configurable"""
        self.config.max_products_per_export = 50
        self.config.export_rate_limit = 5

        self.assertEqual(self.config.max_products_per_export, 50)
        self.assertEqual(self.config.export_rate_limit, 5)

    def test_export_disabled_features(self):
        """Test export features can be disabled"""
        self.config.allow_csv_export = False
        self.config.allow_excel_export = False
        self.config.allow_direct_odoo_import = False

        self.assertFalse(self.config.allow_csv_export)
        self.assertFalse(self.config.allow_excel_export)
        self.assertFalse(self.config.allow_direct_odoo_import)

    def test_unpublished_products_excluded(self):
        """Test unpublished products are excluded from export"""
        unpublished = self.env['product.template'].create({
            'name': 'Unpublished Product',
            'is_published': False,
            'categ_id': self.category.id,
        })

        self.client.access_mode = 'full'
        accessible = self.client._get_accessible_products()

        self.assertIn(self.product, accessible)
        self.assertNotIn(unpublished, accessible)

    def test_custom_product_list_mode(self):
        """Test custom product list access mode"""
        extra_product = self.env['product.template'].create({
            'name': 'Extra Product',
            'is_published': True,
            'categ_id': self.category.id,
        })

        self.client.access_mode = 'custom'
        self.client.allowed_product_ids = [(6, 0, [self.product.id])]

        accessible = self.client._get_accessible_products()

        self.assertIn(self.product, accessible)
        self.assertNotIn(extra_product, accessible)
