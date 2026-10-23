"""数据管线回归：公开数据、可选数据身份合并、显式目录和中文编码。"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_fork import build_data, norm

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def build(*paths):
    with contextlib.redirect_stdout(io.StringIO()):
        return build_data(*paths)[0]


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = build(*(str(DATA / name) for name in (
            "cueb_journal_catalog_2024.json", "cssci_2025_2026.json",
            "cscd_2025_2026.json", "utd24.json", "ft50.json", "ajg_2024.json")))

    def test_public_issn_preserves_catalog_tier(self):
        for name, issn, tier in (
            ("管理科学学报", "10079807", "中文A2"),
            ("计算机学报", "02544164", "中文A2"),
            ("地理学报", "03755444", "中文B1"),
            ("安全与环境学报", "10096094", "中文B1"),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.public["byIssn"][issn], tier)
                self.assertEqual(self.public["issnNames"][issn], norm(name))

    def test_optional_missing_is_normal(self):
        self.assertIsNone(self.public["ssci"])
        self.assertEqual(self.public["inSsci"], {})
        self.assertEqual(self.public["inJcr"], {})
        self.assertEqual(self.public["byName"][norm("经济研究")], "中文A1")

    def test_optional_alias_and_eissn_preserve_tier_and_membership(self):
        with tempfile.TemporaryDirectory(prefix="cueb-data-") as directory:
            folder = Path(directory)

            def save(name, content):
                path = folder / name
                path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
                return str(path)

            catalog = save("catalog.json", {
                "meta": {"effective_date": "2025-01-01"},
                "international": {"levels_order": ["A1"], "levels": {
                    "A1": {"disciplines": {"Test": {"journals": [
                        {"name": "The Fixture Review", "issn": "1111-1111"}
                    ]}}}}},
                "chinese": {"levels_order": ["A1"], "levels": {
                    "A1": {"journals": ["测试中文刊"]}}},
            })
            ssci = save("ssci.json", {"meta": {"title": "synthetic"}, "journals": [
                {"name": "Fixture Review", "issn": "1111-1111", "eissn": "2222-2222"},
                {"name": "New Fixture Journal", "issn": "3333-3333"},
            ]})
            jcr = save("jcr.json", {"meta": {"title": "synthetic"}, "journals": [
                {"name": "Fixture Review", "issn": "1111-1111", "best": "Q1"},
            ]})
            data = build(catalog, None, None, None, None, None, ssci, jcr)
            key = norm("The Fixture Review")
            self.assertEqual(data["byIssn"]["22222222"], "国际A1")
            self.assertEqual(data["byIssn"]["33333333"], "国际B2")
            self.assertEqual(data["canonicalByName"][norm("Fixture Review")], key)
            self.assertEqual(data["inSsci"][key], 1)
            self.assertEqual(data["inJcr"][key], "Q1")
            self.assertEqual(json.loads(json.dumps(data, ensure_ascii=False))["disp"][norm("测试中文刊")], "测试中文刊")

    def test_extra_data_directory_must_be_explicit(self):
        code = "import build_fork,json;print(json.dumps(build_fork._find_data('ssci_2026.json')))"
        with tempfile.TemporaryDirectory(prefix="cueb-path-") as directory:
            external = Path(directory) / "中文 数据"
            external.mkdir()
            dataset = external / "ssci_2026.json"
            dataset.write_text("{}", encoding="utf-8")
            env = os.environ.copy()
            env.pop("CUEB_DATA_DIR", None)
            env["PYTHONPATH"] = str(HERE)
            clean = subprocess.check_output([sys.executable, "-c", code], env=env, cwd=directory, text=True)
            self.assertEqual(Path(json.loads(clean)), DATA / "ssci_2026.json")
            env["CUEB_DATA_DIR"] = str(external)
            explicit = subprocess.check_output([sys.executable, "-c", code], env=env, cwd=directory, text=True)
            self.assertEqual(Path(json.loads(explicit)), dataset)


if __name__ == "__main__":
    unittest.main()
