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

from datetime import datetime
from persistent import Persistent
from persistent.mapping import PersistentMapping
from repoze.folder import Folder
import dateutil.parser
from dateutil.tz import tzutc

import logging
logger = logging.getLogger(__name__)


class Root(PersistentMapping):
    __parent__ = __name__ = None


class SharedItems(Folder):
    """A folder to hold the shared items
    """
    title = "Shared Items"

    def find_by_title(self, title):
        matches = [v for v in self.values() if v.Title == title]
        return matches


class SharedItem(Persistent):
    """An item shared to the CS Portal Pool
    """

    def __init__(self, Title='', portal_type='', Creator='', Modified=None,
                 url='', Description='', Subject=[], Category=None,
                 feed_type=None, tile_urls=[], deleted_tile_urls=[]):
        self.Title = Title
        self.portal_type = portal_type
        self.url = url
        self.Creator = Creator
        if Modified is None:
            self.Modified = datetime.utcnow()
        else:
            self.Modified = Modified
        self.Description = Description
        self.Subject = Subject
        self.Category = Category
        if feed_type is None:
            self.feed_type = []
        else:
            self.feed_type = feed_type
        self.tile_urls = tile_urls
        self.deleted_tile_urls = deleted_tile_urls

    def update_from_entry(self, entry):
        """Update the item based on the feed entry

        NOTE: If you add any new attributes to the entry, you must
              make sure that these are compatible with the Solr schema.
              If they are not, then you need to modify the
              _update_index method in views to remove the attr.
              Otherwise, Solr will return a 400 on indexing.
        """
        logger.debug('update_from_entry')
        if 'title' in entry:
            self.Title = entry['title']
        if 'push_portal_type' in entry:
            self.portal_type = entry['push_portal_type']
        if 'author' in entry:
            self.Creator = entry['author']
        if 'updated' in entry:
            mod_date = dateutil.parser.parse(entry['updated'])
            self.Modified = mod_date.astimezone(tzutc())
        if 'link' in entry:
            self.url = entry['link']
        if 'summary' in entry:
            self.Description = entry['summary']
        if 'tags' in entry:
            self.Subject = [
                i['term'] for i in entry['tags']
                if i.get('label', '') != 'Site Title']
        if 'category' in entry:
            cats = [
                i['term'] for i in entry['tags']
                if i.get('label', '') == 'Site Title']
            if cats:
                self.Category = cats[0]
        if 'feed_link' in entry:
            self.assign_feeds(**entry)
        if 'push_deletion_type' in entry:
            self.deletion_type = entry['push_deletion_type']
        if 'push_tile_urls' in entry:
            if len(self.feed_type) == 1 and 'deleted' in self.feed_type:
                # If the item was completely removed, reset the tile_urls
                previous_tile_urls = self.tile_urls
                self.tile_urls = []
            else:
                current_tiles = set(self.tile_urls)
                push_tile_urls = entry['push_tile_urls'].strip()
                if push_tile_urls:
                    parsed_tiles = set([
                        i.strip()
                        for i in push_tile_urls.split('|')
                    ])
                else:
                    parsed_tiles = set()
                # Clean up the deleted_tiles
                self.deleted_tile_urls = list(
                    set(self.deleted_tile_urls) - parsed_tiles)
                # return a union of the passed in and current values
                self.tile_urls = list(current_tiles | parsed_tiles)
        if 'push_deleted_tile_urls' in entry:
            if len(self.feed_type) == 1 and 'deleted' in self.feed_type:
                # If the item was completely removed, reset the
                # deleted_tile_urls to the previous set of selected
                # tiles.
                self.deleted_tile_urls = previous_tile_urls
            else:
                current_tiles = set(self.deleted_tile_urls)
                push_del_urls = entry['push_deleted_tile_urls'].strip()
                if push_del_urls:
                    parsed_tiles = set([
                        i.strip()
                        for i in push_del_urls.split('|')
                    ])
                else:
                    parsed_tiles = set()
                # Clean up tile_urls by removing the item that was deleted
                self.tile_urls = list(set(self.tile_urls) - parsed_tiles)
                # return a union of the passed in and current values
                self.deleted_tile_urls = list(current_tiles | parsed_tiles)
        # Report what the current state of the item is
        for k, v in self.__dict__.items():
            logger.debug('update entry: %s: %s' % (k, v))

    def assign_feeds(self, feed_link='', push_deletion_type='', **kwargs):
        not_del_msg = "feed_type is not 'deleted' adding '%s'"
        del_sel_msg = "feed_type is 'deleted' and 'selected'"
        del_other_msg = "feed_type is 'deleted' deletion type '%s'"
        if 'shared' in feed_link:
            logger.debug("init feed_type '%s'" % 'shared')
            if not self.feed_type:
                self.feed_type = ['shared', ]
            if 'shared' not in self.feed_type:
                self.feed_type.append('shared')
            if 'deleted' in self.feed_type:
                self.feed_type.remove('deleted')
        elif 'deleted' in feed_link:
            if 'shared' not in self.feed_type:
                logger.debug('tried to delete unshared item')
                return
            if push_deletion_type == 'selected':
                logger.debug(del_sel_msg)
                if 'selected' in self.feed_type:
                    self.feed_type.remove('selected')
                if 'deleted' not in self.feed_type:
                    self.feed_type.append('deleted')
            elif push_deletion_type == 'featured':
                logger.debug('unfeatured item')
                self.feed_type = ['deleted']
            else:
                logger.debug(del_other_msg % push_deletion_type)
                self.feed_type.append('deleted')
        elif 'selected' in feed_link:
            if 'shared' not in self.feed_type:
                logger.debug('tried to select unshared item')
                return
            if 'selected' not in self.feed_type:
                logger.debug(not_del_msg % 'selected')
                self.feed_type.append('selected')


def appmaker(zodb_root):
    if not 'app_root' in zodb_root:
        app_root = Root()
        zodb_root['app_root'] = app_root

        shared_items = SharedItems()
        app_root.shared = shared_items
        shared_items.__name__ = 'shared'
        shared_items.__parent__ = app_root

        import transaction
        transaction.commit()
    return zodb_root['app_root']
