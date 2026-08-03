"""Column allowlist for the endpoints that interpolate SET clauses into SQL.

Values are always bind parameters; the interpolated identifiers come from
Pydantic patch models, so they are safe today. The explicit allowlist keeps
that safety from silently eroding as models grow (aliases, extra fields,
call-site additions) — an unknown key is a hard error, never SQL.
"""

LIKE_SPECIALS = str.maketrans({"%": r"\%", "_": r"\_", "\\": "\\\\"})


def like_contains(value: str) -> str:
    """`%value%` for ILIKE, with the caller's own wildcards neutralised.

    Unescaped, a `_` in a search box silently matches any character and a `%`
    matches every row in the table — the filter returns the wrong records
    rather than none, so it reads as a data bug, not a search miss.
    """
    return f"%{value.strip().translate(LIKE_SPECIALS)}%"


PATCHABLE_COLUMNS: dict[str, frozenset[str]] = {
    # Operator-console edits only; tenant-facing PATCH /tenants/me still
    # writes name/brand directly and never reaches this allowlist.
    "tenants": frozenset({"name", "seats", "plan", "trial_ends_at", "soft_budget_usd", "brand"}),
    "projects": frozenset({"name", "description", "archived"}),
    "documents": frozenset({"project_id", "is_primary"}),
    "proj_projects": frozenset(
        {
            "client_org",
            "delivery_route",
            "homes_planned",
            "start_date",
            "target_completion",
            "site_address",
            "applicability",
            "contract_facts",
        }
    ),
    "proj_stages": frozenset(
        {
            "status",
            "planned_start",
            "planned_end",
            "forecast_start",
            "forecast_end",
            "actual_start",
            "actual_end",
            "gate_exceptions",
        }
    ),
    "proj_tasks": frozenset(
        {
            "title",
            "details",
            "owner_name",
            "due_date",
            "is_milestone",
            "tags",
            "status",
            "stage_key",
            "completed_at",
        }
    ),
    "proj_documents": frozenset({"status", "notes", "vault_document_id"}),
    "proj_funding_sources": frozenset(
        {
            "programme_key",
            "name",
            "funder",
            "kind",
            "amount_sought",
            "amount_secured",
            "status",
            "conditions",
            "drawdown_schedule",
            "notes",
        }
    ),
    "proj_risks": frozenset(
        {
            "category",
            "description",
            "likelihood",
            "impact",
            "owner_name",
            "mitigation",
            "status",
            "review_date",
        }
    ),
    "proj_conditions": frozenset(
        {
            "application_ref",
            "number",
            "description",
            "pre_commencement",
            "status",
            "submitted_at",
            "discharged_at",
            "notes",
        }
    ),
    "proj_stakeholders": frozenset(
        {"name", "org", "role", "email", "phone", "notes", "last_contact"}
    ),
    "grant_funders": frozenset(
        {
            "name",
            "ref_key",
            "kind",
            "website",
            "contact_name",
            "contact_email",
            "relationship",
            "notes",
        }
    ),
    "grant_applications": frozenset(
        {
            "title",
            "funder_id",
            "project_id",
            "reference",
            "programme_key",
            "amount_requested",
            "amount_awarded",
            "restricted",
            "deadline",
            "start_date",
            "end_date",
            "reporting_note",
            "notes",
        }
    ),
    # `status` is deliberately absent: the pipeline moves through
    # POST /grants/applications/{id}/status, which also seeds award conditions
    # and audits the transition. A bare PATCH would skip both.
    "grant_stages": frozenset(
        {
            "status",
            "planned_start",
            "planned_end",
            "forecast_start",
            "forecast_end",
            "actual_start",
            "actual_end",
            "gate_exceptions",
        }
    ),
    "grant_tasks": frozenset(
        {
            "title",
            "stage_key",
            "details",
            "owner_name",
            "due_date",
            "is_milestone",
            "tags",
            "status",
            "completed_at",
        }
    ),
    "grant_documents": frozenset({"status", "notes", "vault_document_id"}),
    "grant_conditions": frozenset(
        {
            "number",
            "description",
            "pre_drawdown",
            "status",
            "due_date",
            "submitted_at",
            "discharged_at",
            "notes",
        }
    ),
    "grant_reporting_periods": frozenset(
        {
            "label",
            "period_start",
            "period_end",
            "due_date",
            "status",
            "submitted_at",
            "accepted_at",
            "notes",
        }
    ),
    "grant_impact_measures": frozenset(
        {"name", "definition", "unit", "baseline", "target", "notes"}
    ),
    "crm_companies": frozenset(
        {
            "name",
            "website",
            "email",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "postcode",
            "notes",
        }
    ),
    "crm_contacts": frozenset(
        {
            "name",
            "company_id",
            "job_title",
            "email",
            "phone",
            "mobile",
            "address",
            "notes",
            "tags",
        }
    ),
}


def patch_sets(table: str, updates: dict, id_param: int = 1) -> tuple[str, list]:
    """Build "col = $n, ..." with parameters numbered after the id param(s)."""
    unknown = set(updates) - PATCHABLE_COLUMNS[table]
    if unknown:
        raise ValueError(f"{table}: refusing to interpolate column(s) {sorted(unknown)}")
    sets = ", ".join(f"{k} = ${i + id_param + 1}" for i, k in enumerate(updates))
    return sets, list(updates.values())
