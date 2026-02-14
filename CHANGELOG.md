# Changelog - Catalog Web Portal

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2025-XX-XX

### Added

- **Direct Odoo Sync (XML-RPC)**
  - Remote connection setup to client's Odoo instance
  - Automatic product synchronization via XML-RPC
  - Connection testing and status tracking
  - SSL verification support
  - Sync history with success/partial/error status

- **Field & Category Mapping**
  - Map supplier fields to client Odoo fields
  - Map supplier categories to client categories
  - Auto-creation of missing categories in client Odoo
  - Default mapping generation

- **Attribute Mapping**
  - Map product attributes between Odoo instances
  - Map attribute values with auto-creation option
  - Full product variant sync support

- **Supplier Info Export**
  - Create `product.supplierinfo` records in client Odoo
  - Configurable price source (list price, cost, pricelist)
  - Price coefficient support
  - Supplier partner matching in client Odoo

- **Reference Generation**
  - Multiple modes: keep original, supplier reference, product ID, custom format
  - Configurable prefix, suffix, and separator
  - Custom format with placeholders (`{prefix}`, `{ref}`, `{id}`, `{suffix}`)

- **Saved Selections**
  - Save product selections with custom name
  - Load and delete saved selections
  - Product count tracking per selection

- **Sync Preview**
  - Dry-run preview before committing sync
  - Field-by-field preview of changes
  - Review mappings before import

- **Product Variant Support**
  - Variant-level selection in portal
  - Variant-specific pricing
  - Attribute/value mapping between instances
  - Variant sync to client Odoo

- **Image Sync Options**
  - Include/exclude product images in sync
  - Preserve client-side images option

---

## [1.0.0] - 2024-XX-XX

### Initial Release

#### Added
- **Backend Features**
  - Catalog configuration module with full settings (branding, limits, export fields)
  - Client management with three access modes (Full, Restricted, Custom)
  - Product publishing controls (Published in Catalog, Featured, Public)
  - Access logging for analytics (views, exports, IP tracking)
  - Security groups (Manager, User, Portal)
  - API key and secret generation per client
  - Configurable export fields (13 pre-configured fields)

- **Frontend Portal**
  - Modern, responsive catalog browser
  - Portal dashboard with statistics and quick actions
  - Product search with live filtering
  - Category-based filtering
  - Multiple sort options (name, price, date, reference)
  - Product detail pages with full information
  - Selection cart with add/remove functionality
  - Session-based selection persistence

- **Export Functionality**
  - CSV export compatible with Odoo standard import
  - Configurable export fields
  - Configurable export options (include images, descriptions)
  - Supplier info in export for invoice matching
  - Rate limiting to prevent abuse (configurable per hour)
  - Product count limits per export
  - Automatic filename generation with client name and date

- **Analytics**
  - Comprehensive access logging (view_catalog, view_product, export_csv, export_excel, direct_import, api_request)
  - User agent and HTTP referer tracking
  - Success/error tracking with error messages
  - Client-specific statistics (export count, last export, access count)
  - Global statistics dashboard (total/active clients, exports today/month)
  - Product-level analytics (export count, view count)

- **Security**
  - Three security groups: Manager (CRUD), User (read-only), Portal (own data)
  - Record-level access rules per group
  - Portal users restricted to published products and own client data
  - Data privacy (no costs, supplier info, or internal notes exposed)
  - Rate limiting on exports
  - All actions logged with IP tracking

- **UI/UX**
  - Clean, modern interface with Bootstrap integration
  - Responsive design (mobile, tablet, desktop breakpoints)
  - Toast notifications for user feedback
  - Loading indicators and animations
  - Smooth transitions and hover effects
  - Accessible breadcrumbs and navigation
  - Branding customization (logo, primary color, welcome message)

#### Technical
- Compatible with Odoo 19.0
- Python 3.10+ support
- PostgreSQL 14+ support
- Depends on: base, product, portal, website, mail
- Full i18n support (English, French)
- Follows Odoo coding guidelines
- 6 test modules with 1,700+ lines of tests

---

## [Unreleased]

### Planned Features

#### High Priority
- Excel (.xlsx) export format
- Stock levels display (optional)
- Public catalog mode (no authentication required)

#### Medium Priority
- Advanced analytics dashboard with charts
- Email notifications on catalog updates
- Webhooks for real-time sync notifications
- PDF catalog generation
- Product comparison feature

#### Low Priority
- Mobile native apps (iOS/Android)
- Multi-language product descriptions
- Scheduled automatic exports and syncs
- Advanced search with faceted filters
- Product recommendations

### Known Issues
- None reported yet

---

## Development Notes

### Version Numbering
- **Major.Minor.Patch** (e.g., 1.0.0)
- **Major**: Breaking changes, major new features
- **Minor**: New features, backwards compatible
- **Patch**: Bug fixes, small improvements

### Release Process
1. Update CHANGELOG.md
2. Update version in __manifest__.py
3. Run tests
4. Create git tag
5. Build package
6. Publish to Odoo Apps Store
7. Announce on website/social media

---

## Support & Feedback

- 🐛 **Report bugs**: GitHub Issues
- 💡 **Suggest features**: GitHub Discussions
- 📧 **Email**: support@yourcompany.com
- 📖 **Documentation**: README.md

---

*Thank you for using Catalog Web Portal!*
