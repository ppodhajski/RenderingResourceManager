#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0601
# pylint: disable=W0611

# Copyright (c) 2014-2015, Human Brain Project
#                          Cyrille Favreau <cyrille.favreau@epfl.ch>
#
# This file is part of RenderingResourceManager
# <https://github.com/BlueBrain/RenderingResourceManager>
#
# This library is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License version 3.0 as published
# by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# All rights reserved. Do not distribute without further notice.

"""
WSGI config for rendering_resource_manager_service project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/
"""

from django.core.wsgi import get_wsgi_application
from rendering_resource_manager_service.session.management \
    import session_manager
from rendering_resource_manager_service.session.management \
    import keep_alive_thread

from rendering_resource_manager_service.session.models import Session

application = get_wsgi_application()
# Start keep-alive thread
# pylint: disable=E1101

thread = keep_alive_thread.KeepAliveThread(Session.objects)
# This guaranties that the thread is destroyed when the main process ends
thread.setDaemon(True)
thread.start()
