# --
# File: flashpoint_consts.py
#
# Copyright (c) Flashpoint, 2020-2026
#
# This unpublished material is proprietary to Flashpoint.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Flashpoint.
#
# Licensed under Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0.txt)
#
# --

# Define your constants here

FLASHPOINT_X_FP_INTEGRATION_PLATFORM = "Phantom"

# Flashpoint endpoints
FLASHPOINT_INDICATORS_V2_ENDPOINT = "/technical-intelligence/v2/indicators"
FLASHPOINT_INDICATOR_V2_ENDPOINT = "/technical-intelligence/v2/indicators/{indicator_id}"
FLASHPOINT_SIGHTINGS_V2_ENDPOINT = "/technical-intelligence/v2/sightings"
FLASHPOINT_SIGHTING_V2_ENDPOINT = "/technical-intelligence/v2/sightings/{sighting_id}"
FLASHPOINT_ALERTS_ENDPOINT = "/alert-management/v1/notifications"
FLASHPOINT_ALL_SEARCH_ENDPOINT = "/sources/v1/noncommunities/search"
FLASHPOINT_ALL_SEARCH_SCROLL_ENDPOINT = "/sources/v1/noncommunities/scroll"
FLASHPOINT_LIST_REPORTS_ENDPOINT = "/finished-intelligence/v1/reports"
FLASHPOINT_GET_REPORT_ENDPOINT = "/finished-intelligence/v1/reports/{report_id}"
FLASHPOINT_LIST_RELATED_REPORTS_ENDPOINT = "/finished-intelligence/v1/reports/{report_id}/related"

FLASHPOINT_PER_PAGE_DEFAULT_LIMIT = 500
# Finished Intelligence reports carry their full HTML body, often with embedded images, so a page of
# them is far larger than a page of any other record. 500 of the newest reports exceed the size
# Splunk SOAR can store for one action result, so the report actions default to, and page by, 50
FLASHPOINT_REPORTS_DEFAULT_LIMIT = 50
FLASHPOINT_DEFAULT_WAIT_TIMEOUT_PERIOD = 5
FLASHPOINT_NUMBER_OF_RETRIES = 1
FLASHPOINT_SESSION_TIMEOUT = 2
# Bounds every REST call so a hung endpoint cannot block an action until the platform kills it.
# A single legitimate call can be slow on this API: 'list reports' at its default limit of 500 was
# measured at 38.6s and a sightings page with 'include_total_count' at 24.3s, so the default leaves
# generous headroom and the asset can raise it further
FLASHPOINT_DEFAULT_REQUEST_TIMEOUT = 120
# The statuses worth a second attempt: 429 is the documented rate-limit response of this API and
# the 5xx set is a transient gateway or backend failure. Every other status is a decision the
# analyst has to act on, so it is surfaced instead of retried
FLASHPOINT_RETRYABLE_STATUS = (429, 500, 502, 503, 504)
FLASHPOINT_RATE_LIMITED_STATUS = 429
# A 429 carries the wait the API asks for in 'Retry-After', as seconds or as an HTTP date. It is
# honoured over the configured wait period, but capped: an action that sleeps longer than this is
# better failed and retried by the next poll than held open until the platform kills it
FLASHPOINT_MAX_RETRY_AFTER = 60

# Technical Intelligence v2 indicator parameters
FLASHPOINT_V2_DEFAULT_SIZE = 10
FLASHPOINT_V2_DEFAULT_FROM = 0
FLASHPOINT_V2_MAX_SIZE = 1000
FLASHPOINT_V2_MAX_SIZE_WITH_EMBED = 500

FLASHPOINT_IOC_TYPES = ("domain", "extracted_config", "file", "ipv4", "ipv6", "url")
FLASHPOINT_EMBED_VALUES = ("all", "apt_description", "external_references", "malware_description", "mitre_attack_ids", "related_iocs")
FLASHPOINT_SCORE_VALUES = ("informational", "suspicious", "malicious")
FLASHPOINT_SORT_VALUES = (
    "created_at:asc",
    "created_at:desc",
    "last_seen_at:asc",
    "last_seen_at:desc",
    "modified_at:asc",
    "modified_at:desc",
)

