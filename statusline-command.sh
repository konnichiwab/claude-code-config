#!/usr/bin/env bash
input=$(cat)

/c/Users/mjjkl/AppData/Local/Programs/Python/Python311/python - <<'EOF' "$input"
import sys, json

try:
    data = json.loads(sys.argv[1])
    cw = data.get('context_window', {})
    used = cw.get('current_usage', {}).get('input_tokens')
    total = cw.get('context_window_size')
    used_pct = cw.get('used_percentage')
    remaining_pct = cw.get('remaining_percentage')

    model = data.get('model', {}).get('display_name', '')
    model_str = f" [{model}]" if model else ""

    if used is not None and total is not None and used_pct is not None:
        print(f"\033[2mContext: {used:,} / {total:,} tokens used ({used_pct:.0f}% used, {remaining_pct:.0f}% remaining){model_str}\033[0m", end='')
    elif total is not None:
        print(f"\033[2mContext: -- / {total:,} tokens (no messages yet){model_str}\033[0m", end='')
except Exception:
    pass
EOF
