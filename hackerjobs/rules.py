import re
from functools import lru_cache
from itertools import pairwise
from typing import Any

from hackerjobs.models import (
    CompanyStage,
    EmploymentType,
    Industry,
    Kind,
    Pay,
    Remote,
    RoleCategory,
    Seniority,
)
from hackerjobs.technologies import canonical_technologies, find_technologies, is_known_technology

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
URL = re.compile(r"https?://[^\s<>\"')\]]+")
# Disguised emails: "name [at] host [dot] com", "name(at)host.com", "name<at/>host<dot/>com",
# "name at host dot com", "name @ host.com". A bare " at " only counts before a common TLD, so
# "email me at jo at acme.com" decodes to jo@acme.com.
_AT = r"(?:\s*(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\}|<at/?>|@)\s*)"
_PLAIN_AT = r"(?:\s+at\s+)"
_DOT = r"(?:\s*(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\}|<dot/?>)\s*|\s+dot\s+|\.)"
_TLD = (
    r"(?:com|org|net|io|ai|co|dev|app|xyz|us|uk|de|fr|in|me|health|tech|eu|pl|ca|nl|se|ch|is|so|sh)"
)
_PART = r"[\w+-]+"
_DISGUISED_EMAIL = re.compile(
    rf"{_PART}(?:{_DOT}{_PART})*(?:{_AT}{_PART}(?:{_DOT}{_PART})+|{_PLAIN_AT}{_PART}(?:{_DOT}{_PART})*{_DOT}{_TLD}\b)",
    re.IGNORECASE,
)
_AT_TOKEN = re.compile(rf"{_AT}|{_PLAIN_AT}", re.IGNORECASE)
_DOT_TOKEN = re.compile(_DOT, re.IGNORECASE)

_TEMPLATE_LINE = re.compile(r"^\s*[-*]?\s*([A-Za-zé/ ]{3,40}?)\s*:\s*(.*)$")
_TEMPLATE_FIELDS = {
    "location": "location",
    "remote": "remote",
    "willing to relocate": "relocate",
    "relocate": "relocate",
    "technologies": "technologies",
    "technologies/skills": "technologies",
    "tech stack": "technologies",
    "skills": "technologies",
    "résumé/cv": "resume",
    "resume/cv": "resume",
    "résumé": "resume",
    "resume": "resume",
    "cv": "resume",
    "email": "email",
    "linkedin": "linkedin",
    "github": "github",
    "website": "website",
    "portfolio": "website",
}
_TIMEZONE = re.compile(
    r"\((?:[^)]*\b(?:UTC|GMT|CET|IST|ET|PT|EST|PST)\b[^)]*)\)|\b(?:UTC|GMT)\s*[+-]\s*\d+(?::\d+)?",
    re.I,
)
_TIMEZONE_NAME = re.compile(
    r"\b(?:UTC|GMT)(?:\s*[+-]\s*\d+(?::\d+)?)?|\b(?:CET|CEST|IST|EST|PST|ET|PT|CT|MT|AEST|JST)\b"
)
_TECH_SEPARATORS = re.compile(r"[,;|()\n]|\s/\s|/|\band\b|\s-\s")
_TECH_FILLER = re.compile(
    r"\b(?:and related technologies|also comfortable with|intermediate|beginner)\b", re.I
)
_EXPERIENCE = re.compile(
    r"(\d{1,2})\+?\s*(?:years|yrs)\b(?:\s+of)?(?:\s+\w+){0,3}?\s+experience", re.I
)

