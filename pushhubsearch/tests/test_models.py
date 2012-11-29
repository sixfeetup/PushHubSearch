from unittest import TestCase

from pushhubsearch.models import SharedItem


class TestFeedTypeAssignment(TestCase):

    def test_add_to_shared(self):
        entry = {'feed_link': 'shared-content.xml'}
        item = SharedItem()
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 1)
        self.assertTrue('shared' in item.feed_type)

    def test_add_to_selected_not_shared(self):
        """A shared item shouldn't be selected if not shared"""
        item = SharedItem()
        entry = {'feed_link': 'atom-selected.xml'}
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 0)
        self.assertTrue('selected' not in item.feed_type)

    def test_add_to_deleted_not_shared(self):
        """Cannot delete items that aren't shared."""
        item = SharedItem()
        entry = {'feed_link': 'atom-deleted.xml'}
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 0)
        self.assertTrue('deleted' not in item.feed_type)

    def test_delete_shared_item(self):
        item = SharedItem()
        item.feed_type = ['shared']
        entry = {
            'feed_link': 'atom-deleted.xml',
            'push_deletion_type': 'shared'
        }
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 2)
        self.assertTrue('shared' in item.feed_type)
        self.assertTrue('deleted' in item.feed_type)

    def test_delete_shared_selected_item(self):
        item = SharedItem()
        item.feed_type = ['shared', 'selected']
        entry = {
            'feed_link': 'atom-deleted.xml',
            'push_deletion_type': 'selected'
        }
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 2)
        self.assertTrue('shared' in item.feed_type)
        self.assertTrue('deleted' in item.feed_type)

    def  test_deleted_item_reshared(self):
        item = SharedItem()
        item.feed_type = ['shared', 'deleted']
        entry = {'feed_link': 'shared-content.xml'}
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 1)
        self.assertTrue('shared' in item.feed_type)

    def test_delete_sharing_on_selected_item(self):
        item = SharedItem()
        item.feed_type = ['shared', 'selected']
        entry = {
            'feed_link': 'atom-deleted.xml',
            'push_deletion_type': 'featured',
        }
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 1)
        self.assertTrue('deleted' in item.feed_type)
