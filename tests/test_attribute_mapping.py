# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogAttributeMapping(TransactionCase):
    """Tests for catalog.attribute.mapping model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Attr Mapping Partner',
            'email': 'attr@example.com',
        })
        cls.client = cls.env['catalog.client'].create({
            'name': 'Attr Mapping Client',
            'partner_id': cls.partner.id,
        })
        cls.connection = cls.env['catalog.client.connection'].create({
            'client_id': cls.client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })
        cls.attribute_color = cls.env['product.attribute'].create({
            'name': 'Color',
        })
        cls.attribute_size = cls.env['product.attribute'].create({
            'name': 'Size',
        })
        cls.value_red = cls.env['product.attribute.value'].create({
            'name': 'Red',
            'attribute_id': cls.attribute_color.id,
        })
        cls.value_blue = cls.env['product.attribute.value'].create({
            'name': 'Blue',
            'attribute_id': cls.attribute_color.id,
        })
        cls.value_small = cls.env['product.attribute.value'].create({
            'name': 'Small',
            'attribute_id': cls.attribute_size.id,
        })

    def test_attribute_mapping_creation(self):
        """Test basic attribute mapping creation"""
        mapping = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
            'client_attribute_id': 42,
            'client_attribute_name': 'Colour',
        })

        self.assertTrue(mapping)
        self.assertEqual(mapping.connection_id, self.connection)
        self.assertEqual(mapping.supplier_attribute_id, self.attribute_color)
        self.assertEqual(mapping.client_attribute_id, 42)
        self.assertEqual(mapping.client_attribute_name, 'Colour')

    def test_supplier_attribute_name_related(self):
        """Test supplier_attribute_name is correctly related"""
        mapping = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
        })

        self.assertEqual(mapping.supplier_attribute_name, 'Color')

    def test_auto_create_default(self):
        """Test auto_create defaults to True"""
        mapping = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
        })

        self.assertTrue(mapping.auto_create)

    def test_unique_supplier_attribute_per_connection(self):
        """Test that each supplier attribute can only be mapped once per connection"""
        self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
        })

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['catalog.attribute.mapping'].create({
                    'connection_id': self.connection.id,
                    'supplier_attribute_id': self.attribute_color.id,
                })

    def test_same_attribute_different_connections(self):
        """Test same attribute can be mapped in different connections"""
        partner2 = self.env['res.partner'].create({
            'name': 'Another Partner',
            'email': 'another@example.com',
        })
        client2 = self.env['catalog.client'].create({
            'name': 'Another Client',
            'partner_id': partner2.id,
        })
        connection2 = self.env['catalog.client.connection'].create({
            'client_id': client2.id,
            'odoo_url': 'https://other.odoo.com',
            'database': 'other_db',
            'api_key': 'other_key',
        })

        m1 = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
            'client_attribute_id': 10,
        })
        m2 = self.env['catalog.attribute.mapping'].create({
            'connection_id': connection2.id,
            'supplier_attribute_id': self.attribute_color.id,
            'client_attribute_id': 20,
        })

        self.assertTrue(m1)
        self.assertTrue(m2)
        self.assertNotEqual(m1.client_attribute_id, m2.client_attribute_id)

    def test_cascade_delete_on_connection(self):
        """Test attribute mappings are deleted when connection is deleted"""
        partner = self.env['res.partner'].create({
            'name': 'Cascade Partner',
            'email': 'cascade@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Cascade Client',
            'partner_id': partner.id,
        })
        conn = self.env['catalog.client.connection'].create({
            'client_id': client.id,
            'odoo_url': 'https://cascade.odoo.com',
            'database': 'cascade_db',
            'api_key': 'cascade_key',
        })
        mapping = self.env['catalog.attribute.mapping'].create({
            'connection_id': conn.id,
            'supplier_attribute_id': self.attribute_color.id,
        })
        mapping_id = mapping.id

        conn.unlink()

        self.assertFalse(
            self.env['catalog.attribute.mapping'].browse(mapping_id).exists()
        )

    def test_multiple_attributes_per_connection(self):
        """Test multiple attribute mappings on same connection"""
        m1 = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
            'client_attribute_id': 10,
        })
        m2 = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_size.id,
            'client_attribute_id': 20,
        })

        self.assertEqual(len(self.connection.attribute_mapping_ids), 2)

    def test_mapping_without_client_id(self):
        """Test mapping can be created without client attribute ID (auto-create)"""
        mapping = self.env['catalog.attribute.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_attribute_id': self.attribute_color.id,
            'auto_create': True,
        })

        self.assertEqual(mapping.client_attribute_id, 0)
        self.assertTrue(mapping.auto_create)


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogAttributeValueMapping(TransactionCase):
    """Tests for catalog.attribute.value.mapping model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Value Mapping Partner',
            'email': 'valuemap@example.com',
        })
        cls.client = cls.env['catalog.client'].create({
            'name': 'Value Mapping Client',
            'partner_id': cls.partner.id,
        })
        cls.connection = cls.env['catalog.client.connection'].create({
            'client_id': cls.client.id,
            'odoo_url': 'https://test.odoo.com',
            'database': 'test_db',
            'api_key': 'test_key',
        })
        cls.attribute = cls.env['product.attribute'].create({
            'name': 'Material',
        })
        cls.value_cotton = cls.env['product.attribute.value'].create({
            'name': 'Cotton',
            'attribute_id': cls.attribute.id,
        })
        cls.value_silk = cls.env['product.attribute.value'].create({
            'name': 'Silk',
            'attribute_id': cls.attribute.id,
        })

    def test_value_mapping_creation(self):
        """Test basic attribute value mapping creation"""
        mapping = self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_cotton.id,
            'client_value_id': 99,
            'client_value_name': 'Cotton Fabric',
        })

        self.assertTrue(mapping)
        self.assertEqual(mapping.supplier_value_id, self.value_cotton)
        self.assertEqual(mapping.client_value_id, 99)
        self.assertEqual(mapping.client_value_name, 'Cotton Fabric')

    def test_supplier_value_name_related(self):
        """Test supplier_value_name is correctly related"""
        mapping = self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_cotton.id,
        })

        self.assertEqual(mapping.supplier_value_name, 'Cotton')

    def test_supplier_attribute_id_related(self):
        """Test supplier_attribute_id is correctly related and stored"""
        mapping = self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_cotton.id,
        })

        self.assertEqual(mapping.supplier_attribute_id, self.attribute)

    def test_unique_supplier_value_per_connection(self):
        """Test each supplier value can only be mapped once per connection"""
        self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_cotton.id,
        })

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['catalog.attribute.value.mapping'].create({
                    'connection_id': self.connection.id,
                    'supplier_value_id': self.value_cotton.id,
                })

    def test_multiple_values_per_connection(self):
        """Test multiple value mappings on same connection"""
        self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_cotton.id,
            'client_value_id': 10,
        })
        self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_silk.id,
            'client_value_id': 20,
        })

        self.assertEqual(len(self.connection.attribute_value_mapping_ids), 2)

    def test_cascade_delete_on_connection(self):
        """Test value mappings are deleted when connection is deleted"""
        partner = self.env['res.partner'].create({
            'name': 'Val Cascade Partner',
            'email': 'valcascade@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Val Cascade Client',
            'partner_id': partner.id,
        })
        conn = self.env['catalog.client.connection'].create({
            'client_id': client.id,
            'odoo_url': 'https://valcascade.odoo.com',
            'database': 'vc_db',
            'api_key': 'vc_key',
        })
        mapping = self.env['catalog.attribute.value.mapping'].create({
            'connection_id': conn.id,
            'supplier_value_id': self.value_cotton.id,
        })
        mapping_id = mapping.id

        conn.unlink()

        self.assertFalse(
            self.env['catalog.attribute.value.mapping'].browse(mapping_id).exists()
        )

    def test_value_mapping_without_client_id(self):
        """Test value mapping can be created without client value ID"""
        mapping = self.env['catalog.attribute.value.mapping'].create({
            'connection_id': self.connection.id,
            'supplier_value_id': self.value_silk.id,
        })

        self.assertEqual(mapping.client_value_id, 0)
