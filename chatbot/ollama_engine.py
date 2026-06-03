"""
chatbot/ollama_engine.py
100% Open-Source AI chatbot engine powered by Ollama + Llama 3.2.

No API key. No internet calls. Runs fully locally.

Requirements:
  1. Install Ollama: https://ollama.com/download  (Windows installer)
  2. Pull model:     ollama pull llama3.2:3b
  3. pip install ollama langchain-ollama langchain-community langchain

Architecture:
  User message
       │
       ▼
  Live DB data fetcher  (tickets, devices, licenses — from Django models)
       │
       ▼
  Conversation history  (last 10 exchanges from DB)
       │
       ▼
  Ollama LLM (Llama 3.2:3B running locally)
       │
       ▼
  Natural language response
"""

import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Model config ──────────────────────────────────────────────────────────────
# Primary model: best balance of quality vs speed on CPU (2GB RAM usage)
PRIMARY_MODEL  = 'llama3.2:3b'
# Fallback if primary not pulled yet
FALLBACK_MODEL = 'phi3:mini'

OLLAMA_HOST = getattr(settings, 'OLLAMA_HOST', 'http://127.0.0.1:11434')


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """You are FluidTrust AI — an intelligent IT operations assistant for Wepsol, a managed IT service provider.

Today: {today}. Time: {time}.

You have access to LIVE data from all IT systems fetched fresh for this query (provided below). Use it to answer accurately.

## Your Capabilities
- Answer questions about support tickets, devices, licenses, backups
- Detect and flag urgent issues: critical open tickets, offline devices, near-exhausted licenses
- Analyze trends: today vs yesterday, this week vs last week
- Make recommendations: which technician to assign, what needs immediate attention
- Compare companies: identify outliers and performance differences
- Remember our full conversation history and answer follow-up questions

## Companies Managed
{companies}

## Active Technicians
{technicians}

## Response Style
- Use **bold** for key numbers and names
- Use bullet points for lists, tables for comparisons
- Flag ⚠️ urgent issues immediately
- For trend questions calculate the delta (e.g. "+3 from yesterday")
- Be concise but complete
- If you spot anomalies in the data, mention them proactively

## Rules
- NEVER invent numbers not present in the live data below
- NEVER say "I don't have access" when data IS provided
- If a question is unrelated to IT operations, politely redirect
- Always base answers on the LIVE DATA section below"""


# ── Live data fetchers ────────────────────────────────────────────────────────

def _ticket_data() -> dict:
    try:
        from tickets.models import TicketCache
        from django.db.models import Count, Q

        qs    = TicketCache.objects.all()
        today = timezone.now().date()

        by_status   = dict(qs.values_list('status').annotate(n=Count('id')).values_list('status', 'n'))
        by_priority = dict(qs.values_list('priority').annotate(n=Count('id')).values_list('priority', 'n'))
        time_counts = {
            'today':     qs.filter(created_at__date=today).count(),
            'yesterday': qs.filter(created_at__date=today - timedelta(days=1)).count(),
            'this_week': qs.filter(created_at__date__gte=today - timedelta(days=7)).count(),
            'last_week': qs.filter(
                created_at__date__gte=today - timedelta(days=14),
                created_at__date__lt=today - timedelta(days=7),
            ).count(),
        }
        open_by_company = dict(
            qs.filter(status='Open')
            .values_list('company_name').annotate(n=Count('id'))
            .order_by('-n')[:10].values_list('company_name', 'n')
        )
        tech_load = dict(
            qs.filter(status__in=['Open', 'Pending', 'In Progress'])
            .exclude(technician_name__isnull=True).exclude(technician_name='')
            .values_list('technician_name').annotate(n=Count('id'))
            .order_by('-n')[:10].values_list('technician_name', 'n')
        )
        unassigned = qs.filter(status='Open').filter(
            Q(technician_name__isnull=True) | Q(technician_name='')
        ).count()
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
            'time_counts': time_counts,
            'open_by_company': open_by_company,
            'technician_active_load': tech_load,
            'unassigned_open': unassigned,
            'urgent_high_open': critical,
        }
    except Exception as e:
        logger.error('Ticket data error: %s', e)
        return {'error': str(e)}


