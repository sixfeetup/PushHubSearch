def normalize_uid(uuid):
    if uuid.startswith('urn:syndication'):
        return uuid[16:]
    else:
        return uuid


def remove_deleted_status(uid, shared, solr):
    response = solr.search(**{'q': 'uid:"%s"' % (uid,)})

    # XXX: should we update the document or remove it?
    for document in response.documents:
        if 'deleted' in document['feed_type']:
            document['feed_type'].remove('deleted')

    # update index with modified documents
    solr.update(response.documents, commit=True)

    if uid in shared:
        if 'deleted' in shared[uid].feed_type:
            shared[uid].feed_type.remove('deleted')
            delattr(shared[uid], 'deletion_type')

    return True
