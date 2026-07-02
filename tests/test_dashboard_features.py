from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import matplotlib
import pandas as pd

matplotlib.use("Agg")

from analysis.charts import diet_comparison_stacked_bar, fish_rate_box
from analysis.core import AnalysisResults, filter_analysis_results
from scripts.clean_data import (
    CleanedTables,
    clean_all_workbooks,
    detect_provisioning_sheet,
    normalize_prey_name,
    read_workbook_sheet,
)


def sample_cleaned(year: int, species: str) -> CleanedTables:
    stints = pd.DataFrame(
        {
            "session_id": [1],
            "session_key": ["session"],
            "stint_id": ["ST00001"],
            "year": [year],
            "species": [species],
            "valid_observation_duration": [True],
            "prey_deliveries_per_hour": [2.0],
        }
    )
    deliveries = pd.DataFrame(
        {
            "delivery_id": ["DL00001"],
            "session_id": [1],
            "session_key": ["session"],
            "stint_id": ["ST00001"],
            "year": [year],
            "species": [species],
            "prey_species": ["Ammodytes"],
        }
    )
    return CleanedTables(
        stints=stints,
        deliveries=deliveries,
        records_with_zeros=deliveries.copy(),
        metadata=pd.DataFrame({"field": ["prey2"]}),
        telemetry=pd.DataFrame({"year": [year], "species": [species]}),
        quality={"observation_stints": 1},
    )


class PreyNormalizationTests(unittest.TestCase):
    def test_known_and_combined_labels(self):
        expected = {
            " a ": "Ammodytes",
            "H": "Herring",
            "ba": "Bay Anchovy",
            "bu": "Butterfish",
            "S": "Silversides",
            "m": "Mackerel",
            "U": "Unknown",
            "unknown": "Unknown",
            "O": "Other",
            "other": "Other",
        }
        for raw, label in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_prey_name(raw), label)

    def test_unrecognized_label_is_preserved(self):
        self.assertEqual(normalize_prey_name("Squid"), "Squid")

    def test_blank_prey2_is_unknown_instead_of_prey1_code(self):
        self.assertEqual(normalize_prey_name(pd.NA), "Unknown")


class MultiWorkbookTests(unittest.TestCase):
    @patch("scripts.clean_data.clean_all")
    def test_source_ids_are_unique(self, clean_all_mock):
        clean_all_mock.side_effect = [
            sample_cleaned(2024, "ROST"),
            sample_cleaned(2025, "ROST"),
        ]
        combined = clean_all_workbooks(
            [Path("2024.xlsx"), Path("2025.xlsx")],
            Path("metadata.csv"),
        )
        self.assertEqual(combined.stints["stint_id"].nunique(), 2)
        self.assertEqual(combined.deliveries["delivery_id"].nunique(), 2)
        self.assertEqual(
            combined.stints["source_workbook"].tolist(),
            ["2024.xlsx", "2025.xlsx"],
        )


