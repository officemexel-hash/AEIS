"""
SYLION Distributed-Ready -- Hetzner Host B provisioning.

Creates a cx23 VPS in fsn1 running ubuntu-24.04 with cloud-init user-data
that installs a minimal sylion-worker heartbeat daemon. The daemon POSTs
status every 60s to WEBHOOK_URL (publicly verifiable).

Run once to provision, prints infra/hetzner_host_b.json path.

ENV:
  HETZNER_API_TOKEN  -- required
  SYLION_WEBHOOK_URL -- optional, heartbeat target; if absent, heartbeat disabled
  SYLION_SSH_KEY_ID  -- optional, Hetzner SSH key ID; if absent, first key used
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from hcloud import Client
from hcloud.server_types import ServerType
from hcloud.images import Image
from hcloud.locations import Location
from hcloud.ssh_keys import SSHKey


def build_cloud_init(webhook_url: str) -> str:
    """Return cloud-init user-data that bootstraps the sylion-worker daemon."""
    # Escape embedded shell special chars: webhook_url is injected as a shell
    # single-quoted literal, so we only need to forbid apostrophes in it.
    if "'" in webhook_url:
        raise ValueError("webhook url contains apostrophe; refuse to embed")
    return f"""#cloud-config
package_update: true
package_upgrade: false
packages:
  - python3
  - python3-pip
  - python3-venv
  - curl
  - jq

write_files:
  - path: /opt/sylion/worker.py
    permissions: '0755'
    content: |
      #!/usr/bin/env python3
      import json, socket, subprocess, time, urllib.request, uuid
      WEBHOOK = '{webhook_url}'
      WORKER_ID = 'hetzner-' + socket.gethostname()
      def push():
          body = json.dumps({{
              'worker_id': WORKER_ID,
              'hostname': socket.gethostname(),
              'ts': int(time.time()),
              'kind': 'sylion.worker.heartbeat',
              'version': '1.0',
          }}).encode()
          req = urllib.request.Request(WEBHOOK, data=body,
              headers={{'Content-Type': 'application/json'}}, method='POST')
          with urllib.request.urlopen(req, timeout=20) as r:
              return r.status
      print('sylion-worker starting, webhook=' + WEBHOOK)
      while True:
          try:
              code = push()
              print('heartbeat ok ' + str(code) + ' ts=' + str(int(time.time())), flush=True)
          except Exception as e:
              print('heartbeat fail: ' + str(e), flush=True)
          time.sleep(60)

  - path: /etc/systemd/system/sylion-worker.service
    permissions: '0644'
    content: |
      [Unit]
      Description=SYLION Worker Heartbeat (Host B)
      After=network-online.target
      Wants=network-online.target

      [Service]
      ExecStart=/usr/bin/python3 /opt/sylion/worker.py
      Restart=always
      RestartSec=5
      StandardOutput=append:/var/log/sylion-worker.log
      StandardError=append:/var/log/sylion-worker.log

      [Install]
      WantedBy=multi-user.target

runcmd:
  - systemctl daemon-reload
  - systemctl enable sylion-worker.service
  - systemctl start sylion-worker.service
"""


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    token = os.environ.get("HETZNER_API_TOKEN", "")
    if not token:
        print("ERROR: HETZNER_API_TOKEN not set", file=sys.stderr)
        return 2
    webhook = os.environ.get("SYLION_WEBHOOK_URL", "")
    if not webhook:
        print("ERROR: SYLION_WEBHOOK_URL not set", file=sys.stderr)
        return 2

    c = Client(token=token)
    keys = c.ssh_keys.get_all()
    if not keys:
        print("ERROR: no SSH key registered in Hetzner account", file=sys.stderr)
        return 2
    desired_key_id = os.environ.get("SYLION_SSH_KEY_ID")
    key = next((k for k in keys if str(k.id) == desired_key_id), keys[0])
    print(f"Using SSH key id={key.id} name={key.name}")

    name = "sylion-host-b-" + str(int(time.time()))
    print(f"Creating server name={name} type=cx23 location=fsn1 image=ubuntu-24.04")
    user_data = build_cloud_init(webhook)
    resp = c.servers.create(
        name=name,
        server_type=ServerType(name="cx23"),
        image=Image(name="ubuntu-24.04"),
        location=Location(name="fsn1"),
        ssh_keys=[SSHKey(id=key.id)],
        user_data=user_data,
        start_after_create=True,
        labels={"purpose": "sylion-distributed", "role": "host-b"},
    )
    server = resp.server
    action = resp.action
    print(f"Server id={server.id} created, waiting for boot...")

    deadline = time.time() + 300
    while time.time() < deadline:
        s = c.servers.get_by_id(server.id)
        print(f"  status={s.status} ip={s.public_net.ipv4.ip if s.public_net.ipv4 else '-'}")
        if s.status == "running":
            server = s
            break
        time.sleep(6)
    else:
        print("ERROR: server did not reach running within 300s", file=sys.stderr)
        return 3

    ip = server.public_net.ipv4.ip
    record = {
        "server_id": server.id,
        "name": server.name,
        "server_type": "cx23",
        "location": "fsn1",
        "image": "ubuntu-24.04",
        "ipv4": ip,
        "created_iso": str(server.created),
        "ssh_key_id": key.id,
        "ssh_key_fingerprint": key.fingerprint,
        "webhook_url": webhook,
        "labels": dict(server.labels),
    }
    out = Path(__file__).resolve().parent.parent / "infra" / "hetzner_host_b.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(f"Wrote {out}")
    print(f"IPv4={ip}")
    print(f"Next: ssh root@{ip}  # after cloud-init finishes (~60-90s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
