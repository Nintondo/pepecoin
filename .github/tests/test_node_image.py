"""Start the actual built node in isolated regtest and exercise its healthcheck."""
import json
import os
from pathlib import Path
import subprocess
import shlex
from test_node_template import render_service
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=json.loads(Path(__file__).with_name('deployment-fixture.json').read_text())[0]
NAME=FIXTURE['env']['SERVICE_NAME']
COIN='bellscoin' if NAME=='bellscoin-dev' else NAME
DAEMON={'bellscoin':'bellsd','dogecoin':'dogecoind','pepecoin':'pepecoind'}[COIN]
CLI={'bellscoin':'bells-cli','dogecoin':'dogecoin-cli','pepecoin':'pepecoin-cli'}[COIN]

def run(*args,**kwargs):
    return subprocess.run(args,check=True,text=True,**kwargs)

def main():
    container='node-regtest-'+uuid.uuid4().hex[:12]
    compose_probe = render_service('regtest')['healthcheck']['test'][1:]
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as temporary:
        data=Path(temporary)/'data'; (data/'node').mkdir(parents=True)
        password=uuid.uuid4().hex
        (data/(COIN+'.conf')).write_text('server=1\nregtest=1\nlisten=0\ndnsseed=0\ndiscover=0\nrpcuser=fixture\nrpcpassword='+password+'\n')
        try:
            run('docker','create','--name',container,'--health-cmd',shlex.join(compose_probe),'--health-interval','2s','--health-timeout','10s','--health-start-period','0s','--health-retries','3','--mount','type=volume,target=/app/data',os.environ['CI_TEST_IMAGE'],f'/app/{DAEMON}','-regtest','-datadir=/app/data/node',f'-conf=/app/data/{COIN}.conf',stdout=subprocess.DEVNULL)
            # Docker may run outside the runner container. Transfer fixture data
            # through the API into an anonymous test volume; no host bind paths.
            run('docker','cp',str(data)+ '/.',container+':/app/data')
            run('docker','start',container,stdout=subprocess.DEVNULL)
            for _ in range(60):
                p=subprocess.run(['docker','exec',container,'/healthcheck.sh'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                status=run('docker','inspect','-f','{{.State.Health.Status}}',container,capture_output=True).stdout.strip()
                if not p.returncode and status=='healthy': break
                time.sleep(2)
            else: raise RuntimeError('Actual node RPC healthcheck did not become ready')
            info=run('docker','exec',container,f'/app/{CLI}','-regtest','-datadir=/app/data/node',f'-conf=/app/data/{COIN}.conf','getblockchaininfo',capture_output=True)
            assert json.loads(info.stdout)['chain']=='regtest'
            print('Actual node regtest RPC, image probe and Compose probe passed:',COIN)
        finally:
            # No production chain, volumes, registry credentials or exposed ports.
            subprocess.run(['docker','stop','-t','30',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['docker','rm','-fv',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            # -v removes only the disposable container's anonymous test volume.

if __name__=='__main__':main()
