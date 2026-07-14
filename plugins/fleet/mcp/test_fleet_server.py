import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).with_name("fleet_server.py")
SPEC = importlib.util.spec_from_file_location("fleet_server", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
fleet_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet_server)


class FleetServerTests(unittest.TestCase):
    def test_tool_surface_includes_dashboard_and_operations(self) -> None:
        names = {tool["name"] for tool in fleet_server.tool_definitions()}
        self.assertIn("fleet_dashboard", names)
        self.assertIn("fleet_preflight", names)
        self.assertIn("fleet_runtime_action", names)

    def test_safe_snapshot_removes_terminal_tails(self) -> None:
        snapshot = fleet_server.safe_snapshot(
            {
                "fleet_id": "swarm",
                "signals": ["head_due_cxo"],
                "board_status_raw_tail": "private terminal output",
                "heads": {
                    "head-cxo": {
                        "sweep_due": True,
                        "runtime": {"state": "stopped", "tail": "private terminal output"},
                    }
                },
            }
        )
        self.assertNotIn("board_status_raw_tail", snapshot)
        self.assertNotIn("tail", snapshot["heads"]["head-cxo"]["runtime"])
        self.assertEqual(snapshot["signals"], ["head_due_cxo"])

    def test_dashboard_is_compact_and_uses_safe_counts(self) -> None:
        text = fleet_server.dashboard(
            {
                "mode": "monitor",
                "fleet": {"fleet_id": "swarm"},
                "baseline": {"last_cycle": 12, "last_cycle_summary": "quiet"},
                "snapshot": {
                    "fleet_posture": {"mode": "standby"},
                    "hands": {"hand-1": {"actionable": 2, "runtime": {"state": "running"}}},
                    "heads": {"head-ceo": {"runtime": {"state": "stopped"}}},
                    "mind": {"inbox_unread": 1},
                    "operator": {"open_count": 0},
                    "integration": {"pending_rtm_count": 1},
                    "signals": ["pending_rtm"],
                },
            }
        )
        self.assertIn("◈ swarm monitor standby · cycle 12", text)
        self.assertIn("Hand 1/1 · Head 0/1", text)
        self.assertIn("work 2 · ✉1 · ⚑0 · ↻1 · !1", text)


if __name__ == "__main__":
    unittest.main()
