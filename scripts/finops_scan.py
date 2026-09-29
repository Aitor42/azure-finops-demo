#!/usr/bin/env python3
"""Idle/orphaned resource scanner (FinOps "Rightsizing").

Scans the ENTIRE subscription and detects:
  - Managed disks not attached to any VM
  - Orphaned public IPs (no NIC associated)
  - NICs not associated with any VM
  - Deallocated VMs that still pay for their disks

Usage:
  AZURE_SUBSCRIPTION_ID=<sub-id> python3 finops_scan.py
"""

import logging
import os
import sys

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient

logger = logging.getLogger(__name__)

SUBSCRIPTION_ID: str | None = os.environ.get("AZURE_SUBSCRIPTION_ID")


# ---------------------------------------------------------------------------
# Individual scanners \u2014 each returns a list of human-readable findings.
# ---------------------------------------------------------------------------


def scan_unattached_disks(compute: ComputeManagementClient) -> list[str]:
    """Detect managed disks not attached to any VM."""
    findings: list[str] = []
    for disk in compute.disks.list():
        if disk.managed_by is None:
            findings.append(f"- [DISK] Unattached disk: `{disk.name}` ({disk.disk_size_gb} GB)")
    return findings


def scan_orphaned_public_ips(network: NetworkManagementClient) -> list[str]:
    """Detect public IP addresses without an associated NIC."""
    findings: list[str] = []
    for pip in network.public_ip_addresses.list_all():
        if pip.ip_configuration is None:
            findings.append(f"- [PUBLIC_IP] Orphaned public IP: `{pip.name}`")
    return findings


def scan_orphaned_nics(network: NetworkManagementClient) -> list[str]:
    """Detect NICs not associated with any VM."""
    findings: list[str] = []
    for nic in network.network_interfaces.list_all():
        if nic.virtual_machine is None:
            findings.append(f"- [NIC] NIC not associated with a VM: `{nic.name}`")
    return findings


def scan_deallocated_vms(compute: ComputeManagementClient) -> list[str]:
    """Detect deallocated VMs that still incur disk charges.

    Uses ``status_only="true"`` to fetch the instance view in a single API call,
    falling back to an explicit ``instance_view()`` request when the SDK does
    not populate the field.
    """
    findings: list[str] = []
    for vm in compute.virtual_machines.list_all(status_only="true"):
        instance_view = getattr(vm, "instance_view", None)
        if instance_view is None:
            if not vm.id or not vm.name:
                continue
            parts = vm.id.split("/")
            if len(parts) < 5 or parts[3].lower() != "resourcegroups":
                continue
            resource_group = parts[4]
            try:
                instance_view = compute.virtual_machines.instance_view(resource_group, vm.name)
            except Exception:
                logger.warning(
                    "Skipping VM %s: unable to fetch instance view",
                    vm.name,
                    exc_info=True,
                )
                continue
        statuses = getattr(instance_view, "statuses", None) or []
        for status in statuses:
            if status.code and status.code.startswith("PowerState/deallocated"):
                findings.append(f"- [VM] Deallocated VM (still paying for disks): `{vm.name}`")
                break
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all scans and print the consolidated FinOps report."""
    if not SUBSCRIPTION_ID:
        logger.error("Define AZURE_SUBSCRIPTION_ID")
        return 2

    credential = DefaultAzureCredential()
    compute = ComputeManagementClient(credential, SUBSCRIPTION_ID)
    network = NetworkManagementClient(credential, SUBSCRIPTION_ID)

    findings: list[str] = [
        *scan_unattached_disks(compute),
        *scan_orphaned_public_ips(network),
        *scan_orphaned_nics(network),
        *scan_deallocated_vms(compute),
    ]

    print("# FinOps report - idle resources")
    print()
    if findings:
        print("\n".join(findings))
        print(f"\n**Total: {len(findings)} findings**")
        return 1
    print("No findings. All clean!")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
    sys.exit(main())
