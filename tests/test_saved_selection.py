# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogSavedSelection(TransactionCase):
    """Tests for catalog.saved.selection model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Selection Test Partner',
            'email': 'selection@example.com',
        })
        cls.client = cls.env['catalog.client'].create({
            'name': 'Selection Test Client',
            'partner_id': cls.partner.id,
        })
        cls.product1 = cls.env['product.template'].create({
            'name': 'Selection Product 1',
            'is_published': True,
            'list_price': 100.0,
        })
        cls.product2 = cls.env['product.template'].create({
            'name': 'Selection Product 2',
            'is_published': True,
            'list_price': 200.0,
        })
        cls.product3 = cls.env['product.template'].create({
            'name': 'Selection Product 3',
            'is_published': True,
            'list_price': 300.0,
        })

    def test_saved_selection_creation(self):
        """Test basic saved selection creation"""
        selection = self.env['catalog.saved.selection'].create({
            'name': 'My Selection',
            'catalog_client_id': self.client.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id])],
        })

        self.assertTrue(selection)
        self.assertEqual(selection.name, 'My Selection')
        self.assertEqual(selection.catalog_client_id, self.client)
        self.assertEqual(len(selection.product_ids), 2)

    def test_product_count_computation(self):
        """Test product_count is computed correctly"""
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Count Test',
            'catalog_client_id': self.client.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id, self.product3.id])],
        })

        self.assertEqual(selection.product_count, 3)

    def test_product_count_empty(self):
        """Test product_count with no products"""
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Empty Selection',
            'catalog_client_id': self.client.id,
        })

        self.assertEqual(selection.product_count, 0)

    def test_product_count_updates_on_change(self):
        """Test product_count updates when products are added/removed"""
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Dynamic Selection',
            'catalog_client_id': self.client.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })

        self.assertEqual(selection.product_count, 1)

        # Add more products
        selection.product_ids = [(6, 0, [self.product1.id, self.product2.id])]
        self.assertEqual(selection.product_count, 2)

        # Remove a product
        selection.product_ids = [(3, self.product1.id)]
        self.assertEqual(selection.product_count, 1)

    def test_action_load_selection(self):
        """Test loading a saved selection into client's cart"""
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Loadable Selection',
            'catalog_client_id': self.client.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id])],
        })

        # Initially client has no selected products
        self.assertEqual(len(self.client.selected_product_ids), 0)

        # Load the selection
        result = selection.action_load_selection()

        # Client should now have the products
        self.assertEqual(len(self.client.selected_product_ids), 2)
        self.assertIn(self.product1, self.client.selected_product_ids)
        self.assertIn(self.product2, self.client.selected_product_ids)

        # Should return a notification action
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')

    def test_load_selection_replaces_current(self):
        """Test that loading a selection replaces the current one"""
        # Set initial selection on client
        self.client.selected_product_ids = [(6, 0, [self.product3.id])]
        self.assertEqual(len(self.client.selected_product_ids), 1)

        # Create and load a different selection
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Replace Selection',
            'catalog_client_id': self.client.id,
            'product_ids': [(6, 0, [self.product1.id, self.product2.id])],
        })
        selection.action_load_selection()

        # Client's cart should be replaced
        self.assertEqual(len(self.client.selected_product_ids), 2)
        self.assertNotIn(self.product3, self.client.selected_product_ids)

    def test_cascade_delete_on_client(self):
        """Test selections are deleted when client is deleted"""
        partner = self.env['res.partner'].create({
            'name': 'Deletable Partner',
            'email': 'deletable@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Deletable Client',
            'partner_id': partner.id,
        })
        selection = self.env['catalog.saved.selection'].create({
            'name': 'Cascade Test',
            'catalog_client_id': client.id,
            'product_ids': [(6, 0, [self.product1.id])],
        })
        selection_id = selection.id

        client.unlink()

        # Selection should be deleted
        self.assertFalse(self.env['catalog.saved.selection'].browse(selection_id).exists())

    def test_ordering_by_create_date(self):
        """Test selections are ordered by create_date descending"""
        sel1 = self.env['catalog.saved.selection'].create({
            'name': 'First Selection',
            'catalog_client_id': self.client.id,
        })
        sel2 = self.env['catalog.saved.selection'].create({
            'name': 'Second Selection',
            'catalog_client_id': self.client.id,
        })

        selections = self.env['catalog.saved.selection'].search([
            ('catalog_client_id', '=', self.client.id),
            ('id', 'in', [sel1.id, sel2.id]),
        ])

        # Most recent first
        self.assertEqual(selections[0].id, sel2.id)

    def test_multiple_selections_per_client(self):
        """Test client can have multiple saved selections"""
        for i in range(5):
            self.env['catalog.saved.selection'].create({
                'name': f'Selection {i}',
                'catalog_client_id': self.client.id,
                'product_ids': [(6, 0, [self.product1.id])],
            })

        selections = self.env['catalog.saved.selection'].search([
            ('catalog_client_id', '=', self.client.id),
        ])
        self.assertEqual(len(selections), 5)
