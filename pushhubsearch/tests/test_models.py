from unittest import TestCase

from pushhubsearch.models import SharedItem


class TestFeedTypeAssignment(TestCase):

    def test_add_to_shared(self):
        entry = {'feed_link': 'shared-content.xml'}
        item = SharedItem()
        item.update_from_entry(entry)
        self.assertEqual(len(item.feed_type), 1)
        self.assertTrue('shared' in item.feed_type)

    def test_add_to_selected_not_shared(self):
        """A shared item should only be allowed to be in selected if
        already shared."""
        item = SharedItem()
        entry = {'feed_link': 'atom-selected.xml'}
        item.update_from_entry(entry)
        self.assertEqual(len(item.feed_type), 0)
        self.assertTrue('selected' not in item.feed_type)
