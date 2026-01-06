from django.shortcuts import render
from django.http import JsonResponse
from .datto_client import DattoClient

def dashboard(request):
    return render(request, 'datto/dashboard.html')

def api_data(request):
    api_type = request.GET.get('type', 'all')
    client = DattoClient()
    data = {}
    
    try:
        if api_type in ['all', 'bcdr_devices']:
            try:
                data['bcdr_devices'] = client.get_devices()
            except Exception as e:
                data['bcdr_devices'] = {'items': [], 'error': str(e)}
                
        if api_type in ['all', 'bcdr_agents']:
            try:
                data['bcdr_agents'] = client.get_agents()
            except Exception as e:
                data['bcdr_agents'] = {'clients': [], 'error': str(e)}
                
        if api_type in ['all', 'dtc_assets']:
            try:
                data['dtc_assets'] = client.get_dtc_assets()
            except Exception as e:
                data['dtc_assets'] = {'items': [], 'error': str(e)}
                
        if api_type in ['all', 'dtc_storage']:
            try:
                storage_data = client.get_dtc_storage_pool()
                data['dtc_storage'] = storage_data if isinstance(storage_data, list) else [storage_data]
            except Exception as e:
                data['dtc_storage'] = {'error': str(e)}
                
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse(data)

def dtc_client_assets(request, client_id):
    client = DattoClient()
    try:
        data = client.get_dtc_client_assets(client_id)
        return JsonResponse({'assets': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
