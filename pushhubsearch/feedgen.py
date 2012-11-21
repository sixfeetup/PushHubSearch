from webhelpers import feedgenerator


class Atom1Feed(feedgenerator.Atom1Feed):
    """Extend the atom1 generator"""

    def root_attributes(self):
        attrs = super(Atom1Feed, self).root_attributes()
        attrs['xmlns:push'] = 'http://ucla.edu/#portal-pool'
        return attrs

    def add_item_elements(self, handler, item):
        # Invoke this same method of the super-class to add the standard
        # elements to the 'item's.
        super(Atom1Feed, self).add_item_elements(handler, item)

        # Add a special category tag for the site title
        handler.addQuickElement(
            u"category",
            "",
            {u"term": item['category'],
             u"label": u"Site Title"}
        )

        # Add portal_type tag under the push namespace
        handler.addQuickElement("push:portal_type", item['portal_type'])
