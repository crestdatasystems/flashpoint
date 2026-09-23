# Flashpoint

Publisher: Flashpoint <br>
Connector Version: 4.0.0 <br>
Product Vendor: Flashpoint <br>
Product Name: Flashpoint <br>
Minimum Product Version: 6.2.1

This app implements the investigative actions for the Flashpoint on the Phantom Platform

## Explanation of Asset Configuration Parameters

The asset configuration parameters affect [test connectivity] and all the other actions of the
application. Below are the explanation and usage of all those parameters.

- **Base URL -** The URL to connect to the Flashpoint server.
- **API Token -** The API token of the user.
- **Request Timeout(in seconds) -** Bounds every API call, so a hung endpoint fails the action
  instead of blocking it until the platform intervenes. It allows only non-zero positive integer
  values as input. The default value is 120 seconds, which leaves headroom for the slower calls
  of this API, such as 'list reports' with a large limit. The retry mechanism applies per call,
  so each API call of a paginated action gets the configured number of retries.
- **Retry Wait Period (in seconds) -** The waiting period held before the same API call is
  attempted again after a transient response. The statuses treated as transient are
  `429 Too Many Requests`, `500`, `502`, `503` and `504`; every other status is a result the
  analyst has to act on and is reported without a retry. It allows only non-zero positive integer
  values as input. The default value is 5 seconds.
  - A `429` carries the wait the API asks for in its `Retry-After` header, as a number of seconds
    or as an HTTP date. That value is used in place of this setting when it is present and
    usable, capped at 60 seconds so an action cannot be held open for minutes; the poll or action
    fails instead and the next run picks the work up. A malformed, zero or already-elapsed header
    falls back to this setting.
- **Number Of Retries -** The number of further attempts made while the API keeps answering with
  one of the transient statuses above. If the condition clears before the retries are exhausted
  the action continues along its workflow with the next set of API calls; if all retries are
  exhausted the action fails with the latest error message being displayed. It allows only zero or
  positive integer values as input. The default value is 1 retry.
- **Session Timeout -** This is an optional asset configuration parameter. The value of this
  parameter will be used as the session timeout value in the ‘Get Compromised Credentials’ and
  ‘Run Query’ actions while using the session scrolling pagination. The default value is 2 minutes
  and the maximum allowed value is 60 minutes.

### On Poll (ingestion) asset configuration parameters

These parameters only affect the [on poll] action. Splunk SOAR permits one ingestion action per
app, so ingesting both alerts and compromised credentials requires **two asset configurations**.

- **Ingestion Type -** Selects the data source of the [on poll] action: `Compromised Credentials`
  (default) or `Alerts`. Settings that do not apply to the selected type are ignored.
- **First Run Window(in days) -** The backfill window used when the asset has no saved checkpoint
  yet. It allows only non-zero positive integer values as input. The default value is 3 days.
- **Maximum Events Per Poll -** The maximum number of containers created by one scheduled poll. A
  manual `POLL NOW` uses the container count supplied by the platform instead. It allows only
  non-zero positive integer values as input. The default value is 100. This is a rate limit, not a
  filter: a poll that cannot finish its window keeps the window and resumes from the position it
  reached, so a backlog drains over consecutive polls and no record is skipped. The action message
  and `action_result.summary` report a window that is not finished. Raise this setting to drain a
  large first-run backfill in fewer polls.
- **Container label -** Set a label under Ingest Settings. Splunk SOAR only accepts a container
  label that already exists on the platform, so ingestion fails with a message asking for one
  rather than falling back to a label of its own.
- **Event Severity -** The severity applied to every ingested container: `low`, `medium` (default)
  or `high`. The alert payload carries no severity field, so the severity comes from this setting.
- **Alerts: standing source filter -** Applied to every alerts poll, with the same accepted values
  as the 'Sources' parameter of [list alerts], as a comma-separated list.
- **Alerts: standing status filter -** Applied to every alerts poll, with the same accepted values
  as the 'Status' parameter of [list alerts]. The endpoint accepts a single status only: a
  comma-separated value is answered with HTTP 422, so the poll rejects it naming the asset
  configuration rather than sending it. `All` (default) polls without the filter.
- **Alerts: standing origin filter -** Applied to every alerts poll, with the same accepted values
  as the 'Origin' parameter of [list alerts] (`searches`, `assets`, `analyst-team`,
  `vuln-alerting`). Single-valued for the same reason as the status filter. `All` (default) polls
  without the filter. Splunk SOAR keeps the last value a dropdown was given and offers no way back
  to an empty one, so `All` is how either filter is removed after it has been configured.
  Changing either filter while a window is still being drained applies it to the remainder of that
  window: the saved cursor was produced under the previous filter, so the records it already
  stepped past are not revisited.
- **Compromised Credentials: Filter -** A standing query filter applied to every poll, written in
  the same syntax as the 'Filter' parameter of the [get compromised credentials] action and
  documented with the same sample values. The connector appends it to the query it builds, so it
  combines with the `+basetypes:credential-sighting` term and the ingestion window; it cannot
  remove either of them. It is optional and unset by default, which ingests every credential
  sighting the tenant's collection returns for the window.
  - Each clause carries its own `+` (required) or `-` (excluded) prefix. A clause with no prefix
    is optional to the search endpoint, which widens the poll instead of narrowing it.
  - Domain matching uses the exact `.keyword` sub-field. `+domain:acme.com` matches the analyzed
    field and returns other domains; `+domain.keyword:acme.com` does not.
  - The exact match covers one domain only, and wildcards are rejected by the endpoint, so every
    sending sub-domain is listed in a group: `+domain.keyword:(acme.com OR mail.acme.com)`.
  - `domain` is the email domain of the compromised account, i.e. your own users;
    `affected_domain` is the site the credential was used on.
  - **Examples:**
    - `+domain.keyword:(acme.com OR mail.acme.com)` - credentials of your own users
    - `+domain.keyword:acme.com -domain.keyword:test.acme.com` - the same, minus a sub-domain
    - `+affected_domain.keyword:shop.acme.com` - accounts breached on your own property
    - `+breach.fpid:nIbeDs_VXyKedBmuhFEaGQ` - one named breach
    - `+password_complexity.has_symbol:true +password_complexity.length:[12 TO *]` - password
      complexity, which the search endpoint exposes as query clauses rather than parameters
  - Changing this setting while a window is still being drained restarts the walk of that window
    from the position it had reached, which was measured against the previous filter. Clear the
    asset's ingestion state, or wait for the action message to stop reporting an unfinished
    window, before changing it.
- **Compromised Credentials: fresh credentials only -** Restricts the poll to records marked
  `is_fresh`, meaning the username/password pair was not seen in an earlier breach. It defaults to
  **true**, and should stay on for unattended ingestion. A credential sighting is one appearance of
  a credential in one collected dump, so the unfiltered stream is dominated by re-sightings of
  pairs already known. Clearing this setting is for a one-off historical backfill, not for a
  schedule.
- **Compromised Credentials: meets pw complexity -** The same server-side Ignite CCM-E filter as
  the [get compromised credentials] action parameter. It defaults to false.
- **Compromised Credentials: store plaintext password -** Whether the breached password is written
  into the ingested container and artifact. It defaults to **false**, which is the safe default:
  the connector then removes `password` from the record before saving, so it appears neither in
  the `password` CEF field nor in `container.data` / `artifact.data`. Everything else about the
  sighting is ingested unchanged, including the `flashpointPasswordComplexity*` fields and
  `flashpointPasswordHashAlgorithms`, which describe the password without disclosing it.
  - Turn it on only if a playbook needs the credential itself, for example to compare it against
    the directory and force a reset on a match. A CEF field is indexed and searchable across the
    platform, so with the setting on every plaintext password is queryable by anyone who can read
    the container. Pair it with a container label restricted to the roles allowed to see it.
  - The setting applies at ingestion time. Containers created while it was on keep the password
    until they are deleted; turning it off stops new ones from carrying it.

## Steps to generate API Token

