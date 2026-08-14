import unittest

from nexus.scripts.run_commit_analysis import commit_subject


class CommitSubjectTests(unittest.TestCase):
    def test_strips_leading_sha_from_git_oneline(self) -> None:
        self.assertEqual(
            commit_subject("72a30cd feat: migrate Commit Analyzer"),
            "feat: migrate Commit Analyzer",
        )

    def test_leaves_sha_only_line_unchanged(self) -> None:
        self.assertEqual(commit_subject("72a30cd"), "72a30cd")


if __name__ == "__main__":
    unittest.main()
