import unittest

from nexus.scripts.run_commit_analysis import commit_subject, local_analysis


class CommitAnalysisFormattingTests(unittest.TestCase):
    def test_commit_subject_strips_leading_sha(self) -> None:
        self.assertEqual(
            commit_subject("fdd03e2 Link progressive.json to usage_stats", "fdd03e2"),
            "Link progressive.json to usage_stats",
        )

    def test_commit_subject_falls_back_to_sha_when_subject_missing(self) -> None:
        self.assertEqual(commit_subject("fdd03e2", "fdd03e2"), "fdd03e2")

    def test_local_analysis_uses_subject_without_duplication(self) -> None:
        output = local_analysis(
            [
                {
                    "sha": "fdd03e2",
                    "oneline": "fdd03e2 Link progressive.json to usage_stats",
                    "details": " config/progressive.json | 9 +++++----\n 1 file changed, 5 insertions(+), 4 deletions(-)\n",
                }
            ]
        )
        self.assertIn("#### `fdd03e2` — Link progressive.json to usage_stats", output)
        self.assertNotIn("#### `fdd03e2` — fdd03e2 Link progressive.json to usage_stats", output)


if __name__ == "__main__":
    unittest.main()
