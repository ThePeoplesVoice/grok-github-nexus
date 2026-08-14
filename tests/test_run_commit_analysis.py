import unittest

from nexus.scripts.run_commit_analysis import commit_subject, local_analysis


class CommitAnalysisFormattingTests(unittest.TestCase):
    def test_commit_subject_strips_leading_sha(self) -> None:
        self.assertEqual(
            commit_subject("8af4732 Merge pull request #12 from branch"),
            "Merge pull request #12 from branch",
        )

    def test_commit_subject_handles_subject_without_sha(self) -> None:
        self.assertEqual(commit_subject("Initial plan"), "Initial plan")

    def test_local_analysis_uses_subject_without_duplicate_sha(self) -> None:
        report = local_analysis([
            {
                "sha": "8af4732",
                "oneline": "8af4732 Merge pull request #12 from branch",
                "details": " file.txt | 1 +\n 1 file changed, 1 insertion(+)\n",
            }
        ])
        self.assertIn("#### `8af4732` — Merge pull request #12 from branch", report)


if __name__ == "__main__":
    unittest.main()