def _pulseway_data() -> dict:
    try:
        from pulseway.models import PulsewayDevice
        from django.db.models import Count, Sum, Q

        qs     = PulsewayDevice.objects.all()
        total  = qs.count()
        online = qs.filter(is_online=True).count()

        by_company = {}
        for row in qs.values('organization_name').annotate(
            total=Count('id'),
            online=Count('id', filter=Q(is_online=True)),
            patches=Sum('pending_patches')
        ).order_by('organization_name'):
            name = row['organization_name'] or 'Unknown'
            by_company[name] = {
                'total':  row['total'],
                'online': row['online'],
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
    except Exception as e:
        logger.error('Pulseway data error: %s', e)
        return {'error': str(e)}


def _mdm_data() -> dict:
    try:
        from mdm.live_service import get_all_customers, get_mdm_stats
        customers  = get_all_customers()
        stats      = get_mdm_stats(customers)
        by_company = {}
        for d in stats.get('devices', []):
            co = d['customer_name'] or 'Unknown'
            if co not in by_company:
                by_company[co] = {'total': 0, 'active': 0}
            by_company[co]['total'] += 1
            if d['status'] == 'active':
                by_company[co]['active'] += 1
        return {'total': stats['total'], 'active': stats['active'], 'by_company': by_company}
    except Exception as e:
        logger.error('MDM data error: %s', e)
        return {'error': str(e)}


def _o365_data() -> dict:
    try:
        from chatbot.models import ChatbotCache
        records = {}
        for r in ChatbotCache.objects.filter(source='office365', data_type='license_summary', success=True):
            age = int((timezone.now() - r.fetched_at).total_seconds() / 60)
            records[r.company_key or 'default'] = {'licenses': r.payload, 'age_minutes': age}
        return records
    except Exception as e:
        logger.error('O365 data error: %s', e)
        return {'error': str(e)}


def _datto_data() -> dict:
    try:
        from chatbot.models import ChatbotCache
        rec = ChatbotCache.objects.filter(source='datto', success=True).order_by('-fetched_at').first()
        if rec:
            age = int((timezone.now() - rec.fetched_at).total_seconds() / 60)
            return {'data': rec.payload, 'age_minutes': age}
        return {'error': 'No Datto data cached'}
    except Exception as e:
        logger.error('Datto data error: %s', e)
        return {'error': str(e)}


# ── Keyword classifiers ───────────────────────────────────────────────────────

_DEVICE_KW  = {'device', 'pulseway', 'online', 'offline', 'patch', 'monitor', 'rmm', 'agent'}
_MDM_KW     = {'mdm', 'mobile', 'phone', 'android', 'iphone', 'enrolled', 'tablet'}
_O365_KW    = {'office', '365', 'license', 'email', 'teams', 'microsoft', 'sharepoint', 'exchange'}
_DATTO_KW   = {'datto', 'backup', 'storage', 'bcdr', 'disaster', 'recovery'}


def _needs(msg: str, kw: set) -> bool:
    return any(k in msg for k in kw)


def _build_live_context(message: str) -> str:
    msg_l  = message.lower()
    blocks = []

    blocks.append('=== LIVE TICKET DATA ===')
    blocks.append(json.dumps(_ticket_data(), indent=2, default=str))

    if _needs(msg_l, _DEVICE_KW) or 'overview' in msg_l or 'all' in msg_l:
        blocks.append('\n=== LIVE PULSEWAY DEVICE DATA ===')
        blocks.append(json.dumps(_pulseway_data(), indent=2, default=str))

    if _needs(msg_l, _MDM_KW):
        blocks.append('\n=== LIVE MDM DATA ===')
        blocks.append(json.dumps(_mdm_data(), indent=2, default=str))

    if _needs(msg_l, _O365_KW):
        blocks.append('\n=== OFFICE 365 LICENSE DATA ===')
        blocks.append(json.dumps(_o365_data(), indent=2, default=str))

    if _needs(msg_l, _DATTO_KW):
        blocks.append('\n=== DATTO BACKUP DATA ===')
        blocks.append(json.dumps(_datto_data(), indent=2, default=str))

    return '\n'.join(blocks)


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
            .values_list('technician_name', flat=True).distinct().order_by('technician_name')[:20]
        )
        return ', '.join(techs) if techs else 'Various'
    except Exception:
        return 'Various'


