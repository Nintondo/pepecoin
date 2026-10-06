"""Validate actual rendered node Compose probes for every supported network."""
import json
import os
from pathlib import Path
import re
import subprocess
from string import Template
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(Path(__file__).with_name('deployment-fixture.json').read_text())[0]
NAME = FIXTURE['env']['SERVICE_NAME']
COIN = 'bellscoin' if NAME == 'bellscoin-dev' else NAME
CLI = {'bellscoin': 'bells-cli', 'dogecoin': 'dogecoin-cli', 'pepecoin': 'pepecoin-cli'}[COIN]
TEMPLATE = {
    'bellscoin': '.github/templates/bellscoin.yml.template',
    'dogecoin': '.github/templates/dogecoin.yml.template',
    'pepecoin': 'deploy/templates/pepecoin.yml.template',
}[COIN]


def render_service(network, custom_paths=False):
    template = (ROOT / TEMPLATE).read_text()
    values = {key: '' for key in re.findall(r'\$\{([A-Z_]+)\}', template)}
    flag = '' if network == 'mainnet' else '-' + network
    network_fragment = ', ' + json.dumps(flag) if flag else ''
    data_path = '/chain/data' if custom_paths else '/app/data/node'
    conf_path = '/chain/node.conf' if custom_paths else '/app/data/' + COIN + '.conf'
    values.update({
        'COMPOSE_SERVICE_NAME': 'node-fixture', 'COMPOSE_SERVICE': 'node-fixture',
        'CONTAINER_NAME': 'node-fixture', 'IMAGE': 'nintondo-ci:check',
        'CI_REGISTRY': 'registry.example', 'CI_REGISTRY_REPO': 'project',
        'SERVICE_NAME': COIN, 'SERVICE_TAG': 'a' * 40,
        'CONFIG_RELATIVE_PATH': 'data/node.conf', 'CONFIG_CONTAINER_PATH': conf_path,
        'DATA_RELATIVE_PATH': 'data/node', 'DATA_CONTAINER_PATH': data_path,
        'PORTS_BLOCK': '      - "11111:11111"', 'EXPOSE_BLOCK': '',
        'DOGECOIN_P2P_PORT_MAPPING_LINE': '- "11111:11111"',
        'PEPECOIN_P2P_PORT': '11111', 'PEPECOIN_RPC_PORT': '11112',
        'COMMAND_EXTRA': network_fragment, 'DOGECOIN_NETWORK_ARG': network_fragment,
        # Daemon flags must stay out of the RPC client invocation.
        'PEPECOIN_COMMAND_ARGS': ', "-listen=0"' + network_fragment,
    })
    if COIN == 'pepecoin':
        result = subprocess.run(
            ['python3', str(ROOT / '.github/scripts/node-health-args.py')],
            env={**os.environ, 'PEPECOIN_COMMAND_ARGS': values['PEPECOIN_COMMAND_ARGS']},
            check=True, capture_output=True, text=True,
        )
        values['PEPECOIN_HEALTH_ARGS'] = result.stdout.strip()
    rendered = Template(template).substitute(values)
    with tempfile.TemporaryDirectory() as directory:
        compose = Path(directory) / 'compose.yml'
        compose.write_text(rendered)
        result = subprocess.run(
            ['docker', 'compose', '-f', str(compose), 'config', '--format', 'json'],
            check=True, capture_output=True, text=True,
        )
    return json.loads(result.stdout)['services']['node-fixture']


class NodeTemplateTests(unittest.TestCase):
    def test_probe_tracks_network_and_keeps_safe_shutdown(self):
        for network in ('mainnet', 'testnet', 'regtest'):
            for custom in ((False, True) if COIN == 'bellscoin' else (False,)):
                with self.subTest(network=network, custom_paths=custom):
                    service = render_service(network, custom)
                    probe = service['healthcheck']
                    args = probe['test']
                    data_path = '/chain/data' if custom else '/app/data/node'
                    conf_path = '/chain/node.conf' if custom else '/app/data/' + COIN + '.conf'
                    expected = ['CMD', 'timeout', '8', '/app/' + CLI,
                                '-datadir=' + data_path, '-conf=' + conf_path]
                    if network != 'mainnet':
                        expected.append('-' + network)
                    self.assertEqual(args, expected + ['getnetworkinfo'])
                    self.assertEqual(probe['interval'], '30s')
                    self.assertEqual(probe['timeout'], '10s')
                    self.assertEqual(probe['start_period'], '2m0s')
                    self.assertEqual(probe['retries'], 3)
                    self.assertEqual(service['stop_grace_period'], '10m0s')
                    self.assertIn('-datadir=' + data_path, service['command'])
                    self.assertIn('-conf=' + conf_path, service['command'])
                    if network != 'mainnet':
                        self.assertIn('-' + network, service['command'])


if __name__ == '__main__':
    unittest.main()
