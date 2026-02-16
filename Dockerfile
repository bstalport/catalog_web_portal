FROM odoo:19.0

USER root

# Install additional Python packages needed by the module
RUN pip3 install --no-cache-dir openpyxl

# Copy module into the Odoo addons directory
COPY --chown=odoo:odoo . /mnt/extra-addons/catalog_web_portal

USER odoo
