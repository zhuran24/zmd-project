set -euo pipefail
source "${1:?env.sh}"
python -B "$HEALTH_RUN/build_a.py"
