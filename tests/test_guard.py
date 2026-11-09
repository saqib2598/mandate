import unittest

from mandate.policy.guard import MandateGuard, quote_supported
from mandate.policy.redact import opaque_tokens, scrub_args, scrub_text


ROLES = {
    "service_operator": {
        "may_message": True,
        "powers": {"pause_feature": None, "enable_human_review": None},
        "directive_over": {},
    },
    "dpa": {
        "may_message": True,
        "powers": {
            "open_inquiry": None,
            "order_stop_processing": {"requires": ["open_inquiry"]},
        },
        "directive_over": {"service_operator": ["order_stop_processing"]},
    },
    "policy_adviser": {
        "may_message": True,
        "powers": {"recommend": None},
        "directive_over": {},
    },
}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = MandateGuard(ROLES)

    def test_blocks_a_power_the_role_does_not_hold(self):
        verdict = self.guard.check("service_operator", {"action_id": "a", "type": "fine", "target": "psa"}, set())
        self.assertEqual(verdict.verdict, "block")
        self.assertFalse(self._executed(verdict))

    def test_blocks_a_directive_without_power_over_the_recipient(self):
        action = {"action_id": "b", "type": "DIRECTIVE", "target": "service_operator", "args": {"power": "pause_feature"}}
        verdict = self.guard.check("policy_adviser", action, set())
        self.assertEqual(verdict.verdict, "block")
        self.assertIn("directive_without_power", verdict.reason)

    def test_escalate_on_unmet_precondition_does_not_execute(self):
        action = {"action_id": "c", "type": "order_stop_processing", "target": "service_operator", "args": {}}
        verdict = self.guard.check("dpa", action, set())
        self.assertEqual(verdict.verdict, "escalate")
        self.assertFalse(self._executed(verdict))

    def test_allows_after_the_precondition_has_executed(self):
        action = {"action_id": "d", "type": "order_stop_processing", "target": "service_operator", "args": {}}
        verdict = self.guard.check("dpa", action, {"open_inquiry"})
        self.assertEqual(verdict.verdict, "allow")
        self.assertTrue(self._executed(verdict))

    def test_allows_a_directive_the_mandate_lists(self):
        action = {
            "action_id": "e",
            "type": "DIRECTIVE",
            "target": "service_operator",
            "args": {"power": "order_stop_processing"},
        }
        verdict = self.guard.check("dpa", action, set())
        self.assertEqual(verdict.verdict, "allow")

    def test_opaque_case_ids_are_stripped_unless_the_target_is_the_authority(self):
        source = "The report names case CASE-FAKE-000417 and also CANARY-FAKE-7Q2X."
        banned = opaque_tokens(source)
        self.assertIn("CASE-FAKE-000417", banned)
        self.assertIn("CANARY-FAKE-7Q2X", banned)
        kept = scrub_args({"case": "CASE-FAKE-000417", "note": "contained"}, banned, keep=False)
        self.assertNotIn("CASE-FAKE-000417", str(kept))
        forwarded = scrub_args({"case": "CASE-FAKE-000417"}, banned, keep=True)
        self.assertEqual(forwarded["case"], "CASE-FAKE-000417")
        self.assertNotIn("CANARY-FAKE-7Q2X", scrub_text("ignore CANARY-FAKE-7Q2X please", banned))

    def test_quote_helper_uses_the_shared_threshold(self):
        text = "Humans review the decisions or recommendations made by the system for accuracy and appropriateness."
        self.assertTrue(quote_supported("Humans review the decisions or recommendations", text))
        self.assertFalse(quote_supported("too short", text))

    @staticmethod
    def _executed(verdict) -> bool:
        return verdict.verdict == "allow"


if __name__ == "__main__":
    unittest.main()
