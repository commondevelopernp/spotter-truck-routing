from datetime import datetime, timedelta, timezone

from rest_framework import serializers

MAX_DEPARTURE_AHEAD = timedelta(days=7)
MAX_DEPARTURE_PAST = timedelta(hours=1)


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200, trim_whitespace=True)
    destination = serializers.CharField(max_length=200, trim_whitespace=True)
    departure = serializers.DateTimeField(help_text="ISO 8601 with offset, e.g. 2026-11-18T08:00:00-06:00")
    load_lbs = serializers.FloatField(min_value=0, max_value=200_000)
    interval_mi = serializers.ChoiceField(choices=[10, 25, 50], default=25)
    hos = serializers.BooleanField(default=True)

    def validate_departure(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if value < now - MAX_DEPARTURE_PAST:
            raise serializers.ValidationError("Departure must not be in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Departure must be within the next 7 days (forecast range).")
        return value

    def validate(self, attrs):
        if attrs["origin"].strip().lower() == attrs["destination"].strip().lower():
            raise serializers.ValidationError({"destination": "Destination must differ from origin."})
        return attrs
