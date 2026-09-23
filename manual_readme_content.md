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
