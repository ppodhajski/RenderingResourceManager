#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=E1101
# pylint: disable=W0403

"""
This class is in charge of handling rendering resources config, such as the
application name, executable name and command line parameters,
and ensures persistent storage in a database
"""

from rendering_resource_manager_service.config.models import RenderingResourceSettings
import rendering_resource_manager_service.utils.custom_logging as log
from django.db import IntegrityError, transaction
from rest_framework.renderers import JSONRenderer


class RenderingResourceSettingsManager(object):
    """
    This class is in charge of handling session and ensures persistent storage in a database
    """

    @classmethod
    def create(cls, params):
        """
        Creates new rendering resource config
        :param params Settings for the new rendering resource
        """
        try:
            settings_id = params['id']
            settings = RenderingResourceSettings(
                id=settings_id,
                command_line=str(params['command_line']),
                environment_variables=str(params['environment_variables']),
                process_rest_parameters_format=str(params['process_rest_parameters_format']),
                scheduler_rest_parameters_format=str(params['scheduler_rest_parameters_format']),
                graceful_exit=params['graceful_exit'])
            with transaction.atomic():
                settings.save(force_insert=True)
            msg = 'Rendering Resource ' + settings_id + ' successfully configured'
            log.debug(1, msg)
            return [201, msg]
        except IntegrityError as e:
            log.error(str(e))
            return [409, str(e)]

    @classmethod
    def update(cls, params):
        """
        Updates some given rendering resource config
        :param params new config for the rendering resource
        """
        try:
            settings_id = str(params['id'])
            settings = RenderingResourceSettings.objects.get(id=settings_id)
            settings.command_line = str(params['command_line'])
            settings.environment_variables = str(params['environment_variables'])
            settings.process_rest_parameters_format = \
                str(params['process_rest_parameters_format'])
            settings.scheduler_rest_parameters_format = \
                str(params['scheduler_rest_parameters_format'])
            settings.graceful_exit = params['graceful_exit']
            with transaction.atomic():
                settings.save()
            return [200, '']
        except RenderingResourceSettings.DoesNotExist as e:
            log.error(str(e))
            return [404, str(e)]

    @classmethod
    def list(cls, serializer):
        """
        Returns a JSON formatted list of active rendering resource config according
        to a given serializer
        :param serializer: Serializer used for formatting the list of session
        """
        settings = RenderingResourceSettings.objects.all()
        return [200, JSONRenderer().render(serializer(settings, many=True).data)]

    @staticmethod
    def get_by_id(settings_id):
        """
        Returns the config rendering resource config
        :param settings_id id of rendering resource or which we want the config
        """
        return RenderingResourceSettings.objects.get(id=settings_id)

    @classmethod
    def delete(cls, settings_id):
        """
        Removes some given rendering resource config
        :param settings_id Identifier of the Rendering resource config to remove
        """
        try:
            settings = RenderingResourceSettings.objects.get(id=settings_id)
            with transaction.atomic():
                settings.delete()
            return [200, 'Settings successfully deleted']
        except RenderingResourceSettings.DoesNotExist as e:
            log.error(str(e))
            return [404, str(e)]

    @staticmethod
    def format_rest_parameters(string_format, hostname, port, schema):
        """
        Returns a string of rest parameters formatted according to the
        string_format argument
        :param string_format Rest parameter string format
        :param hostname Rest hostname
        :param port Rest port
        :param schema Rest schema
        """
        response = string_format
        response = response.replace('${rest_hostname}', str(hostname))
        response = response.replace('${rest_port}', str(port))
        response = response.replace('${rest_schema}', str(schema))
        return response

    @classmethod
    def clear(cls):
        """
        Clear all config
        """
        with transaction.atomic():
            RenderingResourceSettings.objects.all().delete()
        return [200, 'Settings cleared']