# ── Ollama engine ─────────────────────────────────────────────────────────────

class OllamaEngine:
    """
    Open-source chatbot engine using Ollama local LLM.
    Supports conversation history, live DB data, and natural language understanding.
    """

    def __init__(self):
        self._client  = None
        self._model   = None
        self._ready   = None   # None = unchecked

    def _init(self):
        if self._ready is not None:
            return
        try:
            import ollama as _ollama
            # Check Ollama server is reachable and find a suitable model
            models = _ollama.list()
            available = [m.model for m in models.models] if hasattr(models, 'models') else []

            preferred = [PRIMARY_MODEL, FALLBACK_MODEL, 'llama3.2', 'llama3', 'mistral', 'phi3']
            chosen = None
            for pref in preferred:
                match = next((m for m in available if pref in m.lower()), None)
                if match:
                    chosen = match
                    break

            if chosen:
                self._client = _ollama
                self._model  = chosen
                self._ready  = True
                logger.info('OllamaEngine ready — model: %s', chosen)
            else:
                logger.warning(
                    'OllamaEngine: no suitable model found. Pull one with: ollama pull llama3.2:3b\n'
                    'Available: %s', available
                )
                self._ready = False
        except Exception as e:
            logger.warning('OllamaEngine unavailable: %s', e)
            self._ready = False

    @property
    def available(self) -> bool:
        self._init()
        return bool(self._ready)

    @property
    def model_name(self) -> str:
        self._init()
        return self._model or 'none'

    def chat(self, message: str, history: list = None) -> dict:
        """
        Process a message with full live context and conversation memory.

        history: list of {'role': 'user'|'assistant', 'content': str}
                 (last N exchanges from DB, oldest first)
        """
        self._init()

        if not self._ready:
            return self._fallback(message, history=history)

        try:
            now    = datetime.now()
            system = _SYSTEM.format(
                today=now.strftime('%A, %B %d, %Y'),
                time=now.strftime('%H:%M'),
                companies=_get_companies(),
                technicians=_get_technicians(),
            )

            # Build live data context
            live_data = _build_live_context(message)

            # Build message list: history + current message with live data injected
            messages = []

            # Add conversation history (last 10 exchanges = 20 messages)
            for h in (history or [])[-20:]:
                messages.append({'role': h['role'], 'content': h['content']})

            # Attach live data to the current user turn
            full_user_msg = (
                f"{message}\n\n"
                f"--- LIVE DATA (fetched {now.strftime('%H:%M:%S')}) ---\n"
                f"{live_data}"
            )
            messages.append({'role': 'user', 'content': full_user_msg})

            # Call Ollama
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options={
                    'system': system,
                    'temperature': 0.3,     # Low temp = factual, consistent
                    'num_predict': 800,     # Max tokens in response
                    'num_ctx': 4096,        # Context window
                    'top_p': 0.9,
                },
            )

            text = response['message']['content'] if isinstance(response, dict) else response.message.content

            return {
                'response': text,
                'intent':   'ollama_response',
                'entities': {'model': self._model},
                'source':   'ollama',
            }

        except Exception as e:
            logger.error('Ollama chat error: %s', e)
            return self._fallback(message, error=str(e), history=history)

    def _fallback(self, message: str, error: str = None, history: list = None) -> dict:
        """Fall back to keyword engine if Ollama is not running."""
        try:
            from chatbot.intelligent_ai import get_chatbot
            result = get_chatbot().chat(message, history=history)
            result['source'] = 'keyword_fallback'
            return result
        except Exception:
            msg = (
                'AI assistant is starting up. '
                'Make sure Ollama is running (`ollama serve`) and the model is pulled '
                f'(`ollama pull {PRIMARY_MODEL}`).'
            )
            if error:
                msg += f' Error: {error[:100]}'
            return {
                'response': msg,
                'intent':   'error',
                'entities': {},
                'source':   'unavailable',
            }


# ── Module singleton ──────────────────────────────────────────────────────────

_engine: OllamaEngine | None = None


def get_engine() -> OllamaEngine:
    global _engine
    if _engine is None:
        _engine = OllamaEngine()
    return _engine


def reset_engine():
    """Force re-detection (call after starting Ollama)."""
    global _engine
    _engine = None
