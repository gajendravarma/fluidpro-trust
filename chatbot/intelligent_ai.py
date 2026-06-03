"""
Intelligent AI Chatbot — powered by Ollama (llama3.2:3b)

Data sources:
  - Tickets       : ManageEngine ServiceDesk → local DB (TicketCache)
  - Pulseway      : RMM devices → local DB (PulsewayDevice)
  - MDM           : Mobile devices → local DB (mdm.Device)
  - Licenses      : CompanyLicense DB table
  - Office 365    : ChatbotCache snapshots (refreshed by refresh_chatbot_cache command)
  - Datto         : ChatbotCache snapshots (refreshed by refresh_chatbot_cache command)
  - Site24x7      : Live API (no cache — directs to portal)

Falls back to keyword-based logic when Ollama is unavailable.
"""

import json
import re
import os
import logging
from datetime import datetime, timedelta
from calendar import monthrange
from django.db.models import Count, Q, Sum

logger = logging.getLogger(__name__)

# ── Load knowledge base once ──────────────────────────────────────────────────
_KB_PATH = os.path.join(os.path.dirname(__file__), '..', 'company_knowledge.json')
try:
    with open(_KB_PATH, 'r', encoding='utf-8') as _f:
        KB = json.load(_f)
except Exception as _e:
    logger.warning(f"Could not load company_knowledge.json: {_e}")
    KB = {"companies": {}, "ticket_statuses": {}, "technicians": [], "licenses": {}, "modules": {}}

_COMPANIES   = KB.get("companies", {})
_STATUSES    = KB.get("ticket_statuses", {})
_TECHNICIANS = KB.get("technicians", [])
_LICENSES    = KB.get("licenses", {})
_MODULES     = KB.get("modules", {})


# ── Ollama system prompt ──────────────────────────────────────────────────────
# NOTE: Do NOT put hardcoded statistics here. Numbers go stale and the LLM
# will prefer them over the live data passed in each prompt. Describe only the
# *structure* of what is available; the actual figures come from the DB at
# query time and are embedded directly in the generate-response prompt.
_SYSTEM_PROMPT = """You are a helpful IT operations assistant for an MSP (Managed Service Provider).

You answer questions using LIVE data fetched from the database at the time of each query.
The live data is provided to you in the "Data:" section of each prompt — always use those
numbers, never invent or recall your own. Do not use any pre-trained knowledge about
specific device counts, ticket volumes, or license figures.

Data sources available:
1. TICKETS — ManageEngine ServiceDesk local DB cache
   Fields: company_name, status, technician_name, created_at
   Statuses include: Open, In Progress, Closed, Resolved, Pending, Cancelled, On Hold

2. PULSEWAY DEVICES — RMM local DB cache
   Fields: device_name, organization_name, status (online/offline), operating_system, ip_address

3. MDM DEVICES — Mobile Device Management local DB
   Fields: device_type (android/ios/windows), status (managed/active/inactive/retired), company

4. LICENSES — CompanyLicense DB table
   Fields: company, module/package, total_licenses, used_licenses, expiry_date

5. OFFICE 365 — ChatbotCache snapshots (may be a few hours old, age shown in data)
   Data: license SKUs, users, mailbox usage, Teams activity, email activity

6. DATTO BCDR — ChatbotCache snapshot
   Data: BCDR device count, DTC assets, storage pool usage

7. SITE24X7 — Live API (not queryable from chatbot; redirect user to the portal section)

INTENTS you recognize:
ticket_count, ticket_summary, technician_tickets, device_count, device_status,
mdm_devices, license_info, license_expiring, top_companies,
office365_licenses, office365_users, office365_mailbox, office365_teams, office365_email,
datto_storage, datto_devices, site24x7_info, help

Always respond with valid JSON only.
"""


