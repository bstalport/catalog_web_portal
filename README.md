# Catalog Web Portal - Supplier Product Sharing

## 🎯 Overview

**Catalog Web Portal** is an Odoo 19.0 module that allows suppliers to share their product catalog with customers through a secure web portal. Customers can browse, select, and import products directly into their own Odoo instance - **even if they use Odoo Online** (no module installation required on client side).

### Key Benefits

- ✅ **No Client Installation**: Works perfectly with Odoo Online
- ✅ **Secure Access**: Portal authentication with API keys
- ✅ **Easy Export**: CSV format compatible with Odoo standard import
- ✅ **Custom Pricing**: Set specific pricelists per customer
- ✅ **Access Control**: Show different products to different customers
- ✅ **Analytics**: Track who views and exports what
- ✅ **Win-Win Model**: Supplier pays, customer uses for FREE

---

## 📦 Installation

### Requirements

- Odoo 19.0
- Python 3.10+
- Dependencies: `product`, `portal`, `website`, `mail`

### Installation Steps

1. **Download** this module to your Odoo addons directory:
   ```bash
   cd /path/to/odoo/addons
   git clone [your-repo-url] catalog_web_portal
   ```

2. **Restart** Odoo server:
   ```bash
   ./odoo-bin -c odoo.conf
   ```

3. **Update Apps List**:
   - Go to Apps menu
   - Click "Update Apps List"

4. **Install Module**:
   - Search for "Catalog Web Portal"
   - Click "Install"

---

## 🚀 Quick Start Guide

### For Suppliers (Setting Up Your Catalog)

#### Step 1: Configure the Catalog

1. Go to **Catalog Portal → Configuration → Settings**
2. Review and adjust settings:
   - Access modes (portal enabled)
   - Export options (CSV, Excel)
   - Rate limits
   - Branding (logo, colors, welcome message)

#### Step 2: Publish Products

1. Go to **Sales → Products**
2. Select products you want to share
3. In product form, go to **Catalog** tab
4. Check **"Published in Catalog"**
5. Optionally set as **"Featured Product"**

Or use bulk action:
1. Select multiple products in list view
2. **Action → Publish in Catalog**

#### Step 3: Create a Client

1. Go to **Catalog Portal → Clients**
2. Click **Create**
3. Fill in:
   - **Name**: Client company name
   - **Partner**: Select existing partner or create new
   - **Access Mode**:
     - *Full*: All published products
     - *Restricted*: By category
     - *Custom*: Specific product list
   - **Pricelist** (optional): Custom pricing for this client

4. Click **Save**

#### Step 4: Send Portal Invitation

1. From client record, click **"Send Portal Invitation"**
2. Customer receives email with:
   - Portal URL: `https://your-odoo.com/catalog/portal`
   - Login credentials
   - Instructions

Done! 🎉 Your customer can now access the catalog.

---

### For Customers (Accessing the Catalog)

#### Step 1: Login

1. Receive invitation email from supplier
2. Click link or go to supplier's Odoo URL
3. Login with provided credentials
4. Navigate to **Catalog Portal**

#### Step 2: Browse Products

1. Use search bar to find products
2. Filter by category
3. Sort by name, price, date, reference
4. Click on product for detailed view

#### Step 3: Select Products

1. Click **"Add to Selection"** on desired products
2. Products are added to your "cart"
3. View selection count in top-right badge

#### Step 4: Export to CSV

1. Click **"Selection"** button (cart icon)
2. Review selected products
3. Choose options:
   - ☑️ Include product images (optional)
4. Click **"Download CSV File"**

#### Step 5: Import into Your Odoo

1. In **your** Odoo: Go to **Purchase → Products**
2. Click **Favorites → Import records**
3. Upload the CSV file you just downloaded
4. Verify column mappings (auto-detected)
5. Click **Import**
6. Done! Products are now in your Odoo 🎉

---

## 📊 Features in Detail

### Access Control

**Three access modes:**

1. **Full Catalog**
   - Client sees all published products
   - Default mode, simplest setup

2. **Restricted by Category**
   - Client only sees products in specified categories
   - Useful for distributors with specializations

3. **Custom Product List**
   - Client only sees specific products
   - Maximum control, useful for negotiated catalogs

### Custom Pricing

- Assign a pricelist to each client
- Prices in exported CSV reflect client's pricelist
- Supports multi-currency if configured

### Analytics

Track everything:
- Who accessed the catalog (date, time, IP)
- What products were viewed
- What products were exported
- Export frequency

Access logs: **Catalog Portal → Analytics → Access Logs**

