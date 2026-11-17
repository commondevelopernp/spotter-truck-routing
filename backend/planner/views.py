import logging
import re

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import PlanRequestSerializer
from .services import geocode
from .services.http import UpstreamError
from .services.planner import PlanError, TripRequest, heatmap, plan
from .services.routing import NoRouteFound

log = logging.getLogger(__name__)
PLAN_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _error(message: str, code: int, field: str | None = None) -> Response:
    body = {"error": message}
    if field:
        body["field"] = field
    return Response(body, status=code)


@api_view(["GET"])
def health(request):
    return Response({"ok": True})


@api_view(["GET"])
def geocode_view(request):
    q = request.query_params.get("q", "").strip()
    if len(q) < 3:
        return Response({"results": []})
    try:
        return Response({"results": geocode.search(q, limit=5)})
    except UpstreamError as exc:
        return _error(f"Geocoding is temporarily unavailable ({exc.message}).", status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
def plan_view(request):
    ser = PlanRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"error": "Invalid input.", "fields": ser.errors}, status=status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    req = TripRequest(d["origin"], d["destination"], d["departure"], d["load_lbs"], int(d["interval_mi"]), d["hos"])
    try:
        return Response(plan(req))
    except geocode.PlaceNotFound as exc:
        field = "origin" if exc.query == d["origin"] else "destination"
        return _error(str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY, field)
    except (NoRouteFound, PlanError) as exc:
        return _error(str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
    except UpstreamError as exc:
        log.warning("upstream failure: %s", exc)
        return _error(f"A data provider is unavailable right now ({exc.provider}). Please retry.", status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
def heatmap_view(request, plan_id: str):
    if not PLAN_ID_RE.match(plan_id):
        return _error("Unknown plan.", status.HTTP_404_NOT_FOUND)
    try:
        return Response(heatmap(plan_id))
    except PlanError as exc:
        return _error(str(exc), status.HTTP_404_NOT_FOUND)
    except UpstreamError as exc:
        log.warning("upstream failure: %s", exc)
        return _error(f"Weather provider unavailable ({exc.provider}). Please retry.", status.HTTP_502_BAD_GATEWAY)
