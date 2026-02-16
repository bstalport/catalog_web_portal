# -*- coding: utf-8 -*-

import json
import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression  # deprecated in Odoo 19 but still functional

_logger = logging.getLogger(__name__)


class CatalogPortal(CustomerPortal):
    """
    Controller pour le portail catalogue côté client.
    Gère la navigation, recherche, et sélection des produits.
    """

    # ---------- helpers ----------

    @staticmethod
    def _get_catalog_client():
        """Return the active catalog.client for the current portal user, or None."""
        partner = request.env.user.partner_id
        return request.env['catalog.client'].sudo().search([
            ('partner_id', '=', partner.id),
            ('is_active', '=', True),
        ], limit=1) or None

    @staticmethod
    def _safe_int(value, default=0):
        """Safely convert a route/post parameter to int."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    # ---------- portal home ----------

    def _prepare_home_portal_values(self, counters):
        """Ajoute le compteur de produits catalogue au portail"""
        values = super()._prepare_home_portal_values(counters)

        if 'catalog_count' in counters:
            catalog_client = self._get_catalog_client()
            if catalog_client:
                products = catalog_client._get_accessible_products()
                values['catalog_count'] = len(products)

        return values
    
    # ============ PORTAL HOME / DASHBOARD ============

    @http.route(['/catalog/portal'],
                type='http', auth='user', website=True)
    def catalog_portal_dashboard(self, **kwargs):
        """
        Dashboard principal du portail - Point d'entrée avec vue d'ensemble.
        """
        # Vérifier que l'utilisateur a accès au catalogue
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Get connection info
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)

        # Get statistics
        total_products = len(catalog_client._get_accessible_products())
        selected_count = len(catalog_client.selected_product_ids)

        saved_selections = request.env['catalog.saved.selection'].sudo().search([
            ('catalog_client_id', '=', catalog_client.id)
        ], order='create_date desc')
        saved_selections_count = len(saved_selections)

        connection_configured = bool(connection and connection.odoo_url)

        values = {
            'catalog_client': catalog_client,
            'connection': connection,
            'connection_configured': connection_configured,
            'total_products': total_products,
            'selected_count': selected_count,
            'saved_selections': saved_selections,
            'saved_selections_count': saved_selections_count,
        }

        return request.render('catalog_web_portal.portal_catalog_dashboard', values)

    @http.route(['/catalog/portal/browse', '/catalog/portal/browse/page/<int:page>'],
                type='http', auth='user', website=True)
    def catalog_portal_browse(self, page=1, search='', category=None, sortby='name', **kwargs):
        """
        Page de navigation du catalogue.
        Affiche les produits accessibles avec recherche et filtres.
        """
        # Vérifier que l'utilisateur a accès au catalogue
        catalog_client = self._get_catalog_client()
        
        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Initialiser la session avec la sélection sauvegardée du client
        if 'catalog_selection' not in request.session:
            request.session['catalog_selection'] = catalog_client.selected_product_ids.ids

        # Logger l'accès
        request.env['catalog.access.log'].sudo().log_action(
            action='view_catalog',
            client_id=catalog_client.id,
            user_id=request.env.user.id,
            ip_address=request.httprequest.remote_addr,
            user_agent=request.httprequest.headers.get('User-Agent'),
        )
        
        # Récupérer les produits accessibles
        products_domain = [('id', 'in', catalog_client._get_accessible_products().ids)]
        
        # Recherche
        if search:
            search_domain = [
                '|', '|',
                ('name', 'ilike', search),
                ('default_code', 'ilike', search),
                ('description_sale', 'ilike', search)
            ]
            products_domain = expression.AND([products_domain, search_domain])
        
        # Filtre par catégorie
        if category:
            category_domain = [('categ_id', 'child_of', self._safe_int(category))]
            products_domain = expression.AND([products_domain, category_domain])
        
        # Tri
        sort_options = {
            'name': 'name',
            'price': 'list_price',
            'date': 'create_date desc',
            'ref': 'default_code',
        }
        order = sort_options.get(sortby, 'name')
        
        # Compter les produits
        Product = request.env['product.template'].sudo()
        product_count = Product.search_count(products_domain)
        
        # Pagination
        url = '/catalog/portal/browse'
        pager = portal_pager(
            url=url,
            url_args={'search': search, 'category': category, 'sortby': sortby},
            total=product_count,
            page=page,
            step=20,  # Produits par page
        )
        
        # Récupérer les produits pour la page actuelle
        products = Product.search(
            products_domain,
            order=order,
            limit=20,
            offset=pager['offset']
        )
        
        # Catégories disponibles (pour le filtre)
        all_products = catalog_client._get_accessible_products()
        categories = all_products.mapped('categ_id')
        
        # Configuration
        config = request.env['catalog.config'].sudo().get_config()
        
        # Récupérer la sélection depuis la session
        selected_ids = request.session.get('catalog_selection', [])

        values = {
            'products': products,
            'categories': categories,
            'pager': pager,
            'search': search,
            'sortby': sortby,
            'category': self._safe_int(category) if category else None,
            'catalog_client': catalog_client,
            'config': config,
            'product_count': product_count,
            'selected_product_ids': selected_ids,
            'selection_count': len(catalog_client.selected_product_ids),
        }

        return request.render('catalog_web_portal.portal_catalog_browser', values)
    
    # ============ PRODUCT DETAIL ============
    
    @http.route(['/catalog/portal/product/<int:product_id>'], 
                type='http', auth='user', website=True)
    def catalog_product_detail(self, product_id, **kwargs):
        """
        Page de détail d'un produit dans le catalogue.
        """
        # Vérifier accès client
        catalog_client = self._get_catalog_client()
        
        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')
        
        # Récupérer le produit
        Product = request.env['product.template'].sudo()
        product = Product.browse(product_id)
        
        # Vérifier que le client a accès à ce produit
        access_domain = catalog_client._get_accessible_domain()
        if not Product.search_count([('id', '=', product_id)] + access_domain):
            raise AccessError(_('You do not have access to this product.'))
        
        # Logger la vue
        request.env['catalog.access.log'].sudo().log_action(
            action='view_product',
            client_id=catalog_client.id,
            user_id=request.env.user.id,
            product_ids=[product_id],
            ip_address=request.httprequest.remote_addr,
        )
        
        # Prix selon pricelist du client
        if catalog_client.pricelist_id:
            price = catalog_client.pricelist_id._get_product_price(product, 1.0)
        else:
            price = product.list_price
        
        # Variant data
        variants = []
        has_variants = False
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)
        sync_variants = connection.sync_variants if connection else False

        if product.product_variant_count > 1:
            has_variants = True
            selected_variant_ids = set(catalog_client.selected_variant_ids.ids)
            is_template_selected = product.id in catalog_client.selected_product_ids.ids

            for variant in product.product_variant_ids:
                combo_parts = []
                for ptav in variant.product_template_attribute_value_ids:
                    combo_parts.append({
                        'attribute': ptav.attribute_id.name,
                        'value': ptav.name,
                    })
                price_extra = sum(
                    ptav.price_extra
                    for ptav in variant.product_template_attribute_value_ids
                )
                variants.append({
                    'id': variant.id,
                    'combination': combo_parts,
                    'combination_name': ', '.join(
                        f"{c['attribute']}: {c['value']}" for c in combo_parts
                    ),
                    'default_code': variant.default_code or '',
                    'barcode': variant.barcode or '',
                    'price_extra': price_extra,
                    'variant_price': price + price_extra,
                    'has_image': bool(variant.image_variant_1920),
                    'selected': variant.id in selected_variant_ids,
                    'weight': variant.weight,
                })

        values = {
            'product': product,
            'price': price,
            'catalog_client': catalog_client,
            'variants': variants,
            'has_variants': has_variants,
            'sync_variants': sync_variants,
            'selection_count': len(catalog_client.selected_product_ids),
        }

        return request.render('catalog_web_portal.portal_product_detail', values)
    
    # ============ SELECTION / CART ============
    
    @http.route(['/catalog/portal/cart'], 
                type='http', auth='user', website=True)
    def catalog_cart(self, **kwargs):
        """
        Page du "panier" de sélection de produits.
        Affiche les produits sélectionnés et propose l'export.
        """
        catalog_client = self._get_catalog_client()
        
        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer la sélection depuis la base de données (source de vérité)
        # ou depuis la session comme fallback
        selected_product_ids = catalog_client.selected_product_ids.ids
        if not selected_product_ids:
            selected_product_ids = request.session.get('catalog_selection', [])

        # Synchroniser la session avec la base de données
        if selected_product_ids:
            request.session['catalog_selection'] = selected_product_ids

        Product = request.env['product.template'].sudo()
        selected_products = Product.browse(selected_product_ids)
        
        # Vérifier que tous les produits sont accessibles via domain SQL
        access_domain = catalog_client._get_accessible_domain()
        selected_products = Product.search([('id', 'in', selected_product_ids)] + access_domain)
        
        # Configuration
        config = request.env['catalog.config'].sudo().get_config()
        
        values = {
            'selected_products': selected_products,
            'catalog_client': catalog_client,
            'config': config,
            'product_count': len(selected_products),
            'selection_count': len(selected_products),
        }
        
        return request.render('catalog_web_portal.portal_catalog_cart', values)
    
    @http.route(['/catalog/portal/cart/add'], 
                type='json', auth='user')
    def catalog_cart_add(self, product_id, **kwargs):
        """
        Ajoute un produit à la sélection (AJAX).
        
        Returns:
            dict: {success: bool, message: str, count: int}
        """
        try:
            # Vérifier accès
            catalog_client = self._get_catalog_client()
            
            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}
            
            # Vérifier que le produit est accessible
            Product = request.env['product.template'].sudo()
            access_domain = catalog_client._get_accessible_domain()
            if not Product.search_count([('id', '=', product_id)] + access_domain):
                return {'success': False, 'message': 'Product not accessible'}
            
            # Ajouter à la session (copie nécessaire : mutation in-place
            # ne lève pas is_dirty sur Session de Odoo 19)
            selection = list(request.session.get('catalog_selection', []))
            if product_id not in selection:
                selection.append(product_id)
                request.session['catalog_selection'] = selection

                # Sauvegarder dans la base de données
                catalog_client.sudo().write({
                    'selected_product_ids': [(4, product_id)]  # Add product to Many2many
                })

            return {
                'success': True,
                'message': 'Product added to selection',
                'count': len(selection)
            }
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @http.route(['/catalog/portal/cart/remove'],
                type='json', auth='user')
    def catalog_cart_remove(self, product_id, **kwargs):
        """
        Retire un produit de la sélection (AJAX).
        """
        try:
            # Récupérer le client
            catalog_client = self._get_catalog_client()

            selection = list(request.session.get('catalog_selection', []))
            if product_id in selection:
                selection.remove(product_id)
                request.session['catalog_selection'] = selection

                # Retirer de la base de données + variants liées
                if catalog_client:
                    product = request.env['product.template'].sudo().browse(product_id)
                    variant_ids = product.product_variant_ids.ids if product.exists() else []
                    write_vals = {
                        'selected_product_ids': [(3, product_id)],
                    }
                    if variant_ids:
                        write_vals['selected_variant_ids'] = [(3, vid) for vid in variant_ids]
                    catalog_client.sudo().write(write_vals)

            return {
                'success': True,
                'message': 'Product removed from selection',
                'count': len(selection)
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @http.route(['/catalog/portal/cart/clear'],
                type='json', auth='user')
    def catalog_cart_clear(self, **kwargs):
        """Vide la sélection"""
        # Récupérer le client
        catalog_client = self._get_catalog_client()

        request.session['catalog_selection'] = []

        # Vider la base de données (templates + variants)
        if catalog_client:
            catalog_client.sudo().write({
                'selected_product_ids': [(5, 0, 0)],
                'selected_variant_ids': [(5, 0, 0)],
            })

        return {'success': True, 'message': 'Selection cleared', 'count': 0}
    
    @http.route(['/catalog/portal/cart/add-all'],
                type='json', auth='user')
    def catalog_cart_add_all(self, search='', category=None, **kwargs):
        """
        Ajoute tous les produits correspondant aux filtres actuels à la sélection.

        Returns:
            dict: {success: bool, added_count: int, count: int}
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            # Construire le domaine identique à catalog_portal_browse
            products_domain = [('id', 'in', catalog_client._get_accessible_products().ids)]

            if search:
                search_domain = [
                    '|', '|',
                    ('name', 'ilike', search),
                    ('default_code', 'ilike', search),
                    ('description_sale', 'ilike', search)
                ]
                products_domain = expression.AND([products_domain, search_domain])

            if category:
                category_domain = [('categ_id', 'child_of', self._safe_int(category))]
                products_domain = expression.AND([products_domain, category_domain])

            # Récupérer tous les IDs correspondants (sans pagination)
            Product = request.env['product.template'].sudo()
            matching_ids = Product.search(products_domain).ids

            # Ajouter à la session (copie nécessaire pour is_dirty)
            selection = list(request.session.get('catalog_selection', []))
            new_ids = [pid for pid in matching_ids if pid not in selection]
            selection.extend(new_ids)
            request.session['catalog_selection'] = selection

            # Sauvegarder en DB
            if new_ids:
                catalog_client.sudo().write({
                    'selected_product_ids': [(4, pid) for pid in new_ids]
                })

            return {
                'success': True,
                'added_count': len(new_ids),
                'count': len(selection),
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/count'],
                type='json', auth='user')
    def catalog_cart_count(self, **kwargs):
        """Retourne le nombre de produits dans la sélection"""
        # Récupérer depuis la base de données (source de vérité)
        catalog_client = self._get_catalog_client()

        if catalog_client:
            count = len(catalog_client.selected_product_ids)
        else:
            count = len(request.session.get('catalog_selection', []))

        return {'count': count}

    # ============ VARIANT SELECTION ============

    @http.route(['/catalog/portal/cart/variant/toggle'],
                type='json', auth='user')
    def catalog_cart_variant_toggle(self, variant_id, selected, **kwargs):
        """
        Toggle a specific variant in the selection.

        Args:
            variant_id: int, product.product ID
            selected: bool, True = select, False = deselect
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            variant = request.env['product.product'].sudo().browse(variant_id)
            if not variant.exists():
                return {'success': False, 'message': 'Variant not found'}

            # Ensure template is in the selection
            tmpl_id = variant.product_tmpl_id.id
            if tmpl_id not in catalog_client.selected_product_ids.ids:
                catalog_client.write({
                    'selected_product_ids': [(4, tmpl_id)]
                })
                # Update session too
                selection = list(request.session.get('catalog_selection', []))
                if tmpl_id not in selection:
                    selection.append(tmpl_id)
                    request.session['catalog_selection'] = selection

            if selected:
                catalog_client.write({
                    'selected_variant_ids': [(4, variant_id)]
                })
            else:
                catalog_client.write({
                    'selected_variant_ids': [(3, variant_id)]
                })

            return {
                'success': True,
                'selected': selected,
                'variant_id': variant_id,
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/variant/select-all'],
                type='json', auth='user')
    def catalog_cart_variant_select_all(self, product_id, **kwargs):
        """Select all variants of a template."""
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'success': False, 'message': 'Product not found'}

            variant_ids = product.product_variant_ids.ids

            # Add all variants
            catalog_client.write({
                'selected_variant_ids': [(4, vid) for vid in variant_ids]
            })

            return {
                'success': True,
                'selected_count': len(variant_ids),
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/variant/deselect-all'],
                type='json', auth='user')
    def catalog_cart_variant_deselect_all(self, product_id, **kwargs):
        """Deselect all variants of a template."""
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'success': False, 'message': 'Product not found'}

            variant_ids = product.product_variant_ids.ids

            # Remove all variants
            catalog_client.write({
                'selected_variant_ids': [(3, vid) for vid in variant_ids]
            })

            return {
                'success': True,
                'selected_count': 0,
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    # ============ SAVED SELECTIONS ============

    @http.route(['/catalog/portal/cart/save'],
                type='json', auth='user')
    def catalog_cart_save_selection(self, selection_name, **kwargs):
        """
        Save the current selection with a name.

        Args:
            selection_name (str): Name for the saved selection

        Returns:
            dict: {success: bool, message: str, selection_id: int}
        """
        try:
            if not selection_name or not selection_name.strip():
                return {'success': False, 'message': 'Please provide a name for the selection'}

            # Get client
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access found'}

            # Get current selection
            product_ids = catalog_client.selected_product_ids.ids

            if not product_ids:
                return {'success': False, 'message': 'No products in current selection'}

            # Check if name already exists
            existing = request.env['catalog.saved.selection'].sudo().search([
                ('catalog_client_id', '=', catalog_client.id),
                ('name', '=', selection_name.strip())
            ], limit=1)

            if existing:
                return {'success': False, 'message': 'A selection with this name already exists'}

            # Create saved selection
            saved_selection = request.env['catalog.saved.selection'].sudo().create({
                'name': selection_name.strip(),
                'catalog_client_id': catalog_client.id,
                'product_ids': [(6, 0, product_ids)]
            })

            return {
                'success': True,
                'message': 'Selection saved successfully',
                'selection_id': saved_selection.id,
                'product_count': len(product_ids)
            }

        except Exception as e:
            _logger.exception("Error saving selection")
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/saved/list'],
                type='json', auth='user')
    def catalog_cart_list_saved_selections(self, **kwargs):
        """
        Get list of saved selections for the current client.

        Returns:
            dict: {success: bool, selections: list}
        """
        try:
            # Get client
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access found'}

            # Get saved selections
            saved_selections = request.env['catalog.saved.selection'].sudo().search([
                ('catalog_client_id', '=', catalog_client.id)
            ], order='create_date desc')

            selections_data = []
            for sel in saved_selections:
                selections_data.append({
                    'id': sel.id,
                    'name': sel.name,
                    'product_count': sel.product_count,
                    'create_date': sel.create_date.strftime('%Y-%m-%d %H:%M') if sel.create_date else ''
                })

            return {
                'success': True,
                'selections': selections_data
            }

        except Exception as e:
            _logger.exception("Error listing saved selections")
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/saved/load'],
                type='json', auth='user')
    def catalog_cart_load_saved_selection(self, selection_id, **kwargs):
        """
        Load a saved selection into the current cart.

        Args:
            selection_id (int): ID of the saved selection to load

        Returns:
            dict: {success: bool, message: str, product_count: int}
        """
        try:
            # Get client
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access found'}

            # Get saved selection
            saved_selection = request.env['catalog.saved.selection'].sudo().browse(self._safe_int(selection_id))

            if not saved_selection.exists():
                return {'success': False, 'message': 'Saved selection not found'}

            # Verify it belongs to this client
            if saved_selection.catalog_client_id.id != catalog_client.id:
                return {'success': False, 'message': 'Access denied'}

            # Load the selection
            product_ids = saved_selection.product_ids.ids
            catalog_client.selected_product_ids = [(6, 0, product_ids)]

            # Update session
            request.session['catalog_selection'] = product_ids

            return {
                'success': True,
                'message': f'Selection "{saved_selection.name}" loaded successfully',
                'product_count': len(product_ids)
            }

        except Exception as e:
            _logger.exception("Error loading saved selection")
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/cart/saved/delete'],
                type='json', auth='user')
    def catalog_cart_delete_saved_selection(self, selection_id, **kwargs):
        """
        Delete a saved selection.

        Args:
            selection_id (int): ID of the saved selection to delete

        Returns:
            dict: {success: bool, message: str}
        """
        try:
            # Get client
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access found'}

            # Get saved selection
            saved_selection = request.env['catalog.saved.selection'].sudo().browse(self._safe_int(selection_id))

            if not saved_selection.exists():
                return {'success': False, 'message': 'Saved selection not found'}

            # Verify it belongs to this client
            if saved_selection.catalog_client_id.id != catalog_client.id:
                return {'success': False, 'message': 'Access denied'}

            selection_name = saved_selection.name
            saved_selection.unlink()

            return {
                'success': True,
                'message': f'Selection "{selection_name}" deleted successfully'
            }

        except Exception as e:
            _logger.exception("Error deleting saved selection")
            return {'success': False, 'message': str(e)}

    # ============ SYNC / IMPORT DIRECT ============

    @http.route(['/catalog/portal/sync/setup'],
                type='http', auth='user', website=True)
    def catalog_sync_setup(self, **kwargs):
        """
        Page de configuration de la connexion Odoo pour l'import direct.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer la connexion existante si elle existe
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)

        values = {
            'catalog_client': catalog_client,
            'connection': connection,
            'message': kwargs.get('message'),
            'message_type': kwargs.get('message_type'),
        }

        return request.render('catalog_web_portal.portal_sync_setup', values)

    @http.route(['/catalog/portal/sync/save'],
                type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def catalog_sync_save(self, action='save', **post):
        """
        Sauvegarde ou teste la connexion Odoo.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer la connexion existante ou créer une nouvelle
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)

        # Préparer les valeurs
        values = {
            'client_id': catalog_client.id,
            'odoo_url': post.get('odoo_url', '').strip(),
            'database': post.get('database', '').strip(),
            'username': post.get('username', '').strip(),
            'api_key': post.get('api_key', '').strip(),
            'verify_ssl': bool(post.get('verify_ssl')),
            'reference_mode': post.get('reference_mode', 'keep_original'),
            'reference_prefix': post.get('reference_prefix', '').strip(),
            'reference_suffix': post.get('reference_suffix', '').strip(),
            'reference_separator': post.get('reference_separator', '').strip(),
            'reference_custom_format': post.get('reference_custom_format', '').strip(),
            'sync_variants': bool(post.get('sync_variants')),
            'is_active': True,
            # Supplier info settings
            'create_supplierinfo': bool(post.get('create_supplierinfo')),
            'supplierinfo_price_field': post.get('supplierinfo_price_field', 'list_price'),
            'supplierinfo_price_coefficient': float(post.get('supplierinfo_price_coefficient', 1.0) or 1.0),
        }

        # Handle supplier_partner_id separately (may be empty string or invalid)
        supplier_partner_id = post.get('supplier_partner_id', '').strip()
        if supplier_partner_id:
            try:
                values['supplier_partner_id'] = int(supplier_partner_id)
            except (ValueError, TypeError):
                pass  # Ignore invalid supplier_partner_id values

        try:
            if connection:
                connection.write(values)
            else:
                connection = request.env['catalog.client.connection'].sudo().create(values)

            # Créer les field mappings par défaut s'ils n'existent pas
            if not connection.field_mapping_ids:
                connection.action_create_default_mappings()

            # Si action = test, tester la connexion
            if action == 'test':
                connection.action_test_connection()
                message = 'Connection successful! Default field mappings created.'
                message_type = 'success'
            else:
                message = 'Connection settings saved successfully. Default field mappings created.'
                message_type = 'success'

        except Exception as e:
            _logger.error(f"Error saving connection: {e}", exc_info=True)
            message = f'Error: {str(e)}'
            message_type = 'danger'

        # Rediriger vers la page setup avec le message
        return request.redirect('/catalog/portal/sync/setup?message=%s&message_type=%s' % (message, message_type))

    @http.route(['/catalog/portal/sync/preview'],
                type='http', auth='user', website=True)
    def catalog_sync_preview(self, **kwargs):
        """
        Affiche un aperçu des changements avant de lancer la synchronisation.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Vérifier qu'une connexion existe
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id),
            ('is_active', '=', True)
        ], limit=1)

        if not connection:
            return request.redirect('/catalog/portal/sync/setup?message=Please configure your connection first&message_type=warning')

        if connection.connection_status != 'ok':
            return request.redirect('/catalog/portal/sync/setup?message=Please test your connection first&message_type=warning')

        # Récupérer la sélection depuis la base de données (source de vérité)
        # ou depuis la session comme fallback
        selected_product_ids = catalog_client.selected_product_ids.ids
        if not selected_product_ids:
            selected_product_ids = request.session.get('catalog_selection', [])

        # Synchroniser la session avec la base de données
        if selected_product_ids:
            request.session['catalog_selection'] = selected_product_ids

        if not selected_product_ids:
            return request.redirect('/catalog/portal/cart?message=Please select products first&message_type=warning')

        # Créer un wizard de preview
        Preview = request.env['catalog.sync.preview'].sudo()

        # Guard: if a sync is currently executing, redirect to progress page
        executing_preview = Preview.search([
            ('connection_id', '=', connection.id),
            ('state', '=', 'executing')
        ], limit=1)
        if executing_preview:
            return request.redirect('/catalog/portal/sync/progress/%s' % executing_preview.id)

        # Clean up stale cancelled/done previews so they don't block new ones
        stale_previews = Preview.search([
            ('connection_id', '=', connection.id),
            ('state', 'in', ('cancelled', 'done'))
        ])
        if stale_previews:
            stale_previews.unlink()

        # Vérifier s'il existe déjà un preview en cours pour ce client
        existing_preview = Preview.search([
            ('connection_id', '=', connection.id),
            ('state', '=', 'draft')
        ], limit=1)

        if existing_preview:
            preview = existing_preview
            preview.write({
                'product_ids': [(6, 0, selected_product_ids)]
            })
        else:
            preview = Preview.create({
                'connection_id': connection.id,
                'product_ids': [(6, 0, selected_product_ids)]
            })

        # Générer le preview des changements
        try:
            preview.action_generate_preview()
        except Exception as e:
            error_msg = str(e)
            # Si c'est une erreur d'authentification, rediriger vers la page de configuration
            if 'Authentication failed' in error_msg or 'API Key' in error_msg:
                return request.redirect(
                    '/catalog/portal/sync/setup?'
                    'message=Connection Error: Your API Key may be invalid or expired. Please verify your credentials and test the connection again.&'
                    'message_type=danger'
                )
            # Autres erreurs
            return request.redirect('/catalog/portal/cart?message=Error generating preview: %s&message_type=danger' % error_msg)

        values = {
            'catalog_client': catalog_client,
            'connection': connection,
            'preview': preview,
            'json': json,
        }

        return request.render('catalog_web_portal.portal_sync_preview_page', values)

    @http.route(['/catalog/portal/sync/execute'],
                type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def catalog_sync_execute(self, preview_id, **kwargs):
        """
        Exécute la synchronisation.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer le preview
        preview = request.env['catalog.sync.preview'].sudo().browse(self._safe_int(preview_id))

        if not preview.exists() or preview.connection_id.client_id != catalog_client:
            return request.redirect('/catalog/portal/cart?message=Invalid preview&message_type=danger')

        try:
            # Launch background sync (returns immediately)
            preview.action_execute_sync_background()

            # Redirect to progress page
            return request.redirect('/catalog/portal/sync/progress/%s' % preview.id)

        except Exception as e:
            _logger.error(f"Sync execution error: {e}", exc_info=True)
            return request.redirect('/catalog/portal/cart?message=Sync error: %s&message_type=danger' % str(e))

    @http.route(['/catalog/portal/sync/result/<int:history_id>'],
                type='http', auth='user', website=True)
    def catalog_sync_result(self, history_id, **kwargs):
        """
        Affiche le résultat de la synchronisation.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer l'historique
        history = request.env['catalog.sync.history'].sudo().browse(history_id)

        if not history.exists() or history.connection_id.client_id != catalog_client:
            return request.redirect('/catalog/portal/cart?message=Invalid sync history&message_type=danger')

        # Parse product results from history details
        product_results = []
        if history.details:
            try:
                details = json.loads(history.details)
                product_results = details.get('products', [])
            except (json.JSONDecodeError, TypeError):
                pass

        values = {
            'catalog_client': catalog_client,
            'history': history,
            'product_results': product_results,
        }

        return request.render('catalog_web_portal.portal_sync_result', values)

    @http.route(['/catalog/portal/sync/progress/<int:preview_id>'],
                type='http', auth='user', website=True)
    def catalog_sync_progress(self, preview_id, **kwargs):
        """
        Affiche la page de progression du sync en arrière-plan.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        preview = request.env['catalog.sync.preview'].sudo().browse(preview_id)

        if not preview.exists() or preview.connection_id.client_id != catalog_client:
            return request.redirect('/catalog/portal/cart?message=Invalid preview&message_type=danger')

        # If already done, redirect to result
        if preview.state == 'done' and preview.sync_history_id:
            return request.redirect('/catalog/portal/sync/result/%s' % preview.sync_history_id.id)

        # If failed (back to ready with error), redirect to cart with message
        if preview.state == 'ready' and preview.sync_error_message:
            return request.redirect(
                '/catalog/portal/cart?message=Import failed: %s&message_type=danger' % preview.sync_error_message
            )

        # If cancelled and no longer executing (thread finished/died), redirect to cart
        if preview.state == 'cancelled' and preview.sync_history_id:
            return request.redirect('/catalog/portal/sync/result/%s' % preview.sync_history_id.id)

        values = {
            'catalog_client': catalog_client,
            'preview': preview,
        }

        return request.render('catalog_web_portal.portal_sync_progress', values)

    @http.route(['/catalog/portal/sync/cancel'],
                type='jsonrpc', auth='user', website=True)
    def catalog_sync_cancel(self, preview_id, **kwargs):
        """Cancel a running background sync."""
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return {'success': False, 'message': 'No access'}

        preview = request.env['catalog.sync.preview'].sudo().browse(self._safe_int(preview_id))

        if not preview.exists() or preview.connection_id.client_id != catalog_client:
            return {'success': False, 'message': 'Invalid preview'}

        preview.action_cancel_sync()
        return {'success': True}

    @http.route(['/catalog/portal/sync/status'],
                type='jsonrpc', auth='user', website=True)
    def catalog_sync_status(self, preview_id, **kwargs):
        """
        JSON endpoint pour le polling de progression du sync.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return {'error': 'No access'}

        preview = request.env['catalog.sync.preview'].sudo().browse(self._safe_int(preview_id))

        if not preview.exists() or preview.connection_id.client_id != catalog_client:
            return {'error': 'Invalid preview'}

        result = {
            'state': preview.state,
            'progress': preview.sync_progress,
            'current': preview.sync_current,
            'total': preview.sync_total,
            'message': preview.sync_message or '',
            'error_message': preview.sync_error_message or '',
            'history_id': preview.sync_history_id.id if preview.sync_history_id else False,
        }

        # Clear selection when sync is done successfully
        if preview.state == 'done' and preview.sync_history_id:
            if preview.sync_history_id.status in ('success', 'partial'):
                request.session['catalog_selection'] = []
                catalog_client.sudo().write({
                    'selected_product_ids': [(5, 0, 0)]
                })

        return result

    @http.route(['/catalog/portal/sync/mappings'],
                type='http', auth='user', website=True)
    def catalog_sync_mappings(self, **kwargs):
        """
        Affiche les mappings de champs configurés pour la synchronisation.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.render('catalog_web_portal.no_access_template')

        # Récupérer la connexion
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)

        if not connection:
            return request.redirect('/catalog/portal/sync/setup?message=Please configure your connection first&message_type=warning')

        # Préparer les catégories fournisseur pour le dropdown
        supplier_categories = request.env['product.category'].sudo().search(
            [('id', 'in', catalog_client._get_accessible_products().mapped('categ_id').ids)]
        )

        # Préparer les mappings avec sudo pour éviter les problèmes d'accès aux Many2one
        field_mappings = connection.field_mapping_ids.sudo()
        category_mappings = connection.category_mapping_ids.sudo()

        # Build label dictionaries from Selection fields
        MappingModel = request.env['catalog.field.mapping']
        source_labels = dict(MappingModel._fields['source_field'].selection)
        target_labels = dict(MappingModel._fields['target_field'].selection)

        values = {
            'catalog_client': catalog_client,
            'connection': connection,
            'supplier_categories': supplier_categories,
            'field_mappings': field_mappings,
            'category_mappings': category_mappings,
            'source_labels': source_labels,
            'target_labels': target_labels,
        }

        return request.render('catalog_web_portal.portal_sync_mappings', values)

    @http.route(['/catalog/portal/sync/mappings/create-default'],
                type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def catalog_sync_create_default_mappings(self, **kwargs):
        """
        Crée les field mappings par défaut depuis le portail.
        """
        catalog_client = self._get_catalog_client()

        if not catalog_client:
            return request.redirect('/catalog/portal')

        # Récupérer la connexion
        connection = request.env['catalog.client.connection'].sudo().search([
            ('client_id', '=', catalog_client.id)
        ], limit=1)

        if not connection:
            return request.redirect('/catalog/portal/sync/setup')

        try:
            # Créer les mappings par défaut
            connection.action_create_default_mappings()
            message = 'Default field mappings created successfully!'
            message_type = 'success'
        except Exception as e:
            message = f'Error creating mappings: {str(e)}'
            message_type = 'danger'

        return request.redirect('/catalog/portal/sync/mappings?message=%s&message_type=%s' % (message, message_type))

    @http.route(['/catalog/portal/sync/mappings/fetch-categories'],
                type='json', auth='user')
    def catalog_sync_fetch_categories(self, **kwargs):
        """
        Récupère les catégories depuis l'Odoo du client via XML-RPC.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            # Récupérer la connexion
            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            # Récupérer les catégories du client
            categories = connection.fetch_client_categories()

            return {
                'success': True,
                'categories': categories
            }

        except Exception as e:
            _logger.error(f"Error fetching categories: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/mappings/field/delete'],
                type='json', auth='user')
    def catalog_sync_delete_field_mapping(self, mapping_id, **kwargs):
        """
        Supprime un field mapping.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            # Vérifier que le mapping appartient bien au client
            mapping = request.env['catalog.field.mapping'].sudo().browse(mapping_id)
            if mapping.connection_id.client_id != catalog_client:
                return {'success': False, 'message': 'Unauthorized'}

            mapping.unlink()
            return {'success': True, 'message': 'Mapping deleted'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/mappings/field/save'],
                type='json', auth='user')
    def catalog_sync_save_field_mapping(self, mapping_id=None, source_field=None,
                                       target_field=None, sync_mode=None,
                                       apply_coefficient=False, coefficient=1.0,
                                       default_value=False, default_value_apply='never',
                                       **kwargs):
        """
        Crée ou modifie un field mapping.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            # Validate selection fields (security: portal users should not inject arbitrary values)
            valid_source = ['_none', 'name', 'default_code', 'list_price', 'barcode',
                            'weight', 'volume', 'description_sale', 'categ_id',
                            'is_published', 'available_in_pos', 'is_storable']
            valid_target = ['name', 'default_code', 'list_price', 'standard_price',
                            'barcode', 'weight', 'volume', 'description_sale',
                            'description_purchase', 'categ_id', 'type', 'sale_ok', 'purchase_ok',
                            'is_published', 'available_in_pos', 'is_storable']
            valid_sync_modes = ['create_only', 'always', 'if_empty', 'manual']
            valid_default_apply = ['never', 'if_source_empty', 'always']

            if source_field not in valid_source:
                return {'success': False, 'message': f'Invalid source field: {source_field}'}
            if target_field not in valid_target:
                return {'success': False, 'message': f'Invalid target field: {target_field}'}
            if sync_mode not in valid_sync_modes:
                return {'success': False, 'message': f'Invalid sync mode: {sync_mode}'}
            if default_value_apply not in valid_default_apply:
                return {'success': False, 'message': f'Invalid default apply mode: {default_value_apply}'}

            values = {
                'source_field': source_field,
                'target_field': target_field,
                'sync_mode': sync_mode,
                'apply_coefficient': apply_coefficient if source_field != '_none' else False,
                'coefficient': float(coefficient) if coefficient else 1.0,
                'default_value': default_value or False,
                'default_value_apply': default_value_apply,
            }

            if mapping_id:
                # Modification
                mapping = request.env['catalog.field.mapping'].sudo().browse(self._safe_int(mapping_id))
                if mapping.connection_id.client_id != catalog_client:
                    return {'success': False, 'message': 'Unauthorized'}
                mapping.write(values)
            else:
                # Création
                values['connection_id'] = connection.id
                mapping = request.env['catalog.field.mapping'].sudo().create(values)

            return {'success': True, 'message': 'Mapping saved', 'mapping_id': mapping.id}

        except Exception as e:
            _logger.error(f"Error saving field mapping: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/mappings/image-settings/save'],
                type='json', auth='user')
    def catalog_sync_save_image_settings(self, include_images=False, preserve_client_images=False, auto_create_categories=None, **kwargs):
        """Save image import settings from the mappings page."""
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            vals = {
                'include_images': bool(include_images),
                'preserve_client_images': bool(preserve_client_images),
            }
            if auto_create_categories is not None:
                vals['auto_create_categories'] = bool(auto_create_categories)
            connection.write(vals)

            return {'success': True, 'message': 'Settings saved'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/mappings/category/delete'],
                type='json', auth='user')
    def catalog_sync_delete_category_mapping(self, mapping_id, **kwargs):
        """
        Supprime un category mapping.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            # Vérifier que le mapping appartient bien au client
            mapping = request.env['catalog.category.mapping'].sudo().browse(mapping_id)
            if mapping.connection_id.client_id != catalog_client:
                return {'success': False, 'message': 'Unauthorized'}

            mapping.unlink()
            return {'success': True, 'message': 'Category mapping deleted'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/mappings/category/save'],
                type='json', auth='user')
    def catalog_sync_save_category_mapping(self, mapping_id=None, supplier_category_id=None,
                                          client_category_id=None, client_category_name=None,
                                          auto_create=False, **kwargs):
        """
        Crée ou modifie un category mapping.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            values = {
                'supplier_category_id': self._safe_int(supplier_category_id) or False,
                'client_category_id': self._safe_int(client_category_id) or False,
                'client_category_name': client_category_name or False,
                'auto_create': bool(auto_create),
            }

            if mapping_id:
                # Modification
                mapping = request.env['catalog.category.mapping'].sudo().browse(self._safe_int(mapping_id))
                if mapping.connection_id.client_id != catalog_client:
                    return {'success': False, 'message': 'Unauthorized'}
                mapping.write(values)
            else:
                # Création
                values['connection_id'] = connection.id
                mapping = request.env['catalog.category.mapping'].sudo().create(values)

            return {'success': True, 'message': 'Category mapping saved', 'mapping_id': mapping.id}

        except Exception as e:
            _logger.error(f"Error saving category mapping: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    # ============ SUPPLIER INFO (for invoice recognition) ============

    @http.route(['/catalog/portal/sync/supplier/search'],
                type='json', auth='user')
    def catalog_sync_search_supplier(self, **kwargs):
        """
        Search for the supplier partner in client's Odoo via XML-RPC.
        Uses the supplier's company name and VAT to search.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            if connection.connection_status != 'ok':
                return {'success': False, 'message': 'Please test your connection first'}

            # Call the model method
            result = connection.action_search_supplier_partner()

            # If we got here without exception, it was successful
            return {
                'success': True,
                'message': f'Found: {connection.supplier_partner_name} (ID: {connection.supplier_partner_id})',
                'supplier_partner_id': connection.supplier_partner_id,
                'supplier_partner_name': connection.supplier_partner_name,
            }

        except UserError as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            _logger.error(f"Error searching supplier: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/supplier/create'],
                type='json', auth='user')
    def catalog_sync_create_supplier(self, **kwargs):
        """
        Create the supplier partner in client's Odoo via XML-RPC.
        Uses the supplier's company information.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            if connection.connection_status != 'ok':
                return {'success': False, 'message': 'Please test your connection first'}

            # Call the model method
            result = connection.action_create_supplier_partner()

            return {
                'success': True,
                'message': f'Created: {connection.supplier_partner_name} (ID: {connection.supplier_partner_id})',
                'supplier_partner_id': connection.supplier_partner_id,
                'supplier_partner_name': connection.supplier_partner_name,
            }

        except UserError as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            _logger.error(f"Error creating supplier: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/supplier/list'],
                type='json', auth='user')
    def catalog_sync_list_suppliers(self, keyword=None, **kwargs):
        """
        Fetch suppliers from client's Odoo via XML-RPC.
        Returns a list of suppliers (companies with supplier_rank > 0).
        Supports optional keyword search on partner name.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            if connection.connection_status != 'ok':
                return {'success': False, 'message': 'Please test your connection first'}

            # Connect to client's Odoo (uses SSL context from connection settings)
            common = connection._get_xmlrpc_proxy('common')
            uid = common.authenticate(connection.database, connection.username, connection.api_key, {})

            if not uid:
                return {'success': False, 'message': 'Authentication failed'}

            models = connection._get_xmlrpc_proxy('object')

            # Build search domain
            domain = [['is_company', '=', True], ['supplier_rank', '>', 0]]

            # Add keyword filter if provided
            if keyword and keyword.strip():
                domain.append(['name', 'ilike', keyword.strip()])

            # Search for suppliers
            supplier_ids = models.execute_kw(
                connection.database, uid, connection.api_key,
                'res.partner', 'search',
                [domain],
                {'limit': 100, 'order': 'name'}
            )

            if not supplier_ids:
                return {'success': True, 'suppliers': [], 'message': 'No suppliers found'}

            # Read supplier details
            suppliers = models.execute_kw(
                connection.database, uid, connection.api_key,
                'res.partner', 'read',
                [supplier_ids],
                {'fields': ['id', 'name']}
            )

            return {
                'success': True,
                'suppliers': suppliers,
                'message': f'Found {len(suppliers)} suppliers'
            }

        except UserError as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            _logger.error(f"Error listing suppliers: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    @http.route(['/catalog/portal/sync/supplier/save'],
                type='json', auth='user')
    def catalog_sync_save_supplier_settings(self, create_supplierinfo=True,
                                            supplier_partner_id=None,
                                            supplierinfo_price_field='list_price',
                                            supplierinfo_price_coefficient=1.0, **kwargs):
        """
        Save supplier info settings for the connection.
        """
        try:
            catalog_client = self._get_catalog_client()

            if not catalog_client:
                return {'success': False, 'message': 'No catalog access'}

            connection = request.env['catalog.client.connection'].sudo().search([
                ('client_id', '=', catalog_client.id)
            ], limit=1)

            if not connection:
                return {'success': False, 'message': 'No connection configured'}

            connection.write({
                'create_supplierinfo': bool(create_supplierinfo),
                'supplier_partner_id': self._safe_int(supplier_partner_id) or False,
                'supplierinfo_price_field': supplierinfo_price_field,
                'supplierinfo_price_coefficient': float(supplierinfo_price_coefficient) if supplierinfo_price_coefficient else 1.0,
            })

            return {
                'success': True,
                'message': 'Supplier settings saved successfully',
            }

        except Exception as e:
            _logger.error(f"Error saving supplier settings: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}
