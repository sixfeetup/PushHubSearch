from pyramid.config import Configurator
from pyramid_zodbconn import get_connection
from .models import appmaker
from .views import UpdateItems
from .views import delete_items
from .views import update_deletions
from .views import global_shared, global_selected, global_deleted


def root_factory(request):
    conn = get_connection(request)
    return appmaker(conn.root())


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application.
    """
    config = Configurator(root_factory=root_factory, settings=settings)

    config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_route('update', '/update')
    config.add_view(UpdateItems, route_name='update')

    config.add_route('update_deletions', '/update_deletions')
    config.add_view(update_deletions, route_name='update_deletions')

    config.add_route('delete', '/delete')
    config.add_view(delete_items, route_name='delete')

    config.add_route('shared', '/global-shared.xml')
    config.add_view(global_shared, route_name='shared')

    config.add_route('selected', '/global-selected.xml')
    config.add_view(global_selected, route_name='selected')

    config.add_route('deleted', 'global-deletions.xml')
    config.add_view(global_deleted, route_name='deleted')

    return config.make_wsgi_app()