# Indicator action parameters passed through to the API without transformation
FLASHPOINT_V2_TEXT_PARAMS = (
    "ioc_value",
    "cidr_range",
    "last_seen_after",
    "last_seen_before",
    "created_after",
    "created_before",
    "modified_after",
    "modified_before",
)
# Comma-separated parameters; a value tuple restricts the accepted tokens
FLASHPOINT_V2_LIST_PARAMS = {
    "ioc_types": FLASHPOINT_IOC_TYPES,
    "embed": FLASHPOINT_EMBED_VALUES,
    "tags": (),
    "sources": (),
    "actors": (),
    "malware": (),
    "mitre_attack_ids": (),
}
# 'list indicators' pages the most recent IoCs and takes no value-like input: the value lookup and
# every narrowing filter belong to 'search indicators', so the two actions build different requests
# rather than sharing one filter surface
FLASHPOINT_V2_LIST_TEXT_PARAMS = ("last_seen_after",)
FLASHPOINT_V2_LIST_LIST_PARAMS = {"ioc_types": FLASHPOINT_IOC_TYPES}
FLASHPOINT_V2_ENUM_PARAMS = {
    "min_score": FLASHPOINT_SCORE_VALUES,
    "max_score": FLASHPOINT_SCORE_VALUES,
    "sort": FLASHPOINT_SORT_VALUES,
}
FLASHPOINT_V2_BOOLEAN_PARAMS = ("has_intel_report", "has_extracted_config", "include_total_count")
FLASHPOINT_V2_LIST_ENUM_PARAMS = {"sort": FLASHPOINT_SORT_VALUES}
FLASHPOINT_V2_TOTAL_COUNT_KEYS = ("total", "total_count")
# Envelope keys that carry the record list. 'items' is the documented Technical Intelligence v2 key;
# the alert endpoint has no public reference, so the keys used by Flashpoint's own integrations follow
FLASHPOINT_RECORD_LIST_KEYS = ("items", "notifications", "alerts", "data", "results")
FLASHPOINT_NOT_FOUND_STATUS_CODE = "Status code: 404"

# Technical Intelligence v2 indicator-by-id parameters
FLASHPOINT_V2_DEFAULT_SIGHTING_COUNT = 100
FLASHPOINT_V2_MIN_SIGHTING_COUNT = 1
FLASHPOINT_V2_MAX_SIGHTING_COUNT = 1000

# Technical Intelligence v2 sighting parameters
FLASHPOINT_SIGHTING_EMBED_VALUES = ("all", "apt_description", "malware_description", "mitre_attack_ids")
FLASHPOINT_SIGHTING_SORT_VALUES = (
    "created_at:asc",
    "created_at:desc",
    "modified_at:asc",
    "modified_at:desc",
    "sighted_at:asc",
    "sighted_at:desc",
)
FLASHPOINT_SIGHTING_DEFAULT_SIZE = 10

FLASHPOINT_SIGHTING_TEXT_PARAMS = (
    "sighted_after",
    "sighted_before",
    "created_after",
    "created_before",
    "modified_after",
    "modified_before",
)
FLASHPOINT_SIGHTING_LIST_PARAMS = {
    "embed": FLASHPOINT_SIGHTING_EMBED_VALUES,
    "tags": (),
    "sources": (),
}
FLASHPOINT_SIGHTING_ENUM_PARAMS = {"sort": FLASHPOINT_SIGHTING_SORT_VALUES}
FLASHPOINT_SIGHTING_BOOLEAN_PARAMS = ("include_total_count",)

