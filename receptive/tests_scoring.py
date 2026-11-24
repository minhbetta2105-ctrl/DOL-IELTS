"""Offline scoring contract regression tests (can run with unittest or Django)."""
from decimal import Decimal
from unittest import TestCase
from receptive.services.scoring import reference_band_40, overall_reference, band_ranges, full_test_minutes, band_for_result

class ReferenceScoreTests(TestCase):
    def test_boundaries(self):
        for skill in ('READING','LISTENING'):
            for correct, expected in ((40,'9.0'),(39,'9.0'),(38,'8.5'),(35,'8.0'),(30,'7.0'),(23,'6.0')):
                self.assertEqual(reference_band_40(correct,skill),Decimal(expected))
            self.assertIsNone(reference_band_40(-1,skill))
            self.assertIsNone(reference_band_40(41,skill))
        self.assertEqual(reference_band_40(32,'READING'),Decimal('7.0'))
        self.assertEqual(reference_band_40(32,'LISTENING'),Decimal('7.5'))
        self.assertEqual(reference_band_40(4,'READING'), Decimal('2.5'))
        self.assertEqual(reference_band_40(9,'LISTENING'), Decimal('3.5'))
        self.assertEqual(reference_band_40(1,'LISTENING'), Decimal('1.0'))
    def test_overall(self):
        self.assertEqual(overall_reference([6.5,6.5,5,7]),Decimal('6.5'))
        self.assertEqual(overall_reference([6,6,6,6.5]),Decimal('6.0'))
        self.assertEqual(overall_reference([6,6,7,8]),Decimal('7.0'))
        self.assertIsNone(overall_reference([None,6,7,8]))
        self.assertIsNone(overall_reference([6.2,6,7,8]))
    def test_short_not_band(self):
        self.assertIsNone(band_for_result(5,5,"READING"))
        self.assertIsNone(band_for_result(32,40,"READING","PRACTICE"))
        self.assertIsNone(band_for_result(30,30,"LISTENING"))
        self.assertEqual(band_for_result(30,40,"LISTENING"),Decimal("7.0"))
    def test_timing(self):
        self.assertEqual(full_test_minutes('READING',40,20),60)
        self.assertEqual(full_test_minutes('LISTENING',40,20),30)
        self.assertEqual(full_test_minutes('READING',5,20),20)
