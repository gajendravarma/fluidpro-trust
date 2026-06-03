"""
chatbot/claude_engine.py
Intelligent chatbot engine powered by Claude API.

- Fetches live data from TicketCache, PulsewayDevice, MDM API, O365 cache, Datto cache
- Uses claude-haiku-4-5 for quick lookups, claude-sonnet-4-6 for analysis/recommendations
- Keeps conversation history for follow-up questions
- Falls back to keyword engine if API key not configured
"""
import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_FAST_MODEL  = 'claude-haiku-4-5-20251001'
_SMART_MODEL = 'claude-sonnet-4-6'

_ANALYSIS_KEYWORDS = {
    'trend', 'compare', 'analysis', 'analyse', 'recommend', 'predict',
    'why', 'pattern', 'anomal', 'insight', 'summary', 'report',
    'performance', 'sla', 'efficiency', 'best', 'worst', 'top',
}

_NEEDS_PULSEWAY = {'device', 'pulseway', 'online', 'offline', 'patch', 'monitor', 'rmm', 'agent'}
_NEEDS_MDM      = {'mdm', 'mobile', 'phone', 'iphone', 'android', 'enrolled', 'device management', 'tablet'}
_NEEDS_O365     = {'office', '365', 'license', 'email', 'teams', 'mailbox', 'microsoft', 'sharepoint', 'onedrive', 'exchange'}
_NEEDS_DATTO    = {'datto', 'backup', 'storage', 'bcdr', 'disaster', 'recovery', 'pool'}


# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are **FluidTrust AI** — an intelligent IT operations assistant for Wepsol, a managed IT service provider (MSP).

Today is {today}. Current time: {time}.

You have access to **real-time live data** from all IT systems (provided in each message). This data is fetched fresh for every query — tickets are synced every 5 minutes, devices every 30 minutes.

## Your Capabilities
- Answer questions about support tickets, devices, licenses, and backups
- **Proactively flag urgent issues**: critical open tickets, high offline device counts, licenses near exhaustion
- **Analyze trends**: today vs yesterday, this week vs last week, sudden spikes
- **Make intelligent recommendations**: which technician to assign, what needs attention
- **Compare companies**: identify outliers and performance differences
- **Answer follow-up questions** using our conversation history

## Companies You Manage
{companies}

## Current Technicians
{technicians}

## Response Guidelines
- Use **bold** for key numbers and company names
- Use bullet points and tables for structured data
- Highlight ⚠️ urgent issues immediately (Urgent/High priority open tickets, >80% devices offline, <5% license availability)
- For trend questions, calculate the delta (e.g., "+3 from yesterday")
- Always mention data freshness if older than 10 minutes
- Be concise but complete — don't pad responses
- If you see anomalies in the data, proactively mention them even if not asked

## What You Should NOT Do
- Never invent statistics not in the provided data
- Never say "I don't have access to" when data IS provided below
- Don't repeat data the user just saw — add insight"""


# ── Live data builders ────────────────────────────────────────────────────────

