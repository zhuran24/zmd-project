import json
from continuation_b import *
from continuation_build_inputs import verify as verify_build
snapshot=json.loads((RUN/'continuation-b-source.json').read_text());profile=json.loads((RUN/'continuation-test-profile.json').read_text())['profile'];tests=json.loads((RUN/'test-harnesses.json').read_text());art=json.loads((RUN/'continuation-test-artifacts.json').read_text())
check('isolation-resume-before');frozen(snapshot);verify_build();isolation(snapshot,profile,tests,art);verify_build()
