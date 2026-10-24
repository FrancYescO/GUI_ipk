# Additional LuCI translations

This overlay imports 34 nonempty official translation dictionaries for the
existing luci-base, firewall, OLSR, OLSR services and splash applications.
`SOURCES.json` pins each upstream path and revision; `SHA256SUMS` checks the
unchanged bytes. Eight candidate dictionaries contain no translated messages
and are intentionally excluded. A ninth dictionary contains only translations
identical to the source text and produces no LMO, so it is also excluded.
Partial translations remain partial.

Norwegian, Brazilian Portuguese and Chinese directory names map to the legacy
LuCI language identifiers (`no`, `pt-br`, `zh-cn`, `zh-tw`). The accompanying
patch registers Bulgarian, Hindi and Marathi titles. Application code and the
LuCI framework are retained; extra dictionary entries do not add application
features. Existing dictionaries are not replaced.

The userspace build verifies and imports the overlay before Kconfig expansion, invalidating the archived LuCI metadata cache so the
new translation package names are actually discovered.
Target the five existing recipes to build the translation IPKs. Compilation
and language registration do not establish complete UI translation coverage.
