# --
# File: flashpoint_connector.py
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

import copy
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlparse

# Phantom App imports
import phantom.app as phantom
import requests
from bs4 import BeautifulSoup
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

from flashpoint_consts import *


class RetVal(tuple):
    """Represent the Tuple as a return value."""

    def __new__(cls, val1, val2=None):
        """Recursive call for tuple."""
        return tuple.__new__(RetVal, (val1, val2))


class FlashpointConnector(BaseConnector):
    """Represent a connector module that implements the actions that are provided by the app."""

    def __init__(self):
        """Initialize class variables."""
        # Call the BaseConnectors init first
        super().__init__()

        # Define the global state variable
        self._state = None

        # Define the global variables
        self._base_url = None
        self._api_token = None
        self._x_fp_integration_platform_version = None
        self._x_fp_integration_version = None
        self._wait_timeout_period = None
        self._no_of_retries = None
        self._session_timeout = None
        self._request_timeout = FLASHPOINT_DEFAULT_REQUEST_TIMEOUT

        # Variable to hold the number of attempted retries of REST calls
        self._attempted_retries = 0

    @staticmethod
    def _validate_report_id(report_id, action_result):
        """Validate and encode a report identifier as one endpoint path component."""
        if not isinstance(report_id, str) or report_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", report_id):
            return action_result.set_status(phantom.APP_ERROR, "Invalid report ID"), None

        return phantom.APP_SUCCESS, quote(report_id, safe="")

    def _process_empty_response(self, response, action_result):
        """Process empty response.

        :param response: response data
        :param action_result: object of Action Result
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message)
        """
        if response.status_code == 200 or response.status_code == 204:
            return RetVal(phantom.APP_SUCCESS, {})

        return RetVal(
            action_result.set_status(phantom.APP_ERROR, f"Status code: {response.status_code}. Empty response and no information in the header"),
            None,
        )

    def _process_html_response(self, response, action_result):
        """Process html response.

        :param response: response data
        :param action_result: object of Action Result
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message)
        """
        # An html response, treat it like an error
        status_code = response.status_code

        if 200 <= status_code < 399:
            return RetVal(phantom.APP_SUCCESS, response.text)

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove the script, style, footer and navigation part from the HTML message
            for element in soup(["script", "style", "footer", "nav"]):
                element.extract()
            error_text = soup.text
            split_lines = error_text.split("\n")
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = "\n".join(split_lines)
        except Exception:
            error_text = "Cannot parse error details"

        message = f"Status Code: {status_code}. Data from server:\n{error_text}\n"

        message = message.replace("{", "{{").replace("}", "}}")

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):
        """Process json response.

        :param r: response data
        :param action_result: object of Action Result
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message)
        """
        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            error_code, error_message = self._get_error_message_from_exception(e)
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR, f"Unable to parse JSON response. Error Code: {error_code}. Error Message: {error_message}"
                ),
                None,
            )

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        message = None
        # Error handling for different type of error responses from server
        if resp_json.get("error") and isinstance(resp_json.get("error"), dict):
            resp_message = resp_json.get("error", {}).get("message", "Error message not found")
            message = "Error from server. Status code: {}. Error code: {}. Error message: {}".format(
                r.status_code, resp_json.get("error", {}).get("code", "Error code not found"), resp_message
            )

        detail = self._get_api_error_detail(resp_json)
        if detail:
            message = f"Error from server. Status code: {r.status_code}. Data from server: {detail}"

        if resp_json.get("message"):
            resp_message = resp_json.get("message", "Error message not found")
            message = f"Error from server. Status code: {r.status_code}. Data from server: {resp_message}"

        # You should process the error returned in the json if none of the above handling happens for error scenario
        if not message:
            resp_text = r.text if r.text else "Response error text not found"
            message = f"Error from server. Status Code: {r.status_code} Data from server: {resp_text}"

        # 'message' may carry API text with braces, which set_status would read as placeholders
        return RetVal(action_result.set_status(phantom.APP_ERROR, message.replace("{", "{{").replace("}", "}}")), None)

    @staticmethod
    def _get_api_error_detail(resp_json):
        """Render the actionable part of an API error body.

        A validation failure answers with a generic 'detail' and an 'errors' array that names the
        parameter and the rule it broke, so the array is read first and its messages are joined. A
        'detail' that is itself a list of validation objects is rendered the same way, instead of
        dumping the Python repr of the list at the analyst.

        :param resp_json: parsed response body
        :return: readable error text, empty when the body carries none
        """
        for key in FLASHPOINT_API_ERROR_KEYS:
            value = resp_json.get(key)
            if isinstance(value, list) and value:
                messages = []
                for item in value:
                    if not isinstance(item, dict):
                        messages.append(str(item))
                        continue
                    location = ".".join(str(part) for part in (item.get("loc") or []) if part not in ("query", "body"))
                    text = item.get("msg") or item.get("message") or ""
                    messages.append(f"{location}: {text}" if location and text else text or str(item))
                joined = "; ".join(message for message in messages if message)
                if joined:
                    return joined
            elif isinstance(value, str) and value:
                return value

        return ""

    def _process_response(self, r, action_result):
        """Process API response.

        :param r: response data
        :param action_result: object of Action Result
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message)
        """
        # Store the r_text in debug data, it will get dumped in the logs if the action fails
        if hasattr(action_result, "add_debug_data"):
            action_result.add_debug_data({"r_status_code": r.status_code})
            action_result.add_debug_data({"r_text": r.text})
            action_result.add_debug_data({"r_headers": r.headers})

        # Process each 'Content-Type' of response separately

        # it's not response text, handle an empty response
        if not r.text:
            return self._process_empty_response(r, action_result)

        # Process a json response
        if "json" in r.headers.get("Content-Type", ""):
            return self._process_json_response(r, action_result)

        # Process an HTML response, Do this no matter what the api talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if "html" in r.headers.get("Content-Type", ""):
            return self._process_html_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {} Data from server: {}".format(
            r.status_code, r.text.replace("{", "{{").replace("}", "}}") if r.text else "Response error text not found"
        )

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _get_error_message_from_exception(self, e):
        """Get appropriate error message from the exception.

        :param e: Exception object
        :return: error message
        """
        error_message = FLASHPOINT_UNKNOWN_ERROR_MESSAGE

        try:
            if e.args:
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_message = e.args[1]
                elif len(e.args) == 1:
                    error_code = FLASHPOINT_ERROR_CODE_MESSAGE
                    error_message = e.args[0]
            else:
                error_code = FLASHPOINT_ERROR_CODE_MESSAGE
                error_message = FLASHPOINT_UNKNOWN_ERROR_MESSAGE
        except Exception:
            error_code = FLASHPOINT_ERROR_CODE_MESSAGE
            error_message = FLASHPOINT_UNKNOWN_ERROR_MESSAGE

        return error_code, error_message

    def _make_rest_call(self, endpoint, action_result, method="get", params=None, data=None):
        """Make the REST call to the app.

        :param endpoint: REST endpoint that needs to appended to the service address
        :param action_result: object of ActionResult class
        :param method: GET/POST/PUT/DELETE/PATCH (Default will be GET)
        :param params: request parameters
        :param data: request body
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message),
        response obtained by making an API call
        """
        resp_json = None

        # Each call owns its retry budget; a counter shared across the calls of one action would
        # spend page 1's retries out of page 2's allowance
        self._attempted_retries = 0

        try:
            request_func = getattr(requests, method)
        except AttributeError:
            return RetVal(action_result.set_status(phantom.APP_ERROR, f"Invalid method: {method}"), resp_json)

        # Create headers information
        headers = dict()

        headers.update(
            {
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
                "X-FP-IntegrationPlatform": FLASHPOINT_X_FP_INTEGRATION_PLATFORM,
                "X-FP-IntegrationPlatformVersion": self._x_fp_integration_platform_version,
                "X-FP-IntegrationVersion": self._x_fp_integration_version,
            }
        )

        # Create a URL to connect to Flashpoint
        url = f"{self._base_url}{endpoint}"

        self.debug_print("Making a REST call with provided request parameters")

        try:
            r = request_func(url, params=params, headers=headers, data=data, timeout=self._request_timeout)
        except requests.exceptions.Timeout:
            error_message = f"Error connecting to server. The request did not complete within {self._request_timeout} seconds"
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except requests.exceptions.InvalidSchema:
            error_message = f"Error connecting to server. No connection adapters were found for {url}"
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except requests.exceptions.InvalidURL:
            error_message = f"Error connecting to server. Invalid URL {url}"
            return RetVal(action_result.set_status(phantom.APP_ERROR, error_message), resp_json)
        except Exception as e:
            error_code, error_message = self._get_error_message_from_exception(e)
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR, f"Error connecting to server. Error Code: {error_code}. Error Message: {error_message}"
                ),
                resp_json,
            )

        if self._no_of_retries and r.status_code in FLASHPOINT_RETRYABLE_STATUS:
            wait_period = self._get_retry_wait_period(r)
            message = f"Received HTTP {r.status_code} from the server. Retrying API call after {wait_period} seconds"
            self.save_progress(message)
            self.debug_print(message)
            return self._retry_make_rest_call(action_result, url, headers, request_func, wait_period, params=params, data=data)

        return self._process_response(r, action_result)

    def _get_retry_wait_period(self, response):
        """Read the wait period before the next attempt of a transient response.

        A rate-limited response names the wait the API wants in 'Retry-After', as a number of
        seconds or as an HTTP date, and waiting less than that only spends another attempt on the
        same refusal. The header is capped, because an action that sleeps for minutes is better
        failed and picked up by the next poll than held open until the platform kills it.

        :param response: response of the attempt that has to be retried
        :return: number of seconds to wait
        """
        if response.status_code != FLASHPOINT_RATE_LIMITED_STATUS:
            return self._wait_timeout_period

        retry_after = (response.headers or {}).get("Retry-After")
        if not isinstance(retry_after, str) or not retry_after.strip():
            return self._wait_timeout_period

        retry_after = retry_after.strip()
        if retry_after.isdigit():
            seconds = int(retry_after)
        else:
            try:
                moment = parsedate_to_datetime(retry_after)
            except (TypeError, ValueError):
                return self._wait_timeout_period
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            seconds = int((moment - datetime.now(timezone.utc)).total_seconds())

        if seconds <= 0:
            return self._wait_timeout_period

        return min(seconds, FLASHPOINT_MAX_RETRY_AFTER)

    def _retry_make_rest_call(self, action_result, url, headers, request_func, wait_period, params=None, data=None):
        """Wait for the given period after a transient failure and make the REST call again.

        The call is repeated for the configured number of retries while the server keeps answering
        with a transient status: a rate limit or a gateway or backend failure.

        :param action_result: object of ActionResult class
        :param url: URL to connect to Flashpoint
        :param headers: headers information for REST call
        :param request_func: request object used for making REST call
        :param wait_period: number of seconds to wait before this attempt
        :param params: request parameters
        :param data: request body
        :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message),
        response obtained by making an API call
        """
        # Increase attempted retry REST call
        self._attempted_retries += 1

        # Wait for given time(in seconds) for the server to accept the call again
        time.sleep(wait_period)

        try:
            r = request_func(url, params=params, headers=headers, data=data, timeout=self._request_timeout)
        except Exception as e:
            error_code, error_message = self._get_error_message_from_exception(e)
            return RetVal(
                action_result.set_status(
                    phantom.APP_ERROR, f"Error connecting to server. Error Code: {error_code}. Error Message: {error_message}"
                ),
                None,
            )

        if r.status_code in FLASHPOINT_RETRYABLE_STATUS and self._attempted_retries < self._no_of_retries:
            wait_period = self._get_retry_wait_period(r)
            message = f"Received HTTP {r.status_code} from the server. Retrying API call after {wait_period} seconds"
            self.save_progress(message)
            self.debug_print(message)
            return self._retry_make_rest_call(action_result, url, headers, request_func, wait_period, params=params, data=data)

        return self._process_response(r, action_result)

    @staticmethod
    def _validate_list_param(action_result, value, key, allowed_values=()):
        """Validate a comma-separated action parameter and return the API-ready comma-joined value.

        :param action_result: object of ActionResult class
        :param value: value of the action parameter
        :param key: name of the action parameter
        :param allowed_values: accepted tokens; an empty tuple accepts any non-empty token
        :return: comma-joined value of the parameter, None if the parameter is invalid
        """
        tokens = [token.strip() for token in value.split(",")]
        tokens = list(filter(None, tokens))

        if not tokens:
            action_result.set_status(phantom.APP_ERROR, FLASHPOINT_INVALID_COMMA_SEPARATED_LIST_ERROR.format(parameter=key))
            return None

        if allowed_values:
            # The analyst's casing is accepted, but the value sent is the casing the API documents
            canonical = {allowed.lower(): allowed for allowed in allowed_values}
            if any(token.lower() not in canonical for token in tokens):
                action_result.set_status(
                    phantom.APP_ERROR, FLASHPOINT_INVALID_VALUE_ERROR.format(parameter=key, allowed_values=", ".join(allowed_values))
                )
                return None
            tokens = [canonical[token.lower()] for token in tokens]

        return ",".join(tokens)

    @staticmethod
    def _validate_path_id(action_result, value, key):
        """Validate an identifier used as a URL path component and return it percent-encoded.

        :param action_result: object of ActionResult class
        :param value: value of the action parameter
        :param key: name of the action parameter
        :return: percent-encoded identifier, None on a validation failure
        """
        if not isinstance(value, str) or not value.strip():
            action_result.set_status(phantom.APP_ERROR, FLASHPOINT_MISSING_REQUIRED_PARAM_ERROR.format(parameter=key))
            return None

        value = value.strip()

        # A path component carrying a separator or a traversal segment would address a different
        # resource, so it is rejected instead of being encoded into an unintended URL
        if "/" in value or "\\" in value or ".." in value:
            action_result.set_status(phantom.APP_ERROR, FLASHPOINT_INVALID_PATH_ID_ERROR.format(parameter=key))
            return None

        return quote(value, safe="")

    def _build_query_params(
        self,
        action_result,
        param,
        text_params=(),
        list_params=None,
        enum_params=None,
        boolean_params=(),
        default_size=None,
        max_size=None,
        embed_max_size=None,
    ):
        """Build the request parameters of a Technical Intelligence v2 or alert list endpoint.

        Multi-value filters are comma-joined into a single query parameter, different parameters are
        combined by the API using AND logic and the values within one parameter using OR logic.

        :param action_result: object of ActionResult class
        :param param: Dictionary of input parameters
        :param text_params: parameters passed through to the API without transformation
        :param list_params: comma-separated parameters mapped to their accepted tokens
        :param enum_params: single-value parameters mapped to their accepted values
        :param boolean_params: parameters sent only when the analyst enables them
        :param default_size: default per-request page size; None skips the paging parameters
        :param max_size: documented per-request record cap
        :param embed_max_size: lower record cap that applies when 'embed' is provided
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), request parameters, message about a clamped size
        """
        params = dict()

        for key in text_params:
            value = param.get(key)
            value = value.strip() if isinstance(value, str) else value
            if value:
                params[key] = value

        for key, allowed_values in (list_params or {}).items():
            if not param.get(key):
                continue
            value = self._validate_list_param(action_result, param[key], key, allowed_values)
            if value is None:
                return action_result.get_status(), None, None
            params[key] = value

        for key, allowed_values in (enum_params or {}).items():
            value = param.get(key)
            value = value.strip().lower() if isinstance(value, str) else value
            if not value:
                continue
            if value not in allowed_values:
                action_result.set_status(
                    phantom.APP_ERROR, FLASHPOINT_INVALID_VALUE_ERROR.format(parameter=key, allowed_values=", ".join(allowed_values))
                )
                return action_result.get_status(), None, None
            params[key] = value

        # These filters default to false on the API, so they are sent only when the analyst enables them
        for key in boolean_params:
            if param.get(key):
                params[key] = "true"

        if default_size is None:
            return phantom.APP_SUCCESS, params, ""

        # Validate the 'from' action parameter
        offset = self._validate_integers(action_result, param.get("from", FLASHPOINT_V2_DEFAULT_FROM), FLASHPOINT_ACTION_FROM_KEY, True)
        if offset is None:
            return action_result.get_status(), None, None

        # Validate the 'size' action parameter
        size = self._validate_integers(action_result, param.get("size", default_size), FLASHPOINT_ACTION_SIZE_KEY, True)
        if size is None:
            return action_result.get_status(), None, None

        # The API rejects a size above the documented caps, so clamp it here and report the clamp
        size, message = self._clamp_page_size(size, params.get("embed"), max_size, embed_max_size)

        params.update({"from": offset, "size": size})

        return phantom.APP_SUCCESS, params, message

    def _build_indicator_list_params(self, action_result, param):
        """Build the request parameters of the 'list indicators' action.

        The action pages the most recent IoCs, so it carries the type filter, the paging parameters,
        the sort and one date bound. A value lookup and the narrowing filters belong to
        'search indicators', and sending them from here would blur two different jobs into one.

        :param action_result: object of ActionResult class
        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), request parameters, message about a clamped size
        """
        return self._build_query_params(
            action_result,
            param,
            text_params=FLASHPOINT_V2_LIST_TEXT_PARAMS,
            list_params=FLASHPOINT_V2_LIST_LIST_PARAMS,
            enum_params=FLASHPOINT_V2_LIST_ENUM_PARAMS,
            default_size=FLASHPOINT_V2_DEFAULT_SIZE,
        )

    def _build_indicator_search_params(self, action_result, param):
        """Build the request parameters of the 'search indicators' action.

        The action looks an IoC value up and narrows it with every filter the endpoint documents.

        :param action_result: object of ActionResult class
        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), request parameters, message about a clamped size
        """
        return self._build_query_params(
            action_result,
            param,
            text_params=FLASHPOINT_V2_TEXT_PARAMS,
            list_params=FLASHPOINT_V2_LIST_PARAMS,
            enum_params=FLASHPOINT_V2_ENUM_PARAMS,
            boolean_params=FLASHPOINT_V2_BOOLEAN_PARAMS,
            default_size=FLASHPOINT_V2_DEFAULT_SIZE,
        )

    def _build_sighting_params(self, action_result, param, default_size):
        """Build the request parameters of a Technical Intelligence v2 sightings endpoint.

        :param action_result: object of ActionResult class
        :param param: Dictionary of input parameters
        :param default_size: per-request page size default of the endpoint being called
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), request parameters, message about a clamped size
        """
        return self._build_query_params(
            action_result,
            param,
            text_params=FLASHPOINT_SIGHTING_TEXT_PARAMS,
            list_params=FLASHPOINT_SIGHTING_LIST_PARAMS,
            enum_params=FLASHPOINT_SIGHTING_ENUM_PARAMS,
            boolean_params=FLASHPOINT_SIGHTING_BOOLEAN_PARAMS,
            default_size=default_size,
        )

    def _build_alert_params(self, action_result, param):
        """Build the request parameters of the alert notifications endpoint.

        :param action_result: object of ActionResult class
        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), request parameters, message about a clamped size
        """
        # The alert endpoint pages by cursor, so 'from' is not part of its contract
        ret_val, params, message = self._build_query_params(
            action_result,
            param,
            text_params=FLASHPOINT_ALERT_TEXT_PARAMS,
            list_params=FLASHPOINT_ALERT_LIST_PARAMS,
            enum_params=FLASHPOINT_ALERT_ENUM_PARAMS,
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None, None

        # The endpoint rejects a bare relative offset with HTTP 400, so it is caught before the call
        for key in FLASHPOINT_ALERT_DATE_PARAMS:
            value = params.get(key)
            if value and not re.match(FLASHPOINT_ALERT_DATE_PATTERN, value):
                action_result.set_status(phantom.APP_ERROR, FLASHPOINT_INVALID_ALERT_DATE_ERROR.format(parameter=key))
                return action_result.get_status(), None, None

        # The endpoint documents 'size' as 1 to 5000 and answers 0 with HTTP 422, so zero is rejected
        # here rather than sent
        size = self._validate_integers(action_result, param.get("size", FLASHPOINT_ALERT_DEFAULT_SIZE), FLASHPOINT_ACTION_SIZE_KEY)
        if size is None:
            return action_result.get_status(), None, None

        size, message = self._clamp_page_size(size, None, FLASHPOINT_ALERT_MAX_SIZE, FLASHPOINT_ALERT_MAX_SIZE)
        params["size"] = size

        return phantom.APP_SUCCESS, params, message

    @staticmethod
    def _clamp_page_size(size, embed=None, max_size=None, embed_max_size=None):
        """Clamp a per-request page size to the documented record caps.

        :param size: requested number of records per request
        :param embed: value of the 'embed' request parameter, if any
        :param max_size: documented per-request record cap
        :param embed_max_size: lower record cap that applies when 'embed' is provided
        :return: usable page size, message describing the clamp or an empty message
        """
        max_size = FLASHPOINT_V2_MAX_SIZE if max_size is None else max_size
        embed_max_size = FLASHPOINT_V2_MAX_SIZE_WITH_EMBED if embed_max_size is None else embed_max_size

        cap = embed_max_size if embed else max_size
        if size <= cap:
            return size, ""

        reason = FLASHPOINT_EMBED_CLAMP_REASON if embed else FLASHPOINT_MAX_SIZE_CLAMP_REASON

        return cap, FLASHPOINT_SIZE_CLAMPED_MESSAGE.format(size=cap, reason=reason.format(max_size=cap))

    def _handle_list_indicators(self, param):
        """Handle the list indicators action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, params, message = self._build_indicator_list_params(action_result, param)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        return self._fetch_indicators(action_result, params, message)

    def _handle_search_indicators(self, param):
        """Handle the search indicators action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # The quoting of the value is the analyst's intent: a quoted value is an exact match on the
        # API and an unquoted value a partial match, so the value is never re-quoted by the connector
        ioc_value = param.get("ioc_value")
        if not isinstance(ioc_value, str) or not ioc_value.strip():
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_MISSING_REQUIRED_PARAM_ERROR.format(parameter="ioc_value"))

        ret_val, params, message = self._build_indicator_search_params(action_result, param)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        return self._fetch_indicators(action_result, params, message)

    def _fetch_indicators(self, action_result, params, message):
        """Fetch indicators from the Technical Intelligence v2 indicators endpoint.

        :param action_result: object of ActionResult class
        :param params: request parameters
        :param message: message to return with the action status, empty when there is nothing to report
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        ret_val, iocs, total_count = self._paginator_using_offset(
            action_result, FLASHPOINT_INDICATORS_V2_ENDPOINT, params, record_limit=params["size"]
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for ioc in iocs:
            action_result.add_data(ioc)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_iocs"] = action_result.get_data_size()
        if params.get("include_total_count") and total_count is not None:
            summary["total_count"] = total_count

        # Return success
        if message:
            return action_result.set_status(phantom.APP_SUCCESS, message)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_indicator(self, param):
        """Handle the get indicator action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        indicator_id = self._validate_path_id(action_result, param.get("indicator_id"), "indicator_id")
        if indicator_id is None:
            return action_result.get_status()

        params = dict()

        # The by-id endpoint has no 'embed' parameter; the size of the embedded sightings list is
        # the only control it exposes
        sighting_count = self._validate_integers(
            action_result, param.get("sighting_count", FLASHPOINT_V2_DEFAULT_SIGHTING_COUNT), FLASHPOINT_ACTION_SIGHTING_COUNT_KEY
        )
        if sighting_count is None:
            return action_result.get_status()

        if not FLASHPOINT_V2_MIN_SIGHTING_COUNT <= sighting_count <= FLASHPOINT_V2_MAX_SIGHTING_COUNT:
            return action_result.set_status(
                phantom.APP_ERROR,
                FLASHPOINT_INVALID_VALUE_ERROR.format(
                    parameter="sighting_count",
                    allowed_values=f"{FLASHPOINT_V2_MIN_SIGHTING_COUNT} to {FLASHPOINT_V2_MAX_SIGHTING_COUNT}",
                ),
            )

        params["sighting_count"] = sighting_count

        # Make rest call
        ret_val, response = self._make_rest_call(
            FLASHPOINT_INDICATOR_V2_ENDPOINT.format(indicator_id=indicator_id), action_result, params=params
        )
        if phantom.is_fail(ret_val):
            return self._set_not_found_status(action_result, "Indicator")

        if not response:
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR)

        action_result.add_data(response)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_sightings"] = len(response.get("sightings") or [])

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS, "Successfully fetched the indicator")

    def _handle_list_sightings(self, param):
        """Handle the list sightings action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, params, message = self._build_sighting_params(action_result, param, FLASHPOINT_SIGHTING_DEFAULT_SIZE)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        ret_val, sightings, total_count = self._paginator_using_offset(
            action_result, FLASHPOINT_SIGHTINGS_V2_ENDPOINT, params, record_limit=params["size"]
        )
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for sighting in sightings:
            action_result.add_data(sighting)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_sightings"] = action_result.get_data_size()
        if params.get("include_total_count") and total_count is not None:
            summary["total_count"] = total_count

        # Return success
        if message:
            return action_result.set_status(phantom.APP_SUCCESS, message)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_sighting(self, param):
        """Handle the get sighting action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        sighting_id = self._validate_path_id(action_result, param.get("sighting_id"), "sighting_id")
        if sighting_id is None:
            return action_result.get_status()

        # The by-id endpoint exposes no query parameters and always returns the optional blocks that
        # the list endpoint only returns behind 'embed'
        ret_val, response = self._make_rest_call(FLASHPOINT_SIGHTING_V2_ENDPOINT.format(sighting_id=sighting_id), action_result)
        if phantom.is_fail(ret_val):
            return self._set_not_found_status(action_result, "Sighting")

        if not response:
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR)

        action_result.add_data(response)

        # Create summary
        summary = action_result.update_summary({})
        summary["source"] = response.get("source")
        summary["total_related_iocs"] = len(response.get("related_iocs") or [])

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS, "Successfully fetched the sighting")

    def _handle_list_alerts(self, param):
        """Handle the list alerts action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        ret_val, params, message = self._build_alert_params(action_result, param)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # The endpoint pages by cursor, so one action run fetches one page and reports the cursor that
        # continues the walk
        ret_val, alerts, next_cursor, total_count = self._get_alerts(action_result, params)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for alert in alerts:
            action_result.add_data(alert)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_alerts"] = action_result.get_data_size()
        if next_cursor:
            summary["next_cursor"] = next_cursor
        if total_count is not None:
            summary["total_count"] = total_count

        # Return success
        if message:
            return action_result.set_status(phantom.APP_SUCCESS, message)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _set_not_found_status(self, action_result, entity):
        """Replace a raw 404 error with a message naming the missing entity.

        :param action_result: object of ActionResult class
        :param entity: name of the entity that was requested
        :return: status(phantom.APP_ERROR)
        """
        if FLASHPOINT_NOT_FOUND_STATUS_CODE in action_result.get_message():
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NOT_FOUND_ERROR.format(entity=entity))

        return action_result.get_status()

    def _get_alerts(self, action_result, params):
        """Fetch one page of alerts from the alert notifications endpoint.

        Shared by the list alerts action and the alerts ingestion mode.

        :param action_result: object of ActionResult class
        :param params: request parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), alerts, cursor of the next page, total matching alerts
        """
        ret_val, response = self._make_rest_call(FLASHPOINT_ALERTS_ENDPOINT, action_result, params=params)
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None, None, None

        alerts = self._get_records(response)
        if alerts is None:
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None, None, None

        return phantom.APP_SUCCESS, alerts, self._get_next_cursor(response), self._get_total_count(response)

    @staticmethod
    def _get_records(response):
        """Read the record list out of a response envelope.

        The alert endpoint is not covered by the public reference, so the documented Technical
        Intelligence envelope key is tried first and the alternatives observed in Flashpoint's own
        integrations after it.

        :param response: response of make rest call
        :return: list of records, None when the response carries no recognised list
        """
        if not isinstance(response, dict):
            return None

        for key in FLASHPOINT_RECORD_LIST_KEYS:
            records = response.get(key)
            if isinstance(records, list):
                return records

        return None

    @staticmethod
    def _get_next_cursor(response):
        """Read the cursor that continues a cursor-paged walk.

        :param response: response of make rest call
        :return: cursor of the next page, None at exhaustion
        """
        pagination = response.get("pagination") if isinstance(response, dict) else None
        if not isinstance(pagination, dict):
            return None

        next_page = pagination.get("next")
        if not next_page:
            return None

        # The next page is documented as a cursor on this endpoint, but the Technical Intelligence
        # endpoints return an absolute URL, so a URL is reduced to the cursor it carries
        if isinstance(next_page, str) and next_page.startswith("http"):
            cursors = parse_qs(urlparse(next_page).query).get("cursor")
            return cursors[0] if cursors else None

        return next_page if isinstance(next_page, str) else None

    @staticmethod
    def _get_total_count(response):
        """Read the count of matching records from the paging envelope.

        The count is only returned when 'include_total_count' is requested. The Technical Intelligence
        v2 definition models it as a PaginationTotal object, so the count is read from 'total.value'
        when the field carries an object and directly when it carries an integer.

        :param response: response of make rest call
        :return: count of matching records, None when the response does not carry one
        """
        containers = (response, response.get("pagination") or {})
        for container in containers:
            for key in FLASHPOINT_V2_TOTAL_COUNT_KEYS:
                value = container.get(key)
                if isinstance(value, dict):
                    value = value.get("value")
                if isinstance(value, int) and not isinstance(value, bool):
                    return value

        return None

    @staticmethod
    def _get_next_offset(response):
        """Read the offset of the next page from the paging envelope.

        Only the offset is taken from 'pagination.next'; that URL is never requested, so a response
        cannot point the connector at an arbitrary host.

        :param response: response of make rest call
        :return: offset of the next page, None when the result set is exhausted
        """
        next_url = (response.get("pagination") or {}).get("next")
        if not next_url:
            return None

        offsets = parse_qs(urlparse(next_url).query).get("from")
        if not offsets:
            return None

        try:
            return int(offsets[0])
        except ValueError:
            return None

    def _paginator_using_offset(self, action_result, endpoint, params, record_limit=None):
        """Fetch records of a Technical Intelligence v2 list endpoint using offset pagination.

        :param action_result: object of ActionResult class
        :param endpoint: REST endpoint that needs to appended to the service address
        :param params: request parameters, holding the 'from' offset and the per-request 'size'
        :param record_limit: maximum number of records to fetch; None fetches every page
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), fetched records, total matching records
        """
        params = dict(params)
        page_size, _ = self._clamp_page_size(params.get("size", FLASHPOINT_V2_DEFAULT_SIZE), params.get("embed"))
        params["size"] = page_size
        total_items = list()
        total_count = None

        while True:
            # Make rest call
            ret_val, response = self._make_rest_call(endpoint, action_result, params=params)
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None, None

            items = response.get("items")
            if items is None:
                return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None, None

            if total_count is None:
                total_count = self._get_total_count(response)

            # An empty page ends the walk even if the envelope still advertises a next page
            if not items:
                return phantom.APP_SUCCESS, total_items, total_count

            total_items.extend(items)

            if record_limit is not None and len(total_items) >= record_limit:
                return phantom.APP_SUCCESS, total_items[:record_limit], total_count

            next_offset = self._get_next_offset(response)
            if next_offset is None:
                return phantom.APP_SUCCESS, total_items, total_count

            params["from"] = next_offset
            if record_limit is not None:
                params["size"] = min(page_size, record_limit - len(total_items))

    def _handle_run_query(self, param):
        """Handle the run query action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Fetch action parameters
        query = param.get("query")
        if not isinstance(query, str) or not query.strip():
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_MISSING_REQUIRED_PARAM_ERROR.format(parameter="query"))

        limit = param.get("limit", FLASHPOINT_PER_PAGE_DEFAULT_LIMIT)

        # Create request parameters
        params = dict()
        params.update({"query": query})

        # Make rest call
        ret_val, results = self._enable_session_scrolling_paginator(action_result, limit=limit, params=params)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for result in results:
            action_result.add_data(result)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_results"] = action_result.get_data_size()

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_compromised_credentials(self, param):
        """Handle the get compromised credentials action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Fetch action parameters
        query_filter = (param.get("filter") or "").strip()
        limit = param.get("limit", FLASHPOINT_PER_PAGE_DEFAULT_LIMIT)

        # Create request parameters. The filter is a raw query fragment, so it is joined with a
        # space rather than concatenated: without the separator a value that does not open with its
        # own '+' or '-' fuses onto the 'credential-sighting' term, which the endpoint answers with
        # HTTP 400 for a clause and with an empty result set for a bare word - a silent wrong answer
        params = dict()
        query = " ".join(clause for clause in ("+basetypes:credential-sighting", query_filter) if clause)

        params.update({"query": query})

        # The complexity rules are evaluated server-side against the Ignite CCM-E settings and the
        # API defaults the filter to false, so the parameter is sent only when the analyst enables it
        if param.get("meets_pw_complexity"):
            params.update({"meets_pw_complexity": "true"})

        # Make rest call
        ret_val, results = self._enable_session_scrolling_paginator(action_result, limit=limit, params=params)

        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for result in results:
            action_result.add_data(result)

        # Create summary
        summary = action_result.update_summary({})
        summary["total_results"] = action_result.get_data_size()

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_params_endpoint(self, action_result, limit=None, params=None):
        """Preprocess the input parameters for the paginator.

        :param action_result: object of ActionResult class
        :param limit: maximum number of results to be fetched
        :param params: request parameters

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), params, endpoint
        """
        # Validate the 'limit' action parameter
        limit = self._validate_integers(action_result, limit, FLASHPOINT_ACTION_LIMIT_KEY)
        if limit is None:
            return action_result.get_status(), None, None, None

        # Define per page limit
        page_limit = FLASHPOINT_PER_PAGE_DEFAULT_LIMIT

        if limit and limit <= FLASHPOINT_PER_PAGE_DEFAULT_LIMIT:
            page_limit = limit

        if params:
            params.update({"limit": page_limit})
        else:
            params = dict()
            params.update({"limit": page_limit})

        # Enable the session scroll for the first time
        params.update({"scroll": f"{self._session_timeout}m"})

        return phantom.APP_SUCCESS, params, FLASHPOINT_ALL_SEARCH_ENDPOINT, limit

    def _enable_session_scrolling_paginator(self, action_result, limit=None, params=None):
        """Enable session scrolling for the all search APIs and fetch the results based on provided request parameters.

        :param action_result: object of ActionResult class
        :param limit: maximum number of results to be fetched
        :param params: request parameters

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), fetched all search results
        """
        total_items = list()
        endpoint = ""
        scroll_id = None

        # initial processor for paginator which creates endpoint parameters
        ret_val, params, endpoint, limit = self._get_params_endpoint(action_result, limit, params)
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None

        self.debug_print("Making the first REST call to enable session scrolling")

        # Make rest call
        ret_val, response = self._make_rest_call(endpoint, action_result, params=params)
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None

        items, scroll_id = self._paginator_response_processing(response)

        if not items:
            # Disable session scrolling before returning from the initial paginator
            ret_val = self._disable_session_scrolling(action_result, scroll_id)
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

            if items is None:
                return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None

            return phantom.APP_SUCCESS, []

        total_items.extend(items)

        if limit and len(total_items) >= limit:
            # Disable session scrolling before returning from the initial paginator
            ret_val = self._disable_session_scrolling(action_result, scroll_id)
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

            return phantom.APP_SUCCESS, total_items[:limit]

        # Limit for remaining results fetching. A limit below one page would otherwise go negative
        # and slice fetched records away
        limit_for_further_paginator = max(0, limit - len(total_items))

        ret_val, items = self._further_pagination(action_result, limit=limit_for_further_paginator, scroll_id=scroll_id)
        if phantom.is_fail(ret_val):
            # Disable session scrolling before returning from the initial paginator
            self._disable_session_scrolling(action_result, scroll_id)
            return action_result.get_status(), None

        total_items.extend(items)

        # Return success with fetched all data
        return phantom.APP_SUCCESS, total_items

    def _get_scrolling_endpoint(self):
        """Determine the scrolling endpoint for the paginator.

        :return: scrolling endpoint
        """
        return f"{FLASHPOINT_ALL_SEARCH_SCROLL_ENDPOINT}?scroll={self._session_timeout}m"

    def _further_pagination(self, action_result, limit, scroll_id):
        """Fetch all search results using scroll ID.

        :param action_result: object of ActionResult class
        :param limit: maximum number of results to be fetched
        :param scroll_id: it will use to fetch results by scrolling

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), fetched all search results
        """
        total_items = list()

        # If not scroll id, return success with fetched data
        if not scroll_id:
            return phantom.APP_SUCCESS, total_items

        # Create request data for session scrolling
        data = {"scroll_id": scroll_id}

        self.debug_print("Making a further rest call for getting remaning data using fetched scroll ID")
        while True:
            # Make rest call
            ret_val, response = self._make_rest_call(self._get_scrolling_endpoint(), action_result, method="post", data=json.dumps(data))
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

            items, _ = self._paginator_response_processing(response)

            if items is None:
                return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None

            total_items.extend(items)

            # Fetched all data and fetched items list is empty and not None
            if not items:
                self.debug_print("Fetched all data and fetched items list is empty and not None")
                break

            if limit and len(total_items) >= limit:
                # Disable session scrolling before returning from the further paginator
                ret_val = self._disable_session_scrolling(action_result, scroll_id)
                if phantom.is_fail(ret_val):
                    return action_result.get_status(), None

                return phantom.APP_SUCCESS, total_items[:limit]

        # Disable session scrolling before returning from the further paginator
        ret_val = self._disable_session_scrolling(action_result, scroll_id)
        if phantom.is_fail(ret_val):
            return action_result.get_status(), None

        # Return success with fetched data
        return phantom.APP_SUCCESS, total_items

    @staticmethod
    def _paginator_response_processing(response):
        """Get all search results from the response of make rest call.

        :param response: response of make rest call
        :return: all search results, scroll ID
        """
        return response.get("hits", {}).get("hits"), response.get("_scroll_id")

    def _disable_session_scrolling(self, action_result, scroll_id):
        """Disable session scrolling for the all search APIs.

        :param action_result: object of ActionResult class
        :param scroll_id: session scroll id to be disabled.

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        if not scroll_id:
            self.debug_print("Scroll session is not available")
            return phantom.APP_SUCCESS

        data = {"scroll_id": scroll_id}

        self.debug_print("Make a rest call to disable scroll session")

        # Make rest call
        ret_val, _ = self._make_rest_call(FLASHPOINT_ALL_SEARCH_SCROLL_ENDPOINT, action_result, method="delete", data=json.dumps(data))

        if phantom.is_fail(ret_val):
            # If session already disabled
            if FLASHPOINT_ALREADY_DISABLE_SESSION_SCROLL_ERROR_MESSAGE in action_result.get_message():
                self.debug_print("Session is already disabled")
                return phantom.APP_SUCCESS
            return action_result.get_status()

        self.debug_print("Successfully disabled the scroll session")
        return phantom.APP_SUCCESS

    def _paginator_using_skip(self, action_result, endpoint, limit=None, params=None):
        """Fetch reports data using skip pagination.

        :param action_result: object of ActionResult class
        :param endpoint: REST endpoint that needs to appended to the service address
        :param limit: maximum number of results to be fetched
        :param params: request parameters

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), total reports
        """
        total_reports = list()
        skip = 0

        # Define per page limit
        page_limit = FLASHPOINT_REPORTS_DEFAULT_LIMIT

        if limit and limit <= page_limit:
            page_limit = limit

        if params:
            params.update({"limit": page_limit})
        else:
            params = dict()
            params.update({"limit": page_limit})

        while True:
            params.update({"skip": skip})

            # Make rest call
            ret_val, response = self._make_rest_call(endpoint, action_result, params=params)

            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

            # Fetch data from response
            reports = response.get("data")
            if reports is None:
                return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None

            total_reports.extend(reports)

            if limit and len(total_reports) >= limit:
                return phantom.APP_SUCCESS, total_reports[:limit]

            # An exhausted result set ends the walk; the count is absent on some responses, so the
            # empty page is the fallback signal
            total = response.get("total")
            if not reports or (isinstance(total, int) and len(total_reports) >= total):
                return phantom.APP_SUCCESS, total_reports

            skip += page_limit

    def _handle_test_connectivity(self, param):
        """Validate the asset configuration for connectivity using supplied configuration.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.debug_print(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        self.save_progress("Trying to fetch IoCs using indicators endpoint")

        # Fetch single indicator(IoC) for the test connectivity
        param = dict()
        param.update({"size": 1})

        # Make rest call
        ret_val, response = self._make_rest_call(FLASHPOINT_INDICATORS_V2_ENDPOINT, action_result, params=param)

        if phantom.is_fail(ret_val):
            self.save_progress("Test Connectivity Failed")
            return action_result.get_status()

        # A proxy or captive portal answering 2xx with an empty body would otherwise pass the test
        # without a Flashpoint API having been reached, so the record list is what is asserted
        if self._get_records(response) is None:
            self.save_progress("Test Connectivity Failed")
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_UNEXPECTED_RESPONSE_ERROR)

        # Return success
        self.save_progress("Test Connectivity Passed")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _fetch_reports(self, action_result, endpoint, limit):
        """Fetch reports data.

        :param action_result: object of ActionResult class
        :param endpoint: REST endpoint that needs to appended to the service address
        :param limit: maximum number of results to be fetched

        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        # Validate the 'limit' action parameter
        limit = self._validate_integers(action_result, limit, FLASHPOINT_ACTION_LIMIT_KEY)
        if limit is None:
            return action_result.get_status()

        # Call paginator to fetch data
        ret_val, reports = self._paginator_using_skip(action_result, endpoint, limit)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        for report in reports:
            action_result.add_data(report)

        # Return success
        return phantom.APP_SUCCESS

    def _handle_list_reports(self, param):
        """Handle the list reports action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Fetch action parameters
        limit = param.get("limit", FLASHPOINT_REPORTS_DEFAULT_LIMIT)

        # Fetch reports data
        ret_val = self._fetch_reports(action_result, FLASHPOINT_LIST_REPORTS_ENDPOINT, limit)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Create summary
        summary = action_result.update_summary({})
        summary["total_reports"] = action_result.get_data_size()

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_list_related_reports(self, param):
        """Handle the list related reports action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Fetch action parameters
        ret_val, report_id = self._validate_report_id(param.get("report_id"), action_result)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        limit = param.get("limit", FLASHPOINT_REPORTS_DEFAULT_LIMIT)

        # Fetch reports
        ret_val = self._fetch_reports(action_result, FLASHPOINT_LIST_RELATED_REPORTS_ENDPOINT.format(report_id=report_id), limit)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Create summary
        summary = action_result.update_summary({})
        summary["total_related_reports"] = action_result.get_data_size()

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_report(self, param):
        """Handle the get report action.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Fetch action parameters
        ret_val, report_id = self._validate_report_id(param.get("report_id"), action_result)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Make rest call
        ret_val, report = self._make_rest_call(FLASHPOINT_GET_REPORT_ENDPOINT.format(report_id=report_id), action_result)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Add fetched data to action result object
        action_result.add_data(report)

        # Return success
        return action_result.set_status(phantom.APP_SUCCESS, "Successfully fetched report")

    def _validate_integers(self, action_result, parameter, key, allow_zero=False):
        """Check if the provided input parameter value is a non-zero positive integer and returns the integer value of the parameter itself.

        :param action_result: Action result object
        :param parameter: input parameter
        :return: integer value of the parameter
        """
        try:
            if not float(parameter).is_integer():
                action_result.set_status(phantom.APP_ERROR, FLASHPOINT_ERROR_VALID_INT_MESSAGE.format(parameter=key))
                return None

            parameter = int(parameter)
            if parameter <= 0:
                if allow_zero:
                    if parameter < 0:
                        action_result.set_status(phantom.APP_ERROR, FLASHPOINT_LIMIT_VALIDATION_ALLOW_ZERO_MESSAGE.format(parameter=key))
                        return None
                else:
                    action_result.set_status(phantom.APP_ERROR, FLASHPOINT_LIMIT_VALIDATION_MESSAGE.format(parameter=key))
                    return None
        except Exception:
            error_text = (
                FLASHPOINT_LIMIT_VALIDATION_ALLOW_ZERO_MESSAGE.format(parameter=key)
                if allow_zero
                else FLASHPOINT_LIMIT_VALIDATION_MESSAGE.format(parameter=key)
            )
            action_result.set_status(phantom.APP_ERROR, error_text)
            return None
        return parameter

    def _handle_on_poll(self, param):
        """Handle the on poll action by ingesting the data source selected in the asset configuration.

        :param param: Dictionary of input parameters
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        self.save_progress(f"In action handler for: {self.get_action_identifier()}")

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        config = self.get_config()
        ingestion_type = config.get("ingestion_type", FLASHPOINT_DEFAULT_INGESTION_TYPE)

        if ingestion_type not in FLASHPOINT_INGESTION_TYPES:
            return action_result.set_status(
                phantom.APP_ERROR, FLASHPOINT_INVALID_INGESTION_TYPE_ERROR.format(allowed_values=", ".join(FLASHPOINT_INGESTION_TYPES))
            )

        # Validate the 'first_run_window' config parameter
        first_run_window = self._validate_integers(
            action_result, config.get("first_run_window", FLASHPOINT_DEFAULT_FIRST_RUN_WINDOW), FLASHPOINT_CONFIG_FIRST_RUN_WINDOW_KEY
        )
        if first_run_window is None:
            return action_result.get_status()

        # A manual run is bounded by the caps the platform passes in; a scheduled run by the setting
        is_poll_now = self.is_poll_now()
        if is_poll_now:
            max_events = param.get(phantom.APP_JSON_CONTAINER_COUNT, FLASHPOINT_DEFAULT_MAX_EVENTS_PER_POLL)
        else:
            max_events = config.get("max_events_per_poll", FLASHPOINT_DEFAULT_MAX_EVENTS_PER_POLL)

        max_events = self._validate_integers(action_result, max_events, FLASHPOINT_CONFIG_MAX_EVENTS_KEY)
        if max_events is None:
            return action_result.get_status()

        # Splunk SOAR rejects a container whose label does not already exist on the platform, so an
        # unset label is reported here instead of failing every container save of the run
        if not (config.get("ingest") or {}).get("container_label"):
            return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_MISSING_CONTAINER_LABEL_ERROR)

        if ingestion_type == FLASHPOINT_INGESTION_ALERTS:
            return self._ingest_alerts(action_result, config, first_run_window, max_events, is_poll_now)

        return self._ingest_credentials(action_result, config, first_run_window, max_events, is_poll_now)

    def _get_ingestion_window(self, state_key, first_run_window):
        """Read the window an ingestion mode is draining, or open a new one.

        A poll that could not finish its window leaves the window in the state together with the
        position it reached, so the next poll resumes there instead of skipping the remainder. A
        state written before this checkpoint existed carries only 'last_ingested_time', which is
        used as the start of a freshly opened window.

        :param state_key: state key of the ingestion mode
        :param first_run_window: number of days to backfill when there is no saved position
        :return: saved state of the mode, start of the window, end of the window, resuming flag
        """
        mode_state = self._state.get(state_key) or {}

        window_start = mode_state.get(FLASHPOINT_STATE_WINDOW_START)
        window_end = mode_state.get(FLASHPOINT_STATE_WINDOW_END)

        # An unfinished window is resumed exactly as it was, so its upper bound never moves and
        # records that arrived after it are left for the following window
        if window_start and window_end:
            return mode_state, window_start, window_end, True

        # A drained window leaves its advance point in 'window_start' with no upper bound, so that
        # value opens the next window; the legacy key is only read when there is no saved point
        window_start = window_start or mode_state.get(FLASHPOINT_STATE_LEGACY_TIME)
        if not window_start:
            window_start = self._format_datetime(datetime.now(timezone.utc) - timedelta(days=first_run_window))

        return mode_state, window_start, self._format_datetime(datetime.now(timezone.utc)), False

    def _save_ingestion_window(self, state_key, mode_state, window_start, window_end, position, drained):
        """Write the checkpoint of an ingestion mode.

        :param state_key: state key of the ingestion mode
        :param mode_state: saved state of the mode
        :param window_start: start of the window that was read
        :param window_end: end of the window that was read
        :param position: offset or cursor the next poll resumes from; ignored when drained
        :param drained: True when the window held no more records than this poll read
        """
        if drained:
            # The window is finished, so the next one starts where this one ended
            mode_state[FLASHPOINT_STATE_WINDOW_START] = window_end
            mode_state.pop(FLASHPOINT_STATE_WINDOW_END, None)
            mode_state.pop(FLASHPOINT_STATE_OFFSET, None)
            mode_state.pop(FLASHPOINT_STATE_CURSOR, None)
        else:
            mode_state[FLASHPOINT_STATE_WINDOW_START] = window_start
            mode_state[FLASHPOINT_STATE_WINDOW_END] = window_end
            key = FLASHPOINT_STATE_OFFSET if isinstance(position, int) else FLASHPOINT_STATE_CURSOR
            mode_state[key] = position

        # The legacy key is no longer read once a window is saved, so it is dropped rather than left
        # behind to look like a second, contradicting checkpoint
        mode_state.pop(FLASHPOINT_STATE_LEGACY_TIME, None)
        self._state[state_key] = mode_state

    @staticmethod
    def _format_datetime(value):
        """Render a datetime in the ISO-8601 UTC form the API documents for its date filters.

        :param value: datetime object
        :return: ISO-8601 UTC string
        """
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _get_alert_cursor(alert):
        """Build the cursor that resumes an ascending alert walk after the given alert.

        The endpoint's cursor is the 'created_at' of the last alert of a page, as epoch seconds with
        microseconds. Deriving it from a record makes the position of a truncated batch expressible,
        which the cursor of the last page fetched is not.

        :param alert: alert record the next poll resumes after
        :return: cursor value, None when the alert carries no usable 'created_at'
        """
        created_at = alert.get("created_at")
        if not isinstance(created_at, str):
            return None

        try:
            moment = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            try:
                moment = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None

        return f"{moment.timestamp():.6f}"

    @staticmethod
    def _build_ingest_message(containers, records, entity, window_start, window_end, position, drained, is_poll_now):
        """Build the status message of an ingestion run, naming an unfinished window.

        A truncated window used to read exactly like a completed one, so a poll that left records
        behind looked like a poll that had nothing more to fetch.

        :param containers: number of containers created
        :param records: number of records read
        :param entity: name of the ingested entity
        :param window_start: start of the window that was read
        :param window_end: end of the window that was read
        :param position: offset or cursor the next poll resumes from
        :param drained: True when the window held no more records than this poll read
        :param is_poll_now: True for a manual run, which does not move the checkpoint
        :return: status message
        """
        ingested = FLASHPOINT_ON_POLL_INGESTED_MESSAGE.format(containers=containers, records=records, entity=entity)

        if drained or is_poll_now:
            return ingested

        return FLASHPOINT_ON_POLL_RESUME_MESSAGE.format(ingested=ingested, window_start=window_start, window_end=window_end, position=position)

    def _ingest_alerts(self, action_result, config, first_run_window, max_events, is_poll_now):
        """Ingest Flashpoint alerts as containers with one artifact per alert.

        :param action_result: object of ActionResult class
        :param config: asset configuration
        :param first_run_window: number of days to backfill when there is no saved position
        :param max_events: maximum number of containers to create in this run
        :param is_poll_now: True for a manual run, which must not move the checkpoint
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        mode_state, created_after, created_before, resuming = self._get_ingestion_window(FLASHPOINT_STATE_ALERTS_KEY, first_run_window)

        # The endpoint defaults to 'created_at:desc'. The walk is ordered oldest-first so the cursor
        # continues forward, in the same direction the window moves; under the default order the
        # cursor points back into history and contradicts the next window
        params = {
            "created_after": created_after,
            "created_before": created_before,
            "sort": FLASHPOINT_ALERT_INGEST_SORT,
            "size": min(max_events, FLASHPOINT_ALERT_MAX_SIZE),
        }

        if config.get("alert_sources"):
            sources = self._validate_list_param(action_result, config["alert_sources"], "alert_sources", FLASHPOINT_ALERT_SOURCE_VALUES)
            if sources is None:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    FLASHPOINT_INVALID_CONFIG_VALUE_ERROR.format(
                        parameter="alert_sources", allowed_values=", ".join(FLASHPOINT_ALERT_SOURCE_VALUES)
                    ),
                )
            params["sources"] = sources

        # Both filters are single-valued on this endpoint: a comma-joined value is answered with
        # HTTP 422 and a repeated parameter keeps only the last value, so one value is validated
        # here against the same set the 'list alerts' action accepts and rejected before the call
        for config_key, request_key in FLASHPOINT_ALERT_INGEST_ENUM_CONFIG.items():
            value = (config.get(config_key) or "").strip().lower()
            # A SOAR dropdown cannot be cleared once set, so 'All' is the sentinel for no filter
            if not value or value == FLASHPOINT_CONFIG_ALL.lower():
                continue
            allowed_values = FLASHPOINT_ALERT_ENUM_PARAMS[request_key]
            if value not in allowed_values:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    FLASHPOINT_INVALID_CONFIG_VALUE_ERROR.format(parameter=config_key, allowed_values=", ".join(allowed_values)),
                )
            params[request_key] = value

        # A manual run must not consume the saved cursor, otherwise it would advance the scheduled walk
        cursor = None if is_poll_now else mode_state.get(FLASHPOINT_STATE_CURSOR)

        alerts = list()
        next_cursor = None
        drained = False
        while len(alerts) < max_events:
            if cursor:
                params["cursor"] = cursor

            ret_val, page, next_cursor, _ = self._get_alerts(action_result, params)
            if phantom.is_fail(ret_val):
                return action_result.get_status()

            alerts.extend(page)

            # A short page or an exhausted cursor means the window holds nothing further
            if not page or not next_cursor:
                drained = True
                break

            cursor = next_cursor

        # More records than this poll may create: the remainder stays in the window and the cursor
        # of the last page consumed is where the next poll resumes
        if len(alerts) > max_events:
            drained = False
            next_cursor = self._get_alert_cursor(alerts[max_events - 1])

        alerts = alerts[:max_events]

        containers = 0
        for alert in alerts:
            ret_val = self._save_alert_container(action_result, alert, config)
            if phantom.is_fail(ret_val):
                return action_result.get_status()
            containers += 1

        # The checkpoint is written only after the containers of this batch are saved, so a failed
        # poll repeats its window instead of skipping it
        if not is_poll_now:
            self._save_ingestion_window(FLASHPOINT_STATE_ALERTS_KEY, mode_state, created_after, created_before, next_cursor, drained)

        summary = action_result.update_summary({})
        summary["total_containers"] = containers
        summary["window_start"] = created_after
        summary["window_end"] = created_before
        summary["window_drained"] = drained
        if resuming:
            summary["resumed_window"] = True

        return action_result.set_status(
            phantom.APP_SUCCESS,
            self._build_ingest_message(containers, len(alerts), "alert", created_after, created_before, next_cursor, drained, is_poll_now),
        )

    @staticmethod
    def _build_alert_container_name(alert_id, reason, resource):
        """Build the container name for one alert.

        The matched content's own title and the rule name are neither of them unique on their own:
        every reply in the same thread shares the same 'resource.title', and every alert raised by
        the same rule shares its 'reason.name'. The short alert-id fragment is appended so the case
        list stays visually distinguishable even when the content title and the rule repeat.

        :param alert_id: id of the alert
        :param reason: 'reason' block of the alert
        :param resource: 'resource' block of the alert
        :return: container name
        """
        parts = [str(part) for part in (resource.get("title"), reason.get("name")) if part]
        if not parts:
            return f"Flashpoint alert {alert_id}"

        short_id = alert_id[:8]
        return f"{' - '.join(parts)} ({short_id})"

    def _save_alert_container(self, action_result, alert, config):
        """Create the container and artifacts of one alert.

        :param action_result: object of ActionResult class
        :param alert: alert record
        :param config: asset configuration
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        alert_id = str(alert.get("id") or "")
        if not alert_id:
            self.debug_print("Skipping an alert that carries no identifier")
            return phantom.APP_SUCCESS

        reason = alert.get("reason") or {}
        resource = alert.get("resource") or {}
        name = self._build_alert_container_name(alert_id, reason, resource)
        container_label = (self.get_config().get("ingest") or {}).get("container_label")

        container = {
            "name": name,
            "source_data_identifier": alert_id,
            "label": container_label,
            # The alert payload carries no severity field, so the container severity is the setting
            "severity": config.get("event_severity", FLASHPOINT_DEFAULT_EVENT_SEVERITY),
            "data": alert,
        }

        if alert.get("generated_at"):
            container["start_time"] = alert["generated_at"]

        artifacts = [
            {
                "name": "Alert Artifact",
                "source_data_identifier": alert_id,
                "severity": container["severity"],
                "cef": self._build_alert_cef(alert),
                "cef_types": {"requestURL": ["url"]},
                "data": alert,
            }
        ]

        # A vulnerability alert is a digest: one alert carries up to 25 vulnerabilities, each of
        # which is patched, deferred or accepted on its own, so each gets its own artifact. The
        # alert artifact alone would leave a playbook with a rule name and no CVE to act on
        for vulnerability in resource.get("vulns") or []:
            vulnerability_id = str(vulnerability.get("vuln_id") or "")
            if not vulnerability_id:
                continue
            artifacts.append(
                {
                    "name": "Vulnerability Artifact",
                    # The alert id alone repeats across the vulnerabilities of one digest, so the
                    # vulnerability id is part of the identifier that deduplicates a re-poll
                    "source_data_identifier": f"{alert_id}:{vulnerability_id}",
                    "severity": container["severity"],
                    "cef": self._build_vulnerability_cef(vulnerability),
                    "cef_types": {"flashpointVulnUrl": ["url"]},
                    "data": vulnerability,
                }
            )

        return self._save_container_with_artifacts(action_result, container, artifacts)

    @staticmethod
    def _build_vulnerability_cef(vulnerability):
        """Map one vulnerability of a vulnerability-alert digest onto CEF fields.

        The long 'description' and 'solution' texts are left in the artifact data rather than
        copied into CEF, where they would not be read by a playbook.

        :param vulnerability: entry of the alert's 'resource.vulns' list
        :return: CEF dictionary
        """
        cef = dict()
        for cef_key, value in (
            ("flashpointVulnId", vulnerability.get("vuln_id")),
            ("flashpointVulnTitle", vulnerability.get("title")),
            # The two numbers a patch-prioritisation playbook branches on: severity and the
            # probability of exploitation
            ("flashpointVulnCvssV3", vulnerability.get("cvss_v3")),
            ("flashpointVulnEpss", vulnerability.get("epss")),
            ("flashpointVulnLocation", vulnerability.get("location")),
            ("flashpointVulnPublishedAt", vulnerability.get("published_at")),
            ("flashpointVulnUrl", vulnerability.get("ignite_url")),
        ):
            if value is not None and value != "":
                cef[cef_key] = value

        return cef

    @staticmethod
    def _build_alert_cef(alert):
        """Map an alert onto CEF fields playbooks can pivot on.

        :param alert: alert record
        :return: CEF dictionary
        """
        cef = dict()
        reason = alert.get("reason") or {}
        resource = alert.get("resource") or {}
        site = resource.get("site") or {}
        site_actor = resource.get("site_actor") or {}
        # The channel, board or thread the matched content sits in. 'site.title' names the platform
        # ('Telegram'), which is not enough to tell an analyst where to look
        channel = resource.get("container") or {}
        # The resource carries its link as 'native_url'; the reference page's 'url' field is not
        # returned by the endpoint, so the Ignite search link is the last fallback
        resource_url = resource.get("native_url") or resource.get("link") or resource.get("ignite_search_url")
        # When the content was posted, which is not when the rule matched it
        posted_at = (resource.get("created_at") or {}).get("date-time") or resource.get("sort_date")

        for cef_key, value in (
            ("flashpointAlertId", alert.get("id")),
            ("flashpointAlertStatus", alert.get("status")),
            ("flashpointAlertSource", alert.get("source")),
            ("flashpointAlertDataType", alert.get("data_type")),
            ("flashpointAlertReason", reason.get("name")),
            ("flashpointAlertReasonId", reason.get("id")),
            ("flashpointAlertReasonOrigin", reason.get("origin")),
            ("flashpointAlertReasonQuery", reason.get("text")),
            ("flashpointResourceId", resource.get("id")),
            ("flashpointResourceTitle", resource.get("title")),
            ("flashpointSiteTitle", site.get("title")),
            ("flashpointChannelTitle", channel.get("title") or channel.get("name")),
            ("flashpointChannelId", channel.get("native_id")),
            ("sourceUserName", (site_actor.get("names") or {}).get("handle")),
            # A handle is renamed freely; the platform id is what identifies the actor over time
            ("flashpointSiteActorId", site_actor.get("native_id")),
            ("flashpointContentPostedAt", posted_at),
            ("requestURL", resource_url),
            ("flashpointHighlightText", alert.get("highlight_text")),
            ("startTime", alert.get("generated_at")),
            ("endTime", alert.get("created_at")),
        ):
            if value:
                cef[cef_key] = value

        if alert.get("is_read") is not None:
            cef["flashpointAlertIsRead"] = alert["is_read"]

        return cef

    def _ingest_credentials(self, action_result, config, first_run_window, max_events, is_poll_now):
        """Ingest compromised credential sightings as containers with one artifact per sighting.

        :param action_result: object of ActionResult class
        :param config: asset configuration
        :param first_run_window: number of days to backfill when there is no saved position
        :param max_events: maximum number of containers to create in this run
        :param is_poll_now: True for a manual run, which must not move the checkpoint
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        mode_state, start_time, end_time, resuming = self._get_ingestion_window(FLASHPOINT_STATE_CREDENTIALS_KEY, first_run_window)
        # A manual run must not consume the saved position, otherwise it would advance the scheduled walk
        offset = 0 if is_poll_now else int(mode_state.get(FLASHPOINT_STATE_OFFSET) or 0)

        query = self._build_credential_ingest_query(config, start_time, end_time)

        # Ascending order on the watermark field keeps the walk aligned with the saved position. The
        # sortable form of that field is the breach timestamp; a sort on the bare field is ignored
        params = {"query": query, "sort": f"{FLASHPOINT_CREDENTIAL_SORT_FIELD}:asc"}

        if config.get("meets_pw_complexity"):
            params["meets_pw_complexity"] = "true"

        ret_val, records = self._paginator_using_search_offset(action_result, params, max_events, offset)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        containers = 0
        for record in records:
            ret_val = self._save_credential_container(action_result, record, config)
            if phantom.is_fail(ret_val):
                return action_result.get_status()
            containers += 1

        # Fewer records than the poll asked for means the window holds nothing further
        drained = len(records) < max_events
        position = offset + len(records)

        # The endpoint refuses 'from' + 'size' beyond its ceiling, so a window deeper than that is
        # continued by moving its start to the last record read and restarting the offset
        if not drained and position + max_events > FLASHPOINT_SEARCH_OFFSET_CEILING:
            watermark = self._get_credential_watermark(records[-1])
            if watermark:
                start_time, position = watermark, 0

        # The checkpoint is written only after the containers of this batch are saved, so a failed
        # poll repeats its window instead of skipping it
        if not is_poll_now:
            self._save_ingestion_window(FLASHPOINT_STATE_CREDENTIALS_KEY, mode_state, start_time, end_time, position, drained)

        summary = action_result.update_summary({})
        summary["total_containers"] = containers
        summary["window_start"] = start_time
        summary["window_end"] = end_time
        summary["window_drained"] = drained
        if resuming:
            summary["resumed_window"] = True

        return action_result.set_status(
            phantom.APP_SUCCESS,
            self._build_ingest_message(
                containers, len(records), "credential sighting", start_time, end_time, f"offset {position}", drained, is_poll_now
            ),
        )

    def _build_credential_ingest_query(self, config, start_time, end_time):
        """Build the credential ingestion query for the configured window and standing filter.

        :param config: asset configuration
        :param start_time: start of the window
        :param end_time: end of the window
        :return: query
        """
        # A credential-sighting document carries its datetimes under 'breach', so the window is
        # expressed on the breach sub-field; the bare '+created_at:' clause matches no records
        clauses = ["+basetypes:credential-sighting", f"+{FLASHPOINT_CREDENTIAL_DATE_FIELD}:[{start_time} TO {end_time}]"]

        # The standing filter is a raw query fragment in the same syntax as the action parameter,
        # so it is appended as its own clause and left exactly as the analyst wrote it
        credential_filter = (config.get("credential_filter") or "").strip()
        if credential_filter:
            clauses.append(credential_filter)

        if config.get("fresh_credentials_only", FLASHPOINT_DEFAULT_FRESH_CREDENTIALS_ONLY):
            clauses.append("+is_fresh:true")

        return " ".join(clauses)

    @staticmethod
    def _get_credential_watermark(record):
        """Read the window position of a credential sighting.

        Used only when the offset walk reaches the ceiling of the search endpoint: the window is then
        restarted from the datetime of the last record read, which is the one position the endpoint
        can still address.

        :param record: credential sighting record
        :return: ISO-8601 datetime of the record, None when it carries none
        """
        breach = ((record.get("_source") or {}).get("breach") or {}).get(FLASHPOINT_CREDENTIAL_WATERMARK) or {}
        watermark = breach.get("date-time")

        return watermark if isinstance(watermark, str) and watermark else None

    def _paginator_using_search_offset(self, action_result, params, record_limit, start_offset=0):
        """Fetch credential records with offset paging bounded by the documented offset ceiling.

        The noncommunities search rejects a request whose from + size exceeds the ceiling, so the walk
        stops at the ceiling rather than issuing a request the API refuses.

        :param action_result: object of ActionResult class
        :param params: request parameters
        :param record_limit: maximum number of records to fetch
        :param start_offset: offset of the first unread record of the window being resumed
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR), fetched records
        """
        params = dict(params)
        total_records = list()
        offset = start_offset

        while len(total_records) < record_limit:
            page_size = min(FLASHPOINT_CREDENTIAL_INGEST_PAGE_SIZE, record_limit - len(total_records))
            if offset + page_size > FLASHPOINT_SEARCH_OFFSET_CEILING:
                page_size = FLASHPOINT_SEARCH_OFFSET_CEILING - offset

            if page_size <= 0:
                self.debug_print("Reached the documented offset ceiling of the search endpoint; the window is resumed on the next poll")
                break

            params.update({"from": offset, "size": page_size})

            # Make rest call
            ret_val, response = self._make_rest_call(FLASHPOINT_ALL_SEARCH_ENDPOINT, action_result, params=params)
            if phantom.is_fail(ret_val):
                return action_result.get_status(), None

            records = (response.get("hits") or {}).get("hits")
            if records is None:
                return action_result.set_status(phantom.APP_ERROR, FLASHPOINT_NO_DATA_FOUND_ERROR), None

            if not records:
                break

            total_records.extend(records)
            offset += len(records)

        return phantom.APP_SUCCESS, total_records[:record_limit]

    def _save_credential_container(self, action_result, record, config):
        """Create the container and artifact of one credential sighting.

        :param action_result: object of ActionResult class
        :param record: credential sighting record
        :param config: asset configuration
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        source = record.get("_source") or {}
        # The breached password is stored only when the asset opts in: a CEF field is indexed and
        # searchable platform-wide and the raw record is readable on both the container and the
        # artifact, so the default keeps the plaintext out of SOAR altogether
        store_password = config.get("store_plaintext_password", FLASHPOINT_DEFAULT_STORE_PLAINTEXT_PASSWORD)
        if not store_password and "password" in source:
            record = copy.deepcopy(record)
            source = record["_source"]
            source.pop("password", None)

        # The search hit's own '_id' is the stable per-sighting identifier; '_source.fpid' is the
        # credential record, which repeats across sightings of the same credential
        record_id = str(record.get("_id") or source.get("fpid") or "")
        if not record_id:
            self.debug_print("Skipping a credential sighting that carries no identifier")
            return phantom.APP_SUCCESS

        email = source.get("email")
        domain = source.get("domain")
        breach = source.get("breach") or {}
        container_label = (self.get_config().get("ingest") or {}).get("container_label")

        container = {
            "name": f"Flashpoint compromised credential: {email or domain or record_id}",
            "source_data_identifier": record_id,
            "label": container_label,
            "severity": config.get("event_severity", FLASHPOINT_DEFAULT_EVENT_SEVERITY),
            "data": record,
        }

        # The container timeline is the moment the credential was observed, not the moment the poll
        # read it; without this every ingested credential claims to have happened at ingestion time
        observed_at = ((breach.get("first_observed_at") or {}).get("date-time")) or ((breach.get("created_at") or {}).get("date-time"))
        if observed_at:
            container["start_time"] = observed_at

        cef = dict()
        for cef_key, value in (
            ("email", email),
            ("domain", domain),
            # The credential itself: the password a playbook compares against the directory and the
            # account it belongs to, which is not always the email address. The password is present
            # only when the asset opted in; it was stripped from the record otherwise
            ("password", source.get("password")),
            ("sourceUserName", source.get("username")),
            ("destinationDnsDomain", source.get("affected_domain")),
            ("requestURL", source.get("affected_url")),
            # Identifiers a result pivots on: the breach ID is the '+breach.fpid:' filter of
            # 'get compromised credentials', the record ID ties the sightings of one credential
            ("flashpointBreachId", breach.get("fpid")),
            ("flashpointBreachTitle", breach.get("title")),
            ("flashpointBreachSource", breach.get("source")),
            ("flashpointBreachSourceType", breach.get("source_type")),
            ("flashpointBreachType", breach.get("breach_type")),
            ("flashpointBreachVictim", breach.get("victim")),
            ("flashpointCredentialRecordId", source.get("credential_record_fpid")),
            ("flashpointFirstObservedAt", (breach.get("first_observed_at") or {}).get("date-time")),
            ("flashpointLastObservedAt", (source.get("last_observed_at") or {}).get("date-time")),
        ):
            if value:
                cef[cef_key] = value

        for cef_key, value in (
            ("flashpointTimesSeen", source.get("times_seen")),
            ("flashpointIsFresh", source.get("is_fresh")),
            ("flashpointProbableEnterpriseHost", (source.get("heuristics") or {}).get("probable_enterprise_host")),
        ):
            if value is not None:
                cef[cef_key] = value

        password_complexity = source.get("password_complexity") or {}
        for key, value in password_complexity.items():
            # The algorithms the value could be a digest of. It is a guess made from the shape of
            # the string, not a statement that the password is hashed: a plaintext password that
            # happens to look like a digest carries a populated list, so it is advisory only. A
            # list is flattened because a CEF value is a scalar
            if key == "probable_hash_algorithms":
                if value:
                    cef["flashpointPasswordHashAlgorithms"] = ", ".join(str(algorithm) for algorithm in value)
                continue
            cef[f"flashpointPasswordComplexity{key.title().replace('_', '')}"] = value

        artifact = {
            "name": "Compromised Credential Artifact",
            "source_data_identifier": record_id,
            "severity": container["severity"],
            "cef": cef,
            "cef_types": {
                "email": ["email"],
                "domain": ["domain"],
                "destinationDnsDomain": ["domain"],
                "requestURL": ["url"],
            },
            "data": record,
        }

        return self._save_container_with_artifacts(action_result, container, [artifact])

    def _save_container_with_artifacts(self, action_result, container, artifacts):
        """Save a container and attach its artifacts, treating an existing container as a success.

        :param action_result: object of ActionResult class
        :param container: container dictionary
        :param artifacts: list of artifact dictionaries
        :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """
        ret_val, message, container_id = self.save_container(container)
        if phantom.is_fail(ret_val) and not container_id:
            return action_result.set_status(phantom.APP_ERROR, f"Error saving container: {message}")

        for artifact in artifacts:
            artifact["container_id"] = container_id

        ret_val, message, _ = self.save_artifacts(artifacts)
        if phantom.is_fail(ret_val):
            return action_result.set_status(phantom.APP_ERROR, f"Error saving artifacts: {message}")

        return phantom.APP_SUCCESS

    def handle_action(self, param):
        """Get current action identifier and call member function of its own to handle the action.

        :param param: dictionary which contains information about the actions to be executed
        :return: status success/failure
        """
        # Get the action that we are supposed to execute for this App Run
        action = self.get_action_identifier()
        action_execution_status = phantom.APP_SUCCESS

        self.debug_print("action_id", self.get_action_identifier())

        # Dictionary mapping each action with its corresponding actions
        action_mapping = {
            "test_connectivity": self._handle_test_connectivity,
            "list_reports": self._handle_list_reports,
            "get_report": self._handle_get_report,
            "list_related_reports": self._handle_list_related_reports,
            "get_compromised_credentials": self._handle_get_compromised_credentials,
            "run_query": self._handle_run_query,
            "list_indicators": self._handle_list_indicators,
            "search_indicators": self._handle_search_indicators,
            "get_indicator": self._handle_get_indicator,
            "list_sightings": self._handle_list_sightings,
            "get_sighting": self._handle_get_sighting,
            "list_alerts": self._handle_list_alerts,
            "on_poll": self._handle_on_poll,
        }

        if action in list(action_mapping.keys()):
            action_function = action_mapping[action]
            action_execution_status = action_function(param)

        return action_execution_status

    def initialize(self):
        """Initialize the global variables with its value and validate it."""
        # Load the state in initialize, use it to store data
        # that needs to be accessed across actions
        self._state = self.load_state()

        # Get the asset config
        config = self.get_config()

        # A trailing slash would build a double slash in every endpoint
        self._base_url = config["base_url"].strip().rstrip("/")
        self._api_token = config["api_token"]
        self._x_fp_integration_platform_version = self.get_product_version()
        self._x_fp_integration_version = self.get_app_json().get("app_version")

        # Validate the 'wait_timeout_period' config parameter
        self._wait_timeout_period = self._validate_integers(
            self, config.get("wait_timeout_period", FLASHPOINT_DEFAULT_WAIT_TIMEOUT_PERIOD), FLASHPOINT_CONFIG_WAIT_TIMEOUT_PERIOD_KEY
        )
        if self._wait_timeout_period is None:
            return self.get_status()

        # Validate the 'no_of_retries' config parameter
        self._no_of_retries = self._validate_integers(
            self, config.get("no_of_retries", FLASHPOINT_NUMBER_OF_RETRIES), FLASHPOINT_CONFIG_NO_OF_RETRIES_KEY, True
        )
        if self._no_of_retries is None:
            return self.get_status()

        # Validate the 'session_timeout' config parameter
        self._session_timeout = self._validate_integers(
            self, config.get("session_timeout", FLASHPOINT_SESSION_TIMEOUT), FLASHPOINT_CONFIG_SESSION_TIMEOUT_KEY
        )
        if self._session_timeout is None:
            return self.get_status()

        if self._session_timeout > 60:
            return self.set_status(phantom.APP_ERROR, FLASHPOINT_ERROR_SESSION_TIMEOUT_VALUE)

        # Validate the 'request_timeout' config parameter. Every REST call is bounded by it, so a
        # hung endpoint fails the action instead of blocking it until the platform intervenes
        self._request_timeout = self._validate_integers(
            self, config.get("request_timeout", FLASHPOINT_DEFAULT_REQUEST_TIMEOUT), FLASHPOINT_CONFIG_REQUEST_TIMEOUT_KEY
        )
        if self._request_timeout is None:
            return self.get_status()

        return phantom.APP_SUCCESS

    def finalize(self):
        """Perform some final operations or clean up operations.

        :return: status (success/failure)
        """
        # Save the state, this data is saved across actions and app upgrades
        self.save_state(self._state)

        return phantom.APP_SUCCESS


