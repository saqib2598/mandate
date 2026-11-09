import unittest

from mandate.match import best_window_ratio


class MatchTests(unittest.TestCase):
    def test_whitespace_and_case_are_exact(self):
        text = "An automated decision must be subject to meaningful human review before it takes effect."
        self.assertEqual(best_window_ratio("MUST be  subject to\nmeaningful HUMAN review", text), 1.0)

    def test_near_match_clears_the_threshold(self):
        text = "An automated decision must be subject to meaningful human review before it takes effect."
        self.assertGreaterEqual(best_window_ratio("must be subject to meaningfull human review", text), 0.9)

    def test_unrelated_quote_stays_below_the_threshold(self):
        text = "An automated decision must be subject to meaningful human review before it takes effect."
        self.assertLess(best_window_ratio("may waive human review whenever convenient", text), 0.9)

    def test_agrees_with_the_vendored_matcher(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
        import fuzzy_match

        text = "The data subject shall have the right not to be subject to a decision based solely on automated processing."
        quote = "right not to be subject to a decision based solely"
        self.assertEqual(best_window_ratio(quote, text), fuzzy_match.best_window_ratio(quote, text))


if __name__ == "__main__":
    unittest.main()