# Alert parameters. The alert management service publishes no OpenAPI definition, so the filter
# model follows the reference page and is confirmed live: the enums are lowercase and a value
# outside them is rejected with HTTP 422
FLASHPOINT_ALERT_DEFAULT_SIZE = 25
FLASHPOINT_ALERT_MAX_SIZE = 5000
FLASHPOINT_ALERT_STATUS_VALUES = ("archived", "flagged", "sent", "deleted", "none")
FLASHPOINT_ALERT_ORIGIN_VALUES = ("searches", "assets", "analyst-team", "vuln-alerting")
# The code-repository sources are exposed under a 'data_exposure__' prefix and the image source is
# named 'media'; the Ignite UI labels of these values are Github, Gitlab, Bitbucket and Images
FLASHPOINT_ALERT_SOURCE_VALUES = (
    "communities",
    "credentials",
    "data_exposure__bitbucket",
    "data_exposure__github",
    "data_exposure__gitlab",
    "iocs",
    "marketplaces",
    "media",
    "reports",
    "vulnerabilities",
)
# The alert endpoint rejects a bare relative offset such as '-7d' with HTTP 400; it accepts an
# absolute ISO-8601 UTC datetime or a 'now'-anchored value, unlike the Technical Intelligence v2
# date filters, which accept '-7d' and reject 'now-7d'
FLASHPOINT_ALERT_DATE_PARAMS = ("created_after", "created_before")
FLASHPOINT_ALERT_DATE_PATTERN = (
    r"^(?:now(?:[+-]\d+[smhdwMy])?|\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?)$"
)
FLASHPOINT_ALERT_TEXT_PARAMS = ("created_after", "created_before", "cursor", "asset_ip", "asset_type")
# 'status' and 'origin' are single-valued on this endpoint: a comma-joined value is rejected with
# HTTP 422 and repeating the parameter keeps only the last value, so the analyst gets one value or
# a validation error. The remaining filters are genuine OR lists in their comma-joined form
FLASHPOINT_ALERT_ENUM_PARAMS = {
    "status": FLASHPOINT_ALERT_STATUS_VALUES,
    "origin": FLASHPOINT_ALERT_ORIGIN_VALUES,
}
FLASHPOINT_ALERT_LIST_PARAMS = {
    "sources": FLASHPOINT_ALERT_SOURCE_VALUES,
    "tags": (),
    "asset_ids": (),
    "query_ids": (),
}