1. Go to [Flashpoint](https://app.flashpoint.io/) and sign in to your Ignite account.
1. Click on your **profile icon** in the top right corner and select **Manage API Tokens** from the
   dropdown. (Alternatively, go directly to <https://app.flashpoint.io/tokens>.)
1. On the **Manage API Tokens** page, click the **Generate New Token** button.
1. Enter a **name** for the API token in the **Generate API Token** prompt.
1. Click the **Generate Token** button.
1. Click **Copy Token to Clipboard** and paste the token into your integration, code, or API call.
1. Click **Save & Close** to save the generated token and close the token generation page.

**Note-** The token name must be 1 to 64 characters long and can only contain letters, numbers,
underscores, hyphens, and periods. Save your generated API token somewhere secure, as you will no
longer be able to retrieve this key after leaving this page.

## Explanation of Flashpoint Actions' Parameters

1. ### Test Connectivity (Action Workflow Details)
   - This action will test the connectivity of the Splunk SOAR server to the Flashpoint instance by
     making an initial API call to the Technical Intelligence v2 indicators endpoint using the
     provided asset configuration parameters.
   - The action validates the provided asset configuration parameters. Based on the API call
     response, the appropriate success and failure message will be displayed when the action gets
     executed.
1. ### List Indicators
   - This action fetches IoCs from the Technical Intelligence v2 indicators endpoint
     (`GET /technical-intelligence/v2/indicators`). All of its parameters are optional and every
     provided filter narrows the result set.

   - **<u>Action Parameter</u> - IoC Value**

     - Plain-text value matched against the IoC values. A value wrapped in double quotes is
       matched exactly, an unquoted value is matched partially.
     - **Examples:**
       - Partial match on every IoC value containing the domain
         - IoC Value = example.com
       - Exact match on a single IP address
         - IoC Value = "198.51.100.24"

   - **<u>Action Parameter</u> - IoC Types**

     - Comma-separated list of IoC types to match. The allowed values are `domain`,
       `extracted_config`, `file`, `ipv4`, `ipv6` and `url`. Any other value fails the action
       before an API call is made.
     - **Examples:**
       - Fetch file and domain IoCs
         - IoC Types = file,domain

   - **<u>Action Parameter</u> - Size and From**

     - The API pages results by offset. 'Size' is the maximum number of IoCs fetched in one
       request (default 10) and 'From' is the zero-based index of the first IoC (default 0). A
       request returns at most 1000 IoCs, or at most 500 when the 'Embed' parameter is provided;
       a larger 'Size' is reduced by the connector and the reduction is reported in the action
       message. Fetch further IoCs by re-running the action with 'From' advanced by 'Size'.

   - **<u>Action Parameter</u> - CIDR Range**

     - CIDR range matched against the `ipv4` and `ipv6` IoC values.
     - **Examples:**
       - CIDR Range = 198.51.100.0/24

   - **<u>Action Parameter</u> - Tags, Sources, Actors, Malware and MITRE ATT&CK IDs**

     - Comma-separated lists of exact tag matches. 'Tags' accepts any `{prefix}:{suffix}` tag,
       for example `malware:asprox`, `actor:ta505`, `os:windows`, `asn:12345`, `origin:china` or
       `report:004W2YABmBdJgq5I9VMh`. 'Sources', 'Actors' and 'Malware' filter on the
       corresponding tag families and their tag prefix is optional. 'MITRE ATT&CK IDs' accepts
       technique IDs such as `T1041`.
     - The source names are `flashpoint_extraction`, `flashpoint_detection`,
       `flashpoint_apt`, `flashpoint_infected_hosts`, `flashpoint_analyst`, `flashpoint_collab`
       and `external_intelligence`.
     - **Examples:**
       - Fetch every IoC tagged with either malware family
         - Malware = asprox,metastealer

   - **<u>Action Parameter</u> - Min Score and Max Score**

     - Score tier bounds of the fetched IoCs. The tiers are `informational`, `suspicious` and
       `malicious`.

   - **<u>Action Parameter</u> - Has Intel Report and Has Extracted Config**

     - Fetch only the IoCs that have an associated intelligence report, respectively an
       associated extracted configuration. Both default to false and are sent to the API only
       when enabled.

   - **<u>Action Parameter</u> - Embed**

     - Comma-separated list of additional fields to embed in the response. The allowed values
       are `all`, `apt_description`, `external_references`, `malware_description`,
       `mitre_attack_ids` and `related_iocs`. Providing this parameter caps the response at 500
       IoCs.

   - **<u>Action Parameter</u> - Date Filters**

     - 'Last Seen After', 'Last Seen Before', 'Created After', 'Created Before', 'Modified
       After' and 'Modified Before' accept an absolute datetime (`2024-02-09T02:01:02Z`), a date
       (`2024-02-09`) or a relative value (`-30d`, `-8h`, `+1w`). The case matters in relative
       values: `M` is months and `m` is minutes.

   - **<u>Action Parameter</u> - Sort**

     - Date field and direction used to sort the fetched IoCs. The default is
       `last_seen_at:desc`.

   - **<u>Action Parameter</u> - Include Total Count**

     - Fetches the exact number of IoCs matching the query into
       `action_result.summary.total_count`. This increases the API response time on large result
       sets, so it defaults to false.

   - **<u>Notes</u> -**

     - Different parameters are combined by the API using AND logic, while the values within one
       comma-separated parameter are combined using OR logic.
     - **Unless one of the date filters is provided, the API only searches the IoCs with a
       `last_seen_at` date within the last 30 days.** Provide 'Last Seen After' to search
       further back.
1. ### Search Indicators
   - This action fetches the IoCs matching a single IoC value from the Technical Intelligence v2
     indicators endpoint (`GET /technical-intelligence/v2/indicators`). It is the same endpoint
     as [list indicators] with a deliberately narrower filter set.

   - **<u>Action Parameter</u> - IoC Value**

     - This is the only required parameter. A value wrapped in double quotes is matched exactly,
       an unquoted value is matched partially.
     - **Examples:**
       - Search for a file by its hash
         - IoC Value = "aedf215a803599bb3858947f23aaa6cf5b01a4d6cf2d16704a6ff0ff1a9611ad" <!-- pragma: allowlist secret -->
       - Search for every IoC value containing a URL
         - IoC Value = http://ww1.example.com/?subid1=bf5b0786-272c-11e9-b8c7-e15edf920d61

   - **<u>Action Parameter</u> - IoC Types**

     - Comma-separated list of IoC types to match. It is optional, so omitting it searches every
       IoC type. The allowed values are `domain`, `extracted_config`, `file`, `ipv4`, `ipv6` and
       `url`.

   - **<u>Action Parameter</u> - Other Filters**

     - 'Size', 'From', 'CIDR Range', 'Sources', 'Min Score', 'Max Score', 'Last Seen After',
       'Last Seen Before', 'Embed' and 'Sort' behave exactly as documented for
       [list indicators], including the 1000 and 500 record caps and the default 30-day
       `last_seen_at` window.

   - **<u>Notes</u> -** Hashes of every type are fetched through the `file` IoC type. The
     `hashes.md5`, `hashes.sha1` and `hashes.sha256` output datapaths carry the individual
     hashes, while `value` carries the SHA-256 hash for file IoCs.
1. ### Get Indicator
   - This action fetches the full detail of one IoC from the Technical Intelligence v2 indicator
     endpoint (`GET /technical-intelligence/v2/indicators/{id}`). It returns the richest indicator
     payload of the app: the score block, the embedded sightings and the hash fields.

   - **<u>Action Parameter</u> - Indicator ID**

     - This is a required parameter. It is the Flashpoint indicator ID (FPID), which the
       [list indicators] and [search indicators] actions return in the `id` output datapath. It
       carries the `flashpoint indicator id` contains, so those results pivot straight into this
       action. The value is validated and percent-encoded before it is used as a URL path
       component, so an ID containing a path separator fails the action before any API call is
       made.
     - **Examples:**
       - Indicator ID = jMXpz9FQXMyPM420kglTAg

   - **<u>Action Parameter</u> - Sighting Count**

     - Maximum number of most recent sightings returned with the IoC. It is an optional parameter,
       the default value is 100 and the allowed range is 1 to 1000.

   - **<u>Notes</u> -** This endpoint exposes no `embed` parameter; 'Sighting Count' is its only
     query parameter. An unknown ID fails the action with an "Indicator not found" message.
1. ### List Sightings
   - This action fetches sightings, which are the logical groupings of IoCs observed together at a
     point in time. It calls `GET /technical-intelligence/v2/sightings` and mirrors that endpoint
     exactly: the sightings list endpoint has no indicator filter, so neither does this action.
     The sightings of one IoC are returned by [get indicator], whose 'Sighting Count' parameter
     embeds them in the indicator record.

   - **<u>Action Parameter</u> - Size and From**

     - 'Size' is the maximum number of sightings fetched in one request (default 10). The maximum
       is 1000, or 500 when 'Embed' is provided; a larger value is reduced by the connector and
       the reduction is reported in the action message. 'From' is the zero-based index of the
       first sighting (default 0).

   - **<u>Action Parameter</u> - Tags, Sources, Sort and the date filters**

     - 'Tags' and 'Sources' are comma-separated exact matches. 'Sort' accepts `sighted_at`,
       `modified_at` or `created_at` with `:asc`/`:desc` and defaults to `sighted_at:desc`, as the
       endpoint documents. 'Sighted After/Before', 'Created After/Before' and 'Modified
       After/Before' accept the same absolute and relative date forms as [list indicators].

   - **<u>Action Parameter</u> - Embed**

     - Comma-separated list of additional fields to embed. **The sightings embed set is smaller
       than the indicators one:** the allowed values are `all`, `apt_description`,
       `malware_description` and `mitre_attack_ids` — there is no `external_references` and no
       `related_iocs`. Providing this parameter caps the response at 500 sightings.
1. ### Get Sighting
   - This action fetches one sighting by ID from the Technical Intelligence v2 sighting endpoint
     (`GET /technical-intelligence/v2/sightings/{id}`).

   - **<u>Action Parameter</u> - Sighting ID**

     - This is the only parameter and it is required. It is the Flashpoint sighting ID, which
       [list sightings] returns in the `id` output datapath with the `flashpoint sighting id`
       contains, and it is validated and percent-encoded like the [get indicator] ID.

   - **<u>Notes</u> -** This endpoint exposes no query parameters at all. Its response is identical
     to a [list sightings] record **with every optional field included**, so
     `mitre_attack_ids.*`, `malware_description` and `apt_description` are always returned here,
     whereas [list sightings] only returns them when 'Embed' is used — and using 'Embed' costs the
     500-record cap.
1. ### List Alerts
   - This action fetches alerts from the Flashpoint alert management API
     (`GET /alert-management/v1/notifications`), the same endpoint the alerts ingestion mode uses.

   - **<u>Action Parameter</u> - Size and Cursor**

     - This endpoint pages by **cursor, not by offset**. 'Size' is the number of alerts per
       request (default 25, maximum 5000; a larger value is reduced and the reduction is reported
       in the action message). One action run fetches one page and reports the cursor of the next page
       in `action_result.summary.next_cursor`; pass that value back in 'Cursor' to continue the
       walk. Unattended, complete collection is what the [on poll] alerts mode is for.

   - **<u>Action Parameter</u> - Status, Origin and Sources**

     - 'Status' and 'Origin' accept a single value each and 'Sources' accepts a comma-separated
       list. The values are lowercase: 'Status' accepts `archived`, `flagged`, `sent`, `deleted`
       and `none`; 'Origin' accepts `searches`, `assets`, `analyst-team` and `vuln-alerting`;
       'Sources' accepts `communities`, `credentials`, `iocs`, `marketplaces`, `media`, `reports`,
       `vulnerabilities`, `data_exposure__github`, `data_exposure__gitlab` and
       `data_exposure__bitbucket`. The code-repository sources and `media` correspond to the
       Ignite UI labels Github, Gitlab, Bitbucket and Images. The casing of the provided value
       does not matter, but an unrecognised value fails the action before any API call is made.

   - **<u>Action Parameter</u> - Tags, Asset Type, Asset IP, Asset IDs and Query IDs**

     - Optional filters narrowing the alerts to given tags, asset attributes, asset IDs or the
       saved searches ('Query IDs') that raised them.

   - **<u>Action Parameter</u> - Created After and Created Before**

     - Time window of the alert list. Both accept an absolute ISO-8601 UTC datetime
       (`2026-09-01T00:00:00Z`) or a `now`-anchored relative value (`now`, `now-7d`). The alert
       endpoint rejects a bare offset such as `-7d`, unlike the Technical Intelligence v2 date
       filters, so the connector fails that form before the call.

   - **<u>Notes</u> -** An alert carries no title of its own. What an analyst recognises it by is
     `reason.name` (the saved search or alert rule that fired), while the matched content sits under
     `resource.*` (`resource.title`, `resource.native_url`, `resource.site.title`,
     `resource.site_actor.names.handle`) and the matched excerpt in `highlight_text`. The alert
     timestamps are `generated_at` (when Flashpoint raised it) and `created_at` (when it was
     recorded).
1. ### On Poll
   - This action ingests the data source selected by the 'Ingestion Type' asset configuration
     parameter into SOAR containers with one artifact per record, and one further artifact per
     vulnerability of a vulnerability-alert digest.
   - **Alerts mode** calls `GET /alert-management/v1/notifications` with the standing source,
     status and origin filters plus a `created_after`/`created_before` window, and pages by cursor.
     The container name combines the matched content's own title (`resource.title`) and the rule
     name (`reason.name`) with a short fragment of the alert id, because neither the content title
     nor the rule name is unique on its own - every reply in the same thread shares
     `resource.title`, and every alert from the same rule shares `reason.name`. The
     `source_data_identifier` is the full alert `id`, the container `start_time` is
     `generated_at`, and the severity comes from the 'Event
     Severity' setting, because the alert payload carries no severity field. The alert artifact
     carries:
     - `flashpointAlertReason`, `flashpointAlertReasonId`, `flashpointAlertReasonOrigin` and
       `flashpointAlertReasonQuery` - which saved search fired and what it looks for, so a
       playbook routes or suppresses by rule
     - `flashpointHighlightText`, the matched text itself, and `requestURL`
       (`resource.native_url`, falling back to `resource.link` and `resource.ignite_search_url`)
     - `flashpointSiteTitle` for the platform and `flashpointChannelTitle` /
       `flashpointChannelId` for the channel, board or thread the content sits in. The platform
       alone ('Telegram') does not tell an analyst where to look
     - `sourceUserName` for the actor's handle and `flashpointSiteActorId` for the platform id a
       rename does not change
     - `flashpointContentPostedAt`, when the content was posted, as against `generated_at`, when
       the rule matched it
     - `flashpointAlertStatus` and `flashpointAlertIsRead`, the Ignite workflow state
   - **Vulnerability alerts** are digests: one alert carries up to 25 vulnerabilities, each of
     which is patched, deferred or accepted on its own. Each one therefore gets its own artifact
     named 'Vulnerability Artifact', identified by `<alert id>:<vuln id>` so a re-poll creates no
     duplicates, carrying `flashpointVulnId`, `flashpointVulnTitle`, `flashpointVulnCvssV3`,
     `flashpointVulnEpss`, `flashpointVulnLocation`, `flashpointVulnPublishedAt` and
     `flashpointVulnUrl` (with the `url` contains). The long `description` and `solution` texts
     stay in the artifact data rather than in CEF.
   - **Compromised Credentials mode** calls `GET /sources/v1/noncommunities/search` with the
     internally built `+basetypes:credential-sighting` query, the watermark window and the
     standing filter. The container `start_time` is the moment the credential was observed
     (`breach.first_observed_at`, falling back to `breach.created_at`), not the moment the poll
     ran. The artifact carries:
     - `email`, `domain`, `destinationDnsDomain` (`affected_domain`) and `requestURL`
       (`affected_url`) with the matching contains, so a playbook pivots on them directly
     - `sourceUserName` (`username`), the account a credential-response playbook matches against
       the directory and expires. It is mapped separately from `email` because the account name is
       not always the email address
     - `flashpointBreachId` (`breach.fpid`), which is the `+breach.fpid:<id>` filter of
       [get compromised credentials], so one artifact leads to every other victim of the same
       breach, plus `flashpointBreachTitle`, `flashpointBreachSource`, `flashpointBreachSourceType`
       and `flashpointBreachType`
     - `flashpointCredentialRecordId` (`credential_record_fpid`), shared by every sighting of one
       credential, and `flashpointFirstObservedAt` / `flashpointLastObservedAt`
     - `flashpointIsFresh`, `flashpointTimesSeen`, `flashpointProbableEnterpriseHost` and the
       `flashpointPasswordComplexity*` fields
     - `flashpointPasswordHashAlgorithms`, the algorithms the password value could be a digest of.
       It is a guess made from the shape of the string and not a statement that the value is
       hashed: a plaintext password that looks like a digest also carries it
     - `password` **only when the asset's 'store plaintext password' setting is on**, which it is
       not by default. With the setting off the password is removed from the record before saving,
       so neither the CEF field nor the container/artifact data carries it. With it on, the value
       is searchable across the platform: restrict the container label used by a credentials asset
       to the roles that are allowed to see it.
   - **First run:** with no saved checkpoint the action backfills 'First Run Window(in days)'
     ending at the moment the poll starts.
   - **Resume:** later scheduled polls start from the saved checkpoint. The checkpoint is written
     only after the containers of the batch are saved, so an interrupted poll repeats its window
     rather than skipping it. State is namespaced per ingestion mode, so switching the type on one
     asset cannot corrupt the other mode's position.
   - **Deduplication:** every container and artifact carries a stable `source_data_identifier`
     (the alert `id`, respectively the credential search hit's `_id`), so re-polling the same
     window creates zero new containers.
   - **POLL NOW** honours the container count supplied by the platform and does **not** write the
     checkpoint or consume the saved alert cursor.
   - **<u>Notes</u> -** The credential search endpoint rejects a request whose `from` + `size`
     exceeds 10,000. The ingestion walk therefore stops at that ceiling and resumes from the saved
     watermark on the next poll instead of silently skipping records.
1. ### List Reports
   - **<u>Action Parameter</u> ​ - Limit**

     - This is an optional parameter. It is used to limit the number of fetched intelligence
       reports. The default value is 50. Reports are fetched 50 per API call, so a larger limit is
       collected over several calls.

     **<u>Note</u> -** Every report carries its full HTML body, often with embedded images, so a
     single report can be several MB. Splunk SOAR cannot store an action result larger than about
     256 MB, which a limit in the hundreds can exceed; the action then fails with a
     `total size of jsonb array elements exceeds the maximum` error. Keep the limit at or near
     the default, and use [get report] for the full detail of a single report.
1. ### Get Report
   - **<u>Action Parameter</u> ​ - Report ID**
     - This is a required parameter. It is a Flashpoint intelligence report ID.
     - **Examples:**
       - Fetch an intelligence report having the provided report ID value
         - Report ID = wrh9BCZETzu3AO3CUopOlw
1. ### List Related Reports
   - **<u>Action Parameter</u> ​ - Report ID**

     - This is a required parameter. It is a Flashpoint intelligence report ID.
     - **Examples:**
       - Fetch the default 50 related intelligence reports for the provided report ID
         - Report ID = wrh9BCZETzu3AO3CUopOlw
         - Limit = Keep it empty

   - **<u>Action Parameter</u> ​ - Limit**

     - This is an optional parameter. It is used to limit the number of fetched intelligence
       reports. The default value is 50. Reports are fetched 50 per API call, so a larger limit is
       collected over several calls.

     **<u>Note</u> -** The same result-size limit as [list reports] applies: keep the limit at or
     near the default.
1. ### Get Compromised Credentials
   - **<u>Action Parameter</u> ​ - Filter**

     - This parameter will be used for filtering the data of credentials sightings on the
       Flashpoint instance. It is an optional parameter. If not given, it will get all the
       compromised credentials. A few sample values of the filter action parameter are listed
       below.
       - +is_fresh:true (search for only new credential sightings)
       - +breach.first_observed_at.date-time:[now-30d TO now] (search for credential
         sightings which are discovered in the last month based on the date provided from the
         source of this credential sightings data)
       - +breach.fpid:nIbeDs_VXyKedBmuhFEaGQ (search for all credential sightings in a
         Breach)
       - +email:username (search for a username)
       - +email.keyword:username@domain.com (search for an email address)
       - +domain.keyword:domain.com (search for credentials sightings data of a particular
         domain)
     - **Examples:**
       - Search for credential sightings of the given domain and that are discovered in the
         last month based on the date provided from the source of this credential sightings
         data
         - Filter = +domain.keyword:domain.com+breach.first_observed_at.date-time:\[now-30d
           TO now\]
       - Search for credential sightings of the given domain and that are discovered in the
         last month based on the date of indexing of the data into the Flashpoint server
         - Filter = +domain.keyword:domain.com+header\_.indexed_at:[now-30d TO now]
       - Search for credential sightings which are discovered in the last month based on the
         date of indexing of the data into the Flashpoint server
         - Filter = +header\_.indexed_at:[now-30d TO now]
       - Search for credential sightings which are discovered in between the provided
         timestamps based on the date provided from the source of this credential sightings
         data
         - Filter = +breach.first_observed_at.timestamp:[1234567890 TO 1234567890]
     - **Usage:**
       - For making filter parameter value

         - Query= +basetypes:credential-sighting \<filter>

         Here, the filter is any supported values by the search API endpoint. The connector joins
         it to the fixed `+basetypes:credential-sighting` term with a space, so each clause of the
         filter should carry its own `+` (required) or `-` (excluded) prefix; a clause with no
         prefix is optional to the query engine and widens the result set instead of narrowing it.

   - **<u>Action Parameter</u> ​ - Limit**

     - This parameter is used to limit the number of fetched compromised credentials. The
       default value is 500. If the limit is not provided, it will fetch by default 500
       compromised credentials. The internal pagination logic for fetching a large number of
       compromised credentials implements the scrolling session-based Credentials All Search
       APIs.

   - **<u>Action Parameter</u> - Meets Pw Complexity**

     - Filters the credential results for passwords that meet the password complexity rules
       defined in the Ignite CCM-E settings. It is an optional parameter and defaults to false.
       The rules are evaluated by the Flashpoint API, the connector performs no local password
       evaluation. When it is left disabled, the parameter is not sent to the API.
     - **Examples:**
       - Fetch only the compromised credentials whose passwords satisfy the tenant's complexity
         policy
         - Meets Pw Complexity = true
       - The individual complexity attributes of every fetched credential remain available in
         the `_source.password_complexity.*` output datapaths
1. ### Run Query
   - **<u>Action Parameter</u> ​ - Query**

     - This parameter will be used to search across all fields in the marketplace data by
       appending terms to it or limit searches to individual fields by appending \<field
       name>:\<value> to the ‘Query’ parameter. The queries supported by action are listed
       below.
       - Credential breach queries (+basetypes:breach)
       - CVE queries (+basetypes:cve)
       - Card queries (+basetypes:card)
       - Paste queries (+basetypes:paste)
       - Chat queries (+basetypes:generic-product)
       - Indicator attribute queries (+basetypes:indicator_attribute)
       - Credential sightings queries (+basetypes:credential-sighting)
       - Vulnerability queries (+basetypes:vulnerability)
       - Conversation queries (+basetypes:conversation)
       - Chan queries (+basetypes:chan)
       - Blog queries (+basetypes:blog)
       - Reddit queries (+basetypes:reddit)
       - Forum queries (+basetypes:forum)
     - **Examples:**
       - Search for "Analyst Research" breaches
         - Query= +basetypes:breach+source_type:"Analyst Research"
       - Search for "testing" across all free-form fields (message body, channel profile,
         channel name, and user name) for chat queries
         - Query = +basetypes:chat+testing
       - Search for credential sightings of the given domain and that are discovered in the
         last month based on the date provided from the source of this credential sightings
         data
         - Query =
           +basetypes:credential-sighting+domain.keyword:domain.com+breach.first_observed_at.date-time:\[now-30d
           TO now\]
       - Search for all search results which are discovered in the last month based on the
         date of indexing of the data into the Flashpoint server
         - Query = +header\_.indexed_at:[now-30d TO now]
       - Filter all search results by ISO date/time range based on the date provided from the
         source of this search data
         - Query = +created_at.date-time:\["2018-10-24T10:05:10+00:00" TO
           "2018-10-26T10:05:10+00:00"\]
       - Filter results by Unix time for all paste results based on the date provided from
         the source of this paste search data
         - Query = +basetypes:paste+created_at.timestamp:[1234567890 TO 1234567890]
     - **Usage:**
       - For making query parameter value

         - Query= \<basetypes_query>\<search_filter>

         Here, basetypes_query and search_filter are any supported values by the search API
         endpoint.

   - **<u>Action Parameter</u> ​ - Limit**

     - This parameter is used to limit the number of fetched all search data. The default value
       is 500. If the limit is not provided, it will fetch by default 500 search items. The
       internal pagination logic for fetching a large number of search items implements the
       scrolling session-based All Search APIs.

### Configuration variables

This table lists the configuration variables required to operate Flashpoint. These variables are specified when configuring a Flashpoint asset in Splunk SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**base_url** | required | string | Base URL |
**api_token** | required | password | API Token |
**wait_timeout_period** | optional | numeric | Retry Wait Period(in seconds) |
**no_of_retries** | optional | numeric | Number Of Retries |
**session_timeout** | optional | numeric | Session Timeout(in minutes) |
**ingestion_type** | optional | string | Ingestion Type (On Poll data source) |
**first_run_window** | optional | numeric | First Run Window(in days) - backfill window used on the first poll |
**max_events_per_poll** | optional | numeric | Maximum Events Per Poll - containers created per scheduled poll |
**event_severity** | optional | string | Event Severity - severity applied to ingested containers |
**alert_sources** | optional | string | Alerts: standing source filter, comma-separated (e.g. communities,media) |
**alert_status** | optional | string | Alerts: standing status filter. The endpoint accepts one status only. Select "All" for no filter |
**alert_origin** | optional | string | Alerts: standing origin filter. The endpoint accepts one origin only. Select "All" for no filter |
**credential_filter** | optional | string | Compromised Credentials: standing query filter (e.g. +domain.keyword:acme.com) |
**fresh_credentials_only** | optional | boolean | Compromised Credentials: ingest only credentials not seen in an earlier breach |
**meets_pw_complexity** | optional | boolean | Compromised Credentials: ingest only passwords that meet the Ignite CCM-E complexity rules |
**store_plaintext_password** | optional | boolean | Compromised Credentials: store the breached password in the container and artifact (searchable in SOAR) |
**request_timeout** | optional | numeric | Request Timeout(in seconds) - bounds every API call (default: 120) |

### Supported Actions

[test connectivity](#action-test-connectivity) - Validate the asset configuration for connectivity using supplied configuration <br>
[list reports](#action-list-reports) - Fetch a list of all the intelligence reports from the Flashpoint Platform <br>
[get report](#action-get-report) - Fetch a specific intelligence report from the Flashpoint Platform for the provided report ID <br>
[list related reports](#action-list-related-reports) - Fetch a list of all the related intelligence reports from the Flashpoint Platform for the provided report ID <br>
[get compromised credentials](#action-get-compromised-credentials) - Fetch a list of all the Credential Sightings from the Flashpoint Platform <br>
[run query](#action-run-query) - Fetch the data by performing a universal search from the Flashpoint Platform <br>
[list indicators](#action-list-indicators) - Fetch a page of the most recent IoCs from the Flashpoint Technical Intelligence v2 API <br>
[search indicators](#action-search-indicators) - Fetch the IoCs matching the provided IoC value from the Flashpoint Technical Intelligence v2 API, narrowed by the available filters <br>
[get indicator](#action-get-indicator) - Fetch the full detail of a single IoC from the Flashpoint Technical Intelligence v2 API <br>
[list sightings](#action-list-sightings) - Fetch a list of sightings from the Flashpoint Technical Intelligence v2 API, optionally scoped to one IoC <br>
[get sighting](#action-get-sighting) - Fetch the full detail of a single sighting from the Flashpoint Technical Intelligence v2 API <br>
[list alerts](#action-list-alerts) - Fetch a list of alerts from the Flashpoint alert management API <br>
[on poll](#action-on-poll) - Ingest Flashpoint alerts or compromised credentials into SOAR containers and artifacts

## action: 'test connectivity'

Validate the asset configuration for connectivity using supplied configuration

Type: **test** <br>
Read only: **True**

#### Action Parameters

No parameters are required for this action

#### Action Output

No Output

## action: 'list reports'

Fetch a list of all the intelligence reports from the Flashpoint Platform

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**limit** | optional | Maximum number of reports to be fetched (default: 50) | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.limit | numeric | | 501 |
action_result.data.\*.actors.\* | string | | BLACKNET-00 Ransomware |
action_result.data.\*.asset_ids.\* | string | | tDBu6JJ2TSeM_Qv6CijfKw |
action_result.data.\*.assets.\* | string | | /assets/tDBu6JJ2TSeM_Qv6CijfKw |
action_result.data.\*.body | string | | <html><head></head><body>This is a sample body</body></html> |
action_result.data.\*.google_document_id | string | | 1Fpc5TTfqnxGjtxISOP_zgfqjdSTn9O7detqG2oRcXjo |
action_result.data.\*.id | string | `fp report id` | KtHHUswTTSG1IjhreK3ipg |
action_result.data.\*.ingested_at | string | | 2020-02-18T22:56:38.092+00:00 |
action_result.data.\*.is_featured | boolean | | True False |
action_result.data.\*.notified_at | string | | 2020-02-18T22:56:38.092+00:00 |
action_result.data.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/fBPmyqAB7dvfmFc-DQM- |
action_result.data.\*.posted_at | string | | 2020-02-18T22:56:38.092+00:00 |
action_result.data.\*.published_status | string | | published |
action_result.data.\*.sources.\*.original | string | `url` | https://app.flashpoint.io/search/context/communities/OuWVBsllW-CEg8rTqmW7AQ |
action_result.data.\*.sources.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/ZBPuoqAB7dvfmFc-GwMs |
action_result.data.\*.sources.\*.source | string | | |
action_result.data.\*.sources.\*.source_id | string | | |
action_result.data.\*.sources.\*.title | string | `url` | https://app.flashpoint.io/search/context/communities/OuWVBsllW-CEg8rTqmW7AQ |
action_result.data.\*.sources.\*.type | string | | External |
action_result.data.\*.summary | string | | This is a summary message |
action_result.data.\*.tags.\* | string | | Supply chain and third parties |
action_result.data.\*.title | string | | Test Title |
action_result.data.\*.title_asset | string | | /assets/YvrgXc0zQGK8rKLYLvZKEw |
action_result.data.\*.title_asset_id | string | | YvrgXc0zQGK8rKLYLvZKEw |
action_result.data.\*.updated_at | string | | 2020-02-18T22:56:38.092+00:00 |
action_result.data.\*.version_posted_at | string | | 2020-02-18T22:56:38.092+00:00 |
action_result.status | string | | success failed |
action_result.message | string | | Total reports: 501 |
action_result.summary.total_reports | numeric | | 501 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get report'

Fetch a specific intelligence report from the Flashpoint Platform for the provided report ID

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**report_id** | required | Flashpoint intelligence report ID | string | `fp report id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.report_id | string | `fp report id` | 6a_iIe1CQK2-Rjb_wRcKuw |
action_result.data.\*.actors.\* | string | | BLACKNET-00 Ransomware |
action_result.data.\*.body | string | | <html><head></head><body>This is a sample body</body></html> |
action_result.data.\*.google_document_id | string | | 1Fpc5TTfqnxGjtxISOP_zgfqjdSTn9O7detqG2oRcXjo |
action_result.data.\*.id | string | `fp report id` | 6a_iIe1CQK2-Rjb_wRcKuw |
action_result.data.\*.ingested_at | string | | 2020-02-13T21:10:50.521+00:00 |
action_result.data.\*.is_featured | boolean | | True False |
action_result.data.\*.notified_at | string | | 2020-02-13T21:13:24.735+00:00 |
action_result.data.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/fBPmyqAB7dvfmFc-DQM- |
action_result.data.\*.posted_at | string | | 2020-02-13T21:10:50.521+00:00 |
action_result.data.\*.published_status | string | | published |
action_result.data.\*.sources.\*.original | string | `url` | https://app.flashpoint.io/vuln/vulnerabilities/476920 |
action_result.data.\*.sources.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/ZBPuoqAB7dvfmFc-GwMs |
action_result.data.\*.sources.\*.source | string | | |
action_result.data.\*.sources.\*.source_id | string | | |
action_result.data.\*.sources.\*.title | string | `url` | https://app.flashpoint.io/vuln/vulnerabilities/476920 |
action_result.data.\*.sources.\*.type | string | | External |
action_result.data.\*.summary | string | | This is a summary message |
action_result.data.\*.tags.\* | string | | Supply chain and third parties |
action_result.data.\*.title | string | | Test Title |
action_result.data.\*.title_asset | string | | /assets/koILoloySXqHVHcdka76hg |
action_result.data.\*.title_asset_id | string | | koILoloySXqHVHcdka76hg |
action_result.data.\*.updated_at | string | | 2020-02-13T21:13:24.735+00:00 |
action_result.data.\*.version_posted_at | string | | 2020-02-13T21:13:24.735+00:00 |
action_result.data.\*.asset_ids.\* | string | | tDBu6JJ2TSeM_Qv6CijfKw |
action_result.data.\*.assets.\* | string | | /assets/tDBu6JJ2TSeM_Qv6CijfKw |
action_result.status | string | | success failed |
action_result.message | string | | Successfully fetched report |
action_result.summary | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list related reports'

Fetch a list of all the related intelligence reports from the Flashpoint Platform for the provided report ID

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**report_id** | required | Flashpoint intelligence report ID | string | `fp report id` |
**limit** | optional | Maximum number of reports to be fetched (default: 50) | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.limit | numeric | | 50 |
action_result.parameter.report_id | string | `fp report id` | 6a_iIe1CQK2-Rjb_wRcKuw |
action_result.data.\*.actors.\* | string | | Blinkers |
action_result.data.\*.body | string | | <html><head></head><body>This is test body</body></html> |
action_result.data.\*.google_document_id | string | | 1cLbphNDorTE2dDcZjO6kE6KshFSMtFqYU8A7xeph_nY::YQuy2tS9Sp-s0DPwX8euyQ |
action_result.data.\*.id | string | `fp report id` | 2EtSXz6HRX23Bb4ZvrFoHA |
action_result.data.\*.ingested_at | string | | 2020-02-12T22:35:11.579+00:00 |
action_result.data.\*.is_featured | boolean | | True False |
action_result.data.\*.notified_at | string | | 2020-02-12T22:42:57.323+00:00 |
action_result.data.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/fBPmyqAB7dvfmFc-DQM- |
action_result.data.\*.posted_at | string | | 2020-02-12T22:35:11.579+00:00 |
action_result.data.\*.published_status | string | | published |
action_result.data.\*.sources.\*.original | string | `url` | https://app.flashpoint.io/vuln/vulnerabilities/476920 |
action_result.data.\*.sources.\*.platform_url | string | `url` | https://app.flashpoint.io/cti/intelligence/report/ZBPuoqAB7dvfmFc-GwMs |
action_result.data.\*.sources.\*.source | string | | |
action_result.data.\*.sources.\*.source_id | string | | |
action_result.data.\*.sources.\*.title | string | `url` | https://app.flashpoint.io/vuln/vulnerabilities/476920 |
action_result.data.\*.sources.\*.type | string | | External |
action_result.data.\*.summary | string | | This is a summary message |
action_result.data.\*.tags.\* | string | | Blockchain and cryptocurrency |
action_result.data.\*.title | string | | Test Title |
action_result.data.\*.title_asset | string | | /assets/19xWABeWTXGJuFz6Xh4phQ |
action_result.data.\*.title_asset_id | string | | 19xWABeWTXGJuFz6Xh4phQ |
action_result.data.\*.updated_at | string | | 2020-02-12T22:42:57.323+00:00 |
action_result.data.\*.version_posted_at | string | | 2020-02-12T22:42:57.323+00:00 |
action_result.data.\*.asset_ids.\* | string | | tDBu6JJ2TSeM_Qv6CijfKw |
action_result.data.\*.assets.\* | string | | /assets/tDBu6JJ2TSeM_Qv6CijfKw |
action_result.status | string | | success failed |
action_result.message | string | | Total related reports: 50 |
action_result.summary.total_related_reports | numeric | | 50 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get compromised credentials'

Fetch a list of all the Credential Sightings from the Flashpoint Platform

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**filter** | optional | Filtering the data of credentials sightings | string | |
**limit** | optional | Maximum number of compromised credentials to be fetched (default: 500) | numeric | |
**meets_pw_complexity** | optional | Filter credential results for passwords that meet the password complexity rules defined in Ignite CCM-E settings | boolean | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.filter | string | | +is_fresh:true +breach.fpid:nIbeDs_VXyKedBmuhFEaGQ +domain.keyword:domain.com+is_fresh:true |
action_result.parameter.limit | numeric | | 500 |
action_result.parameter.meets_pw_complexity | boolean | | True False |
action_result.data.\*.\_id | string | | AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.\_source.affected_domain | string | `domain` | signup.live.com |
action_result.data.\*.\_source.affected_url | string | `url` | https://signup.live.com/signup |
action_result.data.\*.\_source.basetypes.\* | string | | credential-sighting |
action_result.data.\*.\_source.body.raw | string | | user.name@domain.com:thisapassword |
action_result.data.\*.\_source.breach.basetypes.\* | string | | breach |
action_result.data.\*.\_source.breach.breach_type | string | | credential |
action_result.data.\*.\_source.breach.context | string | | Combo Collection/Lists/list_01.txt |
action_result.data.\*.\_source.breach.created_at.date-time | string | | 2019-04-01T12:00:00Z |
action_result.data.\*.\_source.breach.created_at.timestamp | numeric | | 1554120000 |
action_result.data.\*.\_source.breach.first_observed_at.date-time | string | | 2019-09-20T03:14:00Z |
action_result.data.\*.\_source.breach.first_observed_at.timestamp | numeric | | 1568949240 |
action_result.data.\*.\_source.breach.fpid | string | | Z8VbElXPWHCguJBX6goxRg |
action_result.data.\*.\_source.breach.source | string | | Analyst Research |
action_result.data.\*.\_source.breach.source_type | string | | Analyst Research |
action_result.data.\*.\_source.breach.title | string | | Compromised Users from example.com Apr012019 |
action_result.data.\*.\_source.breach.victim | string | | www.example.com |
action_result.data.\*.\_source.cookies.\*.affected_domain | string | | example.org |
action_result.data.\*.\_source.cookies.\*.allow_subdomains | boolean | | True |
action_result.data.\*.\_source.cookies.\*.key | string | | \_ga |
action_result.data.\*.\_source.cookies.\*.path | string | | / |
action_result.data.\*.\_source.cookies.\*.value | string | | GA1.2.1234567890.1700000000 |
action_result.data.\*.\_source.credential_record_fpid | string | | qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.\_source.customer_id | string | | 0011N00001sDj4A |
action_result.data.\*.\_source.domain | string | `flashpoint ioc value` `domain` | domain.com |
action_result.data.\*.\_source.email | string | `email` | user.name@domain.com |
action_result.data.\*.\_source.extraction_id | string | | tXfm1PGDXRqTmcB57L9-eA |
action_result.data.\*.\_source.extraction_record_id | string | | dhaaFUx8X4G229qg67jrtA |
action_result.data.\*.\_source.fpid | string | | AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*._source.header_.indexed_at | numeric | | 1581371433 |
action_result.data.\*._source.header_.pipeline_duration | numeric | | 63886288675 |
action_result.data.\*.\_source.heuristics.heuristics_version | string | | 2.18.0 |
action_result.data.\*.\_source.heuristics.probable_enterprise_host | boolean | | False |
action_result.data.\*.\_source.infected_host_attributes.fpid | string | | VbMzgQ-uVImWVbPNtoQamA |
action_result.data.\*.\_source.infected_host_attributes.host_id | string | | 0123456789ABCDEF0123456789ABCDEF |
action_result.data.\*.\_source.infected_host_attributes.installed_software.\*.name | string | | Windows Defender |
action_result.data.\*.\_source.infected_host_attributes.installed_software.\*.version | string | | 3.60.45.0 |
action_result.data.\*.\_source.infected_host_attributes.ip | string | | 203.0.113.10 |
action_result.data.\*.\_source.infected_host_attributes.ipv4 | string | | 203.0.113.10 |
action_result.data.\*.\_source.infected_host_attributes.isp.autonomous_system_number | numeric | | 3329 |
action_result.data.\*.\_source.infected_host_attributes.isp.autonomous_system_organization | string | | Vodafone-panafon Hellenic Telecommunications Company SA |
action_result.data.\*.\_source.infected_host_attributes.isp.connection_type | string | | Cellular |
action_result.data.\*.\_source.infected_host_attributes.isp.isp | string | | Vodafone Greece |
action_result.data.\*.\_source.infected_host_attributes.isp.organization | string | | Vodafone Greece |
action_result.data.\*.\_source.infected_host_attributes.location.accuracy_radius | numeric | | 100 |
action_result.data.\*.\_source.infected_host_attributes.location.city_name | string | | Springfield |
action_result.data.\*.\_source.infected_host_attributes.location.continent_name | string | | North America |
action_result.data.\*.\_source.infected_host_attributes.location.country_name | string | | United States |
action_result.data.\*.\_source.infected_host_attributes.location.latitude | numeric | | 37.751 |
action_result.data.\*.\_source.infected_host_attributes.location.location.lat | numeric | | 37.751 |
action_result.data.\*.\_source.infected_host_attributes.location.location.lon | numeric | | -97.822 |
action_result.data.\*.\_source.infected_host_attributes.location.longitude | numeric | | -97.822 |
action_result.data.\*.\_source.infected_host_attributes.location.subdivision_1_name | string | | Example Region |
action_result.data.\*.\_source.infected_host_attributes.location.subdivision_2_name | string | | Springfield |
action_result.data.\*.\_source.infected_host_attributes.machine.architecture | string | | x64 |
action_result.data.\*.\_source.infected_host_attributes.machine.cpu.\* | string | | Intel(R) Core(TM) i7 CPU 930 @ 2.80GHz, 4 Cores |
action_result.data.\*.\_source.infected_host_attributes.machine.extra.\*.key | string | | filelocation |
action_result.data.\*.\_source.infected_host_attributes.machine.extra.\*.value | string | | C:\\Windows\\Microsoft.NET\\Framework\\v4.0.30319\\MsBuild.exe |
action_result.data.\*.\_source.infected_host_attributes.machine.gpu.\* | string | | NVIDIA GeForce GTX 260 |
action_result.data.\*.\_source.infected_host_attributes.machine.language.\* | string | | English |
action_result.data.\*.\_source.infected_host_attributes.machine.os | string | | Windows 10 Pro x64 |
action_result.data.\*.\_source.infected_host_attributes.machine.ram | string | | 8190.49 Mb |
action_result.data.\*.\_source.infected_host_attributes.machine.resolution | string | | {Width=1536, Height=864} |
action_result.data.\*.\_source.infected_host_attributes.machine.user | string | | user01 |
action_result.data.\*.\_source.infected_host_attributes.malware.family | string | | redline_stealer |
action_result.data.\*.\_source.infected_host_attributes.malware.scanned_at.date-time | string | | 2024-03-26T03:24:15Z |
action_result.data.\*.\_source.infected_host_attributes.malware.version | string | `url` | https://t.me/+uuz8-qLUNeU2ZmI0 |
action_result.data.\*.\_source.is_fresh | boolean | | True False |
action_result.data.\*.\_source.last_observed_at.date-time | string | | 2019-09-20T03:14:00Z |
action_result.data.\*.\_source.last_observed_at.timestamp | numeric | | 1568949240 |
action_result.data.\*.\_source.password | string | | thisapassword |
action_result.data.\*.\_source.password_complexity.has_lowercase | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_number | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_symbol | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_uppercase | boolean | | True False |
action_result.data.\*.\_source.password_complexity.length | numeric | | 129 |
action_result.data.\*.\_source.password_complexity.probable_hash_algorithms.\* | string | | CRC-24 |
action_result.data.\*.\_source.times_seen | numeric | | 1 |
action_result.data.\*.\_source.username | string | | user.name@example.com |
action_result.data.\*.matched_queries.\* | string | | dat.edm.org.r |
action_result.status | string | | success failed |
action_result.message | string | | Total results: 4 |
action_result.summary.total_results | numeric | | 4 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'run query'

Fetch the data by performing a universal search from the Flashpoint Platform

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**query** | required | Search across all fields in the marketplace or free text search | string | `fp query basetypes` |
**limit** | optional | Maximum number of search results to be fetched (default: 500) | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.limit | numeric | | 478 |
action_result.parameter.query | string | `fp query basetypes` | +basetypes:card +basetypes:breach +basetypes:cve +basetypes:paste +basetypes:generic-product +basetypes:indicator_attribute +basetypes:credential-sighting +basetypes:vulnerability +basetypes:conversation +basetypes:chan +basetypes:blog +basetypes:reddit +basetypes:forum +basetypes:indicator_attribute+type:"ip-dst|port"+value.\\\*:5.79.68.110|80 |
action_result.data.\*.\_id | string | | 8dKFsRoeV0mP8zOY1uYcLQ |
action_result.data.\*.\_source.affected_domain | string | | signup-live-com.translate.goog |
action_result.data.\*.\_source.affected_url | string | `url` | https://signup-live-com.translate.goog/ |
action_result.data.\*.\_source.basetypes.\* | string | | breach |
action_result.data.\*.\_source.body.raw | string | `url` | This is a test body |
action_result.data.\*.\_source.breach.basetypes.\* | string | | breach |
action_result.data.\*.\_source.breach.breach_type | string | | credential |
action_result.data.\*.\_source.breach.context | string | | Combo Collection/Lists/list_01.txt |
action_result.data.\*.\_source.breach.created_at.date-time | string | | 2019-04-01T12:00:00Z |
action_result.data.\*.\_source.breach.created_at.timestamp | numeric | | 1554120000 |
action_result.data.\*.\_source.breach.first_observed_at.date-time | string | | 2019-09-20T03:14:00Z |
action_result.data.\*.\_source.breach.first_observed_at.timestamp | numeric | | 1568949240 |
action_result.data.\*.\_source.breach.fpid | string | | ZxVbExxxfghuxBX6goxxg |
action_result.data.\*.\_source.breach.source | string | | Analyst Research |
action_result.data.\*.\_source.breach.source_type | string | | Analyst Research |
action_result.data.\*.\_source.breach.title | string | | Compromised Users from example.com Apr012019 |
action_result.data.\*.\_source.breach_intersections.\*.count | numeric | | 7167 |
action_result.data.\*.\_source.breach_intersections.\*.dump | string | | en6DWDl_VKyuLUvCsHk_EQ |
action_result.data.\*.\_source.breach_intersections.\*.title | string | | Compromised Users from example.com Sept2015 |
action_result.data.\*.\_source.cookies.\*.affected_domain | string | | example.org |
action_result.data.\*.\_source.cookies.\*.allow_subdomains | boolean | | True |
action_result.data.\*.\_source.cookies.\*.key | string | | \_ga |
action_result.data.\*.\_source.cookies.\*.path | string | | / |
action_result.data.\*.\_source.cookies.\*.value | string | | GA1.2.1234567890.1700000000 |
action_result.data.\*.\_source.created_at.date-time | string | | 2019-07-14T19:56:37+00:00 |
action_result.data.\*.\_source.created_at.timestamp | numeric | | 1563134197 |
action_result.data.\*.\_source.credential_record_fpid | string | | qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.\_source.customer_id | string | | 0011N00001sDj4A |
action_result.data.\*.\_source.domain | string | `flashpoint ioc value` `domain` | domain.com |
action_result.data.\*.\_source.email | string | `email` | user.name@domain.com |
action_result.data.\*.\_source.extraction_id | string | | tXfm1PGDXRqTmcB57L9-eA |
action_result.data.\*.\_source.extraction_record_id | string | | dhaaFUx8X4G229qg67jrtA |
action_result.data.\*.\_source.first_observed_at.date-time | string | | 2019-05-24T18:11:15Z |
action_result.data.\*.\_source.first_observed_at.timestamp | numeric | | 1558721475 |
action_result.data.\*.\_source.fpid | string | | 8dKFsRoeV0mP8zOY1uYcLQ |
action_result.data.\*._source.header_.indexed_at | numeric | | 1571442668 |
action_result.data.\*._source.header_.pipeline_duration | numeric | | 63795317250 |
action_result.data.\*.\_source.heuristics.heuristics_version | string | | 2.18.0 |
action_result.data.\*.\_source.heuristics.probable_enterprise_host | boolean | | False |
action_result.data.\*.\_source.infected_host_attributes.fpid | string | | VbMzgQ-uVImWVbPNtoQamA |
action_result.data.\*.\_source.infected_host_attributes.host_id | string | | 0123456789ABCDEF0123456789ABCDEF |
action_result.data.\*.\_source.infected_host_attributes.installed_software.\*.name | string | | Windows Defender |
action_result.data.\*.\_source.infected_host_attributes.installed_software.\*.version | string | | 3.60.45.0 |
action_result.data.\*.\_source.infected_host_attributes.ip | string | | 203.0.113.10 |
action_result.data.\*.\_source.infected_host_attributes.ipv4 | string | | 203.0.113.10 |
action_result.data.\*.\_source.infected_host_attributes.isp.autonomous_system_number | numeric | | 3329 |
action_result.data.\*.\_source.infected_host_attributes.isp.autonomous_system_organization | string | | Vodafone-panafon Hellenic Telecommunications Company SA |
action_result.data.\*.\_source.infected_host_attributes.isp.connection_type | string | | Cellular |
action_result.data.\*.\_source.infected_host_attributes.isp.isp | string | | Vodafone Greece |
action_result.data.\*.\_source.infected_host_attributes.isp.organization | string | | Vodafone Greece |
action_result.data.\*.\_source.infected_host_attributes.location.accuracy_radius | numeric | | 100 |
action_result.data.\*.\_source.infected_host_attributes.location.city_name | string | | Springfield |
action_result.data.\*.\_source.infected_host_attributes.location.continent_name | string | | North America |
action_result.data.\*.\_source.infected_host_attributes.location.country_name | string | | United States |
action_result.data.\*.\_source.infected_host_attributes.location.latitude | numeric | | 37.751 |
action_result.data.\*.\_source.infected_host_attributes.location.location.lat | numeric | | 37.751 |
action_result.data.\*.\_source.infected_host_attributes.location.location.lon | numeric | | -97.822 |
action_result.data.\*.\_source.infected_host_attributes.location.longitude | numeric | | -97.822 |
action_result.data.\*.\_source.infected_host_attributes.location.subdivision_1_name | string | | Example Region |
action_result.data.\*.\_source.infected_host_attributes.location.subdivision_2_name | string | | Springfield |
action_result.data.\*.\_source.infected_host_attributes.machine.architecture | string | | x64 |
action_result.data.\*.\_source.infected_host_attributes.machine.cpu.\* | string | | Intel(R) Core(TM) i7 CPU 930 @ 2.80GHz, 4 Cores |
action_result.data.\*.\_source.infected_host_attributes.machine.extra.\*.key | string | | filelocation |
action_result.data.\*.\_source.infected_host_attributes.machine.extra.\*.value | string | | C:\\Windows\\Microsoft.NET\\Framework\\v4.0.30319\\MsBuild.exe |
action_result.data.\*.\_source.infected_host_attributes.machine.gpu.\* | string | | NVIDIA GeForce GTX 260 |
action_result.data.\*.\_source.infected_host_attributes.machine.language.\* | string | | English |
action_result.data.\*.\_source.infected_host_attributes.machine.os | string | | Windows 10 Pro x64 |
action_result.data.\*.\_source.infected_host_attributes.machine.ram | string | | 8190.49 Mb |
action_result.data.\*.\_source.infected_host_attributes.machine.resolution | string | | {Width=1536, Height=864} |
action_result.data.\*.\_source.infected_host_attributes.machine.user | string | | user01 |
action_result.data.\*.\_source.infected_host_attributes.malware.family | string | | redline_stealer |
action_result.data.\*.\_source.infected_host_attributes.malware.scanned_at.date-time | string | | 2024-03-26T03:24:15Z |
action_result.data.\*.\_source.infected_host_attributes.malware.version | string | `url` | https://t.me/+uuz8-qLUNeU2ZmI0 |
action_result.data.\*.\_source.is_fresh | boolean | | True False |
action_result.data.\*.\_source.last_observed_at.date-time | string | | 2019-10-18T23:51:05+00:00 |
action_result.data.\*.\_source.last_observed_at.timestamp | numeric | | 1571442665 |
action_result.data.\*.\_source.new_records | numeric | | 0 |
action_result.data.\*.\_source.old_records | numeric | | 0 |
action_result.data.\*.\_source.password | string | | thisapassword |
action_result.data.\*.\_source.password_complexity.has_lowercase | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_number | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_symbol | boolean | | True False |
action_result.data.\*.\_source.password_complexity.has_uppercase | boolean | | True False |
action_result.data.\*.\_source.password_complexity.length | numeric | | 129 |
action_result.data.\*.\_source.password_complexity.probable_hash_algorithms.\* | string | | CRC-24 |
action_result.data.\*.\_source.source | string | `url` | Analyst Research |
action_result.data.\*.\_source.source_type | string | | Analyst Research |
action_result.data.\*.\_source.times_seen | numeric | | 1 |
action_result.data.\*.\_source.title | string | | CVE-2019-10802 |
action_result.data.\*.\_source.top_domains.\*.count | numeric | | 182662 |
action_result.data.\*.\_source.top_domains.\*.value | string | | testdomainlink.com |
action_result.data.\*.\_source.top_passwords.\*.count | numeric | | 1038 |
action_result.data.\*.\_source.top_passwords.\*.value | string | `sha1` `email` `md5` | e10adc3949ba59abbe56e057f20f883e |
action_result.data.\*.\_source.total_records | numeric | | 671072 |
action_result.data.\*.\_source.unique_records | numeric | | 671066 |
action_result.data.\*.\_source.username | string | | user.name@example.com |
action_result.data.\*.matched_queries.\* | string | | dat.edm.org.r |
action_result.data.\*.sort.\* | numeric | | 9223372036854775807 |
action_result.status | string | | success failed |
action_result.message | string | | Total results: 478 |
action_result.summary.total_results | numeric | | 478 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list indicators'

Fetch a page of the most recent IoCs from the Flashpoint Technical Intelligence v2 API

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**ioc_types** | optional | Comma-separated list of IoC types to match (allowed values: domain, extracted_config, file, ipv4, ipv6, url) | string | `fp attribute type` |
**size** | optional | Maximum number of IoCs to be fetched in one request (default: 10, maximum: 1000, maximum: 500 when 'embed' is provided) | numeric | |
**from** | optional | Zero-based index of the first IoC to be fetched (default: 0) | numeric | |
**sort** | optional | Date field and direction used to sort the fetched IoCs (default: last_seen_at:desc) | string | |
**last_seen_after** | optional | Include IoCs last seen on or after this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.from | numeric | | 0 500 |
action_result.parameter.ioc_types | string | `fp attribute type` | ipv4 domain,url |
action_result.parameter.last_seen_after | string | | -30d 2024-02-09T02:01:02Z |
action_result.parameter.size | numeric | | 10 1000 |
action_result.parameter.sort | string | | last_seen_at:desc |
action_result.data.\*.created_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.entity_type | string | | indicator |
action_result.data.\*.hashes.md5 | string | `md5` | 16139ce9025274a388a4281fef65049e |
action_result.data.\*.hashes.sha1 | string | `sha1` | da39a3ee5e6b4b0d3255bfef95601890afd80709 |
action_result.data.\*.hashes.sha256 | string | `sha256` | aedf215a803599bb3858947f23aaa6cf5b01a4d6cf2d16704a6ff0ff1a9611ad |
action_result.data.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.id | string | `flashpoint indicator id` | AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.last_seen_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.latest_sighting.description | string | | Observation: vidar "b94b6f6f588b8d04747f3e0e0598e88ba95d080f7786aa50b864007b65da76a0" [2026-09-09T11:10:20.637Z] |
action_result.data.\*.latest_sighting.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.latest_sighting.id | string | | 68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.latest_sighting.sighted_at | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.latest_sighting.source | string | | external_intelligence |
action_result.data.\*.latest_sighting.tags.\* | string | | file_type:exe |
action_result.data.\*.modified_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.platform_urls.ignite | string | `url` | https://app.flashpoint.io/technical-intelligence/indicators/AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.score.last_scored_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.score.value | string | | informational suspicious malicious |
action_result.data.\*.sightings.\*.description | string | | Extracted configuration observed by Flashpoint |
action_result.data.\*.sightings.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.sightings.\*.id | string | `flashpoint sighting id` | qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.sightings.\*.sighted_at | string | | 2025-07-20T11:02:13Z |
action_result.data.\*.sightings.\*.source | string | | flashpoint_extraction external_osint |
action_result.data.\*.sightings.\*.tags.\* | string | | malware:metastealer source:flashpoint_extraction |
action_result.data.\*.sort_date | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.total_sightings | numeric | | 1 |
action_result.data.\*.type | string | `fp attribute type` | ipv4 file domain url |
action_result.data.\*.value | string | `flashpoint ioc value` | 198.51.100.24 |
action_result.status | string | | success failed |
action_result.message | string | | Total iocs: 10 The 'size' parameter was reduced to 500 because the API returns at most 500 records when the 'embed' parameter is provided |
action_result.summary.total_iocs | numeric | | 10 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'search indicators'

Fetch the IoCs matching the provided IoC value from the Flashpoint Technical Intelligence v2 API, narrowed by the available filters

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**ioc_value** | required | Plain-text value to match against the IoC values. A value wrapped in double quotes is matched exactly, an unquoted value is matched partially | string | `flashpoint ioc value` |
**ioc_types** | optional | Comma-separated list of IoC types to match (allowed values: domain, extracted_config, file, ipv4, ipv6, url) | string | `fp attribute type` |
**size** | optional | Maximum number of IoCs to be fetched in one request (default: 10, maximum: 1000, maximum: 500 when 'embed' is provided) | numeric | |
**from** | optional | Zero-based index of the first IoC to be fetched (default: 0) | numeric | |
**cidr_range** | optional | CIDR range to match against the ipv4 or ipv6 IoC values | string | |
**tags** | optional | Comma-separated list of exact IoC tags to match, for example malware:asprox, actor:ta505, os:windows or report:004W2YABmBdJgq5I9VMh | string | |
**sources** | optional | Comma-separated list of exact source tags to match, for example flashpoint_extraction, flashpoint_apt or external_intelligence (the 'source:' prefix is optional) | string | |
**actors** | optional | Comma-separated list of exact actor tags to match (the actor tag prefix is optional) | string | |
**malware** | optional | Comma-separated list of exact malware tags to match (the 'malware:' prefix is optional) | string | |
**mitre_attack_ids** | optional | Comma-separated list of MITRE ATT&CK technique IDs to match, for example T1041 | string | |
**min_score** | optional | Minimum score tier of the IoCs to be fetched | string | |
**max_score** | optional | Maximum score tier of the IoCs to be fetched | string | |
**has_intel_report** | optional | Fetch only the IoCs that have an associated intelligence report | boolean | |
**has_extracted_config** | optional | Fetch only the IoCs that have an associated extracted configuration | boolean | |
**embed** | optional | Comma-separated list of additional fields to embed in the response (allowed values: all, apt_description, external_references, malware_description, mitre_attack_ids, related_iocs). Providing this parameter caps the response at 500 IoCs | string | |
**last_seen_after** | optional | Include IoCs last seen on or after this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**last_seen_before** | optional | Include IoCs last seen before this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**created_after** | optional | Include IoCs created on or after this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**created_before** | optional | Include IoCs created before this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**modified_after** | optional | Include IoCs modified on or after this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**modified_before** | optional | Include IoCs modified before this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d, -8h, +1w) | string | |
**sort** | optional | Date field and direction used to sort the fetched IoCs (default: last_seen_at:desc) | string | |
**include_total_count** | optional | Fetch the exact count of the matching IoCs into the action summary. This increases the response time on large result sets | boolean | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.actors | string | | ta505 |
action_result.parameter.cidr_range | string | | 198.51.100.0/24 |
action_result.parameter.created_after | string | | -7d |
action_result.parameter.created_before | string | | 2024-02-11 |
action_result.parameter.embed | string | | all mitre_attack_ids,external_references |
action_result.parameter.from | numeric | | 0 500 |
action_result.parameter.has_extracted_config | boolean | | True False |
action_result.parameter.has_intel_report | boolean | | True False |
action_result.parameter.include_total_count | boolean | | True False |
action_result.parameter.ioc_types | string | `fp attribute type` | ipv4 domain,url |
action_result.parameter.ioc_value | string | `flashpoint ioc value` | example.com "198.51.100.24" |
action_result.parameter.last_seen_after | string | | -30d 2024-02-09T02:01:02Z |
action_result.parameter.last_seen_before | string | | 2024-02-11T02:01:02Z |
action_result.parameter.malware | string | | metastealer |
action_result.parameter.max_score | string | | malicious |
action_result.parameter.min_score | string | | suspicious |
action_result.parameter.mitre_attack_ids | string | | T1041 |
action_result.parameter.modified_after | string | | -1w |
action_result.parameter.modified_before | string | | 2024-02-11 |
action_result.parameter.size | numeric | | 10 1000 |
action_result.parameter.sort | string | | last_seen_at:desc |
action_result.parameter.sources | string | | source:flashpoint_extraction flashpoint_apt,external_intelligence |
action_result.parameter.tags | string | | malware:asprox report:004W2YABmBdJgq5I9VMh |
action_result.data.\*.apt_description | string | | A financially motivated threat actor tracked by Flashpoint since 2019. |
action_result.data.\*.created_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.entity_type | string | | indicator |
action_result.data.\*.external_references.\*.source_name | string | | ThreatExample Blog |
action_result.data.\*.external_references.\*.url | string | `url` | https://threatexample.com |
action_result.data.\*.hashes.md5 | string | `md5` | 16139ce9025274a388a4281fef65049e |
action_result.data.\*.hashes.sha1 | string | `sha1` | da39a3ee5e6b4b0d3255bfef95601890afd80709 |
action_result.data.\*.hashes.sha256 | string | `sha256` | aedf215a803599bb3858947f23aaa6cf5b01a4d6cf2d16704a6ff0ff1a9611ad |
action_result.data.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.id | string | `flashpoint indicator id` | AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.last_seen_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.latest_sighting.apt_description | string | | N/A |
action_result.data.\*.latest_sighting.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.description | string | | Observation: vidar "b94b6f6f588b8d04747f3e0e0598e88ba95d080f7786aa50b864007b65da76a0" [2026-09-09T11:10:20.637Z] |
action_result.data.\*.latest_sighting.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.latest_sighting.id | string | | 68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.latest_sighting.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.latest_sighting.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\* | string | | |
action_result.data.\*.latest_sighting.related_iocs.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/agRd2c-VX8iLTZekIARl_w |
action_result.data.\*.latest_sighting.related_iocs.\*.id | string | | agRd2c-VX8iLTZekIARl_w |
action_result.data.\*.latest_sighting.related_iocs.\*.type | string | | file |
action_result.data.\*.latest_sighting.related_iocs.\*.value | string | | b94b6f6f588b8d04747f3e0e0598e88ba95d080f7786aa50b864007b65da76a0 |
action_result.data.\*.latest_sighting.sighted_at | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.latest_sighting.source | string | | external_intelligence |
action_result.data.\*.latest_sighting.tags.\* | string | | file_type:exe |
action_result.data.\*.malware_description | string | | An information stealer sold as malware-as-a-service. |
action_result.data.\*.mitre_attack_ids.\*.id | string | | T1041 |
action_result.data.\*.mitre_attack_ids.\*.name | string | | Exfiltration Over C2 Channel |
action_result.data.\*.mitre_attack_ids.\*.tactics.\* | string | | Exfiltration |
action_result.data.\*.modified_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.platform_urls.ignite | string | `url` | https://app.flashpoint.io/technical-intelligence/indicators/AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.score.last_scored_at | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.score.value | string | | informational suspicious malicious |
action_result.data.\*.sightings.\*.apt_description | string | | N/A |
action_result.data.\*.sightings.\*.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.description | string | | Extracted configuration observed by Flashpoint |
action_result.data.\*.sightings.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.sightings.\*.id | string | `flashpoint sighting id` | qOpTj49MUeCXD5VXxKaJZA |
action_result.data.\*.sightings.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.sightings.\*.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\* | string | | |
action_result.data.\*.sightings.\*.related_iocs.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.sightings.\*.related_iocs.\*.id | string | `flashpoint indicator id` | AvnahLkdXU6p-ahsDMr_JQ |
action_result.data.\*.sightings.\*.related_iocs.\*.type | string | `fp attribute type` | domain |
action_result.data.\*.sightings.\*.related_iocs.\*.value | string | `flashpoint ioc value` | example.com |
action_result.data.\*.sightings.\*.sighted_at | string | | 2025-07-20T11:02:13Z |
action_result.data.\*.sightings.\*.source | string | | flashpoint_extraction external_osint |
action_result.data.\*.sightings.\*.tags.\* | string | | malware:metastealer source:flashpoint_extraction |
action_result.data.\*.sort_date | string | | 2025-07-21T15:30:00Z |
action_result.data.\*.total_sightings | numeric | | 1 |
action_result.data.\*.type | string | `fp attribute type` | ipv4 file domain url |
action_result.data.\*.value | string | `flashpoint ioc value` | 198.51.100.24 |
action_result.status | string | | success failed |
action_result.message | string | | Total iocs: 10 The 'size' parameter was reduced to 500 because the API returns at most 500 records when the 'embed' parameter is provided |
action_result.summary.total_count | numeric | | 4211 |
action_result.summary.total_iocs | numeric | | 10 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get indicator'

Fetch the full detail of a single IoC from the Flashpoint Technical Intelligence v2 API

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**indicator_id** | required | ID of the IoC to fetch | string | `flashpoint indicator id` |
**sighting_count** | optional | Maximum number of most recent sightings to return with the IoC (default: 100, minimum: 1, maximum: 1000) | numeric | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.indicator_id | string | `flashpoint indicator id` | jMXpz9FQXMyPM420kglTAg |
action_result.parameter.sighting_count | numeric | | 100 |
action_result.data.\*.apt_description | string | | N/A |
action_result.data.\*.created_at | string | | 2020-10-27T13:22:05Z |
action_result.data.\*.entity_type | string | | indicator |
action_result.data.\*.external_references.\*.source_name | string | | Flashpoint |
action_result.data.\*.external_references.\*.url | string | | https://api.flashpoint.io/finished-intelligence/v1/reports/P_ZCCrviScaNDXu-P0ns4w |
action_result.data.\*.hashes.md5 | string | `md5` | 16139ce9025274a388a4281fef65049e |
action_result.data.\*.hashes.sha1 | string | `sha1` | da39a3ee5e6b4b0d3255bfef95601890afd80709 |
action_result.data.\*.hashes.sha256 | string | `sha256` | a885b1f5a26e1a4bd1a24c1c0b0b4a5c9e2f3d4b5a6978695a4b3c2d1e0f4683 |
action_result.data.\*.historical_tags.\* | string | | file_type:exe |
action_result.data.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/jMXpz9FQXMyPM420kglTAg |
action_result.data.\*.id | string | `flashpoint indicator id` | jMXpz9FQXMyPM420kglTAg |
action_result.data.\*.last_seen_at | string | | 2025-05-08T16:47:25Z |
action_result.data.\*.latest_sighting.apt_description | string | | N/A |
action_result.data.\*.latest_sighting.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.description | string | | Observation: mirai "011eb609b33a0cd3971ee0b7e8effee3960913c0688dcf78734a00b151b10529" [2026-09-15T07:00:46.319Z] |
action_result.data.\*.latest_sighting.href | string | | https://api.flashpoint.io/technical-intelligence/v2/sightings/NlBPeIaKUMqX70CFOhDBZg |
action_result.data.\*.latest_sighting.id | string | | NlBPeIaKUMqX70CFOhDBZg |
action_result.data.\*.latest_sighting.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.latest_sighting.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.latest_sighting.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.apt_description | string | | N/A |
action_result.data.\*.latest_sighting.related_iocs.\*.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.entity_type | string | | indicator |
action_result.data.\*.latest_sighting.related_iocs.\*.external_references.\*.source_name | string | | Flashpoint |
action_result.data.\*.latest_sighting.related_iocs.\*.external_references.\*.url | string | | https://api.flashpoint.io/finished-intelligence/v1/reports/P_ZCCrviScaNDXu-P0ns4w |
action_result.data.\*.latest_sighting.related_iocs.\*.hashes.md5 | string | | |
action_result.data.\*.latest_sighting.related_iocs.\*.hashes.sha1 | string | | 1d6cae992e93aa936cf1d5ba31e8a8842b66b636 |
action_result.data.\*.latest_sighting.related_iocs.\*.hashes.sha256 | string | | 011eb609b33a0cd3971ee0b7e8effee3960913c0688dcf78734a00b151b10529 |
action_result.data.\*.latest_sighting.related_iocs.\*.href | string | | https://api.flashpoint.io/technical-intelligence/v2/indicators/OxBHNY9fWYeiK3zjxx9o_w |
action_result.data.\*.latest_sighting.related_iocs.\*.id | string | | OxBHNY9fWYeiK3zjxx9o_w |
action_result.data.\*.latest_sighting.related_iocs.\*.last_seen_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.latest_sighting.related_iocs.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.latest_sighting.related_iocs.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.latest_sighting.related_iocs.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.latest_sighting.related_iocs.\*.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.platform_urls.ignite | string | | https://app.flashpoint.io/cti/malware/iocs/OxBHNY9fWYeiK3zjxx9o_w |
action_result.data.\*.latest_sighting.related_iocs.\*.score.last_scored_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.latest_sighting.related_iocs.\*.score.value | string | | malicious |
action_result.data.\*.latest_sighting.related_iocs.\*.sightings.\* | string | | |
action_result.data.\*.latest_sighting.related_iocs.\*.sort_date | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.latest_sighting.related_iocs.\*.total_sightings | numeric | | 0 |
action_result.data.\*.latest_sighting.related_iocs.\*.type | string | | file |
action_result.data.\*.latest_sighting.related_iocs.\*.value | string | | 011eb609b33a0cd3971ee0b7e8effee3960913c0688dcf78734a00b151b10529 |
action_result.data.\*.latest_sighting.sighted_at | string | | 2026-09-15T07:00:46.319000Z |
action_result.data.\*.latest_sighting.source | string | | flashpoint_extraction |
action_result.data.\*.latest_sighting.tags.\* | string | | extracted_config:true |
action_result.data.\*.malware_description | string | | Lokibot is a resident information stealer. |
action_result.data.\*.mitre_attack_ids.\*.id | string | | T1016 |
action_result.data.\*.mitre_attack_ids.\*.name | string | | System Network Configuration Discovery |
action_result.data.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.modified_at | string | | 2025-05-08T16:47:25Z |
action_result.data.\*.platform_urls.ignite | string | `url` | https://app.flashpoint.io/cti/malware/iocs/jMXpz9FQXMyPM420kglTAg |
action_result.data.\*.reports.\*.html | string | `url` | https://app.flashpoint.io/intelligence/reports/report/KtHHUswTTSG1IjhreK3ipg |
action_result.data.\*.reports.\*.json | string | `url` | https://api.flashpoint.io/finished-intelligence/v1/reports/KtHHUswTTSG1IjhreK3ipg |
action_result.data.\*.score.last_scored_at | string | | 2025-05-08T16:47:25Z |
action_result.data.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.score.value | string | | malicious |
action_result.data.\*.sightings.\*.apt_description | string | | N/A |
action_result.data.\*.sightings.\*.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.description | string | | Observation: vidar "b94b6f6f588b8d04747f3e0e0598e88ba95d080f7786aa50b864007b65da76a0" [2026-09-09T11:10:20.637Z] |
action_result.data.\*.sightings.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.sightings.\*.id | string | | 68U2DrpnUBigRcO8iAi_hQ |
action_result.data.\*.sightings.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.sightings.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.sightings.\*.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.apt_description | string | | N/A |
action_result.data.\*.sightings.\*.related_iocs.\*.created_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.entity_type | string | | indicator |
action_result.data.\*.sightings.\*.related_iocs.\*.external_references.\*.source_name | string | | Flashpoint |
action_result.data.\*.sightings.\*.related_iocs.\*.external_references.\*.url | string | | https://api.flashpoint.io/finished-intelligence/v1/reports/P_ZCCrviScaNDXu-P0ns4w |
action_result.data.\*.sightings.\*.related_iocs.\*.hashes.md5 | string | | |
action_result.data.\*.sightings.\*.related_iocs.\*.hashes.sha1 | string | | 1d6cae992e93aa936cf1d5ba31e8a8842b66b636 |
action_result.data.\*.sightings.\*.related_iocs.\*.hashes.sha256 | string | | 011eb609b33a0cd3971ee0b7e8effee3960913c0688dcf78734a00b151b10529 |
action_result.data.\*.sightings.\*.related_iocs.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/Je_c0xvXX9aBpoYH |
action_result.data.\*.sightings.\*.related_iocs.\*.id | string | `flashpoint indicator id` | Je_c0xvXX9aBpoYHkQ7VDg |
action_result.data.\*.sightings.\*.related_iocs.\*.last_seen_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.sightings.\*.related_iocs.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.sightings.\*.related_iocs.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.sightings.\*.related_iocs.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.sightings.\*.related_iocs.\*.modified_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.platform_urls.ignite | string | | https://app.flashpoint.io/cti/malware/iocs/OxBHNY9fWYeiK3zjxx9o_w |
action_result.data.\*.sightings.\*.related_iocs.\*.score.last_scored_at | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.sightings.\*.related_iocs.\*.score.value | string | | malicious |
action_result.data.\*.sightings.\*.related_iocs.\*.sightings.\* | string | | |
action_result.data.\*.sightings.\*.related_iocs.\*.sort_date | string | | 2026-09-15T06:36:32.867Z |
action_result.data.\*.sightings.\*.related_iocs.\*.total_sightings | numeric | | 0 |
action_result.data.\*.sightings.\*.related_iocs.\*.type | string | | file |
action_result.data.\*.sightings.\*.related_iocs.\*.value | string | `flashpoint ioc value` | f8d437d2b1f0d4e6a7c8b9a0d1e2f3a4 |
action_result.data.\*.sightings.\*.sighted_at | string | | 2020-10-27T13:22:05Z |
action_result.data.\*.sightings.\*.source | string | | flashpoint_extraction |
action_result.data.\*.sightings.\*.tags.\* | string | | file_type:exe |
action_result.data.\*.sort_date | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.total_sightings | numeric | | 1 |
action_result.data.\*.type | string | | file |
action_result.data.\*.value | string | `flashpoint ioc value` | a885b1f5a26e1a4bd1a24c1c0b0b4a5c9e2f3d4b5a6978695a4b3c2d1e0f4683 |
action_result.status | string | | success failed |
action_result.message | string | | Successfully fetched the indicator |
action_result.summary.total_sightings | numeric | | 2 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list sightings'

Fetch a list of sightings from the Flashpoint Technical Intelligence v2 API, optionally scoped to one IoC

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**size** | optional | Maximum number of sightings to be fetched in one request (default: 10; maximum: 1000, maximum: 500 when 'embed' is provided) | numeric | |
**from** | optional | Zero-based index of the first sighting to be fetched (default: 0) | numeric | |
**sort** | optional | Date field and direction used to sort the fetched sightings (default: sighted_at:desc) | string | |
**tags** | optional | Comma-separated list of exact sighting tags to match, for example malware:asprox | string | |
**sources** | optional | Comma-separated list of exact sighting sources to match, for example flashpoint_extraction | string | |
**embed** | optional | Comma-separated list of additional fields to embed in the response (allowed values: all, apt_description, malware_description, mitre_attack_ids). Providing this parameter caps the response at 500 sightings | string | |
**sighted_after** | optional | Include sightings sighted on or after this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d) | string | |
**sighted_before** | optional | Include sightings sighted before this date. Supports an absolute datetime (2024-01-01T00:00:00Z), a date (2024-01-01) or a relative value (-30d) | string | |
**created_after** | optional | Include sightings created on or after this date. Supports an absolute datetime, a date or a relative value | string | |
**created_before** | optional | Include sightings created before this date. Supports an absolute datetime, a date or a relative value | string | |
**modified_after** | optional | Include sightings modified on or after this date. Supports an absolute datetime, a date or a relative value | string | |
**modified_before** | optional | Include sightings modified before this date. Supports an absolute datetime, a date or a relative value | string | |
**include_total_count** | optional | Fetch the exact count of the matching sightings into the action summary. This increases the response time on large result sets | boolean | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.created_after | string | | -30d |
action_result.parameter.created_before | string | | 2026-09-08T00:00:00Z |
action_result.parameter.embed | string | | all |
action_result.parameter.from | numeric | | 0 |
action_result.parameter.include_total_count | boolean | | True False |
action_result.parameter.modified_after | string | | -30d |
action_result.parameter.modified_before | string | | 2026-09-08T00:00:00Z |
action_result.parameter.sighted_after | string | | -3d |
action_result.parameter.sighted_before | string | | now |
action_result.parameter.size | numeric | | 10 |
action_result.parameter.sort | string | | sighted_at:desc |
action_result.parameter.sources | string | | external_intelligence |
action_result.parameter.tags | string | | malware:tofsee |
action_result.data.\*.apt_description | string | | N/A |
action_result.data.\*.created_at | string | | 2026-09-08T09:14:03Z |
action_result.data.\*.description | string | | Observation: berbew "d70ea318...fc" [2026-09-08] |
action_result.data.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/bHVysNDhUua_lrBmW6e_uQ |
action_result.data.\*.id | string | `flashpoint sighting id` | bHVysNDhUua_lrBmW6e_uQ |
action_result.data.\*.malware_description | string | | Tofsee is a modular spambot. |
action_result.data.\*.mitre_attack_ids.\*.id | string | | T1041 |
action_result.data.\*.mitre_attack_ids.\*.name | string | | Exfiltration Over C2 Channel |
action_result.data.\*.mitre_attack_ids.\*.tactics.\* | string | | discovery |
action_result.data.\*.modified_at | string | | 2026-09-08T09:14:03Z |
action_result.data.\*.related_iocs.\*.apt_description | string | | N/A |
action_result.data.\*.related_iocs.\*.created_at | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.related_iocs.\*.entity_type | string | | indicator |
action_result.data.\*.related_iocs.\*.external_references.\*.source_name | string | | Flashpoint |
action_result.data.\*.related_iocs.\*.external_references.\*.url | string | | https://api.flashpoint.io/finished-intelligence/v1/reports/P_ZCCrviScaNDXu-P0ns4w |
action_result.data.\*.related_iocs.\*.hashes.md5 | string | `md5` | |
action_result.data.\*.related_iocs.\*.hashes.sha1 | string | `sha1` | 8f06edf96f194a0818a2da85e631af2fced7d383 |
action_result.data.\*.related_iocs.\*.hashes.sha256 | string | `sha256` | d70ea318a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293afc00 |
action_result.data.\*.related_iocs.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/6w6Dfq3mU6-EEChotntP |
action_result.data.\*.related_iocs.\*.id | string | `flashpoint indicator id` | 6w6Dfq3mU6-EEChotntPzg |
action_result.data.\*.related_iocs.\*.last_seen_at | string | | 2026-09-08T09:00:21Z |
action_result.data.\*.related_iocs.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.related_iocs.\*.modified_at | string | | 2026-09-09T11:18:13.171000Z |
action_result.data.\*.related_iocs.\*.platform_urls.ignite | string | `url` | https://app.flashpoint.io/cti/malware/iocs/agRd2c-VX8iLTZekIARl_w |
action_result.data.\*.related_iocs.\*.score.last_scored_at | string | | 2026-09-09T11:18:11.977888Z |
action_result.data.\*.related_iocs.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.related_iocs.\*.score.value | string | | suspicious |
action_result.data.\*.related_iocs.\*.sightings.\* | string | | |
action_result.data.\*.related_iocs.\*.sort_date | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.related_iocs.\*.total_sightings | numeric | | 0 |
action_result.data.\*.related_iocs.\*.type | string | | file |
action_result.data.\*.related_iocs.\*.value | string | `flashpoint ioc value` | d70ea318a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293afc00 |
action_result.data.\*.sighted_at | string | | 2026-09-08T09:00:21Z |
action_result.data.\*.source | string | | external_intelligence |
action_result.data.\*.tags.\* | string | | file_type:exe |
action_result.status | string | | success failed |
action_result.message | string | | Total sightings: 10 |
action_result.summary.total_count | numeric | | 4211 |
action_result.summary.total_sightings | numeric | | 10 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get sighting'

Fetch the full detail of a single sighting from the Flashpoint Technical Intelligence v2 API

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sighting_id** | required | ID of the sighting to fetch | string | `flashpoint sighting id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.sighting_id | string | `flashpoint sighting id` | bHVysNDhUua_lrBmW6e_uQ |
action_result.data.\*.apt_description | string | | N/A |
action_result.data.\*.created_at | string | | 2026-09-08T09:14:03Z |
action_result.data.\*.description | string | | Observation: berbew "d70ea318...fc" [2026-09-08] |
action_result.data.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/sightings/bHVysNDhUua_lrBmW6e_uQ |
action_result.data.\*.id | string | `flashpoint sighting id` | bHVysNDhUua_lrBmW6e_uQ |
action_result.data.\*.malware_description | string | | Tofsee is a modular spambot. |
action_result.data.\*.mitre_attack_ids.\*.id | string | | T1041 |
action_result.data.\*.mitre_attack_ids.\*.name | string | | Exfiltration Over C2 Channel |
action_result.data.\*.mitre_attack_ids.\*.tactics.\* | string | | discovery |
action_result.data.\*.modified_at | string | | 2026-09-08T09:14:03Z |
action_result.data.\*.related_iocs.\*.apt_description | string | | N/A |
action_result.data.\*.related_iocs.\*.created_at | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.related_iocs.\*.entity_type | string | | indicator |
action_result.data.\*.related_iocs.\*.external_references.\*.source_name | string | | Flashpoint |
action_result.data.\*.related_iocs.\*.external_references.\*.url | string | | https://api.flashpoint.io/finished-intelligence/v1/reports/P_ZCCrviScaNDXu-P0ns4w |
action_result.data.\*.related_iocs.\*.hashes.md5 | string | `md5` | |
action_result.data.\*.related_iocs.\*.hashes.sha1 | string | `sha1` | 1d6cae992e93aa936cf1d5ba31e8a8842b66b636 |
action_result.data.\*.related_iocs.\*.hashes.sha256 | string | `sha256` | d70ea318a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293afc00 |
action_result.data.\*.related_iocs.\*.href | string | `url` | https://api.flashpoint.io/technical-intelligence/v2/indicators/6w6Dfq3mU6-EEChotntP |
action_result.data.\*.related_iocs.\*.id | string | `flashpoint indicator id` | 6w6Dfq3mU6-EEChotntPzg |
action_result.data.\*.related_iocs.\*.last_seen_at | string | | 2026-09-08T09:00:21Z |
action_result.data.\*.related_iocs.\*.malware_description | string | | <p style="">"Mirai" is a botnet that originated in 2016. It targets Linux based operating systems with a focus on Internet of Things (IoT) devices, specifically IP cameras and home routers.</p>\<p styl |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.id | string | | T1005 |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.name | string | | Data from Local System |
action_result.data.\*.related_iocs.\*.mitre_attack_ids.\*.tactics.\* | string | | Collection |
action_result.data.\*.related_iocs.\*.modified_at | string | | 2026-09-09T11:18:13.171000Z |
action_result.data.\*.related_iocs.\*.platform_urls.ignite | string | `url` | https://app.flashpoint.io/cti/malware/iocs/agRd2c-VX8iLTZekIARl_w |
action_result.data.\*.related_iocs.\*.score.last_scored_at | string | | 2026-09-09T11:18:11.977888Z |
action_result.data.\*.related_iocs.\*.score.raw_score | numeric | | 0 |
action_result.data.\*.related_iocs.\*.score.value | string | | suspicious |
action_result.data.\*.related_iocs.\*.sightings.\* | string | | |
action_result.data.\*.related_iocs.\*.sort_date | string | | 2026-09-09T11:10:20.637000Z |
action_result.data.\*.related_iocs.\*.total_sightings | numeric | | 0 |
action_result.data.\*.related_iocs.\*.type | string | | file |
action_result.data.\*.related_iocs.\*.value | string | `flashpoint ioc value` | d70ea318a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293afc00 |
action_result.data.\*.sighted_at | string | | 2026-09-08T09:00:21Z |
action_result.data.\*.source | string | | external_intelligence |
action_result.data.\*.tags.\* | string | | file_type:exe |
action_result.status | string | | success failed |
action_result.message | string | | Successfully fetched the sighting |
action_result.summary.source | string | | external_intelligence |
action_result.summary.total_related_iocs | numeric | | 3 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list alerts'

Fetch a list of alerts from the Flashpoint alert management API

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**size** | optional | Maximum number of alerts to be fetched in one request (default: 25, maximum: 5000) | numeric | |
**cursor** | optional | Continuation cursor returned by a previous run in 'action_result.summary.next_cursor' | string | |
**status** | optional | Alert state to match. The endpoint accepts one state only | string | |
**origin** | optional | Alert origin to match. The endpoint accepts one origin only | string | |
**sources** | optional | Comma-separated list of alert sources to match (allowed values: communities, credentials, iocs, marketplaces, media, reports, vulnerabilities, data_exposure\_\_github, data_exposure\_\_gitlab, data_exposure\_\_bitbucket) | string | |
**tags** | optional | Comma-separated list of exact alert tags to match | string | |
**asset_type** | optional | Asset type that raised the alert | string | |
**asset_ip** | optional | Asset IP that raised the alert | string | `ip` |
**asset_ids** | optional | Comma-separated list of asset IDs whose alerts are fetched | string | |
**query_ids** | optional | Comma-separated list of alert rule identifiers (UUIDs) that raised the alerts, as returned by GET /alert-management/v1/queries | string | |
**created_after** | optional | Include alerts created on or after this date. Supports an absolute ISO-8601 UTC datetime (2024-01-01T00:00:00Z) or a 'now'-anchored relative value (now-7d) | string | |
**created_before** | optional | Include alerts created before this date. Supports an absolute ISO-8601 UTC datetime (2024-01-01T00:00:00Z) or a 'now'-anchored relative value (now) | string | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.parameter.asset_ids | string | | 4fca0cd3-eec1-448e-8b35-6d45192168ed |
action_result.parameter.asset_ip | string | `ip` | 198.51.100.24 |
action_result.parameter.asset_type | string | | domain |
action_result.parameter.created_after | string | | now-7d |
action_result.parameter.created_before | string | | now |
action_result.parameter.cursor | string | | 1788945290.101539 |
action_result.parameter.origin | string | | searches |
action_result.parameter.query_ids | string | | 3f2a9c14-5b7e-4f0a-9d21-8c6b0e5a7d43 |
action_result.parameter.size | numeric | | 25 |
action_result.parameter.sources | string | | communities |
action_result.parameter.status | string | | sent |
action_result.parameter.tags | string | | asset:example.com |
action_result.data.\*.created_at | string | | 2024-06-03T20:16:14Z |
action_result.data.\*.data_type | string | | chat |
action_result.data.\*.generated_at | string | | 2024-06-03T20:16:12Z |
action_result.data.\*.highlight_text | string | | Nah I need 6 figs to leak that |
action_result.data.\*.highlights.body.\* | string | | <p class="c12"><span class="c21">Sparks are brief observations from the Flashpoint team about notable developments th... |
action_result.data.\*.highlights.body.text/plain+urls.\* | string | `url` | https://patched.to/Thread-diamond-%E2%9A%A1-1500-<mark>stealer</mark>-logs-drop-%E2%80%A2-private-mixed-countries-%E2... |
action_result.data.\*.highlights.body.text/plain.\* | string | | lane": "parity-mobile", "title": "fix(mobile): surface blank compo... |
action_result.data.\*.highlights.container.name.\* | string | | <mark>ChatGPT</mark> Plus｜代充交流群 |
action_result.data.\*.highlights.media_v2.image_enrichment.enrichments.v1.image-analysis.text.value.\* | string | | Lakota Man @LakotaMan1 Follow 0 Top 10 Spreaders of <mark>Disinformation</mark> in the US accordi... |
action_result.data.\*.highlights.section.\* | string | | <mark>MALWARE</mark>: вредоносы, крипт, <mark>инжекты</mark>, 0/1day экспы |
action_result.data.\*.highlights.site_actor.names.aliases.\* | string | | WORK VERIFIKASI <mark>BYPASS</mark> |
action_result.data.\*.highlights.summary.\* | string | | Notable posts in Flashpoint collections. |
action_result.data.\*.highlights.title.\* | string | | <mark>chatGPT</mark>-ai-shortcuts-01.md |
action_result.data.\*.id | string | | 8a45bd35-1fac-4b35-aa27-630ab3821507 |
action_result.data.\*.is_read | boolean | | True False |
action_result.data.\*.parent_data_type | string | | board |
action_result.data.\*.reason.details.params.digests.daily | boolean | | False |
action_result.data.\*.reason.details.params.digests.weekly | boolean | | False |
action_result.data.\*.reason.details.params.frequency | string | | email:daily digest |
action_result.data.\*.reason.details.params.params.exploit.\* | string | | exploit_in_wild |
action_result.data.\*.reason.details.params.params.query | string | | |
action_result.data.\*.reason.details.params.params.severity.\* | string | | high |
action_result.data.\*.reason.details.params.tags_cond.\* | string | | OR |
action_result.data.\*.reason.details.sources.\* | string | | communities |
action_result.data.\*.reason.entity | string | | |
action_result.data.\*.reason.id | string | | 218f7b12-8c85-474e-8013-98d014e99c8c |
action_result.data.\*.reason.name | string | | Insider Threat Alerts |
action_result.data.\*.reason.origin | string | | two-face |
action_result.data.\*.reason.text | string | | ("i work at" OR "i am employed") |
action_result.data.\*.resource.actors.\* | string | | BLACKNET-00 Ransomware |
action_result.data.\*.resource.author | string | | |
action_result.data.\*.resource.authors | string | | |
action_result.data.\*.resource.basetypes.\* | string | | paste |
action_result.data.\*.resource.container.container.name | string | | BASI |
action_result.data.\*.resource.container.container.native_id | string | | 104 |
action_result.data.\*.resource.container.container.title | string | | A.I |
action_result.data.\*.resource.container.name | string | | skidbase |
action_result.data.\*.resource.container.native_id | string | | 194772 |
action_result.data.\*.resource.container.server | string | | |
action_result.data.\*.resource.container.title | string | | gen |
action_result.data.\*.resource.country | string | | |
action_result.data.\*.resource.created_at.date-time | string | | 2026-09-09T12:42:28+00:00 |
action_result.data.\*.resource.created_at.timestamp | numeric | | 1717445707 |
action_result.data.\*.resource.description | string | | |
action_result.data.\*.resource.id | string | | LIjNc-xrVUynzUwsoqPfVw |
action_result.data.\*.resource.ignite_search_url | string | `url` | https://app.flashpoint.io/vuln/search/vulns?updated_after=2026-09-08T11:58:07Z&updated_before=2026-09-09T12:00:07Z&se... |
action_result.data.\*.resource.link | string | | |
action_result.data.\*.resource.media_v2.\*.image_enrichment.enrichments.v1.image-analysis.safe_search.adult | numeric | | 1 |
action_result.data.\*.resource.media_v2.\*.image_enrichment.enrichments.v1.image-analysis.safe_search.medical | numeric | | 1 |
action_result.data.\*.resource.media_v2.\*.image_enrichment.enrichments.v1.image-analysis.safe_search.racy | numeric | | 1 |
action_result.data.\*.resource.media_v2.\*.image_enrichment.enrichments.v1.image-analysis.safe_search.spoof | numeric | | 5 |
action_result.data.\*.resource.media_v2.\*.image_enrichment.enrichments.v1.image-analysis.safe_search.violence | numeric | | 2 |
action_result.data.\*.resource.media_v2.\*.media_type | string | | image |
action_result.data.\*.resource.media_v2.\*.mime_type | string | | image/png |
action_result.data.\*.resource.media_v2.\*.phash | string | | dabea543a45aa15c |
action_result.data.\*.resource.media_v2.\*.phash256 | string | | dabb9e84a5b443e5a4b44a5aa1625c0acc45b52bad1dad56594aa365b4adbc9d |
action_result.data.\*.resource.media_v2.\*.sha1 | string | `sha1` | ba528c1c321cc77072c50b3037ceff7686193f58 |
action_result.data.\*.resource.media_v2.\*.storage_uri | string | | gs://kraken-datalake-media/artifacts/80/80b00609c844337505050bffeb80d36207d390d86670eb521001000617a31db0 |
action_result.data.\*.resource.media_v2.image_enrichment.enrichments.v1.image-analysis.safe_search.adult | numeric | | 1 |
action_result.data.\*.resource.media_v2.image_enrichment.enrichments.v1.image-analysis.safe_search.medical | numeric | | 2 |
action_result.data.\*.resource.media_v2.image_enrichment.enrichments.v1.image-analysis.safe_search.racy | numeric | | 2 |
action_result.data.\*.resource.media_v2.image_enrichment.enrichments.v1.image-analysis.safe_search.spoof | numeric | | 2 |
action_result.data.\*.resource.media_v2.image_enrichment.enrichments.v1.image-analysis.safe_search.violence | numeric | | 2 |
action_result.data.\*.resource.media_v2.media_type | string | | image |
action_result.data.\*.resource.media_v2.mime_type | string | | image/png |
action_result.data.\*.resource.media_v2.phash | string | | f1a5a5b12d785a52 |
action_result.data.\*.resource.media_v2.phash256 | string | | f140a540a540b1402d4b780e5ab152bf42bf5abf5abf5abf42a74abf3e3e4780 |
action_result.data.\*.resource.media_v2.sha1 | string | `sha1` | 1212a5675cbe86e60cd95ae50c93360e9988decf |
action_result.data.\*.resource.media_v2.storage_uri | string | | gs://kraken-datalake-media/artifacts/f6/f65f4a8b73c8573aea6ff2dfc8d0e25004b0752537d777257a56d9489bae9b2e |
action_result.data.\*.resource.native_url | string | `url` | https://darknetarmy.st/threads/%F0%9F%93%9Bjailbreak-bypass-chatgpt-rules-working-latest-method-11-4-jenxkaito%F0%9F%... |
action_result.data.\*.resource.parent_basetypes.\* | string | | conversation |
action_result.data.\*.resource.parent_fpid | string | | nFV247utUQuPZ-Je7qOcmQ |
action_result.data.\*.resource.section | string | | A.I |
action_result.data.\*.resource.site.title | string | | Telegram |
action_result.data.\*.resource.site_actor.names.handle | string | | RISK |
action_result.data.\*.resource.site_actor.native_id | string | | example_actor_01 |
action_result.data.\*.resource.sort_date | string | | 2026-09-09T12:42:28Z |
action_result.data.\*.resource.summary | string | | Notable posts in Flashpoint collections. |
action_result.data.\*.resource.tags.\* | string | | Supply chain and third parties |
action_result.data.\*.resource.title | string | | BIGFATCHAT |
action_result.data.\*.resource.version_posted_at | string | | 2026-09-09T02:37:05.114000Z |
action_result.data.\*.resource.vulns.\*.cvss_v3 | numeric | | 5.3 |
action_result.data.\*.resource.vulns.\*.description | string | | Dell Secure Connect Gateway contains a flaw that allows a cross-site scripting (XSS) attack. This flaw exists because... |
action_result.data.\*.resource.vulns.\*.epss | numeric | | 0.00186 |
action_result.data.\*.resource.vulns.\*.ignite_url | string | `url` | https://app.flashpoint.io/vuln/vulnerabilities/473054 |
action_result.data.\*.resource.vulns.\*.location | string | | Remote / Network Access |
action_result.data.\*.resource.vulns.\*.published_at | string | | 2026-09-09T11:47:49Z |
action_result.data.\*.resource.vulns.\*.solution | string | | It has been reported that this has been fixed. Please refer to the product listing for upgraded versions that address... |
action_result.data.\*.resource.vulns.\*.title | string | | Dell Secure Connect Gateway Unspecified XSS (2026-79946) |
action_result.data.\*.resource.vulns.\*.vuln_id | string | | 473054 |
action_result.data.\*.source | string | | communities |
action_result.data.\*.status | string | | In Progress |
action_result.data.\*.tags | string | | |
action_result.status | string | | success failed |
action_result.message | string | | Total alerts: 100 |
action_result.summary.next_cursor | string | | 1788945290.101539 |
action_result.summary.total_alerts | numeric | | 100 |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'on poll'

Ingest Flashpoint alerts or compromised credentials into SOAR containers and artifacts

Type: **ingest** <br>
Read only: **True**

The data source is selected by the 'Ingestion Type' asset configuration. Splunk SOAR permits one ingestion action per app, so ingesting both alerts and compromised credentials requires two asset configurations. A scheduled poll resumes from the saved checkpoint and writes a new one; POLL NOW honours the container count passed in by the platform and leaves the checkpoint untouched.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**container_id** | optional | Container IDs to limit the ingestion to | string | |
**start_time** | optional | Start of time range, in epoch time (milliseconds) | numeric | |
**end_time** | optional | End of time range, in epoch time (milliseconds) | numeric | |
**container_count** | optional | Maximum number of container records to query for | numeric | |
**artifact_count** | optional | Maximum number of artifact records to query for | numeric | |

#### Action Output

No Output

______________________________________________________________________

Auto-generated Splunk SOAR Connector documentation.

Copyright 2026 Splunk Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
