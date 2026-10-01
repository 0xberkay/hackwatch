#!/bin/sh
# hack - one word, total compromise. lab only.
#
# Finds the lab itself (cached target first, LAN scan if needed), then runs
# the full auto chain with no stops: recon, sqli, loot, nuke. The site goes
# down. Anything that is not the lab is refused.
exec hackwatch auto --yes "$@"
