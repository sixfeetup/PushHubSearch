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

from pyramid.config import Configurator
from pyramid_zodbconn import get_connection
from .models import appmaker
from .views import UpdateItems
from .views import delete_items
from .views import update_deletions
from .views import listener
from .views import global_shared, global_selected, global_deleted


def root_factory(request):
    conn = get_connection(request)
    return appmaker(conn.root())


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application.
    """
    config = Configurator(root_factory=root_factory, settings=settings)

    config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_route('listener', '/listener')
    config.add_view(listener, route_name='listener')

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
