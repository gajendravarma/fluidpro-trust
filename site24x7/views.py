from django.shortcuts import render
from django.http import JsonResponse
from .site24x7_client import Site24x7Platform
import json

def dashboard(request):
    return render(request, 'site24x7/dashboard.html')

def api_data(request):
    data_type = request.GET.get('type', 'customers')
    zaaid = request.GET.get('zaaid')
    
    platform = Site24x7Platform()
    
    try:
        if data_type == 'customers':
            data = platform.get_customers()
        elif data_type == 'monitors':
            data = platform.get_monitors(zaaid=zaaid)
        elif data_type == 'current_status':
            data = platform.get_current_status(zaaid=zaaid)
        elif data_type == 'reports':
            monitor_id = request.GET.get('monitor_id')
            period = request.GET.get('period', 1)
            data = platform.get_reports(monitor_id, period=period, zaaid=zaaid)
        else:
            data = {'error': 'Invalid data type'}
        
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def customer_monitors(request, customer_id):
    platform = Site24x7Platform()
    try:
        # Decode customer ID if it's base64 encoded
        decoded_zaaid = Site24x7Platform.decode_zaaid(customer_id)
        monitors = platform.get_monitors(zaaid=decoded_zaaid)
        return JsonResponse({'monitors': monitors})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def monitor_details(request, monitor_id):
    zaaid = request.GET.get('zaaid')
    platform = Site24x7Platform()
    try:
        details = platform.get_monitor_details(monitor_id, zaaid=zaaid)
        return JsonResponse({'details': details})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