class IntelligentChatBot:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2:3b"

    # ── Ollama helpers ────────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str, temperature: float = 0.1, timeout: int = 20) -> str:
        try:
            import requests
            resp = requests.post(self.ollama_url, json={
                "model": self.model,
                "system": _SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature}
            }, timeout=timeout)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
        except Exception as e:
            logger.debug(f"Ollama unavailable: {e}")
        return ""

    def _extract_json(self, text: str) -> dict:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    # ── Intent + entity extraction ────────────────────────────────────────────

    def extract_intent_and_entities(self, query: str) -> dict:
        prompt = f"""Extract the intent and entities from this IT query.

Query: "{query}"

Respond ONLY with valid JSON:
{{
  "intent": "ticket_count|ticket_summary|technician_tickets|device_count|device_status|mdm_devices|license_info|license_expiring|top_companies|office365_licenses|office365_users|office365_mailbox|office365_teams|office365_email|datto_storage|datto_devices|site24x7_info|help",
  "entities": {{
    "company": "company name or null",
    "status": "ticket status or device status or null",
    "technician": "technician name or null",
    "date_range": "today|yesterday|this_week|last_week|this_month|last_month or null",
    "month": "month name or null",
    "year": "year number or null",
    "module": "license module name or null",
    "device_type": "android|ios|windows or null"
  }}
}}"""
        llm_text = self._call_ollama(prompt, temperature=0.1)
        if llm_text:
            parsed = self._extract_json(llm_text)
            if parsed.get("intent"):
                # Enrich entities with internal keys
                entities = parsed.get("entities", {})
                entities = self._enrich_entities(entities, query)
                parsed["entities"] = entities
                return parsed
        return self._keyword_extraction(query)

    def _enrich_entities(self, entities: dict, query: str) -> dict:
        """Resolve company aliases → internal keys; resolve month name → number."""
        q = query.lower()
        company_raw = entities.get("company")
        if company_raw:
            resolved = self._resolve_company(company_raw)
            if resolved:
                entities["_company_data"] = resolved
        # Month resolution
        month_map = {
            'january':1,'february':2,'febrary':2,'march':3,'april':4,'may':5,'june':6,
            'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
        }
        month_raw = entities.get("month", "")
        if month_raw and month_raw.lower() in month_map:
            entities["_month_num"] = month_map[month_raw.lower()]
            year_match = re.search(r'\b(202\d)\b', q)
            entities["year"] = int(year_match.group(1)) if year_match else datetime.now().year
        return entities

    def _keyword_extraction(self, query: str) -> dict:
        q = query.lower()
        entities = {}

        # ── Identity / greeting ───────────────────────────────────────────────
        identity_kw = [
            "who are you", "what are you", "your name", "introduce yourself",
            "how are you", "how r you", "how do you do", "are you an ai",
            "what can you do", "what do you do", "hello", "hi there", "hey there",
        ]
        if any(kw in q for kw in identity_kw):
            return {"intent": "identity", "entities": {}}

        # ── Negation: "apart from X", "except X", "other than X", "excluding X" ─
        negation_patterns = [
            r"apart from (.+?)(?:\?|$)",
            r"except (?:for )?(.+?)(?:\?|$)",
            r"other than (.+?)(?:\?|$)",
            r"excluding (.+?)(?:\?|$)",
            r"besides (.+?)(?:\?|$)",
            r"not (?:including )?(.+?)(?:\?|$)",
        ]
        for pat in negation_patterns:
            m = re.search(pat, q)
            if m:
                excluded_raw = m.group(1).strip()
                excdata = self._resolve_company(excluded_raw)
                if excdata:
                    entities["exclude_company"] = excdata["display_name"]
                    entities["_exclude_company_data"] = excdata
                break

        # Company (only if NOT in a negation phrase)
        if "_exclude_company_data" not in entities:
            for cdata in _COMPANIES.values():
                for alias in cdata.get("aliases", []):
                    if alias.lower() in q:
                        entities["company"] = cdata["display_name"]
                        entities["_company_data"] = cdata
                        break
                if "_company_data" in entities:
                    break

        # Ticket status
        hold_kw = ["on hold","onhold","hold","paused","blocked","observation","spare","dependency","waiting","pending"]
        if any(kw in q for kw in hold_kw):
            entities["status"] = "onhold_group"
        else:
            for sdata in _STATUSES.values():
                if "aliases" in sdata:
                    for alias in sdata["aliases"]:
                        if alias in q:
                            entities["status"] = sdata.get("db_value", alias)
                            break
                if "status" in entities:
                    break

        # Technician
        for tech in _TECHNICIANS:
            for alias in tech.get("aliases", []):
                if alias in q:
                    entities["technician"] = tech["name"]
                    break
            if "technician" in entities:
                break

        # Date range
        if "today" in q:
            entities["date_range"] = "today"
        elif "yesterday" in q:
            entities["date_range"] = "yesterday"
        elif "last week" in q or "past week" in q or "last 7 days" in q:
            entities["date_range"] = "last_week"
        elif "this week" in q:
            entities["date_range"] = "this_week"
        elif "last month" in q or "past month" in q or "last 30 days" in q:
            entities["date_range"] = "last_month"
        elif "this month" in q:
            entities["date_range"] = "this_month"

        # Month
        month_map = {
            'january':1,'february':2,'febrary':2,'march':3,'april':4,'may':5,'june':6,
            'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
        }
        for mname, mnum in month_map.items():
            if mname in q:
                entities["month"] = mname
                entities["_month_num"] = mnum
                yr = re.search(r'\b(202\d)\b', q)
                entities["year"] = int(yr.group(1)) if yr else datetime.now().year
                break

        # Module
        for mod_name, mod_data in _MODULES.items():
            for alias in mod_data.get("aliases", []):
                if alias in q:
                    entities["module"] = mod_name
                    break
            if "module" in entities:
                break

        # Device type (MDM)
        for dtype in ["android","ios","windows"]:
            if dtype in q:
                entities["device_type"] = dtype
                break

        # Intent
        is_ticket = any(w in q for w in ["ticket","support","request","issue","task","helpdesk"])
        is_device = any(w in q for w in ["device","computer","server","machine","endpoint","laptop","desktop"])
        is_mobile = any(w in q for w in ["mobile","phone","mdm","android","ios","smartphone"])
        is_license = any(w in q for w in ["license","expir","renewal","subscription","when does","expire"])
        is_o365  = any(w in q for w in ["office365","office 365","o365","m365","microsoft 365","mailbox","teams","email activity","sharepoint","microsoft"])
        is_datto = any(w in q for w in ["datto","backup","bcdr","disaster recovery","storage pool","dtc"])
        is_s247  = any(w in q for w in ["site24x7","site 24x7","uptime","monitor status","downtime","monitor"])

        if any(w in q for w in ["help","what can you","capability","capabilities"]):
            intent = "help"
        elif is_license and any(w in q for w in ["expiring","expire soon","due","renewal"]):
            intent = "license_expiring"
        elif is_license:
            intent = "license_info"
        elif is_o365:
            if any(w in q for w in ["mailbox","storage","quota","high usage"]):
                intent = "office365_mailbox"
            elif any(w in q for w in ["teams","meeting","chat","message"]):
                intent = "office365_teams"
            elif any(w in q for w in ["email activity","send","sent","receive","received"]):
                intent = "office365_email"
            elif any(w in q for w in ["user","users","who has","how many people","staff"]):
                intent = "office365_users"
            else:
                intent = "office365_licenses"
        elif is_datto:
            if any(w in q for w in ["storage","pool","space","gb","used","available"]):
                intent = "datto_storage"
            else:
                intent = "datto_devices"
        elif is_s247:
            intent = "site24x7_info"
        elif any(w in q for w in ["top","most","ranking","highest","which company"]):
            intent = "top_companies"
        elif is_mobile:
            intent = "mdm_devices"
        elif is_device:
            if any(w in q for w in ["status","online","offline","down","up"]):
                intent = "device_status"
            else:
                intent = "device_count"
        elif is_ticket:
            if any(w in q for w in ["summary","breakdown","overview","report","all status","details"]):
                intent = "ticket_summary"
            elif "technician" in entities:
                intent = "technician_tickets"
            # No specific company + date filter → show all-companies breakdown
            elif "_company_data" not in entities and entities.get("date_range"):
                intent = "ticket_companies_breakdown"
            elif "_exclude_company_data" in entities:
                intent = "ticket_count"
            else:
                intent = "ticket_count"
        elif "technician" in entities:
            intent = "technician_tickets"
        elif "_company_data" in entities:
            intent = "ticket_summary"
        else:
            intent = "help"

        return {"intent": intent, "entities": entities}

    # ── Company resolver ──────────────────────────────────────────────────────

    def _resolve_company(self, raw: str) -> dict | None:
        r = raw.lower()
        for cdata in _COMPANIES.values():
            for alias in cdata.get("aliases", []):
                if alias.lower() in r or r in alias.lower():
                    return cdata
        return None

    # ── Date filter helper ────────────────────────────────────────────────────

    def _apply_date_filter(self, qs, entities: dict):
        dr = entities.get("date_range")
        month_num = entities.get("_month_num")
        year = entities.get("year") or datetime.now().year
        now = datetime.now()
        if month_num:
            start = datetime(year, month_num, 1)
            end = datetime(year, month_num, monthrange(year, month_num)[1], 23, 59, 59)
            return qs.filter(created_at__gte=start, created_at__lte=end)
        if dr == "today":
            return qs.filter(created_at__date=now.date())
        if dr == "yesterday":
            return qs.filter(created_at__date=(now - timedelta(days=1)).date())
        if dr == "this_week":
            start = now - timedelta(days=now.weekday())
            return qs.filter(created_at__gte=start.replace(hour=0, minute=0, second=0))
        if dr == "last_week":
            return qs.filter(created_at__gte=now - timedelta(days=7))
        if dr == "this_month":
            return qs.filter(created_at__year=now.year, created_at__month=now.month)
        if dr == "last_month":
            return qs.filter(created_at__gte=now - timedelta(days=30))
        return qs

    def _apply_ticket_status(self, qs, status: str):
        if status == "onhold_group":
            return qs.filter(
                Q(status__icontains='hold') | Q(status__iexact='onhold') |
                Q(status__icontains='observation') | Q(status__iexact='pending')
            )
        return qs.filter(status__iexact=status)

    # ── DB queries ────────────────────────────────────────────────────────────

    def _query_ticket_count(self, entities: dict) -> dict:
        from tickets.models import TicketCache
        qs = TicketCache.objects.all()
        applied = []

        # Include filter
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        if cdata:
            ticket_name = cdata.get("ticket_company_name", cdata.get("display_name"))
            qs = qs.filter(company_name__icontains=ticket_name)
            applied.append(f"company: {ticket_name}")

        # Exclude filter (negation — "apart from X", "except X")
        excdata = entities.get("_exclude_company_data")
        if excdata:
            exc_name = excdata.get("ticket_company_name", excdata.get("display_name"))
            qs = qs.exclude(company_name__icontains=exc_name)
            applied.append(f"excluding: {excdata['display_name']}")

        if entities.get("status"):
            qs = self._apply_ticket_status(qs, entities["status"])
            applied.append(f"status: {entities['status']}")

        if entities.get("technician"):
            qs = qs.filter(technician_name__icontains=entities["technician"])
            applied.append(f"technician: {entities['technician']}")

        if entities.get("date_range") or entities.get("_month_num"):
            qs = self._apply_date_filter(qs, entities)
            applied.append(f"period: {entities.get('month') or entities.get('date_range')}")

        return {"data_type": "ticket_count", "count": qs.count(), "filters": applied}

    def _query_ticket_companies_breakdown(self, entities: dict) -> dict:
        """All-companies breakdown for a date range. Supports exclude_company negation."""
        from tickets.models import TicketCache
        qs = TicketCache.objects.all()

        if entities.get("date_range") or entities.get("_month_num"):
            qs = self._apply_date_filter(qs, entities)

        if entities.get("status"):
            qs = self._apply_ticket_status(qs, entities["status"])

        # Apply negation exclusion
        excdata = entities.get("_exclude_company_data")
        excluded_label = ""
        if excdata:
            exc_name = excdata.get("ticket_company_name", excdata.get("display_name"))
            qs = qs.exclude(company_name__icontains=exc_name)
            excluded_label = excdata["display_name"]

        rows = list(
            qs.values("company_name")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")[:15]
        )
        total = sum(r["cnt"] for r in rows)
        period = entities.get("date_range") or entities.get("month") or "all time"
        return {
            "data_type": "ticket_companies_breakdown",
            "period": period,
            "total": total,
            "excluded": excluded_label,
            "companies": [{"name": r["company_name"] or "Unknown", "count": r["cnt"]} for r in rows],
        }

    def _query_ticket_summary(self, entities: dict) -> dict:
        from tickets.models import TicketCache
        qs = TicketCache.objects.all()
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        label = "All Companies"
        if cdata:
            ticket_name = cdata.get("ticket_company_name", cdata.get("display_name"))
            qs = qs.filter(company_name__icontains=ticket_name)
            label = ticket_name
        breakdown = list(qs.values("status").annotate(cnt=Count("id")).order_by("-cnt"))
        total = sum(r["cnt"] for r in breakdown)
        return {
            "data_type": "ticket_summary", "company": label, "total": total,
            "breakdown": [{"status": r["status"], "count": r["cnt"],
                           "pct": round(r["cnt"]*100/total,1) if total else 0}
                          for r in breakdown]
        }

    def _query_technician_tickets(self, entities: dict) -> dict:
        from tickets.models import TicketCache
        tech = entities.get("technician")
        if not tech:
            rows = (TicketCache.objects.exclude(technician_name="")
                    .values("technician_name").annotate(cnt=Count("id")).order_by("-cnt")[:10])
            return {"data_type": "technician_list",
                    "technicians": [{"name": r["technician_name"], "count": r["cnt"]} for r in rows]}
        qs = TicketCache.objects.filter(technician_name__icontains=tech)
        breakdown = list(qs.values("status").annotate(cnt=Count("id")).order_by("-cnt"))
        total = sum(r["cnt"] for r in breakdown)
        return {"data_type": "technician_tickets", "technician": tech, "total": total,
                "breakdown": [{"status": r["status"], "count": r["cnt"]} for r in breakdown]}

    def _query_device_count(self, entities: dict) -> dict:
        from pulseway.models import PulsewayDevice
        qs = PulsewayDevice.objects.all()
        label = "All"
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        if cdata:
            orgs = cdata.get("pulseway_orgs", [])
            if orgs:
                q_filter = Q()
                for org in orgs:
                    q_filter |= Q(organization_name__icontains=org)
                qs = qs.filter(q_filter)
            label = cdata["display_name"]
        return {"data_type": "device_count", "company": label, "count": qs.count()}

    def _query_device_status(self, entities: dict) -> dict:
        from pulseway.models import PulsewayDevice
        qs = PulsewayDevice.objects.all()
        label = "All"
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        if cdata:
            orgs = cdata.get("pulseway_orgs", [])
            if orgs:
                q_filter = Q()
                for org in orgs:
                    q_filter |= Q(organization_name__icontains=org)
                qs = qs.filter(q_filter)
            label = cdata["display_name"]
        status_filter = (entities.get("status") or "").lower()
        online = qs.filter(status="online").count()
        offline = qs.filter(status="offline").count()
        total = qs.count()
        if status_filter == "online":
            return {"data_type": "device_status", "company": label, "online": online, "offline": None, "total": total}
        if status_filter == "offline":
            return {"data_type": "device_status", "company": label, "online": None, "offline": offline, "total": total}
        return {"data_type": "device_status", "company": label, "online": online, "offline": offline, "total": total}

    def _query_mdm_devices(self, entities: dict) -> dict:
        from mdm.models import Device as MdmDevice
        qs = MdmDevice.objects.all()
        label = "All"
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        if cdata:
            mdm_name = cdata.get("mdm_company_name")
            if mdm_name:
                qs = qs.filter(mdm_customer__company__name__icontains=mdm_name)
                label = mdm_name
            else:
                return {"data_type": "mdm_devices", "company": cdata["display_name"],
                        "total": 0, "note": f"{cdata['display_name']} does not have MDM enrolled"}

        device_type = entities.get("device_type")
        if device_type:
            qs = qs.filter(device_type=device_type)

        status_filter = (entities.get("status") or "").lower()
        if status_filter in ("managed","active","inactive","retired"):
            qs = qs.filter(status=status_filter)

        by_type = list(qs.values("device_type").annotate(cnt=Count("id")).order_by("-cnt"))
        by_status = list(qs.values("status").annotate(cnt=Count("id")).order_by("-cnt"))
        return {
            "data_type": "mdm_devices",
            "company": label,
            "total": qs.count(),
            "by_type": [{"type": r["device_type"], "count": r["cnt"]} for r in by_type],
            "by_status": [{"status": r["status"], "count": r["cnt"]} for r in by_status]
        }

    def _query_license_info(self, entities: dict) -> dict:
        from rbac.models import CompanyLicense
        qs = CompanyLicense.objects.select_related("company", "package").filter(is_active=True)
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company",""))
        if cdata:
            rbac_name = cdata.get("rbac_name", cdata["display_name"])
            qs = qs.filter(company__name__icontains=rbac_name)
        module = entities.get("module")
        if module:
            qs = qs.filter(package__display_name__icontains=module)
        result = []
        for lic in qs:
            result.append({
                "company": lic.company.name,
                "module": lic.package.display_name,
                "expires": str(lic.expiry_date),
                "total": lic.total_licenses,
                "used": lic.used_licenses,
                "remaining": max(0, lic.total_licenses - lic.used_licenses),
                "expired": lic.is_expired if hasattr(lic, "is_expired") else False
            })
        return {"data_type": "license_info", "licenses": result}

    def _query_license_expiring(self, entities: dict) -> dict:
        from rbac.models import CompanyLicense
        from datetime import date
        today = date.today()
        dr = entities.get("date_range")
        if dr == "this_month":
            threshold = today.replace(day=monthrange(today.year, today.month)[1])
        else:
            threshold = today + timedelta(days=90)  # default: next 90 days
        qs = (CompanyLicense.objects
              .select_related("company", "package")
              .filter(is_active=True, expiry_date__lte=threshold, expiry_date__gte=today)
              .order_by("expiry_date"))
        result = []
        for lic in qs:
            days_left = (lic.expiry_date - today).days
            result.append({
                "company": lic.company.name,
                "module": lic.package.display_name,
                "expires": str(lic.expiry_date),
                "days_left": days_left,
                "total": lic.total_licenses,
                "used": lic.used_licenses
            })
        return {"data_type": "license_expiring", "licenses": result, "threshold_days": (threshold - today).days}

    # ── ChatbotCache helpers ──────────────────────────────────────────────────

    def _get_cache(self, source: str, company_key: str, data_type: str) -> dict | None:
        """Return cached payload or None if missing/failed."""
        from chatbot.models import ChatbotCache
        try:
            obj = ChatbotCache.objects.get(source=source, company_key=company_key, data_type=data_type)
            if obj.success:
                return obj.payload
        except ChatbotCache.DoesNotExist:
            pass
        return None

    def _cache_age_note(self, source: str, company_key: str, data_type: str) -> str:
        from chatbot.models import ChatbotCache
        from datetime import timezone as tz
        try:
            obj = ChatbotCache.objects.get(source=source, company_key=company_key, data_type=data_type)
            delta = datetime.now() - obj.fetched_at.replace(tzinfo=None)
            hours = int(delta.total_seconds() / 3600)
            return f"(data from {hours}h ago)" if hours >= 1 else "(data from <1h ago)"
        except Exception:
            return "(cache age unknown)"

    def _resolve_o365_key(self, company_raw: str) -> str | None:
        """Map company name to O365 customer_key ('cgl', 'wepsol', etc.)"""
        from office365.customer_config import resolve_customer_key
        try:
            return resolve_customer_key(company_raw)
        except Exception:
            return None

    # ── Office 365 queries ────────────────────────────────────────────────────

    def _query_office365_licenses(self, entities: dict) -> dict:
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company", ""))
        company_name = cdata["display_name"] if cdata else None

        # Determine which customer keys to query
        from office365.customer_config import O365_CUSTOMER_KEYS_WITH_DATA
        keys_to_query = []
        if company_name:
            key = self._resolve_o365_key(company_name)
            if key:
                keys_to_query = [key]
        else:
            keys_to_query = ['cgl', 'wepsol']

        results = []
        for key in keys_to_query:
            data = self._get_cache('office365', key, 'license_summary')
            if data:
                age = self._cache_age_note('office365', key, 'license_summary')
                from office365.customer_config import CUSTOMER_CONFIGS
                cname = CUSTOMER_CONFIGS.get(key, {}).get('name', key)
                results.append({"company": cname, "licenses": data, "age": age})

        if not results:
            return {"data_type": "office365_licenses", "results": [],
                    "note": "No Office 365 data in cache. Run: python manage.py refresh_chatbot_cache"}
        return {"data_type": "office365_licenses", "results": results}

    def _query_office365_users(self, entities: dict) -> dict:
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company", ""))
        keys = []
        if cdata:
            key = self._resolve_o365_key(cdata["display_name"])
            if key:
                keys = [key]
        else:
            keys = ['cgl', 'wepsol']

        results = []
        for key in keys:
            data = self._get_cache('office365', key, 'users')
            if data:
                from office365.customer_config import CUSTOMER_CONFIGS
                cname = CUSTOMER_CONFIGS.get(key, {}).get('name', key)
                licensed = sum(1 for u in data if u.get('license_count', 0) > 0)
                results.append({
                    "company": cname,
                    "total_users": len(data),
                    "licensed_users": licensed,
                    "unlicensed_users": len(data) - licensed,
                    "age": self._cache_age_note('office365', key, 'users')
                })
        return {"data_type": "office365_users", "results": results}

    def _query_office365_mailbox(self, entities: dict) -> dict:
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company", ""))
        keys = [self._resolve_o365_key(cdata["display_name"])] if cdata else ['cgl', 'wepsol']
        keys = [k for k in keys if k]

        results = []
        for key in keys:
            data = self._get_cache('office365', key, 'mailbox_usage')
            if data:
                from office365.customer_config import CUSTOMER_CONFIGS
                cname = CUSTOMER_CONFIGS.get(key, {}).get('name', key)
                results.append({
                    "company": cname,
                    "total_mailboxes": data.get("total_mailboxes", 0),
                    "high_usage_count": data.get("high_usage_count", 0),
                    "high_usage_users": data.get("high_usage_users", [])[:5],
                    "age": self._cache_age_note('office365', key, 'mailbox_usage')
                })
        return {"data_type": "office365_mailbox", "results": results}

    def _query_office365_teams(self, entities: dict) -> dict:
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company", ""))
        keys = [self._resolve_o365_key(cdata["display_name"])] if cdata else ['cgl', 'wepsol']
        keys = [k for k in keys if k]

        results = []
        for key in keys:
            data = self._get_cache('office365', key, 'teams_summary')
            if data:
                from office365.customer_config import CUSTOMER_CONFIGS
                cname = CUSTOMER_CONFIGS.get(key, {}).get('name', key)
                results.append({
                    "company": cname, **data,
                    "age": self._cache_age_note('office365', key, 'teams_summary')
                })
        return {"data_type": "office365_teams", "results": results}

    def _query_office365_email(self, entities: dict) -> dict:
        cdata = entities.get("_company_data") or self._resolve_company(entities.get("company", ""))
        keys = [self._resolve_o365_key(cdata["display_name"])] if cdata else ['cgl', 'wepsol']
        keys = [k for k in keys if k]

        results = []
        for key in keys:
            data = self._get_cache('office365', key, 'email_summary')
            if data:
                from office365.customer_config import CUSTOMER_CONFIGS
                cname = CUSTOMER_CONFIGS.get(key, {}).get('name', key)
                results.append({"company": cname, **data,
                                 "age": self._cache_age_note('office365', key, 'email_summary')})
        return {"data_type": "office365_email", "results": results}

    # ── Datto queries ─────────────────────────────────────────────────────────

    def _query_datto_storage(self) -> dict:
        data = self._get_cache('datto', '', 'storage_pool')
        if not data:
            return {"data_type": "datto_storage", "pools": [],
                    "note": "No Datto data in cache. Run: python manage.py refresh_chatbot_cache"}
        return {"data_type": "datto_storage", "pools": data,
                "age": self._cache_age_note('datto', '', 'storage_pool')}

    def _query_datto_devices(self) -> dict:
        data = self._get_cache('datto', '', 'bcdr_devices')
        dtc = self._get_cache('datto', '', 'dtc_assets') or {}
        if not data:
            return {"data_type": "datto_devices", "note": "No Datto data in cache. Run: python manage.py refresh_chatbot_cache"}
        return {
            "data_type": "datto_devices",
            "bcdr_total": data.get("total", 0),
            "bcdr_online": data.get("online", 0),
            "bcdr_offline": data.get("offline", 0),
            "dtc_total": dtc.get("total", 0),
            "devices": data.get("devices", [])[:10],
            "age": self._cache_age_note('datto', '', 'bcdr_devices')
        }

    def _query_top_companies(self) -> dict:
        from tickets.models import TicketCache
        rows = (TicketCache.objects.values("company_name")
                .annotate(cnt=Count("id")).order_by("-cnt")[:8])
        return {"data_type": "top_companies",
                "companies": [{"name": r["company_name"], "count": r["cnt"]} for r in rows]}

    # ── Route to correct query ────────────────────────────────────────────────

    def _route_query(self, intent: str, entities: dict) -> dict:
        try:
            if intent == "identity":           return {"data_type": "identity"}
            if intent == "ticket_count":       return self._query_ticket_count(entities)
            if intent == "ticket_companies_breakdown": return self._query_ticket_companies_breakdown(entities)
            if intent == "ticket_summary":     return self._query_ticket_summary(entities)
            if intent == "technician_tickets": return self._query_technician_tickets(entities)
            if intent == "device_count":       return self._query_device_count(entities)
            if intent == "device_status":      return self._query_device_status(entities)
            if intent == "mdm_devices":        return self._query_mdm_devices(entities)
            if intent == "license_info":       return self._query_license_info(entities)
            if intent == "license_expiring":   return self._query_license_expiring(entities)
            if intent == "top_companies":      return self._query_top_companies()
            if intent == "office365_licenses": return self._query_office365_licenses(entities)
            if intent == "office365_users":    return self._query_office365_users(entities)
            if intent == "office365_mailbox":  return self._query_office365_mailbox(entities)
            if intent == "office365_teams":    return self._query_office365_teams(entities)
            if intent == "office365_email":    return self._query_office365_email(entities)
            if intent == "datto_storage":      return self._query_datto_storage()
            if intent == "datto_devices":      return self._query_datto_devices()
            if intent == "site24x7_info":
                return {"data_type": "site24x7_info",
                        "message": "Site24x7 monitor data is fetched live from the Site24x7 API. Visit the Site24x7 section in the portal to see monitor up/down/trouble status per customer."}
            if intent == "help":
                return {"data_type": "help"}
            return {"data_type": "unknown"}
        except Exception as e:
            logger.error(f"DB query error intent={intent}: {e}", exc_info=True)
            return {"data_type": "error", "error": str(e)}

    # ── Response generation ───────────────────────────────────────────────────

    def _generate_response(self, query: str, intent: str, entities: dict, data: dict) -> str:
        prompt = f"""Answer the IT query below using ONLY the numbers and facts in the LIVE DATA section.
Do NOT use any other knowledge — every figure must come from LIVE DATA.

Query: "{query}"

LIVE DATA (fetched from the database right now — use these exact numbers):
{json.dumps(data, indent=2)}

Rules:
- Lead with the key number/fact from LIVE DATA
- For breakdowns, use a short bullet list
- Mention company name when relevant
- Bold important numbers with **number**
- Under 6 sentences
- If data_type is "site24x7_info", tell the user to visit the portal section

Response:"""
        llm_resp = self._call_ollama(prompt, temperature=0.4, timeout=25)
        if llm_resp and len(llm_resp) > 15:
            return llm_resp
        return self._template_response(intent, entities, data)

    def _template_response(self, intent: str, entities: dict, data: dict) -> str:
        dt = data.get("data_type", "")

        if dt == "error":
            return f"Sorry, I encountered a database error: {data.get('error', 'unknown error')}"

        if dt == "identity":
            return (
                "Hi! 👋 I'm **FluidTrust AI** — your IT operations assistant for Wepsol MSP.\n\n"
                "I have **live access** to all your IT systems:\n"
                "  • 🎫 **Tickets** — ManageEngine ServiceDesk\n"
                "  • 💻 **Devices** — Pulseway RMM\n"
                "  • 📱 **Mobile Devices** — MDM\n"
                "  • 🔑 **Licenses** — All companies\n"
                "  • 📧 **Office 365** — Mailbox, Teams, Email\n"
                "  • 💾 **Datto BCDR** — Backup & storage\n\n"
                "I'm running **100% locally** on your server using open-source AI — no API key or internet needed!\n\n"
                "I can also remember our full conversation — just ask follow-up questions naturally.\n\n"
                "Try asking: *'how many open tickets today?'* or *'which company has the most tickets?'*"
            )

        if dt == "help":
            return (
                "Here's what I can help you with:\n\n"
                "🎫 **Tickets** (from ManageEngine DB)\n"
                "  • Count tickets by company, status, technician, or date\n"
                "  • Full status breakdown per company\n"
                "  • Technician workload summary\n\n"
                "💻 **Pulseway Devices** (from RMM DB)\n"
                "  • Total device count per company\n"
                "  • Online/offline device status\n\n"
                "📱 **MDM Mobile Devices** (from MDM DB)\n"
                "  • Mobile device count by type (android/ios/windows)\n"
                "  • Devices by company (Digtinctive, CG Logistics)\n\n"
                "🔑 **Licenses** (from DB)\n"
                "  • License details per company and module\n"
                "  • Licenses expiring soon\n\n"
                "🌐 **Live Portal Data** (visit the portal sections)\n"
                "  • Office 365 — mailbox, Teams, email activity\n"
                "  • Datto — BCDR devices, storage pool\n"
                "  • Site24x7 — monitor up/down status\n\n"
                "Try: *'how many open tickets for CG Logistics?'* or *'show licenses expiring soon'*"
            )

        if dt == "ticket_companies_breakdown":
            total     = data.get("total", 0)
            period    = data.get("period", "").replace("_", " ")
            excluded  = data.get("excluded", "")
            companies = data.get("companies", [])
            if not companies:
                excnote = f" (excluding **{excluded}**)" if excluded else ""
                return f"No tickets found for **{period}**{excnote}."
            excnote = f" *(excluding {excluded})*" if excluded else ""
            lines = [f"**{total}** tickets raised **{period}** across all companies{excnote}:\n"]
            for i, c in enumerate(companies, 1):
                lines.append(f"  {i}. **{c['name']}**: {c['count']}")
            return "\n".join(lines)

        if dt == "ticket_count":
            c = data.get("count", 0)
            f = data.get("filters", [])
            desc = " | ".join(f) if f else "all tickets"
            return f"Found **{c}** tickets ({desc})."

        if dt == "ticket_summary":
            company = data.get("company", "All")
            total = data.get("total", 0)
            lines = [f"**{company}** — {total} tickets total:"]
            for row in data.get("breakdown", [])[:10]:
                lines.append(f"  • {row['status']}: **{row['count']}** ({row['pct']}%)")
            return "\n".join(lines)

        if dt == "technician_tickets":
            tech = data.get("technician", "")
            total = data.get("total", 0)
            lines = [f"**{tech}** has **{total}** tickets assigned:"]
            for row in data.get("breakdown", [])[:7]:
                lines.append(f"  • {row['status']}: {row['count']}")
            return "\n".join(lines)

        if dt == "technician_list":
            lines = ["**Top technicians by ticket count:**"]
            for i, t in enumerate(data.get("technicians", []), 1):
                lines.append(f"  {i}. {t['name']}: **{t['count']}**")
            return "\n".join(lines)

        if dt == "device_count":
            return f"**{data.get('company','Total')}** has **{data.get('count',0)}** Pulseway-monitored devices."

        if dt == "device_status":
            company = data.get("company", "All")
            online = data.get("online")
            offline = data.get("offline")
            total = data.get("total", 0)
            if online is not None and offline is not None:
                return f"**{company}** devices: **{online} online**, **{offline} offline** (total: {total})"
            if online is not None:
                return f"**{company}** has **{online}** online devices out of {total} total."
            if offline is not None:
                return f"**{company}** has **{offline}** offline devices out of {total} total."

        if dt == "mdm_devices":
            company = data.get("company", "All")
            total = data.get("total", 0)
            note = data.get("note")
            if note:
                return note
            lines = [f"**{company}** MDM devices: **{total}** total"]
            for r in data.get("by_type", []):
                lines.append(f"  • {r['type'].capitalize()}: {r['count']}")
            for r in data.get("by_status", []):
                lines.append(f"  • Status {r['status']}: {r['count']}")
            return "\n".join(lines)

        if dt == "license_info":
            lics = data.get("licenses", [])
            if not lics:
                return "No license records found for that criteria."
            by_company: dict = {}
            for lic in lics:
                by_company.setdefault(lic["company"], []).append(lic)
            lines = []
            for company, clics in by_company.items():
                lines.append(f"**{company}** licenses:")
                for lic in clics:
                    expired_tag = " ⚠️ EXPIRED" if lic.get("expired") else ""
                    lines.append(f"  • {lic['module']}: {lic['used']}/{lic['total']} used | expires {lic['expires']}{expired_tag}")
            return "\n".join(lines)

        if dt == "license_expiring":
            lics = data.get("licenses", [])
            days = data.get("threshold_days", 90)
            if not lics:
                return f"No licenses expiring in the next {days} days."
            lines = [f"**{len(lics)} license(s) expiring within {days} days:**"]
            for lic in lics:
                lines.append(f"  • {lic['company']} — {lic['module']}: expires {lic['expires']} (**{lic['days_left']} days left**)")
            return "\n".join(lines)

        if dt == "top_companies":
            lines = ["**Companies ranked by ticket count:**"]
            for i, c in enumerate(data.get("companies", []), 1):
                lines.append(f"  {i}. {c['name']}: **{c['count']}**")
            return "\n".join(lines)

        if dt == "office365_licenses":
            results = data.get("results", [])
            note = data.get("note")
            if note:
                return note
            if not results:
                return "No Office 365 license data available in cache."
            lines = []
            for r in results:
                lines.append(f"**{r['company']}** O365 licenses {r.get('age','')}:")
                for lic in r.get("licenses", []):
                    lines.append(f"  • {lic['display_name']}: **{lic['consumed']}/{lic['total']}** used ({lic['usage_percent']}%)")
            return "\n".join(lines)

        if dt == "office365_users":
            results = data.get("results", [])
            if not results:
                return "No Office 365 user data available in cache."
            lines = []
            for r in results:
                lines.append(f"**{r['company']}** {r.get('age','')}: "
                             f"**{r['total_users']}** users total, "
                             f"**{r['licensed_users']}** licensed, "
                             f"{r['unlicensed_users']} unlicensed")
            return "\n".join(lines)

        if dt == "office365_mailbox":
            results = data.get("results", [])
            if not results:
                return "No mailbox usage data available in cache."
            lines = []
            for r in results:
                lines.append(f"**{r['company']}** mailboxes {r.get('age','')}: "
                             f"**{r['total_mailboxes']}** total, "
                             f"**{r['high_usage_count']}** at >85% capacity")
                for u in r.get("high_usage_users", []):
                    lines.append(f"  ⚠️ {u.get('display_name','')}: {u.get('used_percent',0):.1f}% full")
            return "\n".join(lines)

        if dt == "office365_teams":
            results = data.get("results", [])
            if not results:
                return "No Teams usage data in cache."
            lines = []
            for r in results:
                lines.append(f"**{r['company']}** Teams {r.get('age','')}: "
                             f"**{r.get('active_users',0)}** active / {r.get('total_users',0)} users | "
                             f"**{r.get('total_messages',0)}** messages | "
                             f"**{r.get('total_meetings',0)}** meetings")
            return "\n".join(lines)

        if dt == "office365_email":
            results = data.get("results", [])
            if not results:
                return "No email activity data in cache."
            lines = []
            for r in results:
                lines.append(f"**{r['company']}** email {r.get('age','')}: "
                             f"**{r.get('active_senders',0)}** active senders | "
                             f"**{r.get('total_sent',0):,}** sent | "
                             f"**{r.get('total_received',0):,}** received")
            return "\n".join(lines)

        if dt == "datto_storage":
            note = data.get("note")
            if note:
                return note
            pools = data.get("pools", [])
            age = data.get("age", "")
            if not pools:
                return "No Datto storage data available."
            lines = [f"**Datto Storage Pool** {age}:"]
            for p in pools:
                lines.append(f"  • {p['name']}: **{p['used_gb']} GB** used / {p['total_gb']} GB total ({p['usage_pct']}%)")
            return "\n".join(lines)

        if dt == "datto_devices":
            note = data.get("note")
            if note:
                return note
            age = data.get("age", "")
            lines = [
                f"**Datto BCDR Devices** {age}:",
                f"  • BCDR devices: **{data.get('bcdr_total',0)}** total — "
                f"**{data.get('bcdr_online',0)} online**, {data.get('bcdr_offline',0)} offline",
                f"  • DTC assets: **{data.get('dtc_total',0)}**"
            ]
            return "\n".join(lines)

        if dt == "site24x7_info":
            return "Site24x7 monitor data is fetched live. Visit the **Site24x7** section in the portal for current Up/Down/Trouble status per customer."

        return "I didn't fully understand that. Try asking about tickets, devices, MDM, or licenses. Type *help* for examples."

    # ── Context inheritance from conversation history ─────────────────────────

    def _inherit_context(self, entities: dict, history: list) -> dict:
        """
        Fill in missing entities from the previous turn so follow-up questions work.
        e.g. User asked about Market Xcel, then says "what about today?" →
             inherit company=Market Xcel from the previous exchange.
        """
        if not history:
            return entities

        # Find the last user message that had meaningful content
        for turn in reversed(history):
            if turn.get("role") == "user":
                prev_extraction = self._keyword_extraction(turn["content"])
                prev_entities   = prev_extraction.get("entities", {})

                # Inherit company only if current query has no company/negation
                if (
                    "_company_data" not in entities
                    and "_exclude_company_data" not in entities
                    and "_company_data" in prev_entities
                    and "exclude" not in turn["content"].lower()
                ):
                    entities["company"] = prev_entities["company"]
                    entities["_company_data"] = prev_entities["_company_data"]
                    entities["_inherited_company"] = True

                # Inherit date_range only if current query has one-word time reference
                if not entities.get("date_range") and not entities.get("_month_num"):
                    if prev_entities.get("date_range"):
                        entities["date_range"] = prev_entities["date_range"]
                        entities["_inherited_date"] = True

                # Inherit intent context (e.g. "just today?" should remain ticket-focused)
                if not entities.get("_intent_hint") and prev_entities.get("status"):
                    entities["status"] = prev_entities["status"]

                break

        return entities

    # ── Public interface ──────────────────────────────────────────────────────

    def chat(self, query: str, history: list = None) -> dict:
        extraction = self.extract_intent_and_entities(query)
        intent   = extraction.get("intent", "help")
        entities = extraction.get("entities", {})

        # For very short follow-up queries, inherit context from history
        short_followup = len(query.split()) <= 6 and intent in ("ticket_count", "help", "ticket_summary")
        if short_followup and history:
            entities = self._inherit_context(entities, history)
            # Re-derive intent after context inheritance
            if "_company_data" in entities and intent == "help":
                intent = "ticket_count"
            if entities.get("date_range") and "_company_data" not in entities and intent == "ticket_count":
                intent = "ticket_companies_breakdown"

        data     = self._route_query(intent, entities)
        response = self._generate_response(query, intent, entities, data)
        return {
            "query": query,
            "intent": intent,
            "entities": {k: v for k, v in entities.items() if not k.startswith("_")},
            "response": response,
            "timestamp": datetime.now().isoformat(),
        }


# Singleton — avoid rebuilding on every API request
_instance = None

def get_chatbot() -> IntelligentChatBot:
    global _instance
    if _instance is None:
        _instance = IntelligentChatBot()
    return _instance