def _ticket_context() -> dict:
    """Build fresh ticket stats from TicketCache (synced every 5 min)."""
    try:
        from tickets.models import TicketCache
        from django.db.models import Count, Q

        qs   = TicketCache.objects.all()
        now  = timezone.now()
        today = now.date()

        # Status breakdown
        by_status = dict(
            qs.values_list('status').annotate(n=Count('id')).values_list('status', 'n')
        )

        # Priority breakdown
        by_priority = dict(
            qs.values_list('priority').annotate(n=Count('id')).values_list('priority', 'n')
        )

        # Time buckets
        counts = {
            'today':     qs.filter(created_at__date=today).count(),
            'yesterday': qs.filter(created_at__date=today - timedelta(days=1)).count(),
            'this_week': qs.filter(created_at__date__gte=today - timedelta(days=7)).count(),
            'last_week': qs.filter(
                created_at__date__gte=today - timedelta(days=14),
                created_at__date__lt=today - timedelta(days=7),
            ).count(),
        }

        # Open tickets by company (top 10)
        open_by_co = dict(
            qs.filter(status='Open')
            .values_list('company_name').annotate(n=Count('id'))
            .order_by('-n')[:10].values_list('company_name', 'n')
        )

        # Technician workload (active tickets)
        tech_load = dict(
            qs.filter(status__in=['Open', 'Pending', 'In Progress'])
            .exclude(technician_name__isnull=True).exclude(technician_name='')
            .values_list('technician_name').annotate(n=Count('id'))
            .order_by('-n')[:10].values_list('technician_name', 'n')
        )

        # Unassigned open
        unassigned = qs.filter(status='Open').filter(
            Q(technician_name__isnull=True) | Q(technician_name='')
        ).count()

        # Urgent/High open tickets (max 8)
        critical = list(
            qs.filter(priority__in=['Urgent', 'High'], status='Open')
            .values('ticket_id', 'subject', 'company_name', 'technician_name', 'priority', 'created_at')
            .order_by('-created_at')[:8]
        )
        for t in critical:
            if t.get('created_at'):
                t['created_at'] = t['created_at'].strftime('%d %b %Y')

        return {
            'total': qs.count(),
            'by_status': by_status,
            'by_priority': by_priority,
            'time_counts': counts,
            'open_by_company': open_by_co,
            'technician_active_load': tech_load,
            'unassigned_open': unassigned,
            'urgent_high_open': critical,
        }
    except Exception as exc:
        logger.error('Ticket context error: %s', exc)
        return {'error': str(exc)}


def _pulseway_context() -> dict:
    """Build Pulseway device stats from local DB."""
    try:
        from pulseway.models import PulsewayDevice
        from django.db.models import Count, Sum, Q

        qs    = PulsewayDevice.objects.all()
        total = qs.count()
        online = qs.filter(is_online=True).count()

        # Per-company breakdown
        by_company = {}
        for row in (
            qs.values('organization_name')
            .annotate(total=Count('id'),
                      online=Count('id', filter=Q(is_online=True)),
                      patches=Sum('pending_patches'))
            .order_by('organization_name')
        ):
            name = row['organization_name'] or 'Unknown'
            by_company[name] = {
                'total':   row['total'],
                'online':  row['online'],
                'offline': row['total'] - row['online'],
                'pending_patches': row['patches'] or 0,
            }

        return {
            'total': total,
            'online': online,
            'offline': total - online,
            'online_pct': round(online * 100 / total) if total else 0,
            'by_company': by_company,
        }
    except Exception as exc:
        logger.error('Pulseway context error: %s', exc)
        return {'error': str(exc)}


def _mdm_context() -> dict:
    """Fetch live MDM stats (one API call per customer, fast)."""
    try:
        from mdm.live_service import get_all_customers, get_mdm_stats
        customers = get_all_customers()
        stats     = get_mdm_stats(customers)

        by_company = {}
        for d in stats.get('devices', []):
            co = d['customer_name'] or 'Unknown'
            if co not in by_company:
                by_company[co] = {'total': 0, 'active': 0, 'types': {}}
            by_company[co]['total'] += 1
            if d['status'] == 'active':
                by_company[co]['active'] += 1
            t = d['device_type'] or 'unknown'
            by_company[co]['types'][t] = by_company[co]['types'].get(t, 0) + 1

        return {
            'total':      stats['total'],
            'active':     stats['active'],
            'pending':    stats['pending'],
            'retired':    stats['retired'],
            'by_company': by_company,
        }
    except Exception as exc:
        logger.error('MDM context error: %s', exc)
        return {'error': str(exc)}


def _o365_context() -> dict:
    """Get O365 license data from cache; refresh if older than 30 min."""
    try:
        from chatbot.models import ChatbotCache

        cutoff = timezone.now() - timedelta(minutes=30)
        records = ChatbotCache.objects.filter(
            source='office365', data_type='license_summary', success=True
        )
        stale = not records.filter(fetched_at__gte=cutoff).exists()

        if stale:
            _refresh_o365()

        result = {}
        for r in ChatbotCache.objects.filter(source='office365', data_type='license_summary', success=True):
            age_min = int((timezone.now() - r.fetched_at).total_seconds() / 60)
            result[r.company_key or 'default'] = {
                'licenses': r.payload,
                'age_minutes': age_min,
            }
        return result
    except Exception as exc:
        logger.error('O365 context error: %s', exc)
        return {'error': str(exc)}


