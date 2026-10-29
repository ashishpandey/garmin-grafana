"""Compatibility adapter for Garmin's official Connect Personal API client."""

from __future__ import annotations

import logging
import os
import zipfile
from datetime import date
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
    resolve_api_key,
)


class UnsupportedOfficialApiOperation(RuntimeError):
    """Raised when Garmin does not expose an operation in the Personal API."""


class OfficialActivityDownloadFormat(Enum):
    ORIGINAL = "original"
    FIT = "fit"
    TCX = "tcx"


class OfficialGarminApiAdapter:
    """Expose the official Personal API subset used by garmin-fetch.

    The adapter intentionally preserves the legacy method names used by the
    existing fetch code. Unsupported legacy operations fail explicitly instead
    of being silently reported as empty data.
    """

    def __init__(self, api_key: str, bearer_token_cache_file: str | Path | None = None):
        auth_kwargs: dict[str, Any] = {}
        if bearer_token_cache_file:
            auth_kwargs["bearer_token_cache_file"] = bearer_token_cache_file

        self._authenticator = PersonalApiAuthenticator(**auth_kwargs)
        token = self._authenticator.obtain_token(api_key)
        self._client = GarminPersonalApiClient(token.access_token)
        self.ActivityDownloadFormat = OfficialActivityDownloadFormat
        self.display_name = self._profile_value("displayName")

    def close(self) -> None:
        self._client.close()
        self._authenticator.close()

    def _profile_value(self, key: str, default: Any = None) -> Any:
        try:
            profile = self._client.get_user_profile_settings() or {}
            return profile.get(key, default)
        except Exception as err:
            logging.warning("Unable to load Garmin profile field '%s': %s", key, err)
            return default

    @staticmethod
    def _date_items(data: Any, date_field: str = "calendarDate") -> list[dict[str, Any]]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("dailySummaries", "summaries", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _for_date(data: Any, day: str, date_field: str = "calendarDate") -> dict[str, Any]:
        if isinstance(data, dict) and (not data or day in (data.get(date_field), data.get("date"))):
            return data
        for item in OfficialGarminApiAdapter._date_items(data, date_field):
            if item.get(date_field) == day or item.get("date") == day:
                return item
        return {}

    def get_stats(self, day: str) -> dict[str, Any]:
        return self._for_date(self._client.get_daily_summaries(day, day), day)

    def get_sleep_data(self, day: str) -> dict[str, Any]:
        return self._client.get_daily_sleep(day) or {}

    def get_steps_data(self, day: str) -> list[dict[str, Any]]:
        data = self._client.get_daily_steps(day, day) or []
        return self._date_items(data)

    def get_stress_data(self, day: str) -> dict[str, Any]:
        return self._for_date(self._client.get_daily_stress(day, day), day)

    def get_body_battery(self, start_date: str, end_date: str) -> Any:
        return self._client.get_daily_body_battery(start_date, end_date)

    def get_heart_rates(self, day: str) -> dict[str, Any]:
        return self._client.get_daily_heart_rate(day) or {}

    def get_hrv_data(self, day: str) -> dict[str, Any]:
        return self._client.get_daily_hrv(day) or {}

    def get_weigh_ins(self, start_date: str, end_date: str) -> dict[str, Any]:
        data = self._client.get_weight_measurements(start_date, end_date)
        if isinstance(data, dict):
            return data
        return {"dailyWeightSummaries": data or []}

    def get_hydration_data(self, day: str) -> dict[str, Any]:
        data = self._client.get_daily_hydration(day, day) or []
        return self._for_date(data, day)

    def get_fitnessage_data(self, day: str) -> dict[str, Any]:
        return self._client.get_fitness_age(day) or {}

    def get_activities_by_date(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        activities = self._client.search_activities(start=0, limit=100, start_date=start_date, end_date=end_date)
        return activities if isinstance(activities, list) else activities or []

    def get_activity(self, activity_id: Any) -> dict[str, Any]:
        return self._client.get_activity(activity_id) or {}

    def get_activity_workouts(self, activity_id: Any) -> Any:
        return self._client.get_activity_workouts(activity_id)

    def download_activity(self, activity_id: Any, dl_fmt: Any = None) -> bytes:
        zip_data = self._client.download_activity(activity_id)
        if dl_fmt == OfficialActivityDownloadFormat.TCX:
            with zipfile.ZipFile(BytesIO(zip_data)) as archive:
                tcx_names = [name for name in archive.namelist() if name.lower().endswith(".tcx")]
                fit_names = [name for name in archive.namelist() if name.lower().endswith(".fit")]
                if tcx_names:
                    return archive.read(tcx_names[0])
                if fit_names:
                    raise UnsupportedOfficialApiOperation(
                        "The official activity ZIP contains FIT data but no TCX export"
                    )
                raise UnsupportedOfficialApiOperation(
                    "The official activity ZIP contains no TCX file"
                )
        return zip_data

    def connectapi(self, path: str, params: dict[str, Any] | None = None, method: str = "GET", **_: Any) -> Any:
        if method.upper() != "GET":
            raise UnsupportedOfficialApiOperation(
                "The official Personal API client supports authenticated GET requests only"
            )
        return self._client.get(path, params=params)

    def _unsupported(self, operation: str) -> None:
        raise UnsupportedOfficialApiOperation(
            f"'{operation}' is not exposed by the official Garmin Connect Personal API client"
        )

    def get_respiration_data(self, day: str) -> dict[str, Any]:
        self._unsupported("get_respiration_data")

    def get_training_status(self, day: str) -> dict[str, Any]:
        self._unsupported("get_training_status")

    def get_training_readiness(self, day: str) -> dict[str, Any]:
        self._unsupported("get_training_readiness")

    def get_hill_score(self, day: str) -> dict[str, Any]:
        self._unsupported("get_hill_score")

    def get_race_predictions(self, **_: Any) -> dict[str, Any]:
        self._unsupported("get_race_predictions")

    def get_max_metrics(self, day: str) -> dict[str, Any]:
        self._unsupported("get_max_metrics")

    def get_endurance_score(self, day: str) -> dict[str, Any]:
        self._unsupported("get_endurance_score")

    def get_blood_pressure(self, *_: Any) -> dict[str, Any]:
        self._unsupported("get_blood_pressure")

    def get_device_solar_data(self, *_: Any) -> dict[str, Any]:
        self._unsupported("get_device_solar_data")

    def get_lifestyle_logging_data(self, *_: Any) -> dict[str, Any]:
        self._unsupported("get_lifestyle_logging_data")

    def get_activity_exercise_sets(self, *_: Any) -> dict[str, Any]:
        self._unsupported("get_activity_exercise_sets")

    def get_activity_hr_in_timezones(self, *_: Any) -> dict[str, Any]:
        self._unsupported("get_activity_hr_in_timezones")

    def get_device_last_used(self) -> dict[str, Any]:
        self._unsupported("get_device_last_used")

    def get_last_activity(self) -> dict[str, Any]:
        self._unsupported("get_last_activity")


def garmin_official_login() -> OfficialGarminApiAdapter:
    """Create the official Personal API adapter from environment configuration."""
    api_key = os.getenv("GARMIN_PERSONAL_API_KEY", "").strip()
    key_file = os.getenv("GARMIN_PERSONAL_API_KEY_FILE")

    try:
        if api_key or key_file:
            resolved_key = resolve_api_key(api_key=api_key or None, key_file=key_file)
        else:
            resolved_key = resolve_api_key()
    except (OSError, RuntimeError, ValueError) as err:
        raise RuntimeError("Unable to resolve Garmin Personal API key") from err

    cache_file = os.getenv("GARMIN_PERSONAL_API_BEARER_CACHE")
    adapter = OfficialGarminApiAdapter(resolved_key, cache_file)
    logging.info("Authenticated with Garmin Connect Personal API")
    return adapter
