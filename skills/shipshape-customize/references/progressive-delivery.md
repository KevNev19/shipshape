# Progressive delivery

`features.progressive_delivery` stays off unless the user asks for it.

Turning it on adds one page, `docs/sdlc/progressive-delivery.md`. That page
is a checklist for a feature flag (a switch that hides a change) and a
canary (a small share of real use). Shipshape does not deploy the project,
does not flip a switch, and does not return people to an older version.

Before you set the flag, say that in one sentence and get an explicit yes.
After apply, tell the user the page is guidance and the automated checks
still come first.

Do not add a deploy workflow from this flag. A workflow that deploys and
rolls back needs one named place the project runs, and this kit does not
pick that place.