def _datto_context() -> dict:
    """Get Datto backup data from cache; refresh if older than 30 min."""
    try:
        from chatbot.models import ChatbotCache

        cutoff = timezone.now() - timedelta(minutes=30)
        rec = ChatbotCache.objects.filter(source='datto', success=True, fetched_at__gte=cutoff).first()
        if not rec:
            _refresh_datto()
            rec = ChatbotCache.objects.filter(source='datto', success=True).first()

        if rec:
            age_min = int((timezone.now() - rec.fetched_at).total_seconds() / 60)
            return {'data': rec.payload, 'age_minutes': age_min}
        return {'error': 'No Datto data'}
    except Exception as exc:
        logger.error('Datto context error: %s', exc)
        return {'error': str(exc)}


def _refresh_o365():
    try:
        from office365.services import Office365API
        from chatbot.models import ChatbotCache

        api     = Office365API()
        summary = api.get_license_summary()
        ChatbotCache.objects.update_or_create(
            source='office365', data_type='license_summary', company_key='default',
            defaults={'payload': summary, 'success': True, 'error': ''},
        )
        logger.info('O365 cache refreshed (%d SKUs)', len(summary))
    except Exception as exc:
        logger.error('O365 refresh failed: %s', exc)


def _refresh_datto():
    try:
        from datto.datto_client import DattoClient
        from chatbot.models import ChatbotCache

        client  = DattoClient()
        storage = client.get_dtc_storage_pool()
        devices = client.get_devices()
        payload = {
            'storage': storage if isinstance(storage, list) else [storage],
            'devices': devices.get('items', []) if isinstance(devices, dict) else [],
        }
        ChatbotCache.objects.update_or_create(
            source='datto', data_type='all', company_key='',
            defaults={'payload': payload, 'success': True, 'error': ''},
        )
        logger.info('Datto cache refreshed')
    except Exception as exc:
        logger.error('Datto refresh failed: %s', exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg_lower(msg: str) -> str:
    return msg.lower()

def _needs(msg_l: str, keywords: set) -> bool:
    return any(k in msg_l for k in keywords)

def _is_analysis(msg_l: str) -> bool:
    return any(k in msg_l for k in _ANALYSIS_KEYWORDS)

def _get_companies() -> str:
    try:
        from rbac.models import Company
        names = list(Company.objects.values_list('name', flat=True).order_by('name'))
        return ', '.join(names) if names else 'CG Logistics, Market Xcel, Digtinctive, Wepsol'
    except Exception:
        return 'CG Logistics, Market Xcel, Digtinctive, Wepsol'

def _get_technicians() -> str:
    try:
        from tickets.models import TicketCache
        techs = list(
            TicketCache.objects.exclude(technician_name='').exclude(technician_name__isnull=True)
            .values_list('technician_name', flat=True).distinct().order_by('technician_name')[:25]
        )
        return ', '.join(techs) if techs else 'Various'
    except Exception:
        return 'Various'


# ── Main engine ───────────────────────────────────────────────────────────────

class ClaudeChatEngine:
    """
    Intelligent chatbot engine.
    Uses Claude API when available; falls back to keyword engine.
    """

    def __init__(self):
        self._client   = None
        self._ready    = None  # None = unchecked, True/False = result

    # ── API client ──────────────────────────────────────────────────────────

    def _init_client(self):
        if self._ready is not None:
            return
        try:
            import anthropic
            key = (
                getattr(settings, 'ANTHROPIC_API_KEY', None)
                or __import__('os').environ.get('ANTHROPIC_API_KEY')
            )
            if key:
                self._client = anthropic.Anthropic(api_key=key)
                self._ready  = True
                logger.info('ClaudeChatEngine: API ready (%s)', _FAST_MODEL)
            else:
                logger.warning('ClaudeChatEngine: ANTHROPIC_API_KEY not set — using fallback')
                self._ready = False
        except ImportError:
            logger.warning('ClaudeChatEngine: anthropic package not installed — using fallback')
            self._ready = False

    @property
    def available(self) -> bool:
        self._init_client()
        return bool(self._ready)

    # ── Data context builder ─────────────────────────────────────────────────

    def _build_context(self, message: str) -> str:
        msg_l  = _msg_lower(message)
        blocks = []

        # Tickets — always included (fast, from DB)
        blocks.append('=== LIVE TICKET DATA (synced every 5 min) ===')
        blocks.append(json.dumps(_ticket_context(), indent=2, default=str))

        if _needs(msg_l, _NEEDS_PULSEWAY) or 'all' in msg_l or 'overview' in msg_l:
            blocks.append('\n=== LIVE PULSEWAY DEVICE DATA (synced every 30 min) ===')
            blocks.append(json.dumps(_pulseway_context(), indent=2, default=str))

        if _needs(msg_l, _NEEDS_MDM):
            blocks.append('\n=== LIVE MDM DEVICE DATA (live API) ===')
            blocks.append(json.dumps(_mdm_context(), indent=2, default=str))

        if _needs(msg_l, _NEEDS_O365):
            blocks.append('\n=== OFFICE 365 LICENSE DATA (auto-refreshed ≤30 min) ===')
            blocks.append(json.dumps(_o365_context(), indent=2, default=str))

        if _needs(msg_l, _NEEDS_DATTO):
            blocks.append('\n=== DATTO BACKUP DATA (auto-refreshed ≤30 min) ===')
            blocks.append(json.dumps(_datto_context(), indent=2, default=str))

        return '\n'.join(blocks)

    # ── Claude call ──────────────────────────────────────────────────────────

    def _call_claude(self, message: str, history: list) -> str:
        now    = datetime.now()
        system = _SYSTEM_PROMPT.format(
            today=now.strftime('%A, %B %d, %Y'),
            time=now.strftime('%H:%M'),
            companies=_get_companies(),
            technicians=_get_technicians(),
        )

        data_block = self._build_context(message)

        # Build message list from history (last 8 exchanges)
        api_messages = []
        for h in (history or [])[-8:]:
            api_messages.append({'role': h['role'], 'content': h['content']})

        # Attach live data to current user message
        full_user = (
            f"{message}\n\n"
            f"--- LIVE DATA (fetched at {now.strftime('%H:%M:%S')}) ---\n"
            f"{data_block}"
        )
        api_messages.append({'role': 'user', 'content': full_user})

        model = _SMART_MODEL if _is_analysis(_msg_lower(message)) else _FAST_MODEL

        resp = self._client.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=api_messages,
        )
        return resp.content[0].text if resp.content else 'No response generated.'

    # ── Public interface ─────────────────────────────────────────────────────

    def chat(self, message: str, history: list = None) -> dict:
        """
        Process a message with full live context.
        history: list of {'role': 'user'|'assistant', 'content': str}
        """
        if not self.available:
            # Fall back to the existing keyword engine
            try:
                from chatbot.intelligent_ai import get_chatbot
                result = get_chatbot().chat(message)
                result['source'] = 'keyword_fallback'
                return result
            except Exception as exc:
                return {
                    'response': (
                        'AI assistant is not configured. '
                        'Please set ANTHROPIC_API_KEY in your environment or settings.py.'
                    ),
                    'intent': 'error',
                    'entities': {},
                    'source': 'unavailable',
                }

        try:
            response_text = self._call_claude(message, history)
            return {
                'response': response_text,
                'intent':   'claude_response',
                'entities': {'model': _SMART_MODEL if _is_analysis(_msg_lower(message)) else _FAST_MODEL},
                'source':   'claude',
            }
        except Exception as exc:
            logger.error('Claude API error: %s', exc)
            # Try keyword fallback
            try:
                from chatbot.intelligent_ai import get_chatbot
                result = get_chatbot().chat(message)
                result['source'] = 'keyword_fallback'
                return result
            except Exception:
                return {
                    'response': f'AI error: {str(exc)[:120]}. Please try again.',
                    'intent':   'error',
                    'entities': {},
                    'source':   'error',
                }


# ── Module-level singleton ────────────────────────────────────────────────────

_engine: ClaudeChatEngine | None = None

def get_engine() -> ClaudeChatEngine:
    global _engine
    if _engine is None:
        _engine = ClaudeChatEngine()
    return _engine
