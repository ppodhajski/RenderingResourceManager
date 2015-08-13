#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0403
# pylint: disable=E1101
# pylint: disable=R0901

"""
This modules defines the data structure used by the rendering resource manager to manager
user sessions
"""
from rest_framework import serializers, viewsets
from django.http import HttpResponse
from models import RenderingResourceSettings
from rendering_resource_manager_service.config.management import \
    rendering_resource_settings_manager


class RenderingResourceSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer to default view (No parameters)
    """
    def __len__(self):
        pass

    def __getitem__(self, item):
        pass

    class Meta(object):
        """
        Meta class for the Command Serializer
        """
        model = RenderingResourceSettings
        fields = ('id', 'command_line',
                  'environment_variables',
                  'process_rest_parameters_format',
                  'scheduler_rest_parameters_format',
                  'graceful_exit')


class RenderingResourceSettingsDetailsViewSet(viewsets.ModelViewSet):
    """
    ViewSets define the default view behavior
    """

    queryset = RenderingResourceSettings.objects.all()
    serializer_class = RenderingResourceSettingsSerializer

    @classmethod
    # pylint: disable=W0613
    def delete(cls, request, settings_id):
        """
        Removes the config for a new rendering resource
        :param request The REST request
        :param settings_id Identifier of the Rendering resource config to remove
        :rtype A Json response containing on ok status or a description of the error
        """
        manager = rendering_resource_settings_manager.RenderingResourceSettingsManager()
        response = manager.delete(settings_id)
        return HttpResponse(status=response[0], content=response[1])


class RenderingResourceSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSets define the default view behavior
    """

    queryset = RenderingResourceSettings.objects.all()
    serializer_class = RenderingResourceSettingsSerializer

    @classmethod
    def create(cls, request):
        """
        Adds the config for a new rendering resource
        :param request The REST request
        :rtype A Json response containing on ok status or a description of the error
        """
        parameters = request.DATA
        manager = rendering_resource_settings_manager.RenderingResourceSettingsManager()
        response = manager.create(parameters)
        return HttpResponse(status=response[0], content=response[1])

    @classmethod
    def update(cls, request):
        """
        Updates the config for a new rendering resource
        :param request The REST request
        :rtype A Json response containing on ok status or a description of the error
        """
        parameters = request.DATA
        manager = rendering_resource_settings_manager.RenderingResourceSettingsManager()
        response = manager.update(parameters)
        return HttpResponse(status=response[0], content=response[1])

    @classmethod
    def list(cls, request):
        """
        Lists the config for a new rendering resource
        :param request The REST request
        :rtype A Json response containing on ok status or a description of the error
        """
        manager = rendering_resource_settings_manager.RenderingResourceSettingsManager()
        return HttpResponse(status=200,
                            content=manager.list(cls.serializer_class))