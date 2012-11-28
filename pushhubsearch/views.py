from datetime import datetime
import copy
import feedparser
from pyramid.httpexceptions import HTTPOk
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response
from pyramid.url import route_url
from .models import SharedItem
from .feedgen import Atom1Feed
from .utils import normalize_uid
from .utils import remove_deleted_status

import logging
logger = logging.getLogger(__name__)

# NOTE: the hub only supports atom at the moment
ALLOWED_CONTENT = (
    'application/atom+xml',
    'application/rss+xml',
)


class UpdateItems(object):
    """Create a new SharedItem or update it if it already exists.
    This will find all the entries, then create / update them. Then
    do a batch index to Solr.
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.create_count = 0
        self.update_count = 0
        self.messages = []
        self.to_index = []
        solr_uri = request.registry.settings.get('push.solr_uri', None)
        if solr_uri is None:
            raise AttributeError(u'A push.solr_uri is required')
        # XXX: We are importing solr here to be able to mock it in the tests
        from mysolr import Solr
        self.solr = Solr(solr_uri)
        self.shared = context.shared

    def __call__(self):
        #  If the request isn't an RSS feed, bail out
        if self.request.content_type not in ALLOWED_CONTENT:
            body_msg = (
                "The content-type of the request must be one of the "
                "following: %s"
            ) % ", ".join(ALLOWED_CONTENT)
            return HTTPBadRequest(body=body_msg)
        # Create / update
        self._process_items()
        # Index in Solr
        self._update_index()
        # Return a 200 with details on what happened in the body
        self.messages.append("%s items created." % self.create_count)
        self.messages.append("%s items updated." % self.update_count)
        return HTTPOk(body=" ".join(self.messages))

    def _process_items(self):
        """Get a list of new items to create and existing items that
        need to be updated.
        """
        shared_content = feedparser.parse(self.request.body)
        for item in shared_content.entries:
            uid = item['id']
            # Get the uid, minus the urn:syndication bit
            item['uid'] = uid = normalize_uid(uid)
            logger.info('Processing item %s' % uid)
            item['link'] = item.link
            item['feed_link'] = shared_content.feed.link
            if uid in self.shared:
                self._update_item(item)
            else:
                self._create_item(item)

    def _create_item(self, entry):
        """Create new items in the feed
        """
        new_item = SharedItem()
        uid = entry['uid']
        logger.info('Creating item %s' % uid)
        new_item.update_from_entry(entry)
        # XXX: Should name and parent be necessary here? Shouldn't
        #      the `add` method do that for us?
        new_item.__name__ = uid
        new_item.__parent__ = self.shared
        self.shared.add(uid, new_item)
        self.to_index.append(self.shared[uid])
        self.create_count += 1

    def _update_item(self, entry):
        """Update existing items in the db using their UID
        """
        uid = entry['uid']
        logger.info('Updating item %s' % uid)
        obj = self.shared[uid]
        # XXX: these aren't coming from the object. Why is that? Is
        #      the `add` method on the folder not setting them?
        obj.__name__ = uid
        obj.__parent__ = self.shared
        if (('selected' in entry['feed_link'] or 'shared' in entry['feed_link'])
                and hasattr(obj, 'deletion_type')):
            remove_deleted_status(entry['uid'],
                                  self.shared,
                                  self.solr)
        obj.update_from_entry(entry)
        self.to_index.append(obj)
        self.update_count += 1

    def _update_index(self):
        """Clean up the item dictionaries to contain only items that
        are valid and send them over to Solr for indexing.
        """
        logger.debug('Updating index for %s objects' % len(self.to_index))
        cleaned = []
        for item in self.to_index:
            item_dict = copy.deepcopy(item.__dict__)
            if 'Modified' in item_dict:
                if hasattr(item_dict['Modified'], 'isoformat'):
                    mod_date = item_dict['Modified'].isoformat()
                else:
                    mod_date = item_dict['Modified']
                # Make sure the date is acceptable to Solr, strip off
                # the +00:00 and replace it with a Z
                item_dict['Modified'] = "%sZ" % mod_date[:-6]
            item_dict['uid'] = item_dict['__name__']
            del item_dict['__name__']
            del item_dict['__parent__']
            cleaned.append(item_dict)
        # XXX: Need to handle Solr errors here
        response = self.solr.update(cleaned)
        return response


def update_deletions(context, request):
    """Receive a UID from the request vars and remove the associated
    object from the deleted feed.
    """
    uid = request.POST.get('uid')
    if not uid:
        return
    solr_uri = request.registry.settings.get('push.solr_uri', None)
    if solr_uri is None:
        raise AttributeError(u'A push.solr_uri is required')
    from mysolr import Solr
    solr = Solr(solr_uri)
    logger.debug('Remove deleted status')
    remove_deleted_status(uid, context.shared, solr)
    return HTTPOk(body="Item no longer marked as deleted")


def delete_items(context, request):
    """Delete the given items from the index
    """
    # If the request isn't an RSS feed, bail out
    if request.content_type not in ALLOWED_CONTENT:
        body_msg = (
            "The content-type of the request must be one of the "
            "following: %s"
        ) % ", ".join(ALLOWED_CONTENT)
        return HTTPBadRequest(body=body_msg)
    solr_uri = request.registry.settings.get('push.solr_uri', None)
    if solr_uri is None:
        raise AttributeError(u'A push.solr_uri is required')
    # XXX: We are importing solr here to be able to mock it in the tests
    from mysolr import Solr
    solr = Solr(solr_uri)
    shared_content = feedparser.parse(request.body)
    missing = []
    removed = 0
    for item in shared_content.entries:
        uid = item['id']
        uid = normalize_uid(uid)
        logger.debug('Deleting %s' % uid)
        if uid not in context.shared:
            missing.append(uid)
            solr.delete_by_key(uid)
            continue
        del context.shared[uid]
        solr.delete_by_key(uid)
        removed += 1
    body_msg = "Removed %s items." % removed
    if missing:
        msg_str = " %s items could not be found for deletion: %s"
        args = (len(missing), ', '.join(missing))
        msg = msg_str % args
        logger.warn(msg)
        body_msg += msg
    return HTTPOk(body=body_msg)


def not_deleted(feed_name, types):
    return feed_name in types and 'deleted' not in types


def combine_entries(container, feed_name):
    """Combines all feeds of a given type (e.g. Shared, Selected)
    """
    logger.debug('Combining entries for %s' % feed_name)
    if feed_name == 'deleted':
        results = [entry for entry in container.values()
                   if feed_name in entry.feed_type]
    else:
        results = [entry for entry in container.values()
                   if not_deleted(feed_name, entry.feed_type)]
    results.sort(key=lambda x: x.Modified, reverse=True)
    return results


def create_feed(entries, title, link, description):
    """Combine the entries into an actual Atom feed."""
    new_feed = Atom1Feed(
        title=title,
        link=link,
        description=description,
    )
    for entry in entries:
        data = dict(
            pubdate=entry.Modified,
            unique_id=entry.__name__,
            categories=entry.Subject,
            category=entry.Category,
            portal_type=entry.portal_type
        )
        if hasattr(entry, 'deletion_type'):
            data['deletion_type'] = entry.deletion_type
        new_feed.add_item(
            entry.Title,
            entry.url,
            entry.Description,
            **data
        )
    return new_feed.writeString('utf-8')


def global_shared(context, request):
    entries = combine_entries(context.shared, 'shared')
    return Response(create_feed(entries,
                       'All Shared Entries',
                       route_url('shared', request),
                       'A combined feed of all entries shared to the PuSH Hub.'
    ))


def global_selected(context, request):
    entries = combine_entries(context.shared, 'selected')
    return Response(create_feed(entries,
                       'All Selected Entries',
                       route_url('selected', request),
                       'A combined feed of all entries selected across '
                       'the PuSH Hub.'
    ))


def global_deleted(context, request):
    entries = combine_entries(context.shared, 'deleted')
    return Response(create_feed(entries,
                       'All Deleted Entries',
                       route_url('deleted', request),
                       'A combined feed of all entries that were deleted '
                       ' across the PuSH Hub.'
    ))
