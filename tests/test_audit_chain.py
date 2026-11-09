import json
import sys
import tempfile
import unittest
from pathlib import Path

from mandate.audit.log import GENESIS, AuditLog, record_hash
from mandate.audit.verify import verify_chain

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import score  # noqa: E402


class AuditChainTests(unittest.TestCase):
    def test_hash_matches_the_scorer(self):
        record = {"b": 1, "a": "é", "prev_hash": "0" * 64}
        self.assertEqual(record_hash(record), score.record_hash(record))

    def test_chain_verifies_and_a_tamper_breaks_it(self):
        log = AuditLog("S1-seed0")
        log.append({"phase": "T0", "type": "deliver", "inject_id": "S1-T0", "to_role": "ombudsperson"})
        log.append({"phase": "T0", "role": "ombudsperson", "actions": [], "guard_verdicts": []})
        self.assertEqual(log.records[0]["prev_hash"], GENESIS)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            log.write(directory)
            self.assertTrue(verify_chain(directory / "audit.jsonl")["ok"])
            lines = (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()
            rec = json.loads(lines[0])
            rec["phase"] = "T9"
            lines[0] = json.dumps(rec)
            (directory / "audit.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = verify_chain(directory / "audit.jsonl")
            self.assertFalse(result["ok"])
            self.assertEqual(result["breaks"][0]["reason"], "hash_mismatch")


if __name__ == "__main__":
    unittest.main()
