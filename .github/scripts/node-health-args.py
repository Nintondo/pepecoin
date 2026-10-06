"""Keep network selection in RPC probes without passing daemon-only flags."""
import json
import os

args = json.loads('["placeholder"' + os.environ.get("PEPECOIN_COMMAND_ARGS", "") + "]")[1:]
if not all(isinstance(arg, str) for arg in args):
    raise ValueError("PEPECOIN_COMMAND_ARGS must contain JSON string arguments")
network_args = [arg for arg in args if arg.split("=", 1)[0] in ("-testnet", "-regtest", "-chain")]
print("".join(", " + json.dumps(arg) for arg in network_args))