MAX_NAME_WORDS = 5
_HEADER_SEPARATOR = re.compile(r"\s+[|\u2014\u2013]\s+|\s*\|\s*")
_ROLE_WORDS = re.compile(
    r"\b(engineer|developer|manager|designer|scientist|lead|architect|intern)s?\b", re.I
)
_REMOTE = re.compile(r"\bremote\b", re.I)
_PARTIAL_REMOTE = re.compile(r"\bpart(?:ial(?:ly)?)?[\s-]+remote\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_DAYS_IN_OFFICE = re.compile(r"\d\s*days?\s*(?:/|a|per)\s*week", re.I)
_ONSITE = re.compile(r"\bon[\s-]?site\b|\bin[\s-]office\b|\bin[\s-]person\b", re.I)
_EMPLOYMENT: dict[EmploymentType, re.Pattern[str]] = {
    "full-time": re.compile(r"\bfull[\s-]?time\b", re.I),
    "part-time": re.compile(r"\bpart[\s-]?time\b", re.I),
    "contract": re.compile(r"\bcontract(?:or)?\b|\bfreelance\b", re.I),
    "internship": re.compile(r"\bintern(?:ship)?s?\b", re.I),
}
_PAY = re.compile(
    r"(?P<cur>[$€£]|\b(?:USD|EUR|GBP|CAD|CHF|AUD)\b)?\s?(?P<low>\d+(?:[.,]\d+)?)\s?(?P<lowk>[kK])?"
    r"\s?(?:-|\u2013|\u2014|to)\s?(?P<cur2>[$€£])?\s?(?P<high>\d+(?:[.,]\d+)?)\s?(?P<highk>[kK])?"
    r"(?:\s?(?P<code>\b(?:USD|EUR|GBP|CAD|CHF|AUD)\b))?"
)
_PAY_LINE = re.compile(r"salary|compensation|\bcomp\b|\bpay\b|\brate\b|base", re.I)
_HOURLY = re.compile(r"/\s?(?:hr|hour)\b|per hour|hourly|an hour", re.I)
_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
_NO_VISA = re.compile(
    r"no (?:new )?visa|not (?:able to |currently )?(?:offer(?:ing)? )?sponsor"
    r"|(?:cannot|can't|unable to|do not|don't) (?:currently )?sponsor"
    r"|without (?:visa )?sponsorship|no (?:new )?(?:visa )?sponsorship",
    re.I,
)
_VISA = re.compile(
    r"(?:will|can|we) sponsor|visa sponsorship (?:is )?(?:available|offered|provided)"
    r"|visa support|sponsor (?:any |work )?visas?",
    re.I,
)
_MIN_EXPERIENCE = re.compile(
    r"(?:minimum of|at least|min\.?)\s*(\d{1,2})\+?\s*years"
    r"|(\d{1,2})\+\s*years?(?:\s+of)?"
    r"(?:\s+(?:professional|programming|relevant|industry|software|engineering))?\s+experience",
    re.I,
)
_RELOCATION = re.compile(
    r"relocation (?:support|assistance|package|help|bonus|& visa|and visa)"
    r"|help (?:with |you )?relocat",
    re.I,
)
_NO_RELOCATION = re.compile(r"\bno relocation\b|relocation (?:is )?not (?:offered|available)", re.I)
_EQUITY = re.compile(r"\bequity\b", re.I)
_NO_EQUITY = re.compile(r"\bno equity\b", re.I)
_CLOSED = re.compile(
    r"\b(?:applications?|position|role|roles|hiring)\s+(?:is\s+|are\s+)?(?:now\s+)?(?:closed|filled)\b"
    r"|\bno longer (?:hiring|accepting)",
    re.I,
)
# Bare domains such as "hermeshealth.com" in a header; known TLDs avoid matching "Node.js".
_DOMAIN = re.compile(
    rf"(?<![@\w.])(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+{_TLD}\b(?:/[^\s|,)]*)?", re.I
)
_JOB_BOARDS = re.compile(
    r"greenhouse|grnh\.se|lever\.co|ashbyhq|workable|personio|notion|linkedin|wellfound|ycombinator|"
    r"news\.ycombinator|forms\.gle|docs\.google|typeform|youtube|youtu\.be|twitter|x\.com/|"
    r"careers?\b|/jobs?\b|apply",
    re.I,
)
_PROFILE_URL = {
    "linkedin": re.compile(r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/[^\s,)\]]+", re.I),
    "github": re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s,)\]]+", re.I),
}
_SENIORITY: tuple[tuple[Seniority, re.Pattern[str]], ...] = (
    ("intern", re.compile(r"\bintern(?:ship)?s?\b", re.I)),
    ("executive", re.compile(r"\b(?:chief|cto|ceo|cpo|coo|cfo|vp|vice president)\b", re.I)),
    ("director", re.compile(r"\b(?:director|head of)\b", re.I)),
    ("manager", re.compile(r"\bmanager\b", re.I)),
    ("principal", re.compile(r"\bprincipal\b", re.I)),
    ("staff", re.compile(r"\bstaff\b", re.I)),
    ("lead", re.compile(r"\blead\b", re.I)),
    ("senior", re.compile(r"\b(?:senior|sr\.?)\b", re.I)),
    ("junior", re.compile(r"\b(?:junior|jr\.?|entry[\s-]level|graduate)\b", re.I)),
    ("mid", re.compile(r"\b(?:mid[\s-]level|intermediate)\b", re.I)),
)
# Words a post must contain for each company stage; also used to check a model's answer.
STAGE_EVIDENCE: dict[CompanyStage, re.Pattern[str]] = {
    "pre-seed": re.compile(r"\bpre[\s-]?seed\b", re.I),
    "seed": re.compile(r"(?<!pre-)(?<!pre )\bseed\b", re.I),
    "series-a": re.compile(r"\bseries[\s-]?a\b", re.I),
    "series-b": re.compile(r"\bseries[\s-]?b\b", re.I),
    "series-c": re.compile(r"\bseries[\s-]?c\b", re.I),
    "series-d+": re.compile(r"\bseries[\s-]?[d-h]\b", re.I),
    "public": re.compile(r"\bpublicly[\s-](?:traded|listed)\b|\b(?:NYSE|NASDAQ)\b|\bIPO\b", re.I),
    "bootstrapped": re.compile(r"\bbootstrapped\b|\bself[\s-]funded\b|\bno VC\b", re.I),
    # "part of" needs a capitalized name after it, so "part of our team" is not evidence.
    "subsidiary": re.compile(r"\bpart of [A-Z]|(?i:\bsubsidiary\b|\ba division of\b|\bowned by\b)"),
    "nonprofit": re.compile(r"\bnon[\s-]?profit\b|\bnot[\s-]for[\s-]profit\b", re.I),
}
# Words a post must contain for an industry the model often over-assigns. Products that sell to
# agencies, or replace them, are not agencies: those mentions are removed before checking.
INDUSTRY_EVIDENCE: dict[Industry, re.Pattern[str]] = {
    "Consulting & agencies": re.compile(
        r"consult|\badvisory\b|\bagenc(?:y|ies)\b|\bstudio\b|\b(?:dev|development|software) "
        r"(?:shop|house)\b|\bstaff(?:ing|\s+aug)|\boutsourc|\bnearshor|\bcontracting\b|\bclients?\b"
        r"|\b(?:professional|managed|it|engineering|technology) services?\b"
        r"|\bservices? (?:firm|company|provider|partner)\b"
        r"|\bcustom (?:\w+ )?(?:software|development)\b|\bengagements?\b",
        re.I,
    ),
}
_SELLS_TO_AGENCIES = re.compile(
    r"\breplac\w* (?:\w+ ){0,2}agencies|\b(?:for|to|helps?) (?:\w+ ){0,3}agencies", re.I
)


