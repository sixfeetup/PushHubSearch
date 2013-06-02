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
from pyramid import testing
from mock import patch
from pushhubsearch.models import Root
from pushhubsearch.models import SharedItems
from pushhubsearch.models import SharedItem
from pushhubsearch.views import delete_items
from pushhubsearch.views import combine_entries

XML_WRAPPER = """\
<?xml version="1.0" encoding="utf-8" ?>
<?xml-stylesheet href="atom.css" type="text/css"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:push="http://ucla.edu/#portal-pool"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xml:base="http://example.com"
      xml:lang="en">

  <link rel="hub" href="http://example.com/hub" />
  <link rel="self" href="http://example.com/deletions.xml" />
  <title type="html">Example Site</title>
  <updated>2012-08-29T16:53:34-04:00</updated>
  <link rel="alternate" type="text/html" href="http://example.com" />
  <id>urn:syndication:http://clyde-vm.local:51108/ucla</id>
  <generator uri="http://ucla.edu" version="1.0">ucla.pool</generator>

%s

</feed>"""
XML_ENTRY = """\
  <entry>
    <link rel="alternate" type="text/html" href="http://example.com/%s" />
    <id>urn:syndication:%s</id>
  </entry>"""


class FakeResponse(object):
    def __init__(self, documents=None):
        self.documents = documents

class FakeSolr(object):

    def __init__(self, solr_uri=None):
        self.solr_uri = solr_uri
        self.deleted = []
        self.catalog = {}

    def delete_by_key(self, key):
        self.deleted.append(key)

    def search(self, **kwargs):
        query = kwargs.get('q', None)
        if not query:
            return
        else:
            uid = query.split(':')[1]
            uid = uid.replace('"', '')
            docs = self.catalog.get(uid)
            new_docs = []
            for doc in docs:
                new_docs.append({'feed_type': doc.feed_type,
                                 'uid': uid
                                })
            return FakeResponse(documents=new_docs)

    def update(self, documents, **kwargs):
        pass


