"""Patch RoundingSat Logger::unsat for parse-time trivial UNSAT proof (zmd sidecar)."""
from pathlib import Path

p = Path.home() / "cert_toolchain/roundingsat/src/Logger.cpp"
src = p.read_text()
old = (
    "  } else {\n"
    '    proof_out << "conclusion UNSAT : " << last_proofID << "\\n";\n'
    "  }\n"
)
new = (
    "  } else {\n"
    "    // local patch (zmd sidecar 2026-07-05): parse-time trivial UNSAT reaches\n"
    "    // here without any logged contradiction (last_proofID may still be\n"
    "    // ID_Trivial = 'rup >= 0', which VeriPB correctly rejects as\n"
    "    // non-contradicting). Emit an explicit RUP empty constraint first;\n"
    "    // sound on all paths (unit propagation yields conflict).\n"
    '    proof_out << "rup >= 1 ;\\n";\n'
    "    ++last_proofID;\n"
    '    proof_out << "conclusion UNSAT : " << last_proofID << "\\n";\n'
    "  }\n"
)
if new in src:
    print("already patched")
elif old in src:
    p.write_text(src.replace(old, new))
    print("patched")
else:
    raise SystemExit("pattern not found")
