"""
Healthcheck endpoint for Railway deployment
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def healthcheck(request):
    """
    Simple healthcheck endpoint that returns 200 OK
    """
    return HttpResponse("OK", status=200)
