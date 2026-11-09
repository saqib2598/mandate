import unittest

from mandate.policy.citations import exact_quote, ground_citations, validate_claims


class CitationTests(unittest.TestCase):
    def test_keeps_a_quote_from_a_retrieved_chunk(self):
        text = "Providing a meaningful explanation to clients of how and why the decision was made in plain language."
        retrieved = {"c1": {"text": text}}
        raw = [{"text": "An explanation is required.", "citations": [{"chunk_id": "c1", "quote": exact_quote(text)}]}]
        kept = validate_claims(raw, retrieved)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["citations"][0]["chunk_id"], "c1")

    def test_strips_a_quote_from_a_chunk_that_was_not_retrieved(self):
        text = "Providing a meaningful explanation to clients of how and why the decision was made."
        raw = [{"text": "An explanation is required.", "citations": [{"chunk_id": "other", "quote": text}]}]
        self.assertEqual(validate_claims(raw, {"c1": {"text": text}}), [])

    def test_strips_a_short_quote_and_a_mismatch(self):
        text = "Providing a meaningful explanation to clients of how and why the decision was made today."
        retrieved = {"c1": {"text": text}}
        raw = [{
            "text": "Mixed.",
            "citations": [
                {"chunk_id": "c1", "quote": "too short"},
                {"chunk_id": "c1", "quote": "this sentence is long enough but it does not appear in the chunk at all"},
            ],
        }]
        self.assertEqual(validate_claims(raw, retrieved), [])

    def test_grounds_a_paraphrase_to_a_verbatim_span_of_the_named_chunk(self):
        text = "Providing a meaningful explanation to clients of how and why the decision was made today."
        raw = [{"text": "An explanation is due.", "citations": [{"chunk_id": "c1", "quote": "a loose paraphrase that is long enough to fail"}]}]
        grounded = ground_citations(raw, {"c1": {"text": text}})
        self.assertEqual(grounded[0]["citations"][0]["quote"], exact_quote(text))
        self.assertEqual(len(validate_claims(grounded, {"c1": {"text": text}})), 1)

    def test_drops_only_the_bad_citation(self):
        text = "Providing a meaningful explanation to clients of how and why the decision was made today."
        raw = [{
            "text": "Mixed.",
            "citations": [
                {"chunk_id": "c1", "quote": "meaningful explanation to clients of how and why"},
                {"chunk_id": "missing", "quote": "meaningful explanation to clients of how and why"},
            ],
        }]
        kept = validate_claims(raw, {"c1": {"text": text}})
        self.assertEqual(len(kept[0]["citations"]), 1)


if __name__ == "__main__":
    unittest.main()
