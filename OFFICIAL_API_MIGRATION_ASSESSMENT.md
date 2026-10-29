# Garmin Connect Personal API Migration Assessment

> **Date:** 2026-10-29
>
> **Subject:** Compatibility of Garmin's official `connect-personal-api-python` library with `garmin-grafana`

## Verdict

A switch from `python-garminconnect` to Garmin's official Connect Personal API Python library is technically possible, but **it cannot preserve all current functionality today**.

The official library is a smaller, newer client focused on Personal API authentication and health/activity data access. Some advanced Garmin Connect endpoints currently used by `garmin-grafana` are not exposed as dedicated wrappers or documented as part of the Personal API endpoint set.

## Official Library Characteristics

- Package: `garmin-connect-personal-api-python`
- GitHub repository: [`garmin/connect-personal-api-python`](https://github.com/garmin/connect-personal-api-python)
- Python requirement: Python 3.12 or newer
- Authentication: Personal API key
- Token exchange: API key is exchanged for a bearer token
- Token cache: bearer token cached locally by the library
- Default key environment variable: `GARMIN_PERSONAL_API_KEY`
- Data access: dedicated convenience wrappers plus generic authenticated `get()` requests
- Activity downloads: returns activity ZIP bytes
- License: Apache 2.0

This repository already requires Python 3.13, so its Python runtime is compatible.

## Current Authentication Model

`garmin-grafana` currently uses `python-garminconnect`, which:

- Accepts Garmin Connect email and password
- Supports MFA during login
- Stores Garmin OAuth session tokens
- Can use persisted session tokens across container restarts
- Supports credentials supplied through environment variables or an interactive prompt

## Proposed Official Authentication Model

The official library uses a Personal API key to obtain and cache bearer tokens:

```python
from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
)

with PersonalApiAuthenticator() as authenticator:
    token = authenticator.obtain_token(api_key)

with GarminPersonalApiClient(token.access_token) as client:
    sleep = client.get_daily_sleep("2026-08-24")
```

An API key can be supplied directly, resolved from `GARMIN_PERSONAL_API_KEY`, or loaded from a key file. The key replaces the email/password and OAuth-login flow. The official library still caches credentials locally, so deployments should protect the key file and bearer-token cache with appropriate filesystem permissions.

## Compatibility Summary

| Existing functionality | Official API/library support |
| --- | --- |
| Daily summaries | Supported |
| Sleep | Supported |
| Steps | Supported |
| Stress | Supported |
| Hydration | Supported |
| Heart rate | Supported |
| HRV | Supported |
| Body battery | Supported |
| Fitness age | Supported |
| Weight measurements | Supported |
| Activities and activity details | Supported |
| Activity workouts | Supported |
| Activity ZIP/FIT download | Supported |
| Weather/device-specific activity fields | Supported if those fields remain in official activity responses |
| Respiration | Not exposed as a dedicated wrapper |
| Blood pressure | Not exposed as a dedicated wrapper |
| Race predictions | Not exposed as a dedicated wrapper |
| Training status/readiness | Not exposed as a dedicated wrapper |
| Hill score | Not exposed as a dedicated wrapper |
| Endurance score | Not exposed as a dedicated wrapper |
| Lactate threshold | Not exposed as a dedicated wrapper |
| Exercise sets and strength activity details | Not exposed as a dedicated wrapper |
| Solar intensity | Not exposed as a dedicated wrapper |
| Lifestyle logging | Not exposed as a dedicated wrapper |
| Last-used device information | No documented wrapper |

## Client Method Audit

The existing fetch implementation directly uses the following Garmin client capabilities:

```text
ActivityDownloadFormat
connectapi
display_name
download_activity
get_activities_by_date
get_activity_exercise_sets
get_activity_hr_in_timezones
get_blood_pressure
get_device_last_used
get_device_solar_data
get_endurance_score
get_fitnessage_data
get_heart_rates
get_hill_score
get_hrv_data
get_hydration_data
get_last_activity
get_lifestyle_logging_data
get_max_metrics
get_race_predictions
get_respiration_data
get_sleep_data
get_stats
get_steps_data
get_stress_data
get_training_readiness
get_training_status
get_weigh_ins
```

The official client currently has dedicated wrappers for a smaller endpoint set, including:

- Daily stress and steps
- Daily hydration
- Weight measurements
- Daily food logs
- User profile settings
- Daily sleep and sleep summaries
- Daily body battery
- Daily summaries
- Daily HRV and HRV summaries
- Heart-rate zones
- Fitness age
- Daily heart rate
- Menstrual cycle endpoints
- Daily SpO2
- Wellness activity summaries
- Activity search and details
- Activity workouts
- Activity downloads

This repository uses `connectapi()` for endpoints that are not represented by dedicated `python-garminconnect` methods. Generic access may also be available through the official `GarminPersonalApiClient.get()` method, but endpoint availability and response schemas must still be verified against the official Personal API.

## Unsupported or Unverified Functionality

The following functionality has not been confirmed through dedicated official-library wrappers and is therefore at risk in a direct migration:

- Training readiness and training status
- Lactate threshold
- Race predictions
- Hill score and endurance score
- Blood pressure summaries
- Respiration data
- Device solar data
- Lifestyle logging
- Strength exercise sets
- Activity heart-rate zones
- Last-used device name and device identifier

These capabilities may:

- Be absent from the Personal API;
- Require endpoint paths not listed in the official Swagger;
- Require use of undocumented paths through `get()`;
- Return data in response shapes different from `python-garminconnect`; or
- Not be available to every Personal API key or account.

## Activity Download Differences

The current implementation supports activity downloads in different formats through:

```python
garmin_obj.download_activity(activity_id, dl_fmt=...
```

The official library's `download_activity(activity_id)` method returns ZIP bytes for the activity:

```python
content = client.download_activity(activity_id)
Path(f"activity-{activity_id}.zip").write_bytes(content)
```

Migration implications:

- FIT extraction can continue by reading files from the returned ZIP.
- TCX format handling needs to account for the contents returned by the official download ZIP.
- The original in-memory/download API shape will require an adapter or revised extraction logic.
- The official library currently holds the whole ZIP in memory and does not provide streaming downloads.

## Recommended Migration Strategy

A direct dependency replacement would introduce data-loss risk. The recommended approach is a phased provider migration.

### Phase 1: Add an Official API Adapter

1. Introduce a Garmin data provider abstraction behind the existing fetch implementation.
2. Authenticate through:
   - `PersonalApiAuthenticator`
   - `GarminPersonalApiClient`
   - `GARMIN_PERSONAL_API_KEY`
3. Keep the existing response parsing isolated from authentication and client selection.
4. Map official endpoint responses to the shapes expected by existing fetch functions.
5. Use `get()` for verified official Personal API endpoints that lack dedicated wrappers.

### Phase 2: Preserve Supported Metrics

Begin with data that has confirmed dedicated official wrappers:

- Daily summaries
- Sleep
- Steps
- Stress
- Hydration
- Heart rate
- HRV
- Body battery
- Fitness age
- Weight
- Activities
- Activity downloads

### Phase 3: Handle Unsupported Metrics Explicitly

For unsupported fetch selections, do one of the following:

- Remove them when operating in official API mode;
- Keep them behind `python-garminconnect` until official support exists;
- Add verified generic endpoint access when a documented official endpoint is available; or
- Report a clear startup/configuration warning rather than silently omitting data.

### Phase 4: Test and Switch Defaults

Before making the official API the default provider:

1. Test authentication and token refresh with real Personal API credentials.
2. Compare every supported response schema against existing data-processing assumptions.
3. Test activity ZIP contents and FIT extraction.
4. Verify unavailable fetch selections are handled consistently.
5. Add Docker configuration and documentation for Personal API key storage.
6. Run historical-date imports and long-running background synchronization tests.
7. Compare generated InfluxDB measurements with those produced by `python-garminconnect`.

## Required Repository Changes

A complete migration would likely require changes to:

- `pyproject.toml`: replace the `garminconnect` dependency with the official package
- `src/garmin_grafana/garmin_fetch.py`: replace login and Garmin client method calls
- Authentication environment variables: replace email/password configuration with `GARMIN_PERSONAL_API_KEY`
- Docker Compose and Kubernetes configuration: add Personal API key storage or environment configuration
- Token volume handling: replace Garmin OAuth token storage with official bearer-token/key storage as appropriate
- Documentation: update setup, first-run, credential, Docker, and Kubernetes instructions
- Activity processing: support official activity ZIP downloads and extraction
- Fetch selection validation: mark or fail unsupported selections clearly

## Configuration Considerations

Existing credential variables include:

```text
GARMINCONNECT_EMAIL
GARMINCONNECT_BASE64_PASSWORD
GARMINCONNECT_IS_CN
TOKEN_DIR
```

The official API migration could use:

```text
GARMIN_PERSONAL_API_KEY
```

Additional configuration may be needed for an explicit key file or bearer-token cache location. The official API key should be treated as a secret and not stored as plaintext in source control.

## Risks

- **Feature loss:** advanced wellness and training metrics may not be available through the Personal API.
- **New API maturity:** the official package was released recently and endpoint coverage may lag.
- **Response differences:** official endpoints may use different field names or structures.
- **Account/API availability:** endpoint access may depend on the account, region, API key, or Garmin enrollment.
- **Python compatibility:** the official package requires Python 3.12 or newer, which is compatible with the current Python 3.13 project requirement.
- **FIT processing:** official activity ZIP contents must be confirmed before format-specific assumptions are changed.
- **Deployment secrets:** API keys and bearer-token caches require secure mounting and permissions.

## Conclusion

The switch is feasible, and the official library would simplify credential handling and eliminate email/password/MFA login for compatible data paths.

However, a direct replacement is not functionally equivalent because this project relies on a broad set of `python-garminconnect` convenience methods and Garmin Connect service endpoints that are outside the current official library's documented wrapper set.

The safest path is an adapter-based, opt-in migration that keeps `python-garminconnect` available as a fallback until all required endpoints are confirmed under the official Personal API.

## References

- [Garmin Connect Personal API overview](https://developer.garmin.com/gc-developer-program/personal/personal-api)
- [Garmin Connect Personal API Swagger documentation](https://developer.garmin.com/gc-developer-program/personal/swagger-docs/)
- [Garmin Connect Personal API Python repository](https://github.com/garmin/connect-personal-api-python)
- [Garmin Personal API key management](https://connect.garmin.com/app/settings/personalApiToken)