def has_industry_evidence(industry: Industry, text: str) -> bool:
    """Tell whether a post supports an industry; industries without a check always pass.

    Args:
        industry: Industry assigned to the post
        text: Plain text of the post

    Returns:
        False only for checked industries whose evidence words the post lacks

    Example:
        >>> has_industry_evidence("Consulting & agencies", "We are a software consultancy.")
        True
        >>> has_industry_evidence("Consulting & agencies", "AI to replace traditional ad agencies.")
        False
    """
    pattern = INDUSTRY_EVIDENCE.get(industry)
    return pattern is None or bool(pattern.search(_SELLS_TO_AGENCIES.sub("", text)))


# Checked in order: the first match wins, so "Data Engineer" is Data & ML, "Product Designer" is
# Design and "Product Engineer" is Engineering.
_ROLE_CATEGORIES: tuple[tuple[RoleCategory, re.Pattern[str]], ...] = (
    (
        "Data & ML",
        re.compile(
            r"\bdata\b|machine learning|\bml\b|\bmlops\b|\banalytics?\b|\banalyst\b|\bscientist\b"
            r"|computer vision|\bnlp\b|deep learning",
            re.I,
        ),
    ),
    ("Design", re.compile(r"\bdesigner\b|\bux\b|\bdesign lead\b|\bhead of design\b", re.I)),
    (
        "Engineering",
        re.compile(
            r"engineer|\bdeveloper\b|\bprogramm(?:er|ing)\b|\bsre\b|devops|\barchitect\b|\bcto\b"
            r"|tech(?:nical)? lead|member of technical staff|\bmts\b",
            re.I,
        ),
    ),
    (
        "Product",
        re.compile(
            r"product manager|product owner|program manager|head of product|product lead|\bpm\b",
            re.I,
        ),
    ),
    (
        "Sales & marketing",
        re.compile(
            r"\bsales\b|account executive|account manager|\bmarketing\b|\bgrowth\b|devrel"
            r"|developer advocate|developer relations|partnerships|business development|\bsdr\b"
            r"|\bbdr\b|copywriter|content writer",
            re.I,
        ),
    ),
    (
        "People & finance",
        re.compile(
            r"recruit|\btalent\b|\bpeople\b|\bhr\b|human resources|finance|accountant|accounting"
            r"|bookkeep|\blegal\b|counsel|controller|payroll",
            re.I,
        ),
    ),
    (
        "Operations & support",
        re.compile(
            r"support|customer success|operations|\bops\b|office manager|(?-i:\bIT\b)|administrator"
            r"|assistant|chief of staff|project manager|coordinator",
            re.I,
        ),
    ),
)
# A post in a hiring thread written in the candidate template is a candidate in the wrong thread.
_SEEKER_TEMPLATE_KEYS = frozenset(
    {"location", "remote", "relocate", "technologies", "resume", "email"}
)
MIN_SEEKER_TEMPLATE_LINES = 4
_APPLY_URL = re.compile(
    r"apply|career|jobs?\b|greenhouse|grnh\.se|lever\.co|ashby|workable|personio|notion", re.I
)