### Rate Limiting

Protect your server from abuse:
- Max products per export (default: 1000)
- Max exports per hour per client (default: 10)
- Configurable in Settings

---

## 🎨 Customization

### Branding

**Catalog Portal → Configuration → Settings → Branding tab**

- **Logo**: Upload your company logo
- **Primary Color**: Set theme color (hex code)
- **Welcome Message**: Customize portal home message

### Product Catalog Fields

Extend product information for catalog:
- **Catalog Description**: Richer description than sales description
- **Featured Product**: Highlight in catalog homepage
- **Public Catalog**: Show in public (unauthenticated) catalog (future feature)

---

## 🔒 Security

### Authentication

- Portal users have limited access (read-only)
- API keys available for advanced integrations
- Session-based selection (cart)

### Data Privacy

**What clients CAN see:**
- Product name, reference, barcode
- Sales price (based on their pricelist)
- Images and descriptions
- Categories, UoM, weight, volume

**What clients CANNOT see:**
- Your purchase prices / costs
- Your supplier information
- Your internal notes
- Other clients' pricelists
- Unpublished products

### Access Rules

- Clients only see published products
- Clients only see products they have access to (based on access mode)
- Portal users cannot modify anything
- All actions are logged

---

## 🛠️ Troubleshooting

### "No catalog access" message

**Problem**: Customer sees access denied page

**Solutions**:
1. Check client record is **Active** (toggle in client form)
2. Verify partner has portal user created
3. Resend portal invitation
4. Check portal access is enabled in Settings

### Products not appearing in catalog

**Problem**: Published products don't show up

**Solutions**:
1. Verify product has **"Published in Catalog"** checked
2. Check client's **Access Mode**:
   - If "Restricted": Product must be in allowed categories
   - If "Custom": Product must be in allowed product list
3. Refresh browser (Ctrl+F5)

### CSV import errors in customer Odoo

**Problem**: CSV file won't import properly

**Solutions**:
1. Ensure Odoo version compatibility (tested with v16+)
2. Check CSV encoding (should be UTF-8)
3. Verify column mappings in import wizard
4. Try importing without images first (uncheck option)

### Export limit reached

**Problem**: "Export limit reached" error

**Solutions**:
1. Wait one hour (rate limit resets)
2. Contact supplier to increase limits
3. Reduce number of selected products

---

## 🔮 Roadmap / Future Features

### Coming Soon

- [ ] **Excel Export**: Native .xlsx export
- [ ] **Direct Odoo Import**: Automatic XML-RPC import
- [ ] **Public Catalog Mode**: Browse without authentication
- [ ] **Multi-language Support**: Translate catalog
- [ ] **Product Variants**: Full variant support in export
- [ ] **Stock Levels**: Show available quantities (optional)
- [ ] **Product Comparison**: Compare multiple products
- [ ] **Favorites**: Save favorite products
- [ ] **Mobile App**: Native iOS/Android apps

### Planned Enhancements

- Webhooks for real-time sync
- Advanced analytics dashboard
- Email notifications on catalog updates
- PDF catalog generation
- Scheduled automatic exports

---

## 📞 Support

### Getting Help

1. **Documentation**: This README + in-app help pages
2. **Issue Tracker**: [GitHub Issues](your-repo-url/issues)
3. **Community**: [Odoo Community Forum](https://www.odoo.com/forum)
4. **Email**: support@yourcompany.com

### Reporting Bugs

When reporting bugs, please include:
- Odoo version
- Module version
- Steps to reproduce
- Error messages / screenshots
- Browser console errors (F12)

---

## 📄 License

This module is licensed under **LGPL-3**.

See [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

Please follow Odoo coding guidelines.

---

## 👥 Credits

**Author**: Your Company

**Contributors**:
- Your Name (you@example.com)

**Special Thanks**:
- Odoo Community Association (OCA)
- All beta testers and early adopters

---

## 📈 Version History

### v1.0.0 (2024-01-XX) - Initial Release

**Features**:
- Secure portal access
- Product browsing with search and filters
- CSV export
- Custom pricelists per client
- Access control (3 modes)
- Analytics and logging
- Responsive design

---

## 🎓 Additional Resources

### Video Tutorials

- [Setup Guide for Suppliers](link)
- [Using the Catalog (Customer POV)](link)
- [Advanced Configuration](link)

### Documentation

- [User Manual (PDF)](link)
- [API Documentation](link)
- [Best Practices Guide](link)

---

**Made with ❤️ for the Odoo Community**

*Questions? Contact us at support@yourcompany.com*
