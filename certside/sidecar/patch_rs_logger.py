"""Patch RoundingSat Logger::unsat for parse-time trivial UNSAT proof (zmd sidecar)."""
from pathlib import Path

p = Path.home() / "cert_toolchain/roundingsat/src/Logger.cpp"
src = p.read_text()
# v2: rup 必须写在 output NONE 之前（proof 段序 derivation→output→conclusion；
# veripb 宽容乱序但 CakePB kernel parser 严格按段序）。unsat() 原文先写 output。
old_v0 = (
    "void Logger::unsat() {\n"
    '  proof_out << "output NONE\\n";\n'
    "  if (optimization) {\n"
    '    proof_out << "conclusion BOUNDS INF INF\\n";\n'
    "  } else {\n"
    '    proof_out << "conclusion UNSAT : " << last_proofID << "\\n";\n'
    "  }\n"
)
old_v1 = (
    "void Logger::unsat() {\n"
    '  proof_out << "output NONE\\n";\n'
    "  if (optimization) {\n"
    '    proof_out << "conclusion BOUNDS INF INF\\n";\n'
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
new = (
    "void Logger::unsat() {\n"
    "  // local patch v2 (zmd sidecar 2026-07-05): parse-time trivial UNSAT reaches\n"
    "  // here without any logged contradiction (last_proofID may still be\n"
    "  // ID_Trivial = 'rup >= 0', which VeriPB correctly rejects as\n"
    "  // non-contradicting). Emit an explicit RUP empty constraint first —\n"
    "  // BEFORE the output section (kernel parsers enforce section order).\n"
    "  // Sound on all paths (unit propagation yields conflict).\n"
    "  if (not optimization) {\n"
    '    proof_out << "rup >= 1 ;\\n";\n'
    "    ++last_proofID;\n"
    "  }\n"
    '  proof_out << "output NONE\\n";\n'
    "  if (optimization) {\n"
    '    proof_out << "conclusion BOUNDS INF INF\\n";\n'
    "  } else {\n"
    '    proof_out << "conclusion UNSAT : " << last_proofID << "\\n";\n'
    "  }\n"
)
if new in src:
    print("already patched (v2)")
elif old_v1 in src:
    p.write_text(src.replace(old_v1, new))
    print("patched (v1 -> v2)")
elif old_v0 in src:
    p.write_text(src.replace(old_v0, new))
    print("patched (v0 -> v2)")
else:
    raise SystemExit("pattern not found")
