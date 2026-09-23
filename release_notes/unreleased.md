**Unreleased**

* Added `meets_pw_complexity` (password complexity) parameter in `get compromised credentials` action
* Updated Technical Intelligence API to v2 for `list indicators` and `search indicators` actions
* [Breaking] Updated parameters and output datapaths of `list indicators` and `search indicators` actions as per v2 API. Existing playbooks using these actions must be updated with the new parameters and datapaths
* Added new actions: `get indicator`, `list sightings`, `get sighting`, `list alerts` and `on poll` (ingestion of alerts and compromised credentials)
* Changed the default `limit` of `list reports` and `list related reports` from 500 to 50.
