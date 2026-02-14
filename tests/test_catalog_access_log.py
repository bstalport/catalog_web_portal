# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from datetime import datetime, timedelta


@tagged('post_install', '-at_install', 'catalog')
class TestCatalogAccessLog(TransactionCase):
    """Tests for catalog.access.log model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Log Test Partner',
            'email': 'logtest@example.com',
        })
        cls.client = cls.env['catalog.client'].create({
            'name': 'Log Test Client',
            'partner_id': cls.partner.id,
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Log Test Product',
            'is_published': True,
        })
        cls.user = cls.env.user

    def test_log_creation_basic(self):
        """Test basic log creation"""
        log = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': self.client.id,
        })

        self.assertTrue(log)
        self.assertEqual(log.action, 'view_catalog')
        self.assertEqual(log.client_id, self.client)
        self.assertTrue(log.success)  # Default

    def test_log_action_helper(self):
        """Test log_action helper method"""
        log = self.env['catalog.access.log'].log_action(
            action='export_csv',
            client_id=self.client.id,
            user_id=self.user.id,
            product_ids=[self.product.id],
            ip_address='192.168.1.1',
            export_format='csv',
        )

        self.assertEqual(log.action, 'export_csv')
        self.assertEqual(log.client_id.id, self.client.id)
        self.assertEqual(log.user_id.id, self.user.id)
        self.assertEqual(log.ip_address, '192.168.1.1')
        self.assertEqual(log.export_format, 'csv')
        self.assertEqual(log.product_count, 1)
        self.assertIn(self.product, log.product_ids)

    def test_log_action_without_products(self):
        """Test log_action without products"""
        log = self.env['catalog.access.log'].log_action(
            action='view_catalog',
            client_id=self.client.id,
        )

        self.assertEqual(log.product_count, 0)
        self.assertFalse(log.product_ids)

    def test_related_fields(self):
        """Test related fields are populated"""
        log = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': self.client.id,
            'user_id': self.user.id,
        })

        self.assertEqual(log.client_name, self.client.name)
        self.assertEqual(log.user_name, self.user.name)

    def test_error_logging(self):
        """Test error logging"""
        log = self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'client_id': self.client.id,
            'success': False,
            'error_message': 'Export limit reached',
        })

        self.assertFalse(log.success)
        self.assertEqual(log.error_message, 'Export limit reached')

    def test_action_view_products(self):
        """Test action_view_products returns correct action"""
        log = self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'product_ids': [(6, 0, [self.product.id])],
        })

        action = log.action_view_products()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'product.template')
        self.assertIn(('id', 'in', [self.product.id]), action['domain'])

    def test_get_statistics_basic(self):
        """Test get_statistics without filters"""
        # Create some logs
        self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': self.client.id,
        })
        self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'client_id': self.client.id,
            'product_count': 5,
        })

        stats = self.env['catalog.access.log'].get_statistics()

        self.assertGreaterEqual(stats['total_accesses'], 2)
        self.assertGreaterEqual(stats['total_exports'], 1)

    def test_get_statistics_with_client_filter(self):
        """Test get_statistics filtered by client"""
        # Create another client and logs
        partner2 = self.env['res.partner'].create({
            'name': 'Other Partner',
            'email': 'other@example.com',
        })
        client2 = self.env['catalog.client'].create({
            'name': 'Other Client',
            'partner_id': partner2.id,
        })

        self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': self.client.id,
        })
        self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': client2.id,
        })

        stats = self.env['catalog.access.log'].get_statistics(
            client_id=self.client.id
        )

        # Should only count logs from client1
        self.assertEqual(stats['unique_clients'], 1)

    def test_get_statistics_with_date_filter(self):
        """Test get_statistics with date filters"""
        # Create a log
        log = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': self.client.id,
        })

        # Get stats for today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        stats = self.env['catalog.access.log'].get_statistics(
            date_from=today,
            date_to=tomorrow,
        )

        self.assertGreaterEqual(stats['total_accesses'], 1)

    def test_get_statistics_success_rate(self):
        """Test success rate calculation"""
        # Create successful and failed logs
        self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'success': True,
        })
        self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'success': True,
        })
        self.env['catalog.access.log'].create({
            'action': 'export_csv',
            'success': False,
        })

        stats = self.env['catalog.access.log'].get_statistics()

        # Success rate should be calculable
        self.assertIn('success_rate', stats)
        self.assertIsInstance(stats['success_rate'], float)

    def test_ordering(self):
        """Test logs are ordered by create_date desc"""
        log1 = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
        })
        log2 = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
        })

        logs = self.env['catalog.access.log'].search([
            ('id', 'in', [log1.id, log2.id])
        ])

        # Most recent should be first
        self.assertEqual(logs[0].id, log2.id)

    def test_all_action_types(self):
        """Test all action types can be created"""
        action_types = [
            'view_catalog',
            'view_product',
            'export_csv',
            'export_excel',
            'direct_import',
            'api_request',
        ]

        for action_type in action_types:
            log = self.env['catalog.access.log'].create({
                'action': action_type,
            })
            self.assertEqual(log.action, action_type)

    def test_export_format_types(self):
        """Test all export format types"""
        formats = ['csv', 'excel', 'json']

        for fmt in formats:
            log = self.env['catalog.access.log'].create({
                'action': 'export_csv',
                'export_format': fmt,
            })
            self.assertEqual(log.export_format, fmt)

    def test_multiple_products(self):
        """Test log with multiple products"""
        product2 = self.env['product.template'].create({
            'name': 'Product 2',
        })
        product3 = self.env['product.template'].create({
            'name': 'Product 3',
        })

        log = self.env['catalog.access.log'].log_action(
            action='export_csv',
            product_ids=[self.product.id, product2.id, product3.id],
        )

        self.assertEqual(log.product_count, 3)
        self.assertEqual(len(log.product_ids), 3)

    def test_client_deletion_sets_null(self):
        """Test that deleting client sets client_id to null"""
        partner = self.env['res.partner'].create({
            'name': 'Deletable Partner',
            'email': 'delete@example.com',
        })
        client = self.env['catalog.client'].create({
            'name': 'Deletable Client',
            'partner_id': partner.id,
        })

        log = self.env['catalog.access.log'].create({
            'action': 'view_catalog',
            'client_id': client.id,
        })

        client.unlink()

        # Log should still exist but client_id should be None
        self.assertTrue(log.exists())
        self.assertFalse(log.client_id)
