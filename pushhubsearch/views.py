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
        selected_or_shared = (
            'selected' in entry['feed_link'] or
            'shared' in entry['feed_link']
        )
        if selected_or_shared and hasattr(obj, 'deletion_type'):
            remove_deleted_status(uid, self.shared, self.solr)
        obj.update_from_entry(entry)
        self.to_index.append(obj)
        self.update_count += 1

    def _update_index(self):
        """Clean up the item dictionaries to contain only items that
        are valid and send them over to Solr for indexing.

        NOTE: Solr may error out on index if it receives a field it is
              not aware of. We should change this code to look up the
              Solr schema, and remove attributes that it doesn't know,
              like __name__ and __parent__ below.
        """
        logger.debug('Updating index for %s objects' % len(self.to_index))
        cleaned = []
        ignored_attrs = [
            '__name__',
            '__parent__',
            'deletion_type',
        ]
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
            if 'content' in item_dict:
                item_dict['content'] = [
                    item['value'] for item in item_dict['content']]
            item_dict['uid'] = item_dict['__name__']
            # XXX: Need to look up the schema, then modify the dict
            #      based on that.
            for attr in ignored_attrs:
                item_dict.pop(attr, '')
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


def combine_entries(container, feed_name):
    """Combines all feeds of a given type (e.g. Shared, Selected)
    """
    logger.debug('Combining entries for %s' % feed_name)
    if feed_name == 'deleted':
        results = [entry for entry in container.values()
                   if feed_name in entry.feed_type]
    else:
        results = []
        for entry in container.values():
            feed_type = entry.feed_type
            feed_match = feed_name in feed_type
            feature_del = (
                'deleted' in feed_type and
                entry.deletion_type == 'featured'
            )
            if not feed_match or (feed_match and feature_del):
                continue
            results.append(entry)
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
            category={'term': entry.Category, 'label': u'Site Title'},
            author_name=entry.Creator,
        )
        data['push:portal_type'] = entry.portal_type
        # Tile urls are added into one element for now
        data['push:tile_urls'] = '|'.join(entry.tile_urls).lstrip('|')
        data['push:deleted_tile_urls'] = '|'.join(
            entry.deleted_tile_urls).lstrip('|')
        if getattr(entry, 'content', None):
            data['content'] = entry.content
        if hasattr(entry, 'deletion_type'):
            data['push:deletion_type'] = entry.deletion_type
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