@lru_cache(maxsize=1024)
def deobfuscate(text: str) -> str:
    """Rewrite disguised email addresses as plain ones.

    Args:
        text: Post text

    Returns:
        The text with each disguised address replaced by a normal one

    Example:
        >>> deobfuscate("mail me: jo [at] acme [dot] com")
        'mail me: jo@acme.com'
    """
    return _DISGUISED_EMAIL.sub(
        lambda match: _DOT_TOKEN.sub(".", _AT_TOKEN.sub("@", match.group())), text
    )


def seniority(title: str) -> Seniority | None:
    """Read a seniority level from the words of a job title; never guessed.

    Args:
        title: Job title

    Returns:
        The most specific level named in the title, or None if it names none

    Example:
        >>> seniority("Senior Android Developer")
        'senior'
        >>> seniority("Engineering Manager")
        'manager'
        >>> seniority("Backend Engineer") is None
        True
    """
    return next((level for level, pattern in _SENIORITY if pattern.search(title)), None)


def role_category(title: str) -> RoleCategory | None:
    """Read a role's kind of work from its title.

    Args:
        title: Job title

    Returns:
        The first category whose keywords the title contains, or None if none match

    Example:
        >>> role_category("Senior Data Engineer")
        'Data & ML'
        >>> role_category("Product Designer")
        'Design'
        >>> role_category("Account Executive")
        'Sales & marketing'
    """
    return next((category for category, pattern in _ROLE_CATEGORIES if pattern.search(title)), None)


def looks_like_seeker(text: str) -> bool:
    """Tell whether a post follows the candidate template (Location:, Remote:, Technologies:, ...).

    Args:
        text: Plain text of the post

    Returns:
        True if it has at least four of the template's lines
    """
    return len(_SEEKER_TEMPLATE_KEYS & _template(text).keys()) >= MIN_SEEKER_TEMPLATE_LINES


