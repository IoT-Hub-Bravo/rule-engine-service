import jwt
from django.conf import settings
from functools import wraps
from django.http import JsonResponse

def jwt_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return JsonResponse({"code": 401, "message": "Unauthorized"}, status=401)
        try:
            payload = jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return JsonResponse({"code": 401, "message": "Token expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"code": 401, "message": "Invalid token"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper