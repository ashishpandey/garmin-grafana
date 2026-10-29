from io import BytesIO
from unittest.mock import Mock
import zipfile

import pytest

from garmin_grafana.garmin_official_api import (
    OfficialActivityDownloadFormat,
    OfficialGarminApiAdapter,
    UnsupportedOfficialApiOperation,
)


def adapter_with_client(client):
    adapter = OfficialGarminApiAdapter.__new__(OfficialGarminApiAdapter)
    adapter._client = client
    adapter.ActivityDownloadFormat = OfficialActivityDownloadFormat
    adapter.display_name = "test-user"
    return adapter


def test_supported_daily_methods_use_official_wrappers():
    client = Mock()
    client.get_daily_summaries.return_value = [{"calendarDate": "2026-10-29", "totalSteps": 42}]
    client.get_daily_sleep.return_value = {"dailySleepDTO": {"id": 123}}
    client.get_daily_steps.return_value = [{"calendarDate": "2026-10-29", "totalSteps": 42}]

    adapter = adapter_with_client(client)

    assert adapter.get_stats("2026-10-29") == {"calendarDate": "2026-10-29", "totalSteps": 42}
    assert adapter.get_sleep_data("2026-10-29") == {"dailySleepDTO": {"id": 123}}
    assert adapter.get_steps_data("2026-10-29") == [{"calendarDate": "2026-10-29", "totalSteps": 42}]
    client.get_daily_summaries.assert_called_once_with("2026-10-29", "2026-10-29")
    client.get_daily_sleep.assert_called_once_with("2026-10-29")
    client.get_daily_steps.assert_called_once_with("2026-10-29", "2026-10-29")


def test_original_activity_download_returns_official_zip():
    zip_bytes = b"official activity zip"
    client = Mock()
    client.download_activity.return_value = zip_bytes
    adapter = adapter_with_client(client)

    assert adapter.download_activity(123, OfficialActivityDownloadFormat.ORIGINAL) == zip_bytes
    client.download_activity.assert_called_once_with(123)


def test_tcx_activity_download_extracts_tcx_from_zip():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("activity.tcx", "<TrainingCenterDatabase />")

    client = Mock()
    client.download_activity.return_value = output.getvalue()
    adapter = adapter_with_client(client)

    result = adapter.download_activity(123, OfficialActivityDownloadFormat.TCX)

    assert result == b"<TrainingCenterDatabase />"


def test_unsupported_operation_fails_explicitly():
    adapter = adapter_with_client(Mock())

    with pytest.raises(UnsupportedOfficialApiOperation, match="get_training_status"):
        adapter.get_training_status("2026-10-29")
