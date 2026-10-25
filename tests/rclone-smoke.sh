#!/bin/sh
# Run only on a compatible ARM Linux device with extracted package payloads.
set -eu
binary=$1
assets=$2
work=$(mktemp -d /tmp/gui-rclone-smoke.XXXXXX)
server_pid=
cleanup() {
	[ -z "$server_pid" ] || { kill "$server_pid" 2>/dev/null || :; wait "$server_pid" 2>/dev/null || :; }
	rm -rf "$work"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$work/input/subdir" "$work/output"
printf 'rclone local transfer\n' > "$work/input/a file.txt"
printf '\000\001\377\002' > "$work/input/subdir/binary"
: > "$work/input/empty"
"$binary" version
"$binary" --config "$work/rclone.conf" copy "$work/input" "$work/output"
"$binary" --config "$work/rclone.conf" check --checksum "$work/input" "$work/output"
cmp "$work/input/a file.txt" "$work/output/a file.txt"
cmp "$work/input/subdir/binary" "$work/output/subdir/binary"
test -f "$work/output/empty"

# Choose an unused loopback TCP port, never change the device's active services.
port=58421
while netstat -lnt 2>/dev/null | grep -q ":$port "; do
	port=$((port + 1))
	[ "$port" -lt 58431 ] || exit 1
done
for interface in ng react; do
	"$binary" --config "$work/rclone.conf" rcd --rc-addr="127.0.0.1:$port" \
		--rc-user=smoke --rc-pass=private-smoke-test \
		--rc-files="$assets/$interface" > "$work/server.log" 2>&1 &
	server_pid=$!
	ready=0
	for attempt in 1 2 3 4 5; do
		if curl --silent --fail --max-time 2 --user smoke:private-smoke-test \
			-X POST "http://127.0.0.1:$port/core/version" > "$work/version.json"; then
			ready=1
			break
		fi
		kill -0 "$server_pid"
		sleep 1
	done
	[ "$ready" -eq 1 ] || { cat "$work/server.log"; exit 1; }
	grep -q 'v1.75.2' "$work/version.json"
	curl --silent --fail --max-time 2 --user smoke:private-smoke-test \
		-X POST "http://127.0.0.1:$port/config/listremotes" > "$work/remotes.json"
	grep -q '"remotes"' "$work/remotes.json"
	curl --silent --fail --max-time 2 --user smoke:private-smoke-test \
		--data-urlencode "fs=$work/input" --data-urlencode 'remote=' \
		"http://127.0.0.1:$port/operations/list" > "$work/list.json"
	grep -q 'a file.txt' "$work/list.json"
	status=$(curl --silent --max-time 2 --output /dev/null --write-out '%{http_code}' \
		-X POST "http://127.0.0.1:$port/core/version")
	[ "$status" = 401 ]
	curl --silent --fail --max-time 2 --user smoke:private-smoke-test \
		"http://127.0.0.1:$port/" > "$work/index.html"
	cmp "$assets/$interface/index.html" "$work/index.html"
	kill "$server_pid"
	wait "$server_pid" || :
	server_pid=
	printf 'Authenticated RC and %s interface: OK\n' "$interface"
done
printf 'Rclone local copy, checksums and private RC smoke: OK\n'