def _template(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in (part for line in text.splitlines() for part in line.split(" | ")):
        match = _TEMPLATE_LINE.match(part)
        if (
            match
            and (key := _TEMPLATE_FIELDS.get(match.group(1).strip().casefold()))
            and key not in fields
        ):
            fields[key] = match.group(2).strip()
    return fields


def _yes_no(value: str) -> bool | None:
    answer = value.strip().casefold()
    if answer.startswith(("yes", "open", "possibl", "willing")):
        return True
    if answer.startswith("no"):
        return False
    return None


def _seeker_remote(value: str) -> Remote | None:
    answer = value.strip().casefold()
    if answer.startswith(("yes", "preferred", "remote", "fully", "open")):
        return "remote"
    if answer.startswith("no"):
        return "onsite"
    return "hybrid" if "hybrid" in answer else None


# Answers on a candidate's "Remote:" line that mean yes.
_REMOTE_YES = (
    "y",
    "sure",
    "absolutely",
    "definitely",
    "enthusiastic",
    "of course",
    "ok",
    "100%",
    "preferabl",
    "preferred",
    "remote",
    "fully",
    "open",
)
_ANY_OFFICE = re.compile(rf"{_ONSITE.pattern}|\boffice\b", re.I)


def _seeker_arrangements(value: str) -> tuple[Remote, ...]:
    """Every arrangement a candidate's "Remote:" answer is open to.

    Example:
        >>> _seeker_arrangements("Yes, or on-site in the Bay Area")
        ('remote', 'onsite')
        >>> _seeker_arrangements("No, hybrid preferred")
        ('hybrid',)
        >>> _seeker_arrangements("Hybrid and onsite also work")
        ('remote', 'hybrid', 'onsite')
        >>> _seeker_arrangements("No")
        ('onsite',)
    """
    answer = value.strip().casefold()
    refused = answer.startswith("no")
    found: list[Remote] = []
    # "Hybrid and onsite also work" answers a question about remote: remote works too.
    also = re.search(r"\balso\b", answer)
    if not refused and (answer.startswith(_REMOTE_YES) or _REMOTE.search(answer) or also):
        found.append("remote")
    if _HYBRID.search(answer):
        found.append("hybrid")
    if _ANY_OFFICE.search(answer) or (refused and not found):
        found.append("onsite")
    return tuple(found)


def _split_technologies(value: str) -> list[str]:
    items = (item.strip(" .-*:") for item in _TECH_SEPARATORS.split(_TECH_FILLER.sub("", value)))
    return [item for item in items if item and len(item.split()) <= 4]


def _email(text: str) -> str | None:
    match = EMAIL.search(text) or EMAIL.search(deobfuscate(text))
    return match.group() if match else None


def _contact(text: str) -> str | None:
    if email := _email(text):
        return email
    urls = [url for url in URL.findall(text) if _APPLY_URL.search(url)]
    return urls[0].rstrip(".,") if urls else None


def _first_url(value: str) -> str | None:
    match = URL.search(value) or _DOMAIN.search(value)
    return match.group().rstrip(".,;") if match else None


def _remote(header: str) -> Remote | None:
    if _REMOTE.search(header) and not _PARTIAL_REMOTE.search(header):
        return "remote"
    if _HYBRID.search(header) or _PARTIAL_REMOTE.search(header):
        return "hybrid"
    if _ONSITE.search(header):
        return "hybrid" if _DAYS_IN_OFFICE.search(header) else "onsite"
    return None


def _amount(number: str, thousands: str | None) -> float:
    value = (
        float(number.replace(",", ""))
        if len(number.split(",")[-1]) == 3
        else float(number.replace(",", "."))
    )
    return value * 1000 if thousands else value


def _pay(lines: list[str]) -> Pay | None:
    for line in lines:
        for match in _PAY.finditer(line):
            symbol = match["code"] or match["cur"] or match["cur2"]
            if symbol is None:
                continue
            low, high = (
                _amount(match["low"], match["lowk"]),
                _amount(match["high"], match["highk"] or match["lowk"]),
            )
            if match["highk"] and not match["lowk"] and low < 1000:
                low *= 1000
            hourly = bool(_HOURLY.search(line))
            if low > high or (not hourly and high < 1000):
                continue
            return Pay(
                low, high, _CURRENCY_SYMBOLS.get(symbol, symbol), "hour" if hourly else "year"
            )
    return None


def _seeker_fields(text: str) -> dict[str, Any]:
    template = _template(text)
    fields: dict[str, Any] = {}
    location_line = template.get("location", "")
    if location := _TIMEZONE.sub("", location_line).strip(" ,/"):
        fields["locations"] = (location,)
    if timezone := _TIMEZONE_NAME.search(location_line):
        fields["timezone"] = timezone.group()
    if "remote" in template and (remote := _seeker_remote(template["remote"])):
        fields["remote"] = remote
    if "remote" in template and (arrangements := _seeker_arrangements(template["remote"])):
        fields["arrangements"] = arrangements
    if "relocate" in template and (relocate := _yes_no(template["relocate"])) is not None:
        fields["willing_to_relocate"] = relocate
    # Free-form skill lists mix in non-technologies, so rules keep only known names.
    listed = (
        name
        for item in _split_technologies(template.get("technologies", ""))
        if is_known_technology(item)
        for name in canonical_technologies(item)
    )
    if technologies := tuple(dict.fromkeys((*listed, *find_technologies(text)))):
        fields["technologies"] = technologies
    if experience := _EXPERIENCE.search(text):
        fields["experience_years"] = int(experience.group(1))
    if email := _email(template.get("email", "") or text):
        fields["contact"] = email
    for name, pattern in _PROFILE_URL.items():
        if (match := pattern.search(template.get(name, "") or text)) and "<" not in match.group():
            fields[name] = match.group().rstrip(".,/;")
    if resume := _first_url(template.get("resume", "")):
        fields["resume_url"] = resume
    if website := _first_url(template.get("website", "")):
        fields["website"] = website
    return fields


def _hiring_fields(text: str) -> dict[str, Any]:
    lines = [
        line for line in text.splitlines() if line.strip() and not line.lower().startswith("edit")
    ]
    header = lines[0] if lines else ""
    segments = [segment.strip() for segment in _HEADER_SEPARATOR.split(header) if segment.strip()]
    fields: dict[str, Any] = {}
    name = URL.sub("", segments[0]).split(" (")[0].strip() if segments else ""
    # A first segment longer than a name is a sentence ("Backed by Sequoia, Peregrine is..."),
    # so the model's reading of the company is used instead.
    if len(segments) > 1 and not _ROLE_WORDS.search(name) and len(name.split()) <= MAX_NAME_WORDS:
        fields["company"] = name
    websites = (
        match.group() for match in _DOMAIN.finditer(header) if not _JOB_BOARDS.search(match.group())
    )
    if website := next(websites, None):
        fields["company_website"] = website.rstrip(".,/")
    if remote := _remote(header):
        fields["remote"] = remote
    if employment := tuple(kind for kind, pattern in _EMPLOYMENT.items() if pattern.search(header)):
        fields["employment_types"] = employment
    # Pay sits on a line mentioning salary or comp, or on the line right after one.
    pay_lines = [
        line
        for previous, line in pairwise(lines)
        if _PAY_LINE.search(line) or _PAY_LINE.search(previous)
    ]
    if pay := _pay([header, *pay_lines]):
        fields["pay"] = pay
    if experience := _MIN_EXPERIENCE.search(text):
        fields["min_experience_years"] = int(experience.group(1) or experience.group(2))
    if _NO_EQUITY.search(text):
        fields["equity"] = False
    elif _EQUITY.search(text):
        fields["equity"] = True
    if _NO_RELOCATION.search(text):
        fields["relocation_support"] = False
    elif _RELOCATION.search(text):
        fields["relocation_support"] = True
    if _CLOSED.search(text):
        fields["applications_closed"] = True
    stages = [stage for stage, pattern in STAGE_EVIDENCE.items() if pattern.search(text)]
    if len(stages) == 1:
        fields["company_stage"] = stages[0]
    if _NO_VISA.search(text):
        fields["visa_sponsorship"] = False
    elif _VISA.search(text):
        fields["visa_sponsorship"] = True
    if technologies := find_technologies(text):
        fields["technologies"] = technologies
    if contact := _contact(text):
        fields["contact"] = contact
    return fields


def extract_rules(kind: Kind, text: str) -> dict[str, Any]:
    """Extract the fields that simple rules can read reliably.

    Seeker posts follow the thread's "Location: / Remote: / ..." template; hiring posts start with
    a "Company | Role | Location | REMOTE" header line.

    Args:
        kind: Thread kind of the post
        text: Plain text of the post

    Returns:
        Posting fields found, keyed by field name; fields not found are absent
    """
    return _seeker_fields(text) if kind is Kind.SEEKING else _hiring_fields(text)
