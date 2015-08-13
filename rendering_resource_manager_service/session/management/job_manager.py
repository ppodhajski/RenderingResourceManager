#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0403

"""
The job manager is in charge of managing slurm jobs.
"""

import signal
import subprocess
import urllib2
import traceback
from threading import Lock

import rendering_resource_manager_service.session.management.session_manager_settings as settings
import rendering_resource_manager_service.utils.custom_logging as log
from rendering_resource_manager_service.config.management import \
    rendering_resource_settings_manager as manager
import saga
import re
from rendering_resource_manager_service.session.models import SESSION_STATUS_SCHEDULED
import rendering_resource_manager_service.service.settings as global_settings


class JobManager(object):
    """
    The job manager class provides methods for managing slurm jobs via saga.
    """

    def __init__(self):
        """
        Setup saga context, session and service
        """

        self._context = saga.Context('UserPass')
        self._context.user_id = global_settings.SLURM_USERNAME
        self._context.user_pass = global_settings.SLURM_PASSWORD
        self._session = saga.Session()
        self._session.add_context(self._context)
        self._service = None
        self._connected = False
        self._mutex = Lock()

    def __connect(self):
        """
        Utility method to connect to slurm queue, if not already done
        """
        response = [200, 'Connected']
        self._mutex.acquire()
        if not self._connected:
            try:
                url = settings.SLURM_SERVICE_URL
                self._service = saga.job.Service(rm=url, session=self._session)
                log.info(1, 'Connected to slurm queue ' + str(self._service.get_url()))
                self._connected = True
            except saga.SagaException as e:
                log.error(str(e))
                response = [400, str(e)]
        self._mutex.release()
        return response

    def schedule(self, session, params, environment):
        """
        Utility method to schedule an instance of the renderer on the cluster
        """
        status = self.__connect()
        if status[0] != 200:
            return status
        try:
            self._mutex.acquire()
            rr_settings = \
                manager.RenderingResourceSettingsManager.get_by_id(session.renderer_id.lower())
            rest_parameters = manager.RenderingResourceSettingsManager.format_rest_parameters(
                str(rr_settings.scheduler_rest_parameters_format),
                str(session.http_host),
                str(session.http_port),
                'rest' + str(rr_settings.id + session.id))

            parameters = rest_parameters.split()
            parameters.append(params)
            environment_variables = rr_settings.environment_variables.split()
            environment_variables.append(environment)
            log.info(1, 'Scheduling job: ' +
                     str(rr_settings.command_line) + ' ' + str(parameters) + ', ' +
                     str(rr_settings.environment_variables) + ' ' + str(environment_variables))
            session.job_id = self.create_job(
                str(rr_settings.command_line), parameters, environment)
            session.status = SESSION_STATUS_SCHEDULED
            session.save()
            return [200, 'Job ' + str(session.job_id) + ' now scheduled']
        except saga.SagaException as e:
            log.error(str(e))
            return [400, str(e)]
        finally:
            self._mutex.release()

    def create_job(self, executable, params, environment):
        """
        Launch a job on the cluster with the given executable and parameters
        :return: The ID of the job
        """
        log.debug(1, 'Creating job for ' + executable)
        description = saga.job.Description()
        description.name = settings.SLURM_JOB_NAME_PREFIX + executable

        # Temporary hack to allow OSPRay execution on the cluster.
        # Intel made a fix to OSPRay's version of Embree to fix the thread affinity issue:
        # commit 9384a2ac9cec5c46a340476356f4e3f540b2a5c8
        # Date:   Thu Apr 16 17:04:16 2015 -0500
        # This fix is in both OSPRay v0.8.1 and v0.8.2, but not in the v0.7.2 that is
        # currently used by BRayns
        description.executable = '#SBATCH --exclusive\n'

        description.executable += 'module purge\n'
        description.executable += 'module load ' + settings.SLURM_DEFAULT_MODULE + '\n'
        description.executable += executable
        description.total_physical_memory = 2000
        description.arguments = params
        description.queue = settings.SLURM_QUEUE
        description.project = settings.SLURM_PROJECT
        description.output = settings.SLURM_OUTPUT_PREFIX + executable + settings.SLURM_OUT_FILE
        description.error = settings.SLURM_OUTPUT_PREFIX + executable + settings.SLURM_ERR_FILE
        if len(environment) > 0:
            description.environment = environment

        log.info(1, 'About to submit job for ' + executable)
        job = self._service.create_job(description)
        job.run()
        log.info(1, 'Submitted job for ' + executable + ', got id ' +
                 str(job.get_id()) + ', state ' + str(job.get_state()))
        return job.get_id()

    def query(self, job_id):
        """
        Verifies that a given job is up and running
        :param job_id: The ID of the job
        :return: A Json response containing on ok status or a description of the error
        """
        status = self.__connect()
        if status[0] != 200:
            return status
        if job_id is not None:
            try:
                self._mutex.acquire()
                job = self._service.get_job(job_id)
                return [200, str(job.get_state())]
            except saga.SagaException as e:
                log.error(str(e))
                return [400, str(e.message)]
            finally:
                self._mutex.release()

        return [400, 'Invalid job_id ' + str(job_id)]

    # subprocess.check_output is backported from python 2.7
    @staticmethod
    def check_output(*popenargs, **kwargs):
        """Run command with arguments and return its output as a byte string.
        Backported from Python 2.7 as it's implemented as pure python on stdlib.
        >>> check_output(['/usr/bin/python', '--version'])
        Python 2.6.2

        https://gist.github.com/edufelipe/1027906
        """
        process = subprocess.Popen(
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        if not unused_err is None:
            log.error(str(unused_err))
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output

    @staticmethod
    def hostname(job_id):
        """
        Retrieve the hostname for the batch host of the given job.
        Note: this uses ssh and scontrol on the SLURM_HOST as saga does not support this feature,
              especially if the job is not persisted. Retrieving the job from the saga service by
              the job_id only sets the state in the job, nothing else.
        :param job_id: The ID of the job
        :return: The hostname of the batch host if the job is running, empty otherwise
        """
        log.debug(1, global_settings.SLURM_USERNAME + ':' + global_settings.SLURM_PASSWORD)
        job_id_as_int = re.search(r'(?=)-\[(\w+)\]', job_id).group(1)
        log.debug(1, 'Job id as int: ' + str(job_id_as_int))
        result = JobManager.check_output(['sshpass', '-p', global_settings.SLURM_PASSWORD, 'ssh',
                                          global_settings.SLURM_USERNAME + '@' +
                                          settings.SLURM_HOST, 'scontrol show job', job_id_as_int])
        log.info(1, str(result))
        state = re.search(r'JobState=(\w+)', result).group(1)
        if state == 'FAILED':
            # Job does not exist
            return state
        if state != 'RUNNING':
            # Job is scheduled but not running
            return ''
        hostname = re.search(r'BatchHost=(\w+)', result).group(1)
        if hostname.find(settings.SLURM_HOST_DOMAIN) == -1:
            hostname += settings.SLURM_HOST_DOMAIN
        return hostname

    # Stop Process
    def stop(self, session):
        """
        Gently stops a given job, waits for 2 seconds and checks for its disappearance
        :param job_id: The ID of the job
        :return: A Json response containing on ok status or a description of the error
        """
        status = self.__connect()
        if status[0] != 200:
            return status
        if session.job_id is not None:
            try:
                self._mutex.acquire()
                log.debug(1, 'Stopping job <' + str(session.job_id) + '>')
                job = self._service.get_job(session.job_id)
                wait_timeout = 2.0
                # pylint: disable=E1101
                setting = \
                    manager.RenderingResourceSettings.objects.get(
                        id=session.renderer_id)
                if setting.graceful_exit:
                    try:
                        url = "http://" + session.http_host + ":" + \
                              str(session.http_port) + "/" + "EXIT"
                        req = urllib2.Request(url=url)
                        urllib2.urlopen(req).read()
                    # pylint: disable=W0702
                    except urllib2.HTTPError as e:
                        msg = str(traceback.format_exc(e))
                        log.debug(1, msg)
                        log.error('Failed to contact rendering resource')
                    except urllib2.URLError as e:
                        msg = str(traceback.format_exc(e))
                        log.debug(1, msg)
                        log.error('Failed to contact rendering resource')

                job.cancel(wait_timeout)
                if job.get_state() == saga.job.CANCELED:
                    msg = 'Job successfully cancelled'
                    log.info(1, msg)
                    result = [200, msg]
                else:
                    msg = 'Could not cancel job ' + str(session.job_id)
                    log.info(1, msg)
                    result = [400, msg]
            except saga.NoSuccess as e:
                msg = str(traceback.format_exc(e))
                log.error(msg)
                result = [400, msg]
            except saga.DoesNotExist as e:
                msg = str(traceback.format_exc(e))
                log.info(1, msg)
                result = [200, msg]
            finally:
                self._mutex.release()
        else:
            log.debug(1, 'No job to stop')

        return result

    # Kill Process
    def kill(self, job_id):
        """
        Kills the given job. This method should only be used if the stop method failed.
        :param job_id: The ID of the job
        :return: A Json response containing on ok status or a description of the error
        """
        if not self.__connect():
            return
        if job_id is not None:
            try:
                self._mutex.acquire()
                job = self._service.get_job(job_id)
                job.signal(signal.SIGKILL)
                if job.get_state() != saga.job.RUNNING:
                    return [200, 'Job successfully killed']
            except saga.SagaException as e:
                log.error(str(e))
                return [400, str(e.message)]
            finally:
                self._mutex.release()
        return [400, 'Could not kill job ' + str(job_id)]

    @staticmethod
    def job_information(session):
        """
        Returns information about the job
        :param session: the session to be queried
        :return: A string containing the information about the job
        """
        try:
            job_id_as_int = re.search(r'(?=)-\[(\w+)\]', session.job_id).group(1)
            result = JobManager.check_output(['sshpass', '-p', global_settings.SLURM_PASSWORD,
                                              'ssh', global_settings.SLURM_USERNAME + '@' +
                                              settings.SLURM_HOST, 'scontrol show job',
                                              job_id_as_int])
            return result
        except IOError as e:
            return str(e)

    @staticmethod
    def rendering_resource_log(session):
        """
        Returns the contents of the rendering resource error file
        :param session: the session to be queried
        :return: A string containing the error log
        """
        try:
            job_id_as_int = re.search(r'(?=)-\[(\w+)\]', session.job_id).group(1)
            rr_settings = \
                manager.RenderingResourceSettingsManager.get_by_id(session.renderer_id.lower())
            filename = settings.SLURM_OUTPUT_PREFIX + \
                       str(rr_settings.command_line) + settings.SLURM_ERR_FILE
            filename = filename.replace('%A', str(job_id_as_int), 1)
            result = filename + ':\n'
            result += JobManager.check_output(['sshpass', '-p', global_settings.SLURM_PASSWORD,
                                               'ssh', global_settings.SLURM_USERNAME + '@' +
                                               settings.SLURM_HOST, 'cat ', filename])
            return result
        except IOError as e:
            return str(e)

# Global job manager used for all allocations
globalJobManager = JobManager()