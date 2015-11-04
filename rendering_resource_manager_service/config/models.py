#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
This modules defines the data model for the rendering resource manager
"""

from django.db import models


class RenderingResourceSettings(models.Model):
    """
    Persistent Rendering Resource Settings
    """

    id = models.CharField(max_length=50, primary_key=True)
    command_line = models.CharField(max_length=1024)
    environment_variables = models.CharField(max_length=4096, default='')
    modules = models.CharField(max_length=4096, default='')
    process_rest_parameters_format = models.CharField(max_length=1024, default='')
    scheduler_rest_parameters_format = models.CharField(max_length=1024, default='')
    graceful_exit = models.BooleanField(default=True)

    class Meta(object):
        """
        A Meta object for the Settings
        """
        ordering = (
            'id', 'command_line',
            'environment_variables',
            'modules',
            'process_rest_parameters_format',
            'scheduler_rest_parameters_format',
            'graceful_exit')

    def __str__(self):
        return '%s' % self.id

    __unicode__ = __str__


class SystemGlobalSettings(models.Model):
    """
    Persistent Global Settings
    """

    id = models.IntegerField(primary_key=True, default=0)
    session_creation = models.BooleanField(default=True)
    session_keep_alive_timeout = models.IntegerField(default=1000)

    class Meta(object):
        """
        A Meta object for the Session
        """
        ordering = ('id', 'session_creation', 'session_keep_alive_timeout')

    def __str__(self):
        return '%s, %s' % (self.session_creation, self.session_keep_alive_timeout)

    __unicode__ = __str__