class TestDeletion(TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.registry.settings['push.solr_uri'] = 'foo'
        # Create an in-memory instance of the root
        self.root = Root()
        self.root.shared = SharedItems()

    def tearDown(self):
        testing.tearDown()
        self.root = None

    def test_bad_content_type(self):
        """If a content type other than RSS or Atom is passed in a
        BadRequest is raised
        """
        request = testing.DummyRequest(
            body='',
            content_type='text/plain')
        response = delete_items(self.root, request)
        self.assertEquals(response.code, 400)

    def test_nonexistent(self):
        """If the item doesn't exist, it will be reported in the body
        of the response.
        """
        feed_item = XML_ENTRY % ('foo', 1)
        feed = XML_WRAPPER % feed_item
        request = testing.DummyRequest(
            body=feed,
            content_type='application/atom+xml')
        patcher = patch('mysolr.Solr', FakeSolr)
        patcher.start()
        response = delete_items(self.root, request)
        patcher.stop()
        self.assertEquals(
            response.body,
            'Removed 0 items. 1 items could not be found for deletion: 1'
        )
        self.assertEquals(response.code, 200)

    def test_removal(self):
        """When an item is present in the feed, it will be deleted
        """
        obj = SharedItem()
        obj.__name__ = 'item_uid'
        obj.__parent__ = self.root.shared
        self.root.shared['item_uid'] = obj
        feed_item = XML_ENTRY % ('foo', 'item_uid')
        feed = XML_WRAPPER % feed_item
        request = testing.DummyRequest(
            body=feed,
            content_type='application/atom+xml')
        patcher = patch('mysolr.Solr', FakeSolr)
        patcher.start()
        response = delete_items(self.root, request)
        patcher.stop()
        self.assertEquals(response.body, 'Removed 1 items.')
        self.assertEquals(response.code, 200)
        self.failIf(self.root.shared.get('item_uid', False))

    def test_removal_multiple(self):
        """When multiple items are present in the feed, they will be
        deleted.
        """
        # Item 1
        obj_foo = SharedItem()
        self.root.shared['foo_uid'] = obj_foo
        # Item 2
        obj_bar = SharedItem()
        self.root.shared['bar_uid'] = obj_bar
        # Create the entries
        feed_items = []
        feed_items.append(XML_ENTRY % ('foo', 'foo_uid'))
        feed_items.append(XML_ENTRY % ('bar', 'bar_uid'))
        feed = XML_WRAPPER % "".join(feed_items)
        # Set up the request
        request = testing.DummyRequest(
            body=feed,
            content_type='application/atom+xml')
        patcher = patch('mysolr.Solr', FakeSolr)
        patcher.start()
        response = delete_items(self.root, request)
        patcher.stop()
        self.assertEquals(response.body, 'Removed 2 items.')
        self.assertEquals(response.code, 200)
        self.failIf(self.root.shared.get('foo_uid', False))
        self.failIf(self.root.shared.get('bar_uid', False))

    def test_removal_mixed(self):
        """When multiple items are present in the feed, but only some
        are present in the database.
        """
        # Item 1
        obj_foo = SharedItem()
        self.root.shared['foo_uid'] = obj_foo
        # Create the entries
        feed_items = []
        feed_items.append(XML_ENTRY % ('foo', 'foo_uid'))
        feed_items.append(XML_ENTRY % ('missing', 'missing_uid'))
        feed = XML_WRAPPER % "".join(feed_items)
        # Set up the request
        request = testing.DummyRequest(
            body=feed,
            content_type='application/atom+xml')
        patcher = patch('mysolr.Solr', FakeSolr)
        patcher.start()
        response = delete_items(self.root, request)
        patcher.stop()
        self.assertEquals(
            response.body,
            ('Removed 1 items. '
             '1 items could not be found for deletion: missing_uid'),
        )
        self.assertEquals(response.code, 200)
        self.failIf(self.root.shared.get('foo_uid', False))
        self.failIf(self.root.shared.get('bar_uid', False))


class TestCombineEntries(TestCase):

    def setUp(self):
        self.item1 = SharedItem()
        self.item1.feed_type = ['shared', 'deleted']
        self.item1.deletion_type = 'featured'
        self.item2 = SharedItem()
        self.item2.feed_type = ['shared', 'selected']
        self.item3 = SharedItem()
        self.item3.feed_type = ['shared', 'selected']
        self.item4 = SharedItem()
        self.item4.feed_type = ['shared', 'selected', 'deleted']
        self.item4.deletion_type = 'featured'

        self.container = {
            'item1': self.item1,
            'item2': self.item2,
            'item3': self.item3,
            'item4': self.item4,
        }

    def remove_deleted(self):
        del self.container['item1']
        del self.container['item4']

    def empty_container(self):
        self.container = {}

    def tearDown(self):
        self.item1 = self.item2 = self.item3 = self.item4 = None

    def test_shared_with_deleted_items(self):
        combined = combine_entries(self.container, 'shared')
        self.assertEqual(len(combined), 2)

    def test_selected_with_deleted_items(self):
        combined = combine_entries(self.container, 'selected')
        self.assertEqual(len(combined), 2)

    def test_deleted(self):
        combined = combine_entries(self.container, 'deleted')
        self.assertEqual(len(combined), 2)

    def test_shared_no_deleted_items(self):
        self.remove_deleted()
        combined = combine_entries(self.container, 'shared')
        self.assertEqual(len(combined), 2)

    def test_selected_no_deleted_items(self):
        self.remove_deleted()
        combined = combine_entries(self.container, 'selected')
        self.assertEqual(len(combined), 2)

    def test_no_shared(self):
        self.empty_container()
        combined = combine_entries(self.container, 'shared')
        self.assertEqual(len(combined), 0)

    def test_no_selected(self):
        self.empty_container()
        combined = combine_entries(self.container, 'selected')
        self.assertEqual(len(combined), 0)

    def test_shared_with_deleted_selection(self):
        self.item1.deletion_type = 'selected'
        combined = combine_entries(self.container, 'shared')
        self.assertEqual(len(combined), 3)
