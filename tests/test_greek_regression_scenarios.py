import unittest

from app.alignment import align_reference
from app.services.greek_morphology_service import get_greek_tokens
from app.services.greek_text_service import get_greek_text
from app.services.textual_apparatus_service import get_apparatus_notes


SCENARIOS = ("MAT 1:1", "JHN 1:1", "JHN 3:16", "JHN 8:32", "ROM 8:1", "1CO 13:4", "REV 22:21")


class GreekRegressionScenarioTests(unittest.TestCase):
    def test_representative_references_keep_layers_separate(self):
        for reference in SCENARIOS:
            with self.subTest(reference=reference):
                text = get_greek_text(reference)
                self.assertEqual(text["source_status"], "available")
                self.assertTrue(text["items"][0]["text"])
                self.assertEqual(text["items"][0]["source"]["name"], "SBLGNT")

                morphology = get_greek_tokens(reference)
                self.assertIn(morphology["source_status"], {"available", "unavailable_in_source"})
                if morphology["source_status"] == "available":
                    self.assertTrue(morphology["tokens"])
                    self.assertEqual(morphology["tokens"][0]["source"]["name"], "MorphGNT SBLGNT")

                apparatus = get_apparatus_notes(reference)
                self.assertIn(apparatus["source_status"], {"available", "no_variants_recorded", "not_imported"})
                alignment = align_reference(reference)
                self.assertIn(alignment["status"], {"MATCHED", "NORMALIZATION_ONLY", "TEXT_DIFFERENCE", "TOKENIZATION_DIFFERENCE", "UNRESOLVED"})

    def test_lemma_search_scenario(self):
        result = get_greek_tokens("JHN 3:16")
        self.assertTrue(any(token["lemma"] == "ἀγαπάω" for token in result["tokens"]))
