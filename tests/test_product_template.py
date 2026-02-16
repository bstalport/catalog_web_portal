# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'catalog')
class TestProductTemplate(TransactionCase):
    """Tests for product.template catalog extensions"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['product.category'].create({
            'name': 'Test Category',
        })
        cls.uom = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.template'].create({
            'name': 'Test Product',
            'default_code': 'TEST001',
            'barcode': '1234567890123',
            'list_price': 150.0,
            'categ_id': cls.category.id,
            'uom_id': cls.uom.id,
            'weight': 1.5,
            'volume': 0.5,
            'description_sale': 'Test description',
            'is_published': True,
            'catalog_featured': True,
        })

        # Ensure config exists
        cls.config = cls.env['catalog.config'].get_config()

    def test_catalog_fields_exist(self):
        """Test that catalog-specific fields exist"""
        self.assertTrue(hasattr(self.product, 'is_published'))
        self.assertTrue(hasattr(self.product, 'catalog_featured'))
        self.assertTrue(hasattr(self.product, 'catalog_description'))
        self.assertTrue(hasattr(self.product, 'catalog_public'))

    def test_default_is_published(self):
        """Test that is_published defaults to False (website module default)"""
        product = self.env['product.template'].create({
            'name': 'New Product',
        })
        self.assertFalse(product.is_published)

    def test_action_publish_catalog(self):
        """Test action_publish_catalog publishes products"""
        product = self.env['product.template'].create({
            'name': 'Unpublished Product',
            'is_published': False,
        })

        self.assertFalse(product.is_published)

        result = product.action_publish_catalog()

        self.assertTrue(product.is_published)
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')

    def test_action_unpublish_catalog(self):
        """Test action_unpublish_catalog unpublishes products"""
        self.assertTrue(self.product.is_published)

        result = self.product.action_unpublish_catalog()

        self.assertFalse(self.product.is_published)
        self.assertEqual(result['type'], 'ir.actions.client')

    def test_action_publish_multiple_products(self):
        """Test publish action works on multiple products"""
        product2 = self.env['product.template'].create({
            'name': 'Product 2',
            'is_published': False,
        })
        product3 = self.env['product.template'].create({
            'name': 'Product 3',
            'is_published': False,
        })

        products = product2 | product3
        products.action_publish_catalog()

        self.assertTrue(product2.is_published)
        self.assertTrue(product3.is_published)

    def test_get_catalog_data_basic(self):
        """Test get_catalog_data returns correct data"""
        # Create export fields to enable
        ExportField = self.env['catalog.export.field']
        fields_to_enable = []
        for name, tech_name in [
            ('Name', 'name'),
            ('Price', 'list_price'),
            ('Reference', 'default_code'),
        ]:
            field = ExportField.search([('technical_name', '=', tech_name)], limit=1)
            if not field:
                field = ExportField.create({
                    'name': name,
                    'technical_name': tech_name,
                    'is_default': True,
                })
            fields_to_enable.append(field.id)

        self.config.export_field_ids = [(6, 0, fields_to_enable)]

        data = self.product.get_catalog_data()

        # Should always include id
        self.assertEqual(data['id'], self.product.id)
        # Should include enabled fields
        self.assertEqual(data.get('name'), 'Test Product')
        self.assertEqual(data.get('list_price'), 150.0)
        self.assertEqual(data.get('default_code'), 'TEST001')

    def test_get_catalog_data_with_pricelist(self):
        """Test get_catalog_data uses pricelist price"""
        # Create a pricelist with a discount
        pricelist = self.env['product.pricelist'].create({
            'name': 'Test Pricelist',
        })
        self.env['product.pricelist.item'].create({
            'pricelist_id': pricelist.id,
            'compute_price': 'fixed',
            'fixed_price': 100.0,
            'applied_on': '1_product',
            'product_tmpl_id': self.product.id,
        })

        # Enable list_price field
        ExportField = self.env['catalog.export.field']
        price_field = ExportField.search([('technical_name', '=', 'list_price')], limit=1)
        if not price_field:
            price_field = ExportField.create({
                'name': 'Price',
                'technical_name': 'list_price',
                'is_default': True,
            })
        self.config.export_field_ids = [(6, 0, [price_field.id])]

        data = self.product.get_catalog_data(pricelist=pricelist)

        self.assertEqual(data.get('list_price'), 100.0)

    def test_get_catalog_data_custom_export_fields(self):
        """Test get_catalog_data respects custom export fields"""
        ExportField = self.env['catalog.export.field']

        # Create and enable only specific fields
        name_field = ExportField.search([('technical_name', '=', 'name')], limit=1)
        if not name_field:
            name_field = ExportField.create({
                'name': 'Name',
                'technical_name': 'name',
            })

        self.config.export_field_ids = [(6, 0, [name_field.id])]

        data = self.product.get_catalog_data()

        # Should include id and name
        self.assertIn('id', data)
        self.assertIn('name', data)
        # Should NOT include other fields
        self.assertNotIn('list_price', data)
        self.assertNotIn('default_code', data)

    def test_get_catalog_data_with_explicit_fields(self):
        """Test get_catalog_data with explicit export_fields parameter"""
        ExportField = self.env['catalog.export.field']

        weight_field = ExportField.search([('technical_name', '=', 'weight')], limit=1)
        if not weight_field:
            weight_field = ExportField.create({
                'name': 'Weight',
                'technical_name': 'weight',
            })

        data = self.product.get_catalog_data(export_fields=weight_field)

        self.assertIn('id', data)
        self.assertIn('weight', data)
        self.assertEqual(data['weight'], 1.5)

    def test_catalog_description_fallback(self):
        """Test catalog_description falls back to description_sale"""
        ExportField = self.env['catalog.export.field']
        desc_field = ExportField.search([('technical_name', '=', 'catalog_description')], limit=1)
        if not desc_field:
            desc_field = ExportField.create({
                'name': 'Catalog Description',
                'technical_name': 'catalog_description',
            })
        self.config.export_field_ids = [(6, 0, [desc_field.id])]

        # Product has description_sale but no catalog_description
        self.assertFalse(self.product.catalog_description)

        data = self.product.get_catalog_data()

        # Should fallback to description_sale
        self.assertEqual(data.get('catalog_description'), 'Test description')

    def test_image_url_format(self):
        """Test image_url is correctly formatted"""
        ExportField = self.env['catalog.export.field']
        image_field = ExportField.search([('technical_name', '=', 'image_url')], limit=1)
        if not image_field:
            image_field = ExportField.create({
                'name': 'Image URL',
                'technical_name': 'image_url',
            })
        self.config.export_field_ids = [(6, 0, [image_field.id])]

        data = self.product.get_catalog_data()

        expected_url = f'/web/image/product.template/{self.product.id}/image_1920'
        self.assertEqual(data.get('image_url'), expected_url)

    def test_action_view_catalog_logs(self):
        """Test action_view_catalog_logs returns correct action"""
        action = self.product.action_view_catalog_logs()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'catalog.access.log')
        self.assertIn(('product_ids', 'in', self.product.id), action['domain'])

    def test_catalog_statistics_computation(self):
        """Test catalog statistics are computed"""
        # Initially zero
        self.assertEqual(self.product.export_count, 0)
        self.assertEqual(self.product.view_count, 0)
        self.assertFalse(self.product.last_export_date)

        # Create logs
        self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'product_ids': [(6, 0, [self.product.id])],
        })
        self.env['catalog.access.log'].create({
            'action': 'view_product',
            'product_ids': [(6, 0, [self.product.id])],
        })

        # Refresh
        self.product.invalidate_recordset()

        self.assertEqual(self.product.export_count, 1)
        self.assertEqual(self.product.view_count, 1)
        self.assertTrue(self.product.last_export_date)

    def test_empty_values_handled(self):
        """Test that empty/None values are handled gracefully"""
        product = self.env['product.template'].create({
            'name': 'Minimal Product',
            # No default_code, barcode, description, etc.
        })

        ExportField = self.env['catalog.export.field']
        fields_to_enable = []
        for tech_name in ['name', 'default_code', 'barcode', 'description_sale']:
            field = ExportField.search([('technical_name', '=', tech_name)], limit=1)
            if not field:
                field = ExportField.create({
                    'name': tech_name,
                    'technical_name': tech_name,
                })
            fields_to_enable.append(field.id)

        self.config.export_field_ids = [(6, 0, fields_to_enable)]

        data = product.get_catalog_data()

        # Should return empty strings for None values
        self.assertEqual(data.get('default_code'), '')
        self.assertEqual(data.get('barcode'), '')
        self.assertEqual(data.get('description_sale'), '')
