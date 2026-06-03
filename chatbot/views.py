from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import uuid
from datetime import datetime
from .models import ChatSession, ChatMessage
from .ollama_engine import get_engine, reset_engine


@login_required
def chat_interface(request):
    engine = get_engine()
    return render(request, 'chatbot/chat.html', {
        'engine_available': engine.available,
        'engine_model':     engine.model_name,
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """Process a chat message with Ollama AI + live DB data."""
    try:
        data       = json.loads(request.body)
        message    = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        # Get or create session
        session = None
        if session_id:
            session = ChatSession.objects.filter(session_id=session_id, user=request.user).first()
        if not session:
            session = ChatSession.objects.create(
                user=request.user,
                session_id=str(uuid.uuid4()),
            )

        # Build conversation history (last 10 exchanges = 20 messages, oldest first)
        history = []
        for msg in session.messages.order_by('-timestamp')[:10]:
            history.insert(0, {'role': 'assistant', 'content': msg.response})
            history.insert(0, {'role': 'user',      'content': msg.message})

        # Call Ollama engine
        engine = get_engine()
        result = engine.chat(message, history=history)

        # Persist to DB
        ChatMessage.objects.create(
            session=session,
            message=message,
            response=result['response'],
            intent=result.get('intent', ''),
            entities=result.get('entities', {}),
        )
        session.save()

        return JsonResponse({
            'response':   result['response'],
            'session_id': session.session_id,
            'intent':     result.get('intent', ''),
            'source':     result.get('source', 'unknown'),
            'model':      result.get('entities', {}).get('model', ''),
            'timestamp':  datetime.now().isoformat(),
        })

    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
def chat_history(request):
    """Return recent chat history for the current user."""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:5]
    history  = []
    for session in sessions:
        msgs = session.messages.order_by('timestamp')[:30]
        history.append({
            'session_id': session.session_id,
            'created_at': session.created_at.isoformat(),
            'messages': [
                {
                    'message':   m.message,
                    'response':  m.response,
                    'intent':    m.intent,
                    'timestamp': m.timestamp.isoformat(),
                }
                for m in msgs
            ],
        })
    return JsonResponse({'history': history})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def new_session(request):
    """Start a fresh chat session."""
    session = ChatSession.objects.create(
        user=request.user,
        session_id=str(uuid.uuid4()),
    )
    return JsonResponse({'session_id': session.session_id})


@login_required
def engine_status(request):
    """Return current AI engine status — used by UI to show correct badge."""
    reset_engine()   # re-probe Ollama on each status check
    engine = get_engine()
    return JsonResponse({
        'available': engine.available,
        'model':     engine.model_name,
        'type':      'ollama' if engine.available else 'keyword_fallback',
    })
