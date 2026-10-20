#!/usr/bin/env python3
"""Read iperf3 JSON objects following explicit benchmark markers."""
import json
import re
import sys
from pathlib import Path

for argument in sys.argv[1:]:
    path = Path(argument)
    content = path.read_text()
    matches = list(re.finditer(r"BENCHMARK (\w+) AES(128|192|256) (forward|reverse)", content))
    if not matches or f"PHASE_PASS {matches[0][1]}" not in content:
        raise ValueError(f"Incomplete traffic or cleanup: {path}")
    for match in matches:
        start = content.index("{", match.end())
        result, _ = json.JSONDecoder().raw_decode(content[start:])
        if "error" in result:
            raise ValueError(result["error"])
        rate = result["end"]["sum_received"]["bits_per_second"] / 1e6
        print(f"{match[1]},{match[2]},{match[3]},{rate:.2f}")
