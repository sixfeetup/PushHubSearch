from pyramid.httpexceptions import HTTPOk
from pyramid.httpexceptions import HTTPBadRequest
from feedparser import parse
from mysolr import Solr
from .models import SharedItem

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
        # XXX: configure the solr address via paster
        self.solr = Solr('http://localhost:55121/solr')
        self.shared = context.shared

    def __call__(self):
        # If the request isn't an RSS feed, bail out
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
        shared_content = parse(self.request.body)
        for item in shared_content.entries:
            item_id = item['id']
            uid = item_id.replace('urn:syndication:', '')
            item['uid'] = uid
            if uid in self.shared:
                self._update_item(item)
            else:
                self._create_item(item)

    def _create_item(self, entry):
        """Create new items in the feed
        """
        new_item = SharedItem()
        new_item.update_from_entry(entry)
        uid = entry['uid']
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
        obj = self.shared[entry['uid']]
        # XXX: these aren't coming from the object. Why is that? Is
        #      the `add` method on the folder not setting them?
        obj.__name__ = entry['uid']
        obj.__parent__ = self.shared
        del entry['uid']
        obj.update_from_entry(entry)
        self.to_index.append(obj)
        self.update_count += 1

    def _update_index(self):
        """Clean up the item dictionaries to contain only items that
        are valid and send them over to Solr for indexing.
        """
        cleaned = []
        for item in self.to_index:
            item_dict = item.__dict__
            item_dict['uid'] = item_dict['__name__']
            del item_dict['__name__']
            del item_dict['__parent__']
            cleaned.append(item_dict)
        self.solr.update(cleaned)


def delete_items(request):
    """Delete the given items from the index

    TODO: Implement me
    """
    return HTTPOk(body="Item removed")
