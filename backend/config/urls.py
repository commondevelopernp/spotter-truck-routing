from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound
from django.urls import include, path, re_path


def spa_index(request):
    """Serve the built React app for any non-API path (client-side routing)."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponseNotFound("Frontend not built. Run `npm run build` in frontend/ or use the Vite dev server.")
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("api/", include("planner.urls")),
    re_path(r"^(?!api/).*$", spa_index),
]
