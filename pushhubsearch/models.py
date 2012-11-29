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


class SharedItem(Persistent):
    """An item shared to the CS Portal Pool
    """

    def __init__(self, Title='', portal_type='', Creator='', Modified=None,
                 url='', Description='', Subject=[], Category=None,
                 feed_type=None):
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


    def update_from_entry(self, entry):
        """Update the item based on the feed entry
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
        # Report what the current state of the item is
        for k, v in self.__dict__.items():
            logger.debug('%s: %s' % (k, v))

    def assign_feeds(self, feed_link='', push_deletion_type=''):
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
