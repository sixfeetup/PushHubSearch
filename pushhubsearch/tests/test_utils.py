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
