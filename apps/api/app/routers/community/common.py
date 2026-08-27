"""Community module gate: every route 404s unless `tenants.features->>'community'`.

The gate itself comes from the module manifest (`app/modules.py`); this
alias keeps the import path consistent with the other modules.
"""

from app.modules import make_feature_gate

require_community = make_feature_gate("community")
