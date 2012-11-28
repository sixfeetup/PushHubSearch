from pushhub.utils import Atom1FeedKwargs


class Atom1Feed(Atom1FeedKwargs):
    """Extend the atom1 generator"""

    def root_attributes(self):
        attrs = super(Atom1Feed, self).root_attributes()
        attrs['xmlns:push'] = 'http://ucla.edu/#portal-pool'
        return attrs
