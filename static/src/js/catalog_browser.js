/* ==========================================================================
   Catalog Web Portal - JavaScript
   ========================================================================== */

(function () {
    'use strict';

    // ========== JSON-RPC helper (replaces web.ajax) ==========
    function jsonRpc(url, params) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                id: new Date().getTime(),
                params: params || {},
            }),
        })
        .then(function (response) { return response.json(); })
        .then(function (result) {
            if (result.error) {
                throw new Error(
                    (result.error.data && result.error.data.message) ||
                    result.error.message ||
                    'RPC Error'
                );
            }
            return result.result;
        });
    }

    // ========== Toast Notifications ==========
    function showToast(message, type) {
        type = type || 'info';
        var toast = $('<div class="catalog-toast ' + type + '">' +
            '<span class="close-toast">&times;</span>' +
            '<div>' + message + '</div>' +
            '</div>');

        $('body').append(toast);

        // Auto-hide after 3 seconds
        setTimeout(function() {
            toast.fadeOut(300, function() {
                $(this).remove();
            });
        }, 3000);

        // Manual close
        toast.find('.close-toast').on('click', function() {
            toast.fadeOut(300, function() {
                $(this).remove();
            });
        });
    }

    // ========== Cart Count Update ==========
    function updateCartCount() {
        jsonRpc('/catalog/portal/cart/count', {})
            .then(function(result) {
                $('#cart-count').text(result.count);

                if (result.count > 0) {
                    $('#cart-count').removeClass('bg-light').addClass('bg-warning');
                } else {
                    $('#cart-count').removeClass('bg-warning').addClass('bg-light');
                }
            });
    }

    $(document).ready(function () {

        // Update count on page load
        updateCartCount();

        // ========== Add to Cart ==========
        $(document).on('click', '.btn-add-to-cart', function(e) {
            e.preventDefault();
            e.stopPropagation();

            var $btn = $(this);
            var productId = parseInt($btn.data('product-id'));

            // Skip if already in selection
            if ($btn.hasClass('btn-success')) {
                showToast('Product already in selection', 'info');
                return;
            }

            $btn.prop('disabled', true);

            jsonRpc('/catalog/portal/cart/add', {
                product_id: productId
            }).then(function(result) {
                if (result.success) {
                    // Update button style - check if grid or list view
                    var isListView = $btn.closest('#products-list').length > 0;
                    var btnText = isListView ?
                        '<i class="fa fa-check"></i> Selected' :
                        '<i class="fa fa-check"></i> Already in Selection';

                    $btn.removeClass('btn-primary')
                        .addClass('btn-success')
                        .html(btnText)
                        .prop('disabled', false);

                    updateCartCount();
                    showToast('Product added to selection', 'success');
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false);
                }
            }).catch(function(error) {
                showToast('Error adding product', 'error');
                $btn.prop('disabled', false);
            });
        });

        // ========== Remove from Cart ==========
        $(document).on('click', '.btn-remove-from-cart', function(e) {
            e.preventDefault();
            e.stopPropagation();

            var $btn = $(this);
            var productId = parseInt($btn.data('product-id'));
            var $row = $btn.closest('tr');

            jsonRpc('/catalog/portal/cart/remove', {
                product_id: productId
            }).then(function(result) {
                if (result.success) {
                    $row.fadeOut(300, function() {
                        $(this).remove();

                        if ($('.product-selection-table tbody tr').length === 0) {
                            location.reload();
                        }
                    });

                    updateCartCount();
                    showToast('Product removed from selection', 'info');
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function(error) {
                showToast('Error removing product', 'error');
            });
        });

        // ========== Clear Selection ==========
        $(document).on('click', '#btn-clear-selection', function(e) {
            e.preventDefault();

            if (!confirm('Are you sure you want to clear your entire selection?')) {
                return;
            }

            jsonRpc('/catalog/portal/cart/clear', {})
                .then(function(result) {
                    if (result.success) {
                        location.reload();
                    } else {
                        showToast('Error clearing selection', 'error');
                    }
                });
        });

        // ========== Saved Selections ==========

        // Load saved selections list
        function loadSavedSelections() {
            var $container = $('#saved-selections-container');
            if (!$container.length) return;

            jsonRpc('/catalog/portal/cart/saved/list', {})
                .then(function(result) {
                    if (result.success && result.selections && result.selections.length > 0) {
                        var html = '<div class="list-group">';
                        result.selections.forEach(function(sel) {
                            html += '<div class="list-group-item d-flex justify-content-between align-items-center">' +
                                '<div>' +
                                '<strong>' + sel.name + '</strong>' +
                                '<br/><small class="text-muted">' + sel.product_count + ' product(s) - ' + sel.create_date + '</small>' +
                                '</div>' +
                                '<div class="btn-group">' +
                                '<button class="btn btn-sm btn-success btn-load-selection" data-selection-id="' + sel.id + '" data-selection-name="' + sel.name + '">' +
                                '<i class="fa fa-upload"></i> Load' +
                                '</button>' +
                                '<button class="btn btn-sm btn-danger btn-delete-selection" data-selection-id="' + sel.id + '" data-selection-name="' + sel.name + '">' +
                                '<i class="fa fa-trash"></i>' +
                                '</button>' +
                                '</div>' +
                                '</div>';
                        });
                        html += '</div>';
                        $container.html(html);
                    } else {
                        $container.html('<p class="text-muted text-center mb-0">No saved selections yet. Click "Save Current Selection" to create one.</p>');
                    }
                })
                .catch(function(error) {
                    $container.html('<p class="text-danger text-center mb-0">Error loading saved selections</p>');
                });
        }

        // Load saved selections on cart page
        if ($('#saved-selections-container').length) {
            loadSavedSelections();
        }

        // Save current selection
        $(document).on('click', '#btn-save-selection', function(e) {
            e.preventDefault();

            var selectionName = prompt('Enter a name for this selection:');
            if (!selectionName || !selectionName.trim()) {
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

            jsonRpc('/catalog/portal/cart/save', {
                selection_name: selectionName.trim()
            }).then(function(result) {
                if (result.success) {
                    showToast('Selection saved successfully', 'success');
                    loadSavedSelections();
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save Current Selection');
            }).catch(function(error) {
                showToast('Error saving selection', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save Current Selection');
            });
        });

        // Load saved selection
        $(document).on('click', '.btn-load-selection', function(e) {
            e.preventDefault();

            var selectionId = $(this).data('selection-id');
            var selectionName = $(this).data('selection-name');

            if (!confirm('Load selection "' + selectionName + '"? This will replace your current selection.')) {
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

            jsonRpc('/catalog/portal/cart/saved/load', {
                selection_id: selectionId
            }).then(function(result) {
                if (result.success) {
                    showToast(result.message, 'success');
                    setTimeout(function() {
                        location.reload();
                    }, 1000);
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-upload"></i> Load');
                }
            }).catch(function(error) {
                showToast('Error loading selection', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-upload"></i> Load');
            });
        });

        // Delete saved selection
        $(document).on('click', '.btn-delete-selection', function(e) {
            e.preventDefault();

            var selectionId = $(this).data('selection-id');
            var selectionName = $(this).data('selection-name');

            if (!confirm('Delete selection "' + selectionName + '"? This action cannot be undone.')) {
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

            jsonRpc('/catalog/portal/cart/saved/delete', {
                selection_id: selectionId
            }).then(function(result) {
                if (result.success) {
                    showToast(result.message, 'success');
                    loadSavedSelections();
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-trash"></i>');
                }
            }).catch(function(error) {
                showToast('Error deleting selection', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-trash"></i>');
            });
        });

        // ========== Product Card Click ==========
        $(document).on('click', '.product-card', function(e) {
            if ($(e.target).closest('.btn').length) {
                return;
            }

            var productId = $(this).data('product-id');
            if (productId) {
                window.location.href = '/catalog/portal/product/' + productId;
            }
        });

        // ========== View Toggle (Grid / List) ==========
        (function() {
            var $grid = $('#products-grid');
            var $list = $('#products-list');
            var $btnGrid = $('#btn-view-grid');
            var $btnList = $('#btn-view-list');

            function applyView(mode) {
                if (mode === 'list') {
                    $grid.hide();
                    $list.show();
                    $btnGrid.removeClass('active');
                    $btnList.addClass('active');
                } else {
                    $grid.show();
                    $list.hide();
                    $btnGrid.addClass('active');
                    $btnList.removeClass('active');
                }
            }

            // Restore saved preference, default to list view
            var saved = localStorage.getItem('catalog_view_mode');
            if (saved === 'grid') {
                applyView('grid');
            } else if ($list.length) {
                // Default to list view if list exists
                applyView('list');
            }

            $btnGrid.on('click', function() {
                applyView('grid');
                localStorage.setItem('catalog_view_mode', 'grid');
            });

            $btnList.on('click', function() {
                applyView('list');
                localStorage.setItem('catalog_view_mode', 'list');
            });
        })();

        // ========== Search Form Enhancement ==========
        $('select[name="category"]').on('change', function() {
            $(this).closest('form').submit();
        });

        // ========== Export Format Switcher ==========
        var exportLabels = {
            csv:   '<i class="fa fa-download"></i> Download CSV File',
            excel: '<i class="fa fa-download"></i> Download Excel File'
        };
        var exportActions = {
            csv:   '/catalog/export/csv',
            excel: '/catalog/export/excel'
        };

        $('input[name="export_format"]').on('change', function() {
            var fmt = $(this).val();
            $('#export-form').attr('action', exportActions[fmt] || exportActions.csv);
            $('#btn-export').html(exportLabels[fmt] || exportLabels.csv);
        });

        $('#export-form').on('submit', function() {
            showToast('Preparing export... This may take a moment.', 'info');
        });

        // ========== Keyboard Shortcuts ==========
        $(document).on('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                $('input[name="search"]').focus().select();
            }

            if (e.key === 'Escape' && $('input[name="search"]').is(':focus')) {
                $('input[name="search"]').val('');
            }
        });

        // ========== Smooth Scroll ==========
        $('a[href^="#"]').on('click', function(e) {
            e.preventDefault();
            var target = $($(this).attr('href'));
            if (target.length) {
                $('html, body').animate({
                    scrollTop: target.offset().top - 100
                }, 500);
            }
        });

        // ========== Fetch Client Categories ==========
        $(document).on('click', '#btn-fetch-categories', function(e) {
            e.preventDefault();

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Loading...');

            jsonRpc('/catalog/portal/sync/mappings/fetch-categories', {})
                .then(function(result) {
                    if (result.success) {
                        var $tbody = $('#categories-tbody');
                        $tbody.empty();

                        // Also populate the client category dropdown
                        var $clientSelect = $('#new-client-category');
                        $clientSelect.empty();
                        $clientSelect.append('<option value="">-- Select a category --</option>');

                        if (result.categories && result.categories.length > 0) {
                            result.categories.forEach(function(cat) {
                                var displayName = cat.complete_name || cat.name;

                                // Add to table
                                var $row = $('<tr>');
                                $row.append($('<td>').text(displayName));
                                $row.append($('<td>').append($('<code>').text(cat.id)));
                                $tbody.append($row);

                                // Add to dropdown
                                $clientSelect.append(
                                    $('<option>').val(cat.id).text(displayName).data('name', displayName)
                                );
                            });

                            $('#client-categories-list').slideDown();

                            // Show dropdown, hide text input
                            $clientSelect.show();
                            $('#new-client-category-name').hide();

                            showToast('Loaded ' + result.categories.length + ' categories', 'success');
                        } else {
                            showToast('No categories found in your Odoo', 'info');
                        }

                        $btn.prop('disabled', false).html('<i class="fa fa-download"></i> Fetch Categories from My Odoo');
                    } else {
                        showToast('Error: ' + result.message, 'error');
                        $btn.prop('disabled', false).html('<i class="fa fa-download"></i> Fetch Categories from My Odoo');
                    }
                })
                .catch(function(error) {
                    showToast('Error fetching categories', 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-download"></i> Fetch Categories from My Odoo');
                });
        });

        // ========== Image Import Settings ==========
        $(document).on('click', '#btn-save-image-settings', function(e) {
            e.preventDefault();
            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

            jsonRpc('/catalog/portal/sync/mappings/image-settings/save', {
                include_images: $('#opt-include-images').is(':checked'),
                preserve_client_images: $('#opt-preserve-client-images').is(':checked'),
                auto_create_categories: $('#opt-auto-create-categories').is(':checked')
            }).then(function(result) {
                if (result.success) {
                    showToast('Image settings saved', 'success');
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save Image Settings');
            }).catch(function(error) {
                showToast('Error saving image settings', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save Image Settings');
            });
        });

        // ========== Field Mapping Management ==========

        // Toggle add field mapping form
        $(document).on('click', '#btn-toggle-add-field-mapping', function(e) {
            e.preventDefault();
            $('#form-add-field-mapping').slideToggle();
        });

        // Save new field mapping
        $(document).on('click', '#btn-save-field-mapping', function(e) {
            e.preventDefault();

            var sourceField = $('#new-source-field').val();
            var targetField = $('#new-target-field').val();
            var syncMode = $('#new-sync-mode').val();
            var coefficient = $('#new-coefficient').val();
            var defaultValue = $('#new-default-value').val().trim();
            var defaultValueApply = $('#new-default-value-apply').val();

            if (!targetField) {
                showToast('Please select a target field', 'error');
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

            var applyCoefficient = sourceField !== '_none' && coefficient && parseFloat(coefficient) !== 1.0;

            jsonRpc('/catalog/portal/sync/mappings/field/save', {
                source_field: sourceField,
                target_field: targetField,
                sync_mode: syncMode,
                apply_coefficient: applyCoefficient,
                coefficient: coefficient,
                default_value: defaultValue || false,
                default_value_apply: defaultValueApply
            }).then(function(result) {
                if (result.success) {
                    showToast('Field mapping created successfully', 'success');
                    setTimeout(function() {
                        location.reload();
                    }, 1000);
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-save"></i>');
                }
            }).catch(function(error) {
                showToast('Error saving mapping', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i>');
            });
        });

        // Delete field mapping
        $(document).on('click', '.btn-delete-field-mapping', function(e) {
            e.preventDefault();

            if (!confirm('Are you sure you want to delete this field mapping?')) {
                return;
            }

            var mappingId = $(this).data('mapping-id');
            var $row = $(this).closest('tr');

            jsonRpc('/catalog/portal/sync/mappings/field/delete', {
                mapping_id: mappingId
            }).then(function(result) {
                if (result.success) {
                    $row.fadeOut(300, function() {
                        $(this).remove();
                    });
                    showToast('Field mapping deleted', 'success');
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function(error) {
                showToast('Error deleting mapping', 'error');
            });
        });

        // Delete category mapping
        $(document).on('click', '.btn-delete-category-mapping', function(e) {
            e.preventDefault();

            if (!confirm('Are you sure you want to delete this category mapping?')) {
                return;
            }

            var mappingId = $(this).data('mapping-id');
            var $row = $(this).closest('tr');

            jsonRpc('/catalog/portal/sync/mappings/category/delete', {
                mapping_id: mappingId
            }).then(function(result) {
                if (result.success) {
                    $row.fadeOut(300, function() {
                        $(this).remove();
                    });
                    showToast('Category mapping deleted', 'success');
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function(error) {
                showToast('Error deleting category mapping', 'error');
            });
        });

        // Toggle add category mapping form
        $(document).on('click', '#btn-toggle-add-category-mapping', function(e) {
            e.preventDefault();
            $('#form-add-category-mapping').slideToggle();
        });

        // Save new category mapping
        $(document).on('click', '#btn-save-category-mapping', function(e) {
            e.preventDefault();

            var supplierCategoryId = $('#new-supplier-category').val();
            if (!supplierCategoryId) {
                showToast('Please select a supplier category', 'error');
                return;
            }

            // Get client category: from dropdown if visible, or from text input
            var clientCategoryId = null;
            var clientCategoryName = null;
            var $clientSelect = $('#new-client-category');

            if ($clientSelect.is(':visible') && $clientSelect.val()) {
                clientCategoryId = $clientSelect.val();
                clientCategoryName = $clientSelect.find('option:selected').data('name') || $clientSelect.find('option:selected').text();
            } else {
                clientCategoryName = $('#new-client-category-name').val().trim();
            }

            var autoCreate = $('#new-cat-auto-create').is(':checked');

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saving...');

            jsonRpc('/catalog/portal/sync/mappings/category/save', {
                supplier_category_id: parseInt(supplierCategoryId),
                client_category_id: clientCategoryId ? parseInt(clientCategoryId) : false,
                client_category_name: clientCategoryName || false,
                auto_create: autoCreate
            }).then(function(result) {
                if (result.success) {
                    showToast('Category mapping created successfully', 'success');
                    setTimeout(function() {
                        location.reload();
                    }, 1000);
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save');
                }
            }).catch(function(error) {
                showToast('Error saving category mapping', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-save"></i> Save');
            });
        });

        // ========== Dashboard Saved Selections ==========

        // Load saved selection from dashboard
        $(document).on('click', '.btn-load-saved-selection', function(e) {
            e.preventDefault();

            var selectionId = $(this).data('selection-id');
            var selectionName = $(this).data('selection-name');

            if (!confirm('Load selection "' + selectionName + '"? This will replace your current selection.')) {
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

            jsonRpc('/catalog/portal/cart/saved/load', {
                selection_id: selectionId
            }).then(function(result) {
                if (result.success) {
                    showToast(result.message, 'success');
                    setTimeout(function() {
                        location.reload();
                    }, 1000);
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-upload"></i> Load');
                }
            }).catch(function(error) {
                showToast('Error loading selection', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-upload"></i> Load');
            });
        });

        // Delete saved selection from dashboard
        $(document).on('click', '.btn-delete-saved-selection', function(e) {
            e.preventDefault();

            var selectionId = $(this).data('selection-id');
            var selectionName = $(this).data('selection-name');

            if (!confirm('Delete selection "' + selectionName + '"? This action cannot be undone.')) {
                return;
            }

            var $btn = $(this);
            var $item = $btn.closest('.list-group-item');
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

            jsonRpc('/catalog/portal/cart/saved/delete', {
                selection_id: selectionId
            }).then(function(result) {
                if (result.success) {
                    showToast(result.message, 'success');
                    $item.fadeOut(300, function() {
                        $(this).remove();
                        // Check if there are no more selections
                        if ($('.btn-delete-saved-selection').length === 0) {
                            location.reload();
                        }
                    });
                } else {
                    showToast('Error: ' + result.message, 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-trash"></i>');
                }
            }).catch(function(error) {
                showToast('Error deleting selection', 'error');
                $btn.prop('disabled', false).html('<i class="fa fa-trash"></i>');
            });
        });

        // Clear selection from dashboard
        $(document).on('click', '#btn-clear-selection-dashboard', function(e) {
            e.preventDefault();

            if (!confirm('Are you sure you want to clear your entire selection?')) {
                return;
            }

            var $btn = $(this);
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Clearing...');

            jsonRpc('/catalog/portal/cart/clear', {})
                .then(function(result) {
                    if (result.success) {
                        showToast('Selection cleared successfully', 'success');
                        setTimeout(function() {
                            location.reload();
                        }, 1000);
                    } else {
                        showToast('Error clearing selection', 'error');
                        $btn.prop('disabled', false).html('<i class="fa fa-trash"></i> Clear Selection');
                    }
                })
                .catch(function(error) {
                    showToast('Error clearing selection', 'error');
                    $btn.prop('disabled', false).html('<i class="fa fa-trash"></i> Clear Selection');
                });
        });

        // ========== Variant Selection (Product Detail Page) ==========

        // Toggle individual variant
        $(document).on('change', '.variant-checkbox', function() {
            var $cb = $(this);
            var variantId = parseInt($cb.data('variant-id'));
            var isSelected = $cb.is(':checked');

            jsonRpc('/catalog/portal/cart/variant/toggle', {
                variant_id: variantId,
                selected: isSelected
            }).then(function(result) {
                if (result.success) {
                    showToast(
                        isSelected ? 'Variant selected' : 'Variant deselected',
                        isSelected ? 'success' : 'info'
                    );
                    updateCartCount();
                } else {
                    // Revert checkbox
                    $cb.prop('checked', !isSelected);
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function() {
                $cb.prop('checked', !isSelected);
                showToast('Error toggling variant', 'error');
            });
        });

        // Select all variants
        $(document).on('click', '.btn-variant-select-all', function(e) {
            e.preventDefault();
            var productId = parseInt($(this).data('product-id'));

            jsonRpc('/catalog/portal/cart/variant/select-all', {
                product_id: productId
            }).then(function(result) {
                if (result.success) {
                    $('.variant-checkbox').prop('checked', true);
                    showToast('All variants selected', 'success');
                    updateCartCount();
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function() {
                showToast('Error selecting variants', 'error');
            });
        });

        // Deselect all variants
        $(document).on('click', '.btn-variant-deselect-all', function(e) {
            e.preventDefault();
            var productId = parseInt($(this).data('product-id'));

            jsonRpc('/catalog/portal/cart/variant/deselect-all', {
                product_id: productId
            }).then(function(result) {
                if (result.success) {
                    $('.variant-checkbox').prop('checked', false);
                    showToast('All variants deselected', 'info');
                    updateCartCount();
                } else {
                    showToast('Error: ' + result.message, 'error');
                }
            }).catch(function() {
                showToast('Error deselecting variants', 'error');
            });
        });

        // ========== Preview Variant Toggle ==========
        $(document).on('click', '.btn-toggle-variants', function(e) {
            e.preventDefault();
            var target = $(this).data('target');
            var $row = $('#' + target);
            $row.toggle();
            var $icon = $(this).find('i');
            if ($row.is(':visible')) {
                $icon.removeClass('fa-cubes').addClass('fa-minus-square');
            } else {
                $icon.removeClass('fa-minus-square').addClass('fa-cubes');
            }
        });

        // ========== Sync Progress Polling ==========
        (function () {
            var $previewId = $('#sync-preview-id');
            if (!$previewId.length) return;

            var previewId = parseInt($previewId.val());
            var startTime = Date.now();
            var pollInterval = null;
            var cancelledSince = null;
            var POLL_DELAY = 2000; // 2 seconds
            var MAX_DURATION = 10 * 60 * 1000; // 10 minutes safety timeout
            var CANCEL_FORCE_TIMEOUT = 30000; // 30s after cancel, show force-leave

            function formatTime(seconds) {
                if (seconds < 60) return Math.round(seconds) + 's';
                var min = Math.floor(seconds / 60);
                var sec = Math.round(seconds % 60);
                return min + 'm ' + sec + 's';
            }

            function updateProgress(data) {
                var progress = data.progress || 0;

                // Update progress bar
                $('#sync-progress-bar')
                    .css('width', progress + '%')
                    .attr('aria-valuenow', progress);
                $('#sync-progress-text').text(progress + '%');

                // Update stats
                $('#sync-stat-current').text(data.current || 0);
                $('#sync-stat-total').text(data.total || 0);

                // Update status message
                if (data.message) {
                    $('#sync-status-message').html(
                        '<i class="fa fa-spinner fa-spin"></i> ' + data.message
                    );
                }

                // Elapsed time
                var elapsed = (Date.now() - startTime) / 1000;
                $('#sync-stat-elapsed').text(formatTime(elapsed));

                // Estimated remaining
                if (data.current > 0 && data.total > 0 && data.current < data.total) {
                    var timePerItem = elapsed / data.current;
                    var remaining = timePerItem * (data.total - data.current);
                    $('#sync-stat-remaining').text(formatTime(remaining));
                } else if (data.current >= data.total && data.total > 0) {
                    $('#sync-stat-remaining').text('Almost done...');
                }
            }

            function onDone(data) {
                clearInterval(pollInterval);
                $('#sync-cancel-container').hide();

                var wasCancelled = data.message && data.message.indexOf('cancelled') !== -1;

                // Animate bar
                $('#sync-progress-bar')
                    .removeClass('bg-info progress-bar-animated')
                    .addClass(wasCancelled ? 'bg-warning' : 'bg-success')
                    .css('width', '100%');
                $('#sync-progress-text').text('100%');
                $('#sync-status-message').html(
                    wasCancelled
                        ? '<i class="fa fa-stop-circle text-warning"></i> Import cancelled. Redirecting...'
                        : '<i class="fa fa-check-circle text-success"></i> Import complete! Redirecting...'
                );

                // Redirect to result page
                if (data.history_id) {
                    setTimeout(function () {
                        window.location.href = '/catalog/portal/sync/result/' + data.history_id;
                    }, 1500);
                }
            }

            function onError(data) {
                clearInterval(pollInterval);

                // Red bar
                $('#sync-progress-bar')
                    .removeClass('bg-info progress-bar-animated')
                    .addClass('bg-danger');
                $('#sync-status-message').html(
                    '<i class="fa fa-times-circle text-danger"></i> Import failed'
                );

                // Show error alert
                var msg = data.error_message || 'An unknown error occurred.';
                $('#sync-error-message').text(msg);
                $('#sync-error-alert').show();
            }

            function pollStatus() {
                // Safety timeout
                if (Date.now() - startTime > MAX_DURATION) {
                    clearInterval(pollInterval);
                    $('#sync-status-message').html(
                        '<i class="fa fa-clock-o text-warning"></i> Import is taking longer than expected. ' +
                        'Please check back later.'
                    );
                    return;
                }

                jsonRpc('/catalog/portal/sync/status', { preview_id: previewId })
                    .then(function (data) {
                        if (data.error) {
                            // Don't stop polling for access errors (might be transient)
                            return;
                        }

                        if (data.state === 'done') {
                            onDone(data);
                        } else if (data.state === 'ready' && data.error_message) {
                            onError(data);
                        } else if (data.state === 'cancelled') {
                            // Cancellation requested — keep polling but track time
                            if (!cancelledSince) cancelledSince = Date.now();
                            updateProgress(data);
                            $('#sync-status-message').html(
                                '<i class="fa fa-spinner fa-spin"></i> Cancelling... finishing current product'
                            );
                            // If stuck for too long, show force-leave option
                            if (Date.now() - cancelledSince > CANCEL_FORCE_TIMEOUT) {
                                clearInterval(pollInterval);
                                $('#sync-status-message').html(
                                    '<i class="fa fa-exclamation-triangle text-warning"></i> ' +
                                    'The current operation seems stuck. You can safely leave this page.'
                                );
                                $('#sync-cancel-container').html(
                                    '<a href="/catalog/portal" class="btn btn-warning">' +
                                    '<i class="fa fa-home"></i> Go to Dashboard</a> ' +
                                    '<a href="/catalog/portal/cart" class="btn btn-secondary ml-2">' +
                                    '<i class="fa fa-arrow-left"></i> Back to Selection</a>'
                                );
                            }
                        } else {
                            updateProgress(data);
                        }
                    })
                    .catch(function (err) {
                        // Network error — don't stop polling, it might recover
                        console.warn('Sync status poll error:', err);
                    });
            }

            // Cancel button
            $('#btn-cancel-sync').on('click', function () {
                var $btn = $(this);
                if (!confirm('Are you sure you want to cancel the import? Products already imported will remain.')) {
                    return;
                }
                $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Cancelling...');
                jsonRpc('/catalog/portal/sync/cancel', { preview_id: previewId })
                    .then(function (result) {
                        if (result.success) {
                            showToast('Cancel requested. Finishing current product...', 'info');
                        }
                    })
                    .catch(function () {
                        showToast('Error requesting cancel', 'error');
                        $btn.prop('disabled', false).html('<i class="fa fa-stop"></i> Cancel Import');
                    });
            });

            // Start polling
            pollInterval = setInterval(pollStatus, POLL_DELAY);
            // Also poll immediately
            pollStatus();

        })();

        // ========== Initialization Complete ==========
        console.log('Catalog Web Portal initialized');
    });

})();