# On Poll constants
FLASHPOINT_INGESTION_ALERTS = "Alerts"
FLASHPOINT_INGESTION_CREDENTIALS = "Compromised Credentials"
FLASHPOINT_INGESTION_TYPES = (FLASHPOINT_INGESTION_CREDENTIALS, FLASHPOINT_INGESTION_ALERTS)
FLASHPOINT_DEFAULT_INGESTION_TYPE = FLASHPOINT_INGESTION_CREDENTIALS
# Sentinel value of the optional single-select asset settings. A SOAR configuration dropdown keeps
# the last value it was given and offers no way back to empty, so the 'no filter' state is an
# explicit option rather than a blank one
FLASHPOINT_CONFIG_ALL = "All"
# The single-valued alert filters an asset applies to every poll, mapped to the request parameter
# each one carries. They are validated against the same value sets as the 'list alerts' action
FLASHPOINT_ALERT_INGEST_ENUM_CONFIG = {
    "alert_status": "status",
    "alert_origin": "origin",
}
# The credential ingestion watermark field. A credential-sighting document carries this datetime
# under 'breach', so both the window clause and the sort are built on the breach sub-fields; the
# bare top-level field matches no records on the noncommunities search endpoint
FLASHPOINT_CREDENTIAL_WATERMARK = "created_at"
FLASHPOINT_CREDENTIAL_DATE_FIELD = f"breach.{FLASHPOINT_CREDENTIAL_WATERMARK}.date-time"
FLASHPOINT_CREDENTIAL_SORT_FIELD = f"breach.{FLASHPOINT_CREDENTIAL_WATERMARK}.timestamp"
FLASHPOINT_CREDENTIAL_INGEST_PAGE_SIZE = 1000
FLASHPOINT_DEFAULT_FIRST_RUN_WINDOW = 3
FLASHPOINT_DEFAULT_MAX_EVENTS_PER_POLL = 100
FLASHPOINT_DEFAULT_EVENT_SEVERITY = "medium"
# Ingestion default of the freshness filter. A credential sighting is 'fresh' when its
# username/password pair was not seen in an earlier breach; without the filter a poll ingests every
# re-sighting of the same pair, which on a live tenant is over 99% of the window (20,320 sightings
# in a one-day window against 149 fresh ones) and buries the new exposures a playbook must act on
FLASHPOINT_DEFAULT_FRESH_CREDENTIALS_ONLY = True
# Ingestion default of the breached-password setting. A CEF field is indexed and searchable across
# the platform and the raw record is readable on the container and the artifact, so storing the
# plaintext is an explicit choice the deploying admin makes rather than a default of the app
FLASHPOINT_DEFAULT_STORE_PLAINTEXT_PASSWORD = False
# The noncommunities search rejects a request whose from + size exceeds this ceiling, so a walk
# stops there and resumes from the saved watermark on the next poll instead of losing records
FLASHPOINT_SEARCH_OFFSET_CEILING = 10000
# A container label must already exist on the platform: SOAR rejects an unknown label and the save
# fails, so ingestion requires the label of the asset's ingest settings rather than a built-in one
FLASHPOINT_STATE_ALERTS_KEY = "alerts_ingestion"
FLASHPOINT_STATE_CREDENTIALS_KEY = "credentials_ingestion"
# The ingestion checkpoint records how far through a window the poll actually read. 'window_start'
# and 'window_end' bound the window being drained, 'offset' is the next unread record of the
# credential walk and 'cursor' the next unread page of the alert walk. A poll that cannot finish a
# window keeps it and resumes, so 'max_events_per_poll' is a rate limit and never a filter
FLASHPOINT_STATE_WINDOW_START = "window_start"
FLASHPOINT_STATE_WINDOW_END = "window_end"
FLASHPOINT_STATE_OFFSET = "offset"
FLASHPOINT_STATE_CURSOR = "cursor"
# Assets saved by 3.0.3 and by 4.0.0 builds before the resumable checkpoint carry only this key
FLASHPOINT_STATE_LEGACY_TIME = "last_ingested_time"
# The alert endpoint defaults to 'created_at:desc'. Ingestion walks a window oldest-first so the
# cursor continues forward, in the same direction the window moves
FLASHPOINT_ALERT_INGEST_SORT = "created_at:asc"

# Validate Integers key constants
FLASHPOINT_CONFIG_WAIT_TIMEOUT_PERIOD_KEY = "'Retry Wait Period(in seconds)' asset configuration"
FLASHPOINT_CONFIG_NO_OF_RETRIES_KEY = "'Number Of Retries' asset configuration"
FLASHPOINT_CONFIG_SESSION_TIMEOUT_KEY = "'Session Timeout(in minutes)' asset configuration"
FLASHPOINT_CONFIG_REQUEST_TIMEOUT_KEY = "'Request Timeout(in seconds)' asset configuration"
FLASHPOINT_ACTION_LIMIT_KEY = "'limit' action"
FLASHPOINT_ACTION_SIZE_KEY = "'size' action"
FLASHPOINT_ACTION_FROM_KEY = "'from' action"
FLASHPOINT_ACTION_SIGHTING_COUNT_KEY = "'sighting_count' action"
FLASHPOINT_CONFIG_FIRST_RUN_WINDOW_KEY = "'First Run Window(in days)' asset configuration"
FLASHPOINT_CONFIG_MAX_EVENTS_KEY = "'Maximum Events Per Poll' asset configuration"

