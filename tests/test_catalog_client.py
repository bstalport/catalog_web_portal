# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogClient(TransactionCase):
    """Tests for catalog.client model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Client Partner',
            'email': 'testclient@example.com',
        })

        # Create test product category
        cls.category = cls.env['product.category'].create({
            'name': 'Test Category',
        })

        # Create test products
        cls.product1 = cls.env['product.template'].create({
            'name': 'Test Product 1',
            'is_published': True,
            'categ_id': cls.category.id,
            'list_price': 100.0,
        })
        cls.product2 = cls.env['product.template'].create({
            'name': 'Test Product 2',
            'is_published': True,
            'categ_id': cls.category.id,
            'list_price': 200.0,
        })
        cls.product_unpublished = cls.env['product.template'].create({
            'name': 'Unpublished Product',
            'is_published': False,
            'categ_id': cls.category.id,
        })

    def test_client_creation(self):
        """Test basic client creation"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        self.assertTrue(client)
        self.assertEqual(client.name, 'Test Client')
        self.assertEqual(client.partner_id, self.partner)
        self.assertTrue(client.is_active)
        self.assertEqual(client.access_mode, 'full')

    def test_api_credentials_generated_on_create(self):
        """Test that API credentials are generated on creation"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        self.assertTrue(client.api_key)
        self.assertTrue(client.api_secret)
        self.assertTrue(client.api_key.startswith('cat_'))
        self.assertEqual(len(client.api_key), 36)  # 'cat_' + 32 chars
        self.assertEqual(len(client.api_secret), 48)

    def test_api_credentials_regeneration(self):
        """Test API credentials can be regenerated"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        old_key = client.api_key
        old_secret = client.api_secret

        client.action_regenerate_api_credentials()

        self.assertNotEqual(client.api_key, old_key)
        self.assertNotEqual(client.api_secret, old_secret)

    def test_unique_partner_constraint(self):
        """Test that one partner can only have one client"""
        self.env['catalog.client'].create({
            'name': 'First Client',
            'partner_id': self.partner.id,
        })

        # Create another partner for second client
        partner2 = self.env['res.partner'].create({
            'name': 'Another Partner',
            'email': 'another@example.com',
        })

        with self.assertRaises(ValidationError):
            self.env['catalog.client'].create({
                'name': 'Second Client',
                'partner_id': self.partner.id,  # Same partner
            })

    def test_accessible_products_full_mode(self):
        """Test full access mode returns all published products"""
        partner = self.env['res.partner'].create({
            'name': 'Full Access Partner',
            'email': 'full@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Full Access Client',
            'partner_id': partner.id,
            'access_mode': 'full',
        })

        products = client._get_accessible_products()

        # Should include published products
        self.assertIn(self.product1, products)
        self.assertIn(self.product2, products)
        # Should not include unpublished
        self.assertNotIn(self.product_unpublished, products)

    def test_accessible_products_restricted_mode(self):
        """Test restricted mode returns only products in allowed categories"""
        partner = self.env['res.partner'].create({
            'name': 'Restricted Partner',
            'email': 'restricted@example.com',
        })

        # Create another category with a product
        other_category = self.env['product.category'].create({
            'name': 'Other Category',
        })
        other_product = self.env['product.template'].create({
            'name': 'Other Product',
            'is_published': True,
            'categ_id': other_category.id,
        })

        client = self.env['catalog.client'].create({
            'name': 'Restricted Client',
            'partner_id': partner.id,
            'access_mode': 'restricted',
            'allowed_category_ids': [(6, 0, [self.category.id])],
        })

        products = client._get_accessible_products()

        # Should include products from allowed category
        self.assertIn(self.product1, products)
        self.assertIn(self.product2, products)
        # Should not include products from other categories
        self.assertNotIn(other_product, products)

    def test_accessible_products_custom_mode(self):
        """Test custom mode returns only specified products"""
        partner = self.env['res.partner'].create({
            'name': 'Custom Partner',
            'email': 'custom@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Custom Client',
            'partner_id': partner.id,
            'access_mode': 'custom',
            'allowed_product_ids': [(6, 0, [self.product1.id])],
        })

        products = client._get_accessible_products()

        # Should only include product1
        self.assertIn(self.product1, products)
        self.assertNotIn(self.product2, products)

    def test_email_related_field(self):
        """Test that email is related to partner"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        self.assertEqual(client.email, 'testclient@example.com')

        # Update partner email
        self.partner.email = 'newemail@example.com'
        self.assertEqual(client.email, 'newemail@example.com')

    def test_access_url_computation(self):
        """Test that access_url is computed correctly"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        self.assertEqual(client.access_url, '/catalog/portal')

    def test_action_view_access_logs(self):
        """Test action_view_access_logs returns correct action"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        action = client.action_view_access_logs()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'catalog.access.log')
        self.assertIn(('client_id', '=', client.id), action['domain'])

    def test_action_open_portal(self):
        """Test action_open_portal returns correct action"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        action = client.action_open_portal()

        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'], '/catalog/portal')
        self.assertEqual(action['target'], 'new')

    def test_create_portal_user_requires_email(self):
        """Test that creating portal user requires email"""
        partner_no_email = self.env['res.partner'].create({
            'name': 'No Email Partner',
        })
        client = self.env['catalog.client'].with_context(
            no_reset_password=True
        ).create({
            'name': 'No Email Client',
            'partner_id': partner_no_email.id,
        })

        # Manually try to create portal user (bypassing auto-creation)
        partner_no_email.user_ids.unlink()
        with self.assertRaises(UserError):
            client._create_portal_user()

    def test_export_statistics(self):
        """Test export statistics computation"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        # Initially zero
        self.assertEqual(client.export_count, 0)
        self.assertFalse(client.last_export_date)

        # Create export log
        self.env['catalog.access.log'].create({
            'client_id': client.id,
            'action': 'export_csv',
            'product_count': 5,
        })

        # Refresh computed fields
        client.invalidate_recordset()

        self.assertEqual(client.export_count, 1)
        self.assertTrue(client.last_export_date)

    def test_access_statistics(self):
        """Test access statistics computation"""
        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
        })

        # Initially zero
        self.assertEqual(client.total_access_count, 0)
        self.assertFalse(client.last_access_date)

        # Create access log
        self.env['catalog.access.log'].create({
            'client_id': client.id,
            'action': 'view_catalog',
        })

        # Refresh computed fields
        client.invalidate_recordset()

        self.assertEqual(client.total_access_count, 1)
        self.assertTrue(client.last_access_date)

    def test_pricelist_assignment(self):
        """Test that pricelist can be assigned to client"""
        pricelist = self.env['product.pricelist'].create({
            'name': 'Test Pricelist',
        })

        client = self.env['catalog.client'].create({
            'name': 'Test Client',
            'partner_id': self.partner.id,
            'pricelist_id': pricelist.id,
        })

        self.assertEqual(client.pricelist_id, pricelist)
