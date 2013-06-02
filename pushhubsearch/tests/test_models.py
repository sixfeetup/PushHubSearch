"""
Copyright (c) 2013, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  * Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

  * Neither the name of the University of California nor the names of its
    contributors may be used to endorse or promote products derived from this
    software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from unittest import TestCase
from mock import Mock

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

    def test_unused_keyword_args(self):
        item = SharedItem()
        entry = {
            'feed_link': 'shared-content.xml',
            'updated': None,
            'foo': 'bar'
        }
        item.assign_feeds(**entry)
        self.assertEqual(len(item.feed_type), 1)


class TestEntryUpdateCallsAssignment(TestCase):

    def test_update_items_calling_assignment(self):
        item = SharedItem()
        item.assign_feeds = Mock()
        entry = {
            'title': 'Test',
            'feed_link': 'shared-content.xml'
        }
        item.update_from_entry(entry)
        self.assertTrue(item.assign_feeds.called)
        item.assign_feeds.assert_called_with(
            feed_link='shared-content.xml',
            title='Test'
        )