# Error message constants
FLASHPOINT_ERROR_VALID_INT_MESSAGE = "Please provide a valid integer value in the {parameter} parameter"
FLASHPOINT_LIMIT_VALIDATION_ALLOW_ZERO_MESSAGE = "Please provide zero or positive integer value in the {parameter} parameter"
FLASHPOINT_LIMIT_VALIDATION_MESSAGE = "Please provide a valid non-zero positive integer value in the {parameter} parameter"
FLASHPOINT_INVALID_CONFIG_VALUE_ERROR = (
    "Please provide a valid value in the '{parameter}' asset configuration. Allowed values are: {allowed_values}"
)
FLASHPOINT_ALREADY_DISABLE_SESSION_SCROLL_ERROR_MESSAGE = "Status code: 404"
FLASHPOINT_ERROR_CODE_MESSAGE = "Error code unavailable"
FLASHPOINT_UNKNOWN_ERROR_MESSAGE = "Unknown error occurred. Please check the asset configuration and|or the action parameters."
FLASHPOINT_INVALID_COMMA_SEPARATED_LIST_ERROR = "Please provide a valid comma-separated list of values in the '{parameter}' action parameter"
FLASHPOINT_INVALID_VALUE_ERROR = "Please provide a valid value in the '{parameter}' action parameter. Allowed values are: {allowed_values}"
FLASHPOINT_MISSING_REQUIRED_PARAM_ERROR = "Please provide a non-empty value in the '{parameter}' action parameter"
FLASHPOINT_NO_DATA_FOUND_ERROR = "No data found"
FLASHPOINT_UNEXPECTED_RESPONSE_ERROR = (
    "The server answered without a record list. The configured Base URL does not appear to serve the "
    "Flashpoint API; check it and any proxy in front of it"
)
# A validation failure carries the actionable text in an 'errors' array beside a generic 'detail'
FLASHPOINT_API_ERROR_KEYS = ("errors", "detail")
FLASHPOINT_SIZE_CLAMPED_MESSAGE = "The 'size' parameter was reduced to {size} because {reason}"
FLASHPOINT_EMBED_CLAMP_REASON = "the API returns at most {max_size} records when the 'embed' parameter is provided"
FLASHPOINT_MAX_SIZE_CLAMP_REASON = "the API returns at most {max_size} records per request"
FLASHPOINT_ERROR_SESSION_TIMEOUT_VALUE = "Please provide session timeout value between 1 and 60."
FLASHPOINT_INVALID_PATH_ID_ERROR = "Please provide a valid value in the '{parameter}' action parameter. Path separators are not allowed"
FLASHPOINT_NOT_FOUND_ERROR = "{entity} not found for the provided ID"
FLASHPOINT_INVALID_ALERT_DATE_ERROR = (
    "Please provide a valid value in the '{parameter}' action parameter. The alert endpoint accepts an absolute "
    "ISO-8601 UTC datetime (2024-01-01T00:00:00Z) or a 'now'-anchored relative value (now, now-7d)"
)
FLASHPOINT_MISSING_CONTAINER_LABEL_ERROR = (
    "Select a container label in the asset's Ingest Settings. Splunk SOAR only accepts a label that "
    "already exists on the platform, so ingestion cannot fall back to a label of its own"
)
# Reported when a window holds more records than one poll may create, so a truncated window is
# visible to the analyst instead of looking like a completed one
FLASHPOINT_ON_POLL_RESUME_MESSAGE = (
    "{ingested} Ingestion of the window [{window_start} to {window_end}] is not finished and resumes from {position} on the next scheduled poll"
)
FLASHPOINT_INVALID_INGESTION_TYPE_ERROR = "Please provide a valid 'Ingestion Type' asset configuration. Allowed values are: {allowed_values}"
FLASHPOINT_ON_POLL_INGESTED_MESSAGE = "Ingested {containers} container(s) from {records} {entity} record(s)"
