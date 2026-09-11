"""
Natural sorting utilities for handling numeric and string mixed names.

Converts batch names like "10A" to sort after "2A" (natural order)
instead of before (lexicographic order).
"""
import re
from typing import Any, Tuple, List


def natural_sort_key(text: str) -> Tuple[Any, ...]:
    """
    Convert a string into a tuple of (type_flag, value) pairs for natural sorting.

    Example:
        >>> natural_sort_key("Batch 10A")
        ((0, 'batch '), (1, 10), (0, 'a'))

        >>> natural_sort_key("Batch 2A")
        ((0, 'batch '), (1, 2), (0, 'a'))

    This ensures "Batch 2A" sorts before "Batch 10A".
    Type flags (0 for str, 1 for int) ensure comparable tuples.

    Args:
        text: The string to convert (e.g., batch name)

    Returns:
        A tuple of (type_flag, value) pairs suitable for sorting.
    """
    # Split on digit boundaries, keeping the delimiters
    parts = re.split(r'(\d+)', text)

    result = []
    for part in parts:
        if not part:  # Skip empty parts
            continue
        if part.isdigit():
            # Use type flag 1 for integers
            result.append((1, int(part)))
        else:
            # Use type flag 0 for strings, lowercase for case-insensitive sorting
            result.append((0, part.lower()))

    return tuple(result) if result else ((0, ''),)


def natural_sort(items: List[Any], key=None) -> List[Any]:
    """
    Sort items using natural sort order.

    Args:
        items: List of items to sort
        key: Optional function to extract sortable text from each item.
             If None, items are assumed to be strings.

    Returns:
        Sorted list using natural sort order.

    Example:
        >>> batches = ['Batch 10A', 'Batch 2A', 'Batch 1A']
        >>> natural_sort(batches)
        ['Batch 1A', 'Batch 2A', 'Batch 10A']
    """
    if key is None:
        key = lambda x: x
    return sorted(items, key=lambda x: natural_sort_key(key(x)))
