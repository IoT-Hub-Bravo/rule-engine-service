from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError

def health_check(request):
    db_ok = True

    try:
        connections['default'].cursor()
    except OperationalError:
        db_ok = False

    status = "ok" if db_ok else "degraded"

    return JsonResponse({
        "status": status,
        "database": db_ok,
    }, status=200 if db_ok else 503)