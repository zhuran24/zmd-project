#!/usr/bin/env bash
# P2 #14 PoC Gemini run — 同 prompt (跟 Opus 4.7 子代理收到的)
# 用 gemini-3.1-pro-preview, 输出 raw response + 文本部分

set -euo pipefail

ENV_FILE="${HOME}/.config/google_ai_studio/.env"
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a

OUT_DIR="$(dirname "$(realpath "$0")")"
PROMPT_FILE="$OUT_DIR/gemini_prompt.txt"
RAW_FILE="$OUT_DIR/gemini_raw_response.json"
TXT_FILE="$OUT_DIR/gemini_output.md"
META_FILE="$OUT_DIR/gemini_run_meta.json"

[[ -f "$PROMPT_FILE" ]] || { echo "ERROR: prompt 未拷到 $PROMPT_FILE" >&2; exit 1; }

MODEL="gemini-3.1-pro-preview"
URL="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}"

echo "=== Gemini PoC: $MODEL ==="
echo "Prompt size: $(wc -c < "$PROMPT_FILE") bytes"
START_TS=$(date -Iseconds)

BODY=$(jq -Rs '{
  contents: [{parts: [{text: .}]}],
  generationConfig: {temperature: 1.0, maxOutputTokens: 8192, topP: 0.95}
}' "$PROMPT_FILE")

curl -sS -X POST "$URL" -H "Content-Type: application/json" -d "$BODY" > "$RAW_FILE"
END_TS=$(date -Iseconds)

# Extract text
python3 -c "
import json, sys
d = json.load(open('$RAW_FILE'))
if 'candidates' not in d:
    print('ERROR raw response:', json.dumps(d, indent=2, ensure_ascii=False))
    sys.exit(1)
text = d['candidates'][0]['content']['parts'][0]['text']
open('$TXT_FILE', 'w').write(text)
print('OK: text ->', '$TXT_FILE', f'({len(text)} chars)')
print('Finish reason:', d['candidates'][0].get('finishReason'))
print('Token usage:', d.get('usageMetadata', {}))
"

# Meta
jq -n --arg s "$START_TS" --arg e "$END_TS" --arg m "$MODEL" \
  '{model:$m, start:$s, end:$e}' > "$META_FILE"
echo "Meta -> $META_FILE"
