"""Tests for finops_scan.py — each scanner function + main() integration."""

from unittest.mock import MagicMock, patch

from finops_scan import (
    main,
    scan_deallocated_vms,
    scan_orphaned_nics,
    scan_orphaned_public_ips,
    scan_unattached_disks,
)

# ---------------------------------------------------------------------------
# scan_unattached_disks
# ---------------------------------------------------------------------------


class TestScanUnattachedDisks:
    """Disks with managed_by=None should be reported."""

    def test_detects_unattached_disk(self):
        disk = MagicMock(name="orphan-disk", disk_size_gb=128, managed_by=None)
        # MagicMock's own `name` kwarg is special; override it explicitly.
        disk.name = "orphan-disk"
        compute = MagicMock()
        compute.disks.list.return_value = [disk]

        findings = scan_unattached_disks(compute)
        assert len(findings) == 1
        assert "orphan-disk" in findings[0]
        assert "128" in findings[0]

    def test_ignores_attached_disk(self):
        disk = MagicMock(managed_by="/subscriptions/.../vms/my-vm")
        compute = MagicMock()
        compute.disks.list.return_value = [disk]

        assert scan_unattached_disks(compute) == []

    def test_empty_subscription(self):
        compute = MagicMock()
        compute.disks.list.return_value = []
        assert scan_unattached_disks(compute) == []


# ---------------------------------------------------------------------------
# scan_orphaned_public_ips
# ---------------------------------------------------------------------------


class TestScanOrphanedPublicIps:
    """Public IPs with ip_configuration=None should be reported."""

    def test_detects_orphaned_ip(self):
        pip = MagicMock(ip_configuration=None)
        pip.name = "orphan-ip"
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = [pip]

        findings = scan_orphaned_public_ips(network)
        assert len(findings) == 1
        assert "orphan-ip" in findings[0]

    def test_ignores_attached_ip(self):
        pip = MagicMock(ip_configuration=MagicMock())
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = [pip]

        assert scan_orphaned_public_ips(network) == []


# ---------------------------------------------------------------------------
# scan_orphaned_nics
# ---------------------------------------------------------------------------


class TestScanOrphanedNics:
    """NICs with virtual_machine=None should be reported."""

    def test_detects_orphaned_nic(self):
        nic = MagicMock(virtual_machine=None)
        nic.name = "orphan-nic"
        network = MagicMock()
        network.network_interfaces.list_all.return_value = [nic]

        findings = scan_orphaned_nics(network)
        assert len(findings) == 1
        assert "orphan-nic" in findings[0]

    def test_ignores_attached_nic(self):
        nic = MagicMock(virtual_machine=MagicMock())
        network = MagicMock()
        network.network_interfaces.list_all.return_value = [nic]

        assert scan_orphaned_nics(network) == []


# ---------------------------------------------------------------------------
# scan_deallocated_vms
# ---------------------------------------------------------------------------


class TestScanDeallocatedVms:
    """Deallocated VMs that still incur disk charges should be reported."""

    def test_detects_deallocated_vm(self):
        status = MagicMock(code="PowerState/deallocated")
        vm = MagicMock()
        vm.name = "stopped-vm"
        vm.instance_view.statuses = [status]

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]

        findings = scan_deallocated_vms(compute)
        assert len(findings) == 1
        assert "stopped-vm" in findings[0]

    def test_ignores_running_vm(self):
        status = MagicMock(code="PowerState/running")
        vm = MagicMock()
        vm.instance_view.statuses = [status]

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]

        assert scan_deallocated_vms(compute) == []

    def test_fallback_when_instance_view_is_none(self):
        """Falls back to an explicit API call when instance_view is missing."""
        status = MagicMock(code="PowerState/deallocated")
        fallback_view = MagicMock(statuses=[status])

        vm = MagicMock()
        vm.name = "fallback-vm"
        vm.id = (
            "/subscriptions/x/resourceGroups/rg/providers/"
            "Microsoft.Compute/virtualMachines/fallback-vm"
        )
        vm.instance_view = None  # triggers fallback

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]
        compute.virtual_machines.instance_view.return_value = fallback_view

        findings = scan_deallocated_vms(compute)
        assert len(findings) == 1
        compute.virtual_machines.instance_view.assert_called_once_with("rg", "fallback-vm")

    def test_skips_vm_when_api_fails(self):
        """Gracefully skips a VM when the fallback API call errors."""
        vm = MagicMock()
        vm.name = "error-vm"
        vm.id = (
            "/subscriptions/x/resourceGroups/rg/providers/"
            "Microsoft.Compute/virtualMachines/error-vm"
        )
        vm.instance_view = None

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]
        compute.virtual_machines.instance_view.side_effect = Exception("API error")

        assert scan_deallocated_vms(compute) == []

    def test_skips_vm_when_id_or_name_missing(self):
        """Gracefully skips when vm.id or vm.name is None without instance_view."""
        vm_no_id = MagicMock(id=None, name="no-id-vm", instance_view=None)
        vm_no_name = MagicMock(
            id="/subscriptions/x/resourceGroups/rg/providers/vm", name=None, instance_view=None
        )

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm_no_id, vm_no_name]

        assert scan_deallocated_vms(compute) == []

    def test_skips_vm_when_id_is_malformed(self):
        """Gracefully skips when vm.id does not match Azure resource ID pattern."""
        vm = MagicMock(id="/invalid/id", name="bad-id-vm", instance_view=None)
        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]

        assert scan_deallocated_vms(compute) == []

    def test_handles_none_statuses(self):
        """Handles instance_view.statuses being None without crashing."""
        vm = MagicMock()
        vm.name = "no-status-vm"
        vm.instance_view.statuses = None

        compute = MagicMock()
        compute.virtual_machines.list_all.return_value = [vm]

        assert scan_deallocated_vms(compute) == []


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMain:
    """End-to-end tests for the CLI entry point."""

    def test_exits_2_without_subscription_id(self):
        with patch("finops_scan.SUBSCRIPTION_ID", None):
            assert main() == 2

    def test_returns_0_when_no_findings(self, capsys):
        compute = MagicMock()
        compute.disks.list.return_value = []
        compute.virtual_machines.list_all.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.network_interfaces.list_all.return_value = []

        with (
            patch("finops_scan.SUBSCRIPTION_ID", "test-sub"),
            patch("finops_scan.DefaultAzureCredential"),
            patch("finops_scan.ComputeManagementClient", return_value=compute),
            patch("finops_scan.NetworkManagementClient", return_value=network),
        ):
            result = main()

        assert result == 0
        assert "All clean" in capsys.readouterr().out

    def test_returns_1_with_findings(self, capsys):
        disk = MagicMock(managed_by=None, disk_size_gb=64)
        disk.name = "orphan"
        compute = MagicMock()
        compute.disks.list.return_value = [disk]
        compute.virtual_machines.list_all.return_value = []
        network = MagicMock()
        network.public_ip_addresses.list_all.return_value = []
        network.network_interfaces.list_all.return_value = []

        with (
            patch("finops_scan.SUBSCRIPTION_ID", "test-sub"),
            patch("finops_scan.DefaultAzureCredential"),
            patch("finops_scan.ComputeManagementClient", return_value=compute),
            patch("finops_scan.NetworkManagementClient", return_value=network),
        ):
            result = main()

        assert result == 1
        assert "1 findings" in capsys.readouterr().out
