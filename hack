#!/bin/sh
# hack - one word, total compromise. lab only.
#
# Full auto chain with no stops: recon, sqli, loot, nuke. The site goes down.
# Only ever runs against the hackwatch lab; anything else is refused.
exec hackwatch auto --yes "$@"
