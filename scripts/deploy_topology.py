"""
SYLION -- Topology Deployment Generator

Generates Terraform and Ansible files for 5/8/10-server topologies.

Usage:
    python scripts/deploy_topology.py --variant 8_server --output ./infra
    python scripts/deploy_topology.py --variant 5_server --output ./infra
    python scripts/deploy_topology.py --variant 10_server --output ./infra

Then:
    cd infra/8_server/terraform && terraform init && terraform apply
    cd infra/8_server/ansible && ansible-playbook -i inventory.ini playbook.yml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "sylion-pipeline"))

from sylion.infra.topology_templates import generate_all, TOPOLOGIES


def main():
    parser = argparse.ArgumentParser(description="Generate SYLION topology deployment files")
    parser.add_argument("--variant", required=True, choices=list(TOPOLOGIES.keys()), help="Topology variant")
    parser.add_argument("--output", default="./infra", help="Output directory")
    args = parser.parse_args()

    result = generate_all(args.variant, args.output)

    print(f"Generated {args.variant} topology in {Path(args.output) / args.variant}")
    print(f"  Terraform: {result['terraform']}")
    print(f"  Inventory: {result['inventory']}")
    print(f"  Playbook:  {result['playbook']}")
    print("")
    print("Next steps:")
    print(f"  1. cd {Path(args.output) / args.variant / 'terraform'} && terraform init")
    print(f"  2. Update ansible/inventory.ini with real IP addresses")
    print(f"  3. cd {Path(args.output) / args.variant / 'ansible'} && ansible-playbook -i inventory.ini playbook.yml")


if __name__ == "__main__":
    main()
