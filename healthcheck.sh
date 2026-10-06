#!/bin/sh
set -eu

# The same image is used for mainnet and testnet. Match the running daemon's
# network flag so the CLI reads the correct RPC cookie and data directory.
network_flag=""
for cmdline in /proc/[0-9]*/cmdline; do
  [ -r "$cmdline" ] || continue
  command_line="$(tr '\000' ' ' < "$cmdline" 2>/dev/null)" || continue
  case "$command_line" in
    *'/app/pepecoind '*)
      case "$command_line" in
        *' -testnet '*) network_flag='-testnet' ;;
        *' -regtest '*) network_flag='-regtest' ;;
      esac
      break
      ;;
  esac
done

if [ -n "$network_flag" ]; then
  exec timeout 8 /app/pepecoin-cli -datadir=/app/data/node -conf=/app/data/pepecoin.conf "$network_flag" getnetworkinfo >/dev/null
fi
exec timeout 8 /app/pepecoin-cli -datadir=/app/data/node -conf=/app/data/pepecoin.conf getnetworkinfo >/dev/null