class SheetDetectionTests(unittest.TestCase):
    columns = [
        "DATE",
        "SPECIES",
        "BLIND",
        "TIME START",
        "TIME STOP",
        "TIME OF DELIVERY",
        "NEST #",
        "PREY1",
        "PREY2",
        "OBSERVER",
        "NEST1 #",
    ]

    def test_detects_arbitrary_sheet_name_and_late_header(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "historical.xlsx"
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame([["Annual provisioning records"]]).to_excel(
                    writer,
                    sheet_name="2022 Observations",
                    index=False,
                    header=False,
                )
                pd.DataFrame(columns=self.columns).to_excel(
                    writer,
                    sheet_name="2022 Observations",
                    index=False,
                    startrow=3,
                )
                pd.DataFrame({"note": ["not raw data"]}).to_excel(
                    writer,
                    sheet_name="Read Me",
                    index=False,
                )
            detected = detect_provisioning_sheet(path)
            self.assertIsNotNone(detected.recommended)
            self.assertEqual(detected.recommended.sheet_name, "2022 Observations")
            self.assertEqual(detected.recommended.header_row, 3)
            selected = read_workbook_sheet(path, "2022 Observations", 3)
            self.assertIn("time_of_delivery", selected.columns)

    def test_equal_candidates_are_marked_ambiguous(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.xlsx"
            with pd.ExcelWriter(path) as writer:
                for sheet in ["Raw Data", "Backup"]:
                    pd.DataFrame(columns=self.columns).to_excel(
                        writer,
                        sheet_name=sheet,
                        index=False,
                    )
            detected = detect_provisioning_sheet(path)
            self.assertTrue(detected.ambiguous)
            self.assertEqual(len(detected.valid_candidates), 2)

    def test_invalid_workbook_reports_closest_candidate(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.xlsx"
            incomplete = [column for column in self.columns if column != "PREY2"]
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame(columns=incomplete).to_excel(
                    writer,
                    sheet_name="Field Records",
                    index=False,
                )
            detected = detect_provisioning_sheet(path)
            self.assertIsNone(detected.recommended)
            self.assertEqual(detected.candidates[0].missing_required, ("prey2",))


class FilteringAndChartTests(unittest.TestCase):
    def test_filter_applies_to_cleaned_data_and_tables(self):
        first = sample_cleaned(2024, "ROST")
        second = sample_cleaned(2025, "COTE")
        cleaned = CleanedTables(
            stints=pd.concat([first.stints, second.stints], ignore_index=True),
            deliveries=pd.concat([first.deliveries, second.deliveries], ignore_index=True),
            records_with_zeros=pd.concat(
                [first.records_with_zeros, second.records_with_zeros],
                ignore_index=True,
            ),
            metadata=first.metadata,
            telemetry=pd.concat([first.telemetry, second.telemetry], ignore_index=True),
            quality={},
        )
        summary = cleaned.stints[["year", "species"]].copy()
        summary["mean"] = [2.0, 3.0]
        filtered = filter_analysis_results(
            AnalysisResults(cleaned, {"summary": summary}),
            years=[2025],
            species=["COTE"],
        )
        self.assertEqual(filtered.cleaned.stints["year"].tolist(), [2025])
        self.assertEqual(filtered.tables["summary"]["species"].tolist(), ["COTE"])

    def test_stacked_diet_comparison_has_two_percentage_panels(self):
        all_summary = pd.DataFrame(
            {
                "year": [2025, 2025, 2025, 2025],
                "species": ["COTE", "COTE", "ROST", "ROST"],
                "prey_species": ["Ammodytes", "Unknown", "Ammodytes", "Unknown"],
                "diet_percent": [70.0, 30.0, 80.0, 20.0],
            }
        )
        identified = all_summary[all_summary["prey_species"] == "Ammodytes"].copy()
        identified["diet_percent"] = 100.0
        figure = diet_comparison_stacked_bar(all_summary, identified)
        self.assertEqual(len(figure.axes), 2)
        self.assertEqual(tuple(figure.axes[0].get_ylim()), (0.0, 100.0))
        self.assertEqual(
            [tick.get_text() for tick in figure.axes[0].get_xticklabels()],
            ["COTE", "ROST"],
        )
        self.assertTrue(figure.legends)

    def test_fish_boxplot_contains_both_metrics(self):
        rates = pd.DataFrame(
            {
                "year": [2025, 2025, 2025, 2025],
                "species": ["ROST"] * 4,
                "metric_name": [
                    "fish_deliveries_per_hour",
                    "fish_deliveries_per_hour",
                    "fish_deliveries_per_chick_hour",
                    "fish_deliveries_per_chick_hour",
                ],
                "metric_value": [1.0, 2.0, 0.5, 1.0],
            }
        )
        figure = fish_rate_box(rates)
        labels = [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
        self.assertEqual(len(labels), 2)


if __name__ == "__main__":
    unittest.main()