if __name__ == "__main__":
    import argparse

    import pudb

    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument("input_test_json", help="Input Test JSON file")
    argparser.add_argument("-u", "--username", help="username", required=False)
    argparser.add_argument("-p", "--password", help="password", required=False)
    argparser.add_argument("-v", "--verify", action="store_true", help="verify", required=False, default=False)

    args = argparser.parse_args()
    session_id = None
    verify = args.verify

    username = args.username
    password = args.password

    if username is not None and password is None:
        # User specified a username but not a password, so ask
        import getpass

        password = getpass.getpass("Password: ")

    if username and password:
        try:
            login_url = FlashpointConnector._get_phantom_base_url() + "/login"

            print("Accessing the Login page")
            r = requests.get(login_url, verify=verify, timeout=FLASHPOINT_DEFAULT_REQUEST_TIMEOUT)
            csrftoken = r.cookies["csrftoken"]

            data = dict()
            data["username"] = username
            data["password"] = password
            data["csrfmiddlewaretoken"] = csrftoken

            headers = dict()
            headers["Cookie"] = "csrftoken=" + csrftoken
            headers["Referer"] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=verify, data=data, headers=headers, timeout=FLASHPOINT_DEFAULT_REQUEST_TIMEOUT)
            session_id = r2.cookies["sessionid"]
        except Exception as e:
            print("Unable to get session id from the platform. Error: " + str(e))
            sys.exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = FlashpointConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json["user_session_token"] = session_id
            connector._set_csrf_info(csrftoken, headers["Referer"])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    sys.exit(0)
