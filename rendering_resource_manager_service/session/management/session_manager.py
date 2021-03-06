#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=E1101
# pylint: disable=W0403
# pylint: disable=R0912
# pylint: disable=R0915

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
This class is in charge of handling session and ensures persistent storage in a database
"""

import requests
import datetime
import uuid
import json

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from rendering_resource_manager_service.config.models import SystemGlobalSettings
from rendering_resource_manager_service.session.models import Session, \
    SESSION_STATUS_STOPPED, SESSION_STATUS_SCHEDULED, SESSION_STATUS_STARTING, \
    SESSION_STATUS_RUNNING, SESSION_STATUS_STOPPING, SESSION_STATUS_BUSY, \
    SESSION_STATUS_GETTING_HOSTNAME, SESSION_STATUS_SCHEDULING, SESSION_STATUS_FAILED
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
import rest_framework.status as http_status
import rendering_resource_manager_service.utils.custom_logging as log
import rendering_resource_manager_service.session.management.session_manager_settings as consts
from rendering_resource_manager_service.session.management import keep_alive_thread
from rendering_resource_manager_service.config.management import \
    rendering_resource_settings_manager as manager
import rendering_resource_manager_service.service.settings as global_settings
from job_manager import globalJobManager
import process_manager


class JSONResponse(HttpResponse):
    """
    This class constructs HTTP response with JSON formatted body
    """
    def __len__(self):
        pass

    def __getitem__(self, item):
        pass

    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


class SessionManager(object):
    """
    This class is in charge of handling session and ensures persistent storage in a database
    """

    def __init__(self):
        """
        Initializes the SessionManager class and creates the global config if
        they do not already exist in the database
        """
        try:
            SystemGlobalSettings.objects.get(id=0)
        except SystemGlobalSettings.DoesNotExist:
            sgs = SystemGlobalSettings(
                id=0,
                session_creation=True,
                session_keep_alive_timeout=keep_alive_thread.KEEP_ALIVE_TIMEOUT)
            sgs.save(force_insert=True)

    @classmethod
    def create_session(cls, session_id, owner, configuration_id):
        """
        Creates a user session
        :param session_id: Id for the new session
        :param owner: Session owner
        :param configuration_id: Id of the configuration associated to the session
        :rtype A tuple containing the status and the description of the potential error
        """
        sgs = SystemGlobalSettings.objects.get()
        if sgs.session_creation:
            try:
                session = Session(
                    id=session_id,
                    owner=owner,
                    configuration_id=configuration_id,
                    created=datetime.datetime.utcnow(),
                    valid_until=datetime.datetime.now() +
                    datetime.timedelta(seconds=sgs.session_keep_alive_timeout))
                with transaction.atomic():
                    session.save(force_insert=True)
                msg = 'Session successfully created'
                log.debug(1, msg)
                response = json.dumps({'contents': msg})
                return [http_status.HTTP_201_CREATED, response]
            except IntegrityError as e:
                log.error(e)
                response = json.dumps({'contents': str(e)})
                return [http_status.HTTP_409_CONFLICT, response]
        else:
            msg = 'Session creation is currently suspended'
            log.error(msg)
            response = json.dumps({'contents': str(msg)})
            return [http_status.HTTP_403_FORBIDDEN, response]

    @classmethod
    def get_session(cls, session_id, request, serializer):
        """
        Returns information about the session
        :param session_id: Id of the session
        :rtype A tuple containing the status and a JSON string with the
               serialized session, or a potential error description
        """
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist as e:
            log.error(e)
            response = json.dumps({'contents': str(e)})
            return [http_status.HTTP_404_NOT_FOUND, response]

        if request.method == consts.REST_VERB_GET:
            serializer = serializer(session)
            response = json.dumps({'contents': str(serializer.data)})
            return [http_status.HTTP_200_OK, response]

        elif request.method == consts.REST_VERB_PUT:
            data = JSONParser().parse(request)
            serializer = serializer(session, data=data)
            if serializer.is_valid():
                serializer.save()
                response = json.dumps({'contents': str(serializer.data)})
                return [http_status.HTTP_200_OK, response]
            log.error(serializer.errors)
            response = json.dumps({'contents': str(serializer.errors)})
            return [http_status.HTTP_400_BAD_REQUEST, response]

    @classmethod
    def delete_session(cls, session_id):
        """
        Deletes a session
        :param session_id: Id of the session to delete
        :rtype A tuple containing the status and a potential error description
        """
        try:
            session = Session.objects.get(id=session_id)
            log.info(1, 'Removing session ' + str(session_id))
            session.status = SESSION_STATUS_STOPPING
            session.save()
            if session.process_pid != -1:
                process_manager.ProcessManager.stop(session)
            if session.job_id is not None and session.job_id != '':
                globalJobManager.stop(session)
                globalJobManager.kill(session)
            session.delete()
            msg = 'Session successfully destroyed'
            log.info(1, msg)
            response = json.dumps({'contents': str(msg)})
            return [http_status.HTTP_200_OK, response]
        except Session.DoesNotExist as e:
            log.error(str(e))
            response = json.dumps({'contents': str(e)})
            return [http_status.HTTP_404_NOT_FOUND, response]
        except Exception as e:
            log.error(str(e))
            response = json.dumps({'contents': str(e)})
            return [http_status.HTTP_500_INTERNAL_SERVER_ERROR, response]
        msg = 'Session is currently being destroyed'
        response = json.dumps({'contents': msg})
        log.info(1, msg)
        return [http_status.HTTP_200_OK, response]

    @classmethod
    def list_sessions(cls, serializer):
        """
        Returns a JSON formatted list of active session according to a given serializer
        :param serializer: Serializer used for formatting the list of session
        """
        sessions = Session.objects.all()
        return [http_status.HTTP_200_OK, JSONResponse(serializer(sessions, many=True).data)]

    @classmethod
    def suspend_sessions(cls):
        """
        Suspends the creation of new session. This administration feature is
        here to prevent overloading of the system
        """
        sgs = SystemGlobalSettings.objects.get(id=0)
        if not sgs.session_creation:
            msg = 'Session creation already suspended'
        else:
            sgs.session_creation = False
            sgs.save()
            msg = 'Creation of new session now suspended'
        log.debug(1, msg)
        return [http_status.HTTP_200_OK, msg]

    @classmethod
    def clear_sessions(cls):
        """
        Suspends the creation of new session. This administration feature is
        here to prevent overloading of the system
        """
        Session.objects.all().delete()
        return [http_status.HTTP_200_OK, 'Sessions cleared']

    @classmethod
    def resume_sessions(cls):
        """
        Resumes the creation of new session.
        """
        sgs = SystemGlobalSettings.objects.get(id=0)
        if sgs.session_creation:
            msg = 'Session creation already resumed'
        else:
            sgs.session_creation = True
            sgs.save()
            msg = 'Creation of new session now resumed'
        log.debug(1, msg)
        return [http_status.HTTP_200_OK, msg]

    @classmethod
    def request_vocabulary(cls, session_id):
        """
        Queries the rendering resource vocabulary
        :param session_id: Id of the session to be queried
        :return 200 code if rendering resource is able to provide vocabulary. 503
                otherwise. 404 if specified session does not exist.
        """
        try:
            session = Session.objects.get(id=session_id)
            try:
                url = 'http://' + session.http_host + ':' + \
                      str(session.http_port) + '/' + consts.RR_SPECIFIC_COMMAND_VOCABULARY
                log.info(1, 'Requesting vocabulary from ' + url)
                r = requests.put(
                    url=url,
                    timeout=global_settings.REQUEST_TIMEOUT)
                response = r.text
                r.close()
                return [http_status.HTTP_200_OK, response]
            except requests.exceptions.RequestException as e:
                # Failed to contact rendering resource, make sure that the corresponding
                # job is still allocated
                log.info(1, str(e))
                hostname = ''
                try:
                    hostname = globalJobManager.hostname(session)
                except AttributeError as e:
                    log.error(str(e))

                if hostname == '':
                    log.info(1, 'Job has been cancelled. Destroying session')
                    cls.delete_session(session_id)
                    return [http_status.HTTP_404_NOT_FOUND, str(e)]
                return [http_status.HTTP_503_SERVICE_UNAVAILABLE, str(e)]
        except Session.DoesNotExist as e:
            # Requested session does not exist
            log.info(1, str(e))
            return [http_status.HTTP_404_NOT_FOUND, str(e)]

    @staticmethod
    def __status_response(http_code, session_id, code, description, hostname, port):
        """
        Builds a JSon representation of the given parameters for HTTP responses
        :param http_code: HTTP code
        :param session_id: Session identifier
        :param code: Status code
        :param description: Status description
        :param hostname: Hostname of the rendering resource
        :param port: Port of the rendering resource
        :return: JSon representation of the given parameters
        """
        return [http_code, json.dumps({
            'session': str(session_id),
            'code': code,
            'description': description,
            'hostname': hostname,
            'port': str(port)
        })]

    @staticmethod
    def status_as_string(status):
        """
        :param status:
        :return:
        """
        # pylint: disable=R0911
        if status == SESSION_STATUS_STOPPED:
            return 'Stopped'
        elif status == SESSION_STATUS_SCHEDULING:
            return 'Scheduling'
        elif status == SESSION_STATUS_SCHEDULED:
            return 'Scheduled'
        elif status == SESSION_STATUS_GETTING_HOSTNAME:
            return 'Getting hostname'
        elif status == SESSION_STATUS_STARTING:
            return 'Running'
        elif status == SESSION_STATUS_RUNNING:
            return 'Running'
        elif status == SESSION_STATUS_STOPPING:
            return 'Stopping'
        elif status == SESSION_STATUS_FAILED:
            return 'Failed'
        elif status == SESSION_STATUS_BUSY:
            return 'Busy'

    @staticmethod
    def query_status(session_id):
        """
        Queries the session status and updates it accordingly
        - Stopped: Default status, when no rendering resource is active
        - Scheduled: The slurm job was created but the rendering resource is not yet started.
        - Starting: The rendering resource is started but is not ready to respond to REST requests
        - Running: The rendering resource is started and ready to respond to REST requests
        - Stopping: tThe request for stopping the slurm job was made, but the application is not yet
          terminated
        :param session_id: Id of the session to be queried
        :return 200 code if rendering resource is able to process REST requests. 503
                otherwise. 404 if specified session does not exist.
        """
        try:
            session = Session.objects.get(id=session_id)
            status_description = 'Undefined'
            session_status = session.status

            log.info(1, 'Current session status is: ' +
                     SessionManager.status_as_string(session_status))

            if session_status == SESSION_STATUS_SCHEDULING:
                status_description = str(session.configuration_id + ' is scheduled')
            elif session_status == SESSION_STATUS_SCHEDULED or \
                            session_status == SESSION_STATUS_GETTING_HOSTNAME:
                if session.http_host != '':
                    status_description = session.configuration_id + ' is starting'
                    log.info(1, status_description)
                    session.status = SESSION_STATUS_STARTING
                    session.save()
                else:
                    status_description = str(session.configuration_id + ' is scheduled')
            elif session_status == SESSION_STATUS_STARTING:
                # Rendering resource might be running but not yet capable of
                # serving REST requests. The vocabulary is invoked to make
                # sure that the rendering resource is ready to serve REST
                # requests.
                rr_settings = \
                    manager.RenderingResourceSettingsManager.\
                        get_by_id(session.configuration_id.lower())
                if not rr_settings.wait_until_running:
                    status_description = session.configuration_id + ' is up and running'
                    log.info(1, status_description)
                    session.status = SESSION_STATUS_RUNNING
                    session.save()
                else:
                    log.info(1, 'Requesting rendering resource vocabulary')
                    status = SessionManager.request_vocabulary(session_id)
                    if status[0] == http_status.HTTP_200_OK and \
                                    status[0] != http_status.HTTP_404_NOT_FOUND:
                        status_description = session.configuration_id + ' is up and running'
                        log.info(1, status_description)
                        session.status = SESSION_STATUS_RUNNING
                        session.save()
                    elif status[0] == http_status.HTTP_404_NOT_FOUND:
                        return [http_status.HTTP_404_NOT_FOUND, 'Job has been cancelled']
                    else:
                        status_description = session.configuration_id + \
                            ' is starting but the HTTP interface is not yet available'
            elif session_status == SESSION_STATUS_RUNNING:
                # Update the timestamp if the current value is expired
                sgs = SystemGlobalSettings.objects.get()
                if datetime.datetime.now() > session.valid_until:
                    session.valid_until = datetime.datetime.now() + datetime.timedelta(
                        seconds=sgs.session_keep_alive_timeout)
                    session.save()
                status = SessionManager.request_vocabulary(session_id)
                if status[0] == http_status.HTTP_200_OK:
                    # Rendering resource is currently running
                    status_description = session.configuration_id + ' is up and running'
                elif status[0] == http_status.HTTP_404_NOT_FOUND:
                    return SessionManager.__status_response(
                        http_code=status[0], session_id=session_id,
                        code=SESSION_STATUS_STOPPED, description='Job has been cancelled',
                        hostname='', port=0)
                else:
                    # Rendering resource has been started but is not responding anymore, it is busy
                    status_description = session.configuration_id + ' is busy'
                    session.status = SESSION_STATUS_BUSY
                    session.save()

            elif session_status == SESSION_STATUS_BUSY:
                status = SessionManager.request_vocabulary(session_id)
                if status[0] == http_status.HTTP_200_OK:
                    # Rendering resource is not busy anymore
                    status_description = session.configuration_id + ' is up and running'
                    session.status = SESSION_STATUS_RUNNING
                    session.save()
                else:
                    if status[0] == http_status.HTTP_404_NOT_FOUND:
                        return SessionManager.__status_response(
                            http_code=status[0], session_id=session_id,
                            code=SESSION_STATUS_STOPPED, description='Job has been cancelled',
                            hostname='', port=0)
                    else:
                        status_description = session.configuration_id + ' is busy'

            elif session_status == SESSION_STATUS_STOPPING:
                # Rendering resource is currently in the process of terminating.
                status_description = str(session.configuration_id + ' is terminating...')
                session.delete()
                session.save()
            elif session_status == SESSION_STATUS_STOPPED:
                # Rendering resource is currently not active.
                status_description = str(session.configuration_id + ' is not active')
            elif session_status == SESSION_STATUS_FAILED:
                status_description = str('Job allocation failed for ' + session.configuration_id)

            status_code = session.status
            return SessionManager.__status_response(
                http_code=http_status.HTTP_200_OK, session_id=session_id,
                code=status_code, description=status_description,
                hostname=session.http_host, port=session.http_port)
        except Session.DoesNotExist as e:
            # Requested session does not exist
            log.error(str(e))
            return [http_status.HTTP_404_NOT_FOUND, str(e)]

    @classmethod
    def keep_alive_session(cls, session_id):
        """
        Updated the specified session with a new expiration timestamp
        :param session_id: Id of the session to update
        """
        log.debug(1, 'Session ' + str(session_id) + ' is being updated')
        try:
            sgs = SystemGlobalSettings.objects.get(id=0)
            session = Session.objects.get(id=session_id)
            session.valid_until = datetime.datetime.now() + \
                datetime.timedelta(seconds=sgs.session_keep_alive_timeout)
            session.save()
            msg = 'Session ' + str(session_id) + ' successfully updated'
            return [http_status.HTTP_200_OK, msg]
        except Session.DoesNotExist as e:
            log.error(str(e))
            return [http_status.HTTP_404_NOT_FOUND, str(e)]

    @staticmethod
    def get_session_id():
        """
        Utility function that returns a unique session ID
        :return: a UUID session identifier
        """
        session_id = uuid.uuid1()
        return session_id

    @staticmethod
    def get_session_id_from_request(request):
        """
        Utility function that returns the session ID from a given HTTP request
        :return: a UUID session identifier
        """
        log.debug(1, 'Getting cookie from request')
        return request.QUERY_PARAMS[consts.REQUEST_PARAMETER_SESSIONID]

    @staticmethod
    def get_authentication_token_from_request(request):
        """
        Utility function that returns the authentication token from a given HTTP request
        :return: the authentication token
        """
        try:
            auth_token = 'Bearer ' + request.META[consts.REQUEST_HEADER_AUTHORIZATION]
            log.info(1, 'Authentication token: ' + auth_token)
            return auth_token
        except KeyError:
            log.error('No authentication token provided')
            return None
