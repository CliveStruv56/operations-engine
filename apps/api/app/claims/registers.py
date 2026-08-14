"""Reading the UK public registers, and turning what they say into claims.

Deliberately plain HTTP clients, not LiteLLM routes: these are registers, not
model providers, so the gateway constraint does not apply — the same reasoning
`app/search.py` records for Exa, and this follows that file's shape throughout
(one timeout, no retry, missing key is a 503, an upstream failure is a 502,
client injectable so tests never touch the network).

Three registers, one shape. `RegisterFacts` is what every client returns and
the only thing `service.py` knows about, so a fourth register is a new module
and nothing else.

What each one gives, honestly:

- **Companies House** — identity, officers, filing dates. Free key, HTTP Basic
  with the key as username and an empty password, 600 requests per five
  minutes per application. No income, no headcount, no insurance.
- **Charity Commission (England and Wales)** — identity plus objects, income,
  expenditure and trustees. Free subscription key in a header. Rate limits are
  reserved in the terms but unpublished, so we are conservative.
- **OSCR (Scotland)** — the same ground as the Charity Commission, plus staff
  numbers from the annual return, which no other UK register publishes.
  Trustee names have been on the Scottish Charity Register since 9 March 2026
  under the Charities (Regulation and Administration) (Scotland) Act 2023;
  trustees may hold an exemption where publication would put them at risk, so
  an absent list is normal and must never read as a failure.

All three publish under the Open Government Licence, which requires
attribution. That is discharged by `source_url` riding on every claim and
surfacing in the Data sources appendix of anything drafted from one.

Personal data is deliberately narrowed at this boundary. Companies House also
returns partial dates of birth, nationality and occupation for every officer;
none of it is read here, because the cheapest place to not hold something is
before it arrives.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from app.config import get_settings
from app.errors import ApiError

COMPANIES_HOUSE_BASE = "https://api.company-information.service.gov.uk"
CHARITY_COMMISSION_BASE = "https://api.charitycommission.gov.uk/register/api"
OSCR_BASE = "https://oscrapi.azurewebsites.net/api"

#: Public pages a person can open to check what we imported. These are the
#: attribution and the audit trail; the API hosts above are neither.
COMPANIES_HOUSE_PUBLIC = "https://find-and-update.company-information.service.gov.uk/company/{n}"
CHARITY_COMMISSION_PUBLIC = (
    "https://register-of-charities.charitycommission.gov.uk/en/charity-search/-/charity-details/{n}"
)
OSCR_PUBLIC = (
    "https://www.oscr.org.uk/about-charities/search-the-register/charity-details?number={n}"
)

#: Shorter than Exa's 15s: a register lookup happens with somebody watching a
#: spinner on a settings screen, and a slow answer is worse than "try again".
TIMEOUT_S = 10.0

#: England and Wales charities must file within ten months of their financial
#: year end; Scotland allows nine. Used to date the next review of a finance
#: claim from the filing calendar rather than from an arbitrary cycle, which
#: is what makes "due for review" mean the register has probably changed.
EW_FILING_MONTHS = 10
SCOTTISH_FILING_MONTHS = 9

#: Register values meaning the organisation is live. Anything else is gated.
ACTIVE_COMPANY_STATUS = "active"
ACTIVE_CHARITY_STATUSES = frozenset({"registered", "active", "r"})

#: Live Azure APIM `reg_status` is a code; older docs and our fixtures used prose.
_CC_REG_STATUS = {"R": "Registered", "RM": "Removed"}


@dataclass(frozen=True)
class RegisterFact:
    """One fact a register asserted, before it becomes a claim.

    `kind` is a `ref_claim_kinds` key. `subject` names which instance of a
    multi-valued kind this is (a trustee's name); `period` names which slice of
    a series. `review_on` lets a client date a fact from the filing calendar,
    overriding the kind's own cycle.
    """

    kind: str
    value: Any
    subject: str | None = None
    period: str | None = None
    as_of: date | None = None
    review_on: date | None = None


@dataclass(frozen=True)
class RegisterFacts:
    register: str
    source_url: str
    registration_status: str
    active: bool
    facts: list[RegisterFact] = field(default_factory=list)


def _months_after(start: date | None, months: int) -> date | None:
    """Add whole months without pulling in a date library for one call site."""
    if start is None:
        return None
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp rather than overflow: a 31 January year end plus ten months is
    # 30 November, not 1 December.
    day = min(start.day, [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    if month == 2 and day == 29 and (year % 4 or (not year % 100 and year % 400)):
        day = 28
    return date(year, month, day)


def _parse_date(raw: Any) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _clean(raw: Any) -> str | None:
    """A register field as a usable string, or nothing at all.

    Registers return empty strings, whitespace and the literal "N/A" for
    absent values. Each of those becomes a claim reading "The organisation's
    registered office is N/A" if it is not stopped here.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"n/a", "na", "none", "not available", "null"}:
        return None
    return text


async def _request(
    url: str,
    headers: dict[str, str],
    register_label: str,
    *,
    params: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """One GET, with the whole error posture in one place.

    A 404 is a genuine answer — that number is not on this register — and says
    so rather than becoming a generic upstream failure, because the two lead a
    user to completely different next actions.
    """
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as own:
                resp = await own.get(url, headers=headers, params=params, auth=auth)
        else:  # injected in tests (httpx.MockTransport)
            resp = await client.get(url, headers=headers, params=params, auth=auth)
        if resp.status_code == 404:
            raise ApiError(
                404, "register_not_found", f"That number is not on the {register_label} register"
            )
        if resp.status_code == 429:
            raise ApiError(
                429,
                "register_rate_limited",
                f"The {register_label} register is rate limiting us — try again shortly",
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise ApiError(
            502, "register_failed", f"Could not reach the {register_label} register — try again"
        ) from exc
    except ValueError as exc:
        # A 200 whose body is not JSON — what a withdrawn Azure APIM operation
        # returns. An ApiError keeps `_optional_request` optional and turns a
        # primary-call failure into a clean 502 instead of a 500.
        raise ApiError(
            502,
            "register_failed",
            f"The {register_label} register returned an unreadable response — try again",
        ) from exc


async def _optional_request(
    url: str,
    headers: dict[str, str],
    register_label: str,
    *,
    params: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """A secondary register call that must not fail an import already in hand.

    OSCR annual returns established the posture: a charity that exists but has
    not filed, or an operation the portal has since dropped, still imports.
    """
    try:
        return await _request(url, headers, register_label, params=params, auth=auth, client=client)
    except ApiError:
        return None


def _require_key(key: str, register_label: str) -> str:
    if not key:
        raise ApiError(
            503,
            "register_unavailable",
            f"Lookups against the {register_label} register are not configured",
        )
    return key


# --- Companies House ---------------------------------------------------------

#: Companies House returns a type code, not prose. Anything unmapped falls
#: through as the raw code rather than being guessed at — a claim saying
#: "constituted as private-limited-guarant-nsc" is ugly but true, and a
#: mistranslation on a funder's form is not.
_COMPANY_TYPES = {
    "ltd": "a private company limited by shares",
    "plc": "a public limited company",
    "private-limited-guarant-nsc": "a private company limited by guarantee without share capital",
    "private-limited-guarant-nsc-limited-exemption": (
        "a private company limited by guarantee, exempt from using 'limited'"
    ),
    "community-interest-company": "a community interest company",
    "royal-charter": "a royal charter body",
    "registered-society-non-jurisdictional": "a registered society",
    "industrial-and-provident-society": "an industrial and provident society",
    "charitable-incorporated-organisation": "a charitable incorporated organisation",
    "scottish-charitable-incorporated-organisation": (
        "a Scottish charitable incorporated organisation"
    ),
    "llp": "a limited liability partnership",
}


def _address_line(address: dict[str, Any] | None) -> str | None:
    if not isinstance(address, dict):
        return None
    parts = [
        _clean(address.get(k))
        for k in (
            "care_of",
            "premises",
            "address_line_1",
            "address_line_one",
            "address_line_2",
            "address_line_two",
            "address_line_three",
            "address_line_four",
            "address_line_five",
            "locality",
            "region",
            "postal_code",
            "address_post_code",
            "country",
        )
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _idv_value(raw: Any) -> str:
    """The ECCTA `identity_verification_details` field, read defensively.

    Observed in two shapes (CH developer forum, Aug 2026): a record carrying
    the verified date and the ACSP that carried out the check, or a bare
    completion statement — and the field is absent entirely on an unverified
    officer. Every value returned here begins `verified` or `not yet
    verified`; the readiness panel keys off that prefix, so the prefix is
    contract, not copy.
    """
    if isinstance(raw, dict):
        verified_on = _parse_date(
            _pick(raw, "identity_verified_on", "verified_on", "date_verified")
        )
        agent = _clean(_pick(raw, "acsp_name", "verified_by", "authorised_agent"))
        if verified_on and agent:
            return f"verified on {verified_on} via {agent}"
        if verified_on:
            return f"verified on {verified_on}"
        raw = _pick(raw, "statement", "status", "description")
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        lowered = text.lower()
        # A completion statement is evidence of verification — keep the
        # register's own wording — but any negation means it is not.
        if ("verif" in lowered or "complete" in lowered) and " not" not in f" {lowered}":
            return text if lowered.startswith("verified") else f"verified — {text}"
    return "not yet verified"


async def fetch_companies_house(
    number: str, *, client: httpx.AsyncClient | None = None
) -> RegisterFacts:
    key = _require_key(get_settings().companies_house_api_key, "Companies House")
    # HTTP Basic with the key as username and an empty password (RFC2617),
    # which is how the Developer Hub documents API-key applications.
    auth = (key, "")
    profile = await _request(
        f"{COMPANIES_HOUSE_BASE}/company/{number}", {}, "Companies House", auth=auth, client=client
    )

    status = _clean(profile.get("company_status")) or "unknown"
    accounts = profile.get("accounts") or {}
    confirmation = profile.get("confirmation_statement") or {}
    # Identity facts age with the confirmation statement, finance facts with
    # the accounts — both are the date the register itself expects to change.
    identity_review = _parse_date(confirmation.get("next_due"))
    finance_review = _parse_date(accounts.get("next_due"))

    facts: list[RegisterFact] = []

    def add(kind: str, value: Any, **kw: Any) -> None:
        if value is not None:
            facts.append(RegisterFact(kind=kind, value=value, **kw))

    add("registered_name", _clean(profile.get("company_name")), review_on=identity_review)
    add("company_number", _clean(profile.get("company_number")), review_on=identity_review)
    raw_type = _clean(profile.get("type"))
    add(
        "legal_form",
        _COMPANY_TYPES.get(raw_type or "", raw_type),
        review_on=identity_review,
    )
    add("registration_status", status, review_on=identity_review)
    add(
        "date_registered",
        _parse_date(profile.get("date_of_creation")),
        review_on=identity_review,
    )
    add(
        "registered_office",
        _address_line(profile.get("registered_office_address")),
        review_on=identity_review,
    )
    last_accounts = accounts.get("last_accounts") or {}
    year_end = _parse_date(accounts.get("next_made_up_to") or last_accounts.get("made_up_to"))
    add("accounts_year_end", year_end, review_on=finance_review)
    # The filing deadlines themselves, as facts. Each one's review date is the
    # deadline, so a passed filing date goes stale through the ordinary
    # machinery — and the confirmation-statement date is also every existing
    # director's ECCTA identity-verification deadline.
    add("confirmation_statement_due", identity_review, review_on=identity_review)
    add("accounts_due", finance_review, review_on=finance_review)

    officers = await _request(
        f"{COMPANIES_HOUSE_BASE}/company/{number}/officers",
        {},
        "Companies House",
        params={"items_per_page": "100"},
        auth=auth,
        client=client,
    )
    for officer in officers.get("items", []):
        # Resigned officers are still returned and are still public. They are
        # not the current board, which is what every form asks for.
        if officer.get("resigned_on"):
            continue
        role = (_clean(officer.get("officer_role")) or "").lower()
        if "director" not in role:
            continue  # secretaries and LLP members are not the governing body
        name = _clean(officer.get("name"))
        if name is None:
            continue
        # Name, role and appointment date only. The payload also carries a
        # partial date of birth, nationality and occupation; none is read.
        facts.append(
            RegisterFact(
                kind="director",
                subject=name,
                value={"role": role, "appointed_on": str(_parse_date(officer.get("appointed_on")))}
                if officer.get("appointed_on")
                else {"role": role},
                as_of=_parse_date(officer.get("appointed_on")),
                review_on=identity_review,
            )
        )
        facts.append(
            RegisterFact(
                kind="director_idv",
                subject=name,
                value=_idv_value(officer.get("identity_verification_details")),
                review_on=identity_review,
            )
        )

    return RegisterFacts(
        register="companies_house",
        source_url=COMPANIES_HOUSE_PUBLIC.format(n=number),
        registration_status=status,
        active=status.lower() == ACTIVE_COMPANY_STATUS,
        facts=facts,
    )


# --- Charity Commission for England and Wales --------------------------------


def _pick(row: dict[str, Any], *keys: str) -> Any:
    """First present, non-empty field. Live Azure APIM names and older docs differ."""
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is None or value == "" or value == []:
            continue
        return value
    return None


def _cc_status(raw: Any) -> str:
    text = _clean(raw)
    if text is None:
        return "unknown"
    return _CC_REG_STATUS.get(text.upper(), text)


async def fetch_charity_commission(
    number: str, *, client: httpx.AsyncClient | None = None
) -> RegisterFacts:
    key = _require_key(get_settings().charity_commission_api_key, "Charity Commission")
    headers = {"Ocp-Apim-Subscription-Key": key, "Accept": "application/json"}
    # Suffix 0 is the charity itself; non-zero suffixes are linked subsidiary
    # charities registered under the same number.
    detail = await _request(
        f"{CHARITY_COMMISSION_BASE}/allcharitydetailsV2/{number}/0",
        headers,
        "Charity Commission",
        client=client,
    )

    status = _cc_status(_pick(detail, "charity_registration_status", "reg_status"))
    year_end = _parse_date(
        _pick(detail, "latest_acc_fin_period_end_date", "latest_acc_fin_year_end_date")
    )
    finance_review = _months_after(year_end, EW_FILING_MONTHS)
    identity_review = finance_review

    facts: list[RegisterFact] = []

    def add(kind: str, value: Any, **kw: Any) -> None:
        if value is not None:
            facts.append(RegisterFact(kind=kind, value=value, **kw))

    add("registered_name", _clean(detail.get("charity_name")), review_on=identity_review)
    add(
        "charity_number",
        _clean(_pick(detail, "reg_charity_number", "registered_charity_number") or number),
        review_on=identity_review,
    )
    add(
        "company_number",
        _clean(_pick(detail, "charity_company_registration_number", "charity_co_reg_number")),
        review_on=identity_review,
    )
    add("legal_form", _clean(detail.get("charity_type")), review_on=identity_review)
    add("registration_status", status, review_on=identity_review)
    add(
        "date_registered",
        _parse_date(detail.get("date_of_registration")),
        review_on=identity_review,
    )
    add(
        "registered_office",
        _address_line(detail.get("charity_contact_address"))
        or _clean(detail.get("charity_contact_address"))
        or _address_line(detail),
        review_on=identity_review,
    )
    objects = _clean(detail.get("charity_objects"))
    activities = _clean(detail.get("charity_activities"))
    if objects is None:
        governing = await _optional_request(
            f"{CHARITY_COMMISSION_BASE}/charitygoverningdocument/{number}/0",
            headers,
            "Charity Commission",
            client=client,
        )
        if isinstance(governing, dict):
            objects = _clean(governing.get("charitable_objects"))
    if activities is None:
        overview = await _optional_request(
            f"{CHARITY_COMMISSION_BASE}/charityoverview/{number}/0",
            headers,
            "Charity Commission",
            client=client,
        )
        if isinstance(overview, dict):
            activities = _clean(overview.get("activities"))
    add("charitable_objects", objects, review_on=identity_review)
    add("activities", activities, review_on=identity_review)
    add("accounts_year_end", year_end, review_on=finance_review)
    for key_name, kind in (
        ("latest_income", "annual_income"),
        ("latest_expenditure", "annual_expenditure"),
    ):
        raw = detail.get(key_name)
        if isinstance(raw, (int, float)):
            add(kind, float(raw), as_of=year_end, review_on=finance_review)

    for source_key, kind in (
        ("area_of_operation", "area_of_operation"),
        ("CharityAoORegion", "area_of_operation"),
        ("CharityAoOLocalAuthority", "area_of_operation"),
        ("CharityAoOCountryContinent", "area_of_operation"),
        ("who_what_where", "beneficiary_groups"),
    ):
        if any(f.kind == kind for f in facts):
            continue
        values = _string_list(detail.get(source_key))
        if values:
            add(kind, values, review_on=identity_review)

    # Live V2 embeds trustee_names. The older charitytrustees operation 404s
    # on the current product; a missing list is normal (exemption), not a
    # "number not on the register".
    if "trustee_names" in detail:
        trustees = detail.get("trustee_names")
    else:
        trustees = await _optional_request(
            f"{CHARITY_COMMISSION_BASE}/charitytrustees/{number}/0",
            headers,
            "Charity Commission",
            client=client,
        )
    for trustee in _as_list(trustees):
        name = _clean(trustee.get("trustee_name") if isinstance(trustee, dict) else trustee)
        if name is None:
            continue
        facts.append(
            RegisterFact(kind="trustee", subject=name, value={}, review_on=identity_review)
        )

    return RegisterFacts(
        register="charity_commission",
        source_url=CHARITY_COMMISSION_PUBLIC.format(n=number),
        registration_status=status,
        active=status.lower() in ACTIVE_CHARITY_STATUSES,
        facts=facts,
    )


# --- OSCR (Scotland) ---------------------------------------------------------


async def fetch_oscr(number: str, *, client: httpx.AsyncClient | None = None) -> RegisterFacts:
    """The Scottish Charity Register.

    Two calls: the register entry, and the annual returns which carry the
    finance series and staff numbers. The returns call is best-effort — it is
    the richer half, but a charity too new to have filed one still has a
    perfectly good register entry, and losing the whole import over that would
    be absurd.
    """
    key = _require_key(get_settings().oscr_api_key, "OSCR")
    headers = {"x-functions-key": key, "Accept": "application/json"}
    payload = await _request(
        f"{OSCR_BASE}/all_charities",
        headers,
        "OSCR",
        params={"charitynumber": number},
        client=client,
    )
    entries = _as_list(payload)
    if not entries:
        raise ApiError(
            404, "register_not_found", "That number is not on the Scottish Charity Register"
        )
    detail = entries[0]

    status = _clean(_pick(detail, "charity_status", "charityStatus")) or "unknown"
    year_end = _parse_date(_pick(detail, "year_end", "yearEnd"))
    finance_review = _months_after(year_end, SCOTTISH_FILING_MONTHS)
    identity_review = finance_review

    facts: list[RegisterFact] = []

    def add(kind: str, value: Any, **kw: Any) -> None:
        if value is not None:
            facts.append(RegisterFact(kind=kind, value=value, **kw))

    add(
        "registered_name",
        _clean(_pick(detail, "charity_name", "charityName")),
        review_on=identity_review,
    )
    add(
        "charity_number",
        _clean(_pick(detail, "charity_number", "charityNumber")) or number,
        review_on=identity_review,
    )
    add(
        "legal_form",
        _clean(
            _pick(detail, "constitutional_form", "constitutionalForm", "currentConstitutionalForm")
        ),
        review_on=identity_review,
    )
    add("registration_status", status, review_on=identity_review)
    add(
        "date_registered",
        _parse_date(_pick(detail, "registered_date", "registeredDate")),
        review_on=identity_review,
    )
    office = _pick(detail, "principal_office", "principalOffice")
    contact = _clean(_pick(detail, "principalContactAddress"))
    if contact and contact.lower() == "address withheld":
        contact = None
    add(
        "registered_office",
        _address_line(office) or _clean(office) or contact,
        review_on=identity_review,
    )
    add(
        "charitable_objects",
        _clean(detail.get("objectives")),
        review_on=identity_review,
    )
    add(
        "activities",
        _clean(detail.get("activities"))
        or (", ".join(_string_list(detail.get("typesOfActivities"))) or None),
        review_on=identity_review,
    )
    add("accounts_year_end", year_end, review_on=finance_review)
    values = _string_list(detail.get("beneficiaries"))
    if values:
        add("beneficiary_groups", values, review_on=identity_review)
    geographic = _string_list(
        _pick(
            detail,
            "geographical_spread",
            "geographicalSpread",
            "main_operating_location",
            "mainOperatingLocation",
        )
    )
    if geographic:
        add("area_of_operation", geographic, review_on=identity_review)

    # Trustee names have been on the public web register since 9 March 2026.
    # The API still has no trustees operation (confirmed 14 Aug 2026 against
    # Sanday Development Trust SC035495). Absent is normal; it is never an error.
    for trustee in _as_list(detail.get("trustees") or detail.get("charity_trustees")):
        name = _clean(trustee.get("trustee_name") if isinstance(trustee, dict) else trustee)
        if name is None:
            continue
        facts.append(
            RegisterFact(kind="trustee", subject=name, value={}, review_on=identity_review)
        )

    charity_id = _pick(detail, "id", "charity_id", "charityId") or number
    try:
        returns = await _request(
            f"{OSCR_BASE}/annualreturns",
            headers,
            "OSCR",
            params={"charityid": str(charity_id)},
            client=client,
        )
    except ApiError:
        returns = []  # best effort: a charity that has not filed still imports

    filed = [e for e in _as_list(returns) if isinstance(e, dict)]
    filed.sort(
        key=lambda e: (
            _parse_date(_pick(e, "year_end", "yearEnd", "AccountingReferenceDate")) or date.min
        ),
        reverse=True,
    )
    for entry in filed[:5]:
        period_end = _parse_date(_pick(entry, "year_end", "yearEnd", "AccountingReferenceDate"))
        if period_end is None:
            continue
        # A filed year is a slice of a series; the most recent one also stands
        # as the current figure, which `service.py` resolves by writing the
        # period-less row from the latest entry.
        period = f"{period_end.year - 1}/{str(period_end.year)[-2:]}"
        review = _months_after(period_end, SCOTTISH_FILING_MONTHS)
        for source_key, kind in (
            ("income", "annual_income"),
            ("GrossIncome", "annual_income"),
            ("expenditure", "annual_expenditure"),
            ("GrossExpenditure", "annual_expenditure"),
        ):
            if any(f.kind == kind and f.period == period for f in facts):
                continue
            raw = entry.get(source_key)
            if isinstance(raw, (int, float)):
                facts.append(
                    RegisterFact(
                        kind=kind,
                        value=float(raw),
                        period=period,
                        as_of=period_end,
                        review_on=review,
                    )
                )
        staff = _pick(entry, "staff", "employees", "number_of_employees", "PaidStaff")
        if isinstance(staff, (int, float)) and not any(
            f.kind == "employees_headcount" and f.as_of == period_end for f in facts
        ):
            facts.append(
                RegisterFact(
                    kind="employees_headcount",
                    value=int(staff),
                    as_of=period_end,
                    review_on=review,
                )
            )
    # Each figure falls back on its own absence: an annual return that carries
    # income but no expenditure line must not discard the detail record's
    # expenditure figure.
    if not any(f.kind == "annual_income" for f in facts):
        latest = _pick(detail, "mostRecentYearIncome")
        if isinstance(latest, (int, float)):
            add("annual_income", float(latest), as_of=year_end, review_on=finance_review)
    if not any(f.kind == "annual_expenditure" for f in facts):
        spent = _pick(detail, "mostRecentYearExpenditure")
        if isinstance(spent, (int, float)):
            add("annual_expenditure", float(spent), as_of=year_end, review_on=finance_review)

    return RegisterFacts(
        register="oscr",
        source_url=OSCR_PUBLIC.format(n=number),
        registration_status=status,
        active=status.lower() in ACTIVE_CHARITY_STATUSES,
        facts=facts,
    )


def _as_list(raw: Any) -> list[Any]:
    """Registers disagree about whether one result is a list or an object."""
    if isinstance(raw, str):
        # OSCR annualreturns returns a JSON array encoded as a JSON string.
        text = raw.strip()
        if text[:1] in "[{":
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                return []
        else:
            return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("items", "results", "data", "charities"):
            nested = raw.get(key)
            if isinstance(nested, list):
                return nested
        return [raw]
    return []


def _string_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                text = _clean(
                    item.get("classification_description")
                    or item.get("classification_desc")
                    or item.get("description")
                    or item.get("name")
                    or item.get("country")
                    or item.get("region")
                    or item.get("value")
                )
            else:
                text = _clean(item)
            if text:
                out.append(text)
        return out
    return []
