from unittest import TestCase

from pyramid import testing

from pushhubsearch.models import Root, SharedItems, SharedItem
from pushhubsearch.utils import remove_deleted_status
from .test_views import FakeSolr


class TestRemovalBase(TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.config.registry.settings['push.solr_uri'] = 'foo'
        self.root = Root()
        self.root.shared = SharedItems()
        item = SharedItem()
        uid = 'uuuuid'
        self.uid = uid
        item.__name__ = uid
        item.__parent__ = uid
        item.feed_type = ['selected', 'deleted']
        self.root.shared['uuuuid'] = item
        self.solr = FakeSolr()
        self.solr.catalog[uid] = [item]
        self.item = item

    def tearDown(self):
        testing.tearDown()
        self.root = None


class TestRemoveDeletedStatus(TestRemovalBase):
    def setUp(self):
        super(TestRemoveDeletedStatus, self).setUp()

    def test_remove_deleted(self):
        remove_deleted_status('uuuuid', self.root.shared, self.solr)
        self.assertTrue('deleted' not in self.item.feed_type)


class TestNotDeletedStatus(TestRemovalBase):
    def setUp(self):
        super(TestNotDeletedStatus, self).setUp()
        self.item.feed_type = ['shared', 'selected']
        self.solr.catalog[self.item.__name__][0].feed_type = self.item.feed_type

    def test_no_side_effects(self):
        remove_deleted_status('uuuuid', self.root.shared, self.solr)
        self.assertTrue('shared' in self.item.feed_type)
        self.assertTrue('selected' in self.item.feed_type)
