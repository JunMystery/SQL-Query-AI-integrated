import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlbot_desktop.infrastructure.few_shot_repository import FewShotRepository
from sqlbot_desktop.services.embedding_service import DeterministicEmbeddingModel
from sqlbot_desktop.agents.example_store import ExampleStore


class TestExampleStore(unittest.TestCase):
    """Verify ExampleStore load, save, embed, and select operations."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "few_shots.json"
        self.repository = FewShotRepository(self.file_path)
        self.store = ExampleStore(self.repository)
        self.emb_model = DeterministicEmbeddingModel(dimensions=8)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_and_select_example(self) -> None:
        self.store.add_example(
            question="Lấy toàn bộ người dùng",
            sql="SELECT * FROM users",
            dialect="sqlite",
            tags=["users", "select"],
            embedding_model=self.emb_model
        )

        examples = self.store.select_few_shots(
            question="hiển thị người dùng",
            dialect="sqlite",
            limit=1,
            embedding_model=self.emb_model
        )

        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].question, "Lấy toàn bộ người dùng")
        self.assertEqual(examples[0].sql, "SELECT * FROM users")
        self.assertTrue(len(examples[0].embedding) > 0)


if __name__ == "__main__":
    unittest.main()
