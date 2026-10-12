"""CRM module gate: every route 404s unless `tenants.features->>'contacts'`.

The gate itself comes from the module manifest (`app/modules.py`); this
alias keeps the import path every CRM router already uses.
"""

from app.modules import make_feature_gate

require_contacts = make_feature_gate("contacts")
# Deletes and the bulk CSV import, which overwrites names in place.
require_contacts_admin = make_feature_gate("contacts", minimum="admin")
