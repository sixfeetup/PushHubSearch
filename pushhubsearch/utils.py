def normalize_uid(uuid):
    if uuid.startswith('urn:syndication'):
        return uuid[16:]
    else:
        return uuid
