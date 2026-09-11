"""
Tests for natural sort utilities (Issue #9 - batch name sorting).
"""
import pytest
from core.utils.natural_sort import natural_sort_key, natural_sort


class TestNaturalSortKey:
    """Test the natural_sort_key function."""

    def test_simple_numbers(self):
        """Test sorting simple numeric strings."""
        key_2a = natural_sort_key("2A")
        key_10a = natural_sort_key("10A")
        assert key_2a < key_10a, "2A should sort before 10A"

    def test_batch_names(self):
        """Test sorting batch names."""
        key_batch_1a = natural_sort_key("Batch 1A")
        key_batch_2a = natural_sort_key("Batch 2A")
        key_batch_10a = natural_sort_key("Batch 10A")

        assert key_batch_1a < key_batch_2a < key_batch_10a

    def test_mixed_numbers_and_letters(self):
        """Test sorting mixed alphanumeric strings."""
        key_class_1_primary = natural_sort_key("Class 1 Primary")
        key_class_2_primary = natural_sort_key("Class 2 Primary")
        key_class_10_primary = natural_sort_key("Class 10 Primary")

        assert key_class_1_primary < key_class_2_primary < key_class_10_primary

    def test_empty_string(self):
        """Test handling empty strings."""
        key_empty = natural_sort_key("")
        key_a = natural_sort_key("A")
        assert key_empty <= key_a

    def test_pure_numbers(self):
        """Test pure numeric strings."""
        keys = [natural_sort_key(str(i)) for i in [1, 10, 2, 20, 3]]
        sorted_keys = sorted(keys)
        # 1, 2, 3, 10, 20
        assert sorted_keys[0] == natural_sort_key("1")
        assert sorted_keys[1] == natural_sort_key("2")
        assert sorted_keys[2] == natural_sort_key("3")
        assert sorted_keys[3] == natural_sort_key("10")
        assert sorted_keys[4] == natural_sort_key("20")


class TestNaturalSort:
    """Test the natural_sort function."""

    def test_sort_batch_names(self):
        """Test sorting batch names."""
        batches = ["Batch 10A", "Batch 2A", "Batch 1A", "Batch 20A"]
        expected = ["Batch 1A", "Batch 2A", "Batch 10A", "Batch 20A"]
        result = natural_sort(batches)
        assert result == expected

    def test_sort_class_names(self):
        """Test sorting class names."""
        classes = ["Class 10", "Class 2", "Class 1", "Class 20"]
        expected = ["Class 1", "Class 2", "Class 10", "Class 20"]
        result = natural_sort(classes)
        assert result == expected

    def test_sort_with_key_function(self):
        """Test sorting with a key extraction function."""

        class Batch:
            def __init__(self, name):
                self.name = name

            def __repr__(self):
                return f"Batch({self.name})"

        batches = [
            Batch("Batch 10A"),
            Batch("Batch 2A"),
            Batch("Batch 1A"),
        ]
        result = natural_sort(batches, key=lambda b: b.name)
        names = [b.name for b in result]
        assert names == ["Batch 1A", "Batch 2A", "Batch 10A"]

    def test_sort_preserves_stability(self):
        """Test that equal items maintain their relative order."""
        items = ["A1", "B1", "A1", "C1"]
        result = natural_sort(items)
        # A1 items should maintain their relative order
        assert result == ["A1", "A1", "B1", "C1"]

    def test_case_insensitive(self):
        """Test that sorting is case-insensitive."""
        items = ["Batch A", "batch b", "BATCH C"]
        result = natural_sort(items)
        # Should sort by the lowercase version
        assert len(result) == 3
        assert all(isinstance(item, str) for item in result)

    def test_real_world_batch_scenario(self):
        """Test a real-world batch naming scenario."""
        batches = ["Grade 12A", "Grade 2A", "Grade 10A", "Grade 1A", "Grade 3A"]
        expected = ["Grade 1A", "Grade 2A", "Grade 3A", "Grade 10A", "Grade 12A"]
        result = natural_sort(batches)
        assert result == expected
