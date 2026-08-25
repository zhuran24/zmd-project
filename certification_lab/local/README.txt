ZMD CERTIFICATION LOCAL RUNTIME AREA
====================================

This directory holds non-durable certification runtime material:

  replay logs
  temporary clean environments
  solver output and model dumps
  reproduced large external artifacts
  caches and basetemps
  scratch counterexamples
  local packet unpacking before frozen intake

Everything except this README and .gitignore is ignored by Git. Durable checker
source, small fixtures, packet bytes, review findings, and verdicts belong in
tracked paths outside local/.

A local file is not evidence merely because it exists. Any local object that
bears a verdict must be copied into a frozen packet/review location or recorded
with path, size, SHA-256, provenance, and retention policy.
