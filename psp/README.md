# PSP package status

PSP support is not implemented yet. This directory is a placeholder for future
platform-specific engine, ROM, and visual tooling.

The shared assets under `assets/text/` already retain proved PSP identities,
reference variants, and PSP-only wording where that evidence is useful. Those
records are not a PSP build: there are currently no physical PSP bindings,
extraction/repacking commands, generated outputs, or install profile in this
repository.

Future PSP work should reuse the shared semantic assets and add PSP-owned
bindings, surface limits, codecs, engine changes, media validation, and a
top-level build workflow rather than copying the Saturn binary model.
