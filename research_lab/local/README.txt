RESEARCH LOCAL RUNTIME AREA
===========================

Everything below this directory is ignored except this file and .gitignore.
Use it for material whose existence helps the current session but does not make a
durable research conclusion:

  runs/<campaign>/<experiment>/<run-id>/
  scratch/
  cache/
  models/
  notebooks/
  mounts/

Recommended run directory contents
----------------------------------
  command.txt or argv.json
  input_identities.json
  stdout.log
  stderr.log
  result.json
  EXIT_CODE
  .DONE

A run becomes durable by extracting a compact, checked conclusion into the
campaign experiment directory and RESULTS.txt. Do not commit a raw run merely to
avoid summarizing what it taught.

External mounts
---------------
The research tree may refer to verified large inputs or historical evidence in
/home/zhuran24/zmd-pj. Put optional local symlinks or copied payloads under
local/mounts/, record the source digest in the experiment, and keep the mount out
of Git.

Deletion
--------
This area is disposable after durable conclusions and required evidence identities
have been recorded. Never delete the history/material tree's source evidence as
part of cleaning this directory.
