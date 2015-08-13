from django.test import TestCase
from nose import tools as nt
import rendering_resource_manager_service.utils.custom_logging as log
from rendering_resource_manager_service.config.management.rendering_resource_settings_manager \
    import RenderingResourceSettingsManager
from rendering_resource_manager_service.config.views import \
    RenderingResourceSettingsSerializer


class TestSessionManager(TestCase):
    def setUp(self):
        log.debug(1, 'setUp')
        manager = RenderingResourceSettingsManager()
        # Clear session
        status = manager.clear()
        nt.assert_true(status[0] == 200)

    def tearDown(self):
        log.debug(1, 'tearDown')
        # Clear session
        manager = RenderingResourceSettingsManager()
        status = manager.clear()
        nt.assert_true(status[0] == 200)

    def test_create_settings(self):
        log.debug(1, 'test_create_settings')
        # Create Settings
        manager = RenderingResourceSettingsManager()
        params = dict()
        params['id'] = 'rtneuron'
        params['command_line'] = 'rtneuron-app.py'
        params['environment_variables'] = \
            'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512'
        params['process_rest_parameters_format'] = '--rest {$rest_hostname}:${rest_port}'
        params['scheduler_rest_parameters_format'] = '--rest $SLURMD_NODENAME:${rest_port}'
        params['graceful_exit'] = True
        status = manager.create(params)
        nt.assert_true(status[0] == 201)
        # Delete Settings
        status = manager.delete(params['id'])
        nt.assert_true(status[0] == 200)

    def test_duplicate_settings(self):
        log.debug(1, 'test_duplicate_settings')
        manager = RenderingResourceSettingsManager()
        params = dict()
        params['id'] = 'rtneuron'
        params['command_line'] = 'rtneuron-app.py'
        params['environment_variables'] = \
            'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512'
        params['process_rest_parameters_format'] = '--rest {$rest_hostname}:${rest_port}'
        params['scheduler_rest_parameters_format'] = '--rest $SLURMD_NODENAME:${rest_port}'
        params['graceful_exit'] = True
        status = manager.create(params)
        nt.assert_true(status[0] == 201)
        # Duplicate
        status = manager.create(params)
        nt.assert_true(status[0] == 409)
        # Delete Settings
        status = manager.delete(params['id'])
        nt.assert_true(status[0] == 200)

    def test_delete_invalid_settings(self):
        log.debug(1, 'test_delete_invalid_settings')
        manager = RenderingResourceSettingsManager()
        params = dict()
        params['id'] = '@%$#$'
        # Delete Settings
        status = manager.delete(params)
        nt.assert_true(status[0] == 404)

    def test_list_settings(self):
        log.debug(1, 'test_list_settings')
        manager = RenderingResourceSettingsManager()
        params = dict()
        params['id'] = 'rtneuron'
        params['command_line'] = 'rtneuron-app.py'
        params['environment_variables'] = \
            'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512'
        params['process_rest_parameters_format'] = '--rest {$rest_hostname}:${rest_port}'
        params['scheduler_rest_parameters_format'] = '--rest $SLURMD_NODENAME:${rest_port}'
        params['graceful_exit'] = True
        status = manager.create(params)
        nt.assert_true(status[0] == 201)

        params['id'] = 'livre'
        params['command_line'] = 'livre'
        params['environment_variables'] = \
            'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512'
        params['process_rest_parameters_format'] = \
            '--rest {$rest_hostname}:${rest_port}:${rest_schema}'
        params['scheduler_rest_parameters_format'] = \
            '--rest $SLURMD_NODENAME:${rest_port}:${rest_schema}'
        params['graceful_exit'] = True
        status = manager.create(params)
        nt.assert_true(status[0] == 201)
        status = manager.list(RenderingResourceSettingsSerializer)
        nt.assert_true(status[0] == 200)
        value = status[1]
        reference = '[{"id": "livre", "command_line": "livre", ' + \
                    '"environment_variables": "EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512", ' +\
                    '"process_rest_parameters_format": "--rest {$rest_hostname}' + \
                    ':${rest_port}:${rest_schema}", "scheduler_rest_parameters_format": ' + \
                    '"--rest $SLURMD_NODENAME:${rest_port}:${rest_schema}", "graceful_exit": true}, ' + \
                    '{"id": "rtneuron", "command_line": "rtneuron-app.py", ' + \
                    '"environment_variables": "EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512", ' +\
                    '"process_rest_parameters_format": "--rest {$rest_hostname}:${rest_port}", ' + \
                    '"scheduler_rest_parameters_format": ' + \
                    '"--rest $SLURMD_NODENAME:${rest_port}", "graceful_exit": true}]'
        nt.assert_true(value == reference)

    def test_get_by_name_settings(self):
        log.debug(1, 'test_get_by_name_settings')
        manager = RenderingResourceSettingsManager()
        params = dict()
        params['id'] = 'rtneuron'
        params['command_line'] = 'rtneuron-app.py'
        params['environment_variables'] = \
            'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512'
        params['process_rest_parameters_format'] = '--rest {$rest_hostname}:${rest_port}'
        params['scheduler_rest_parameters_format'] = '--rest $SLURMD_NODENAME:${rest_port}'
        params['graceful_exit'] = True
        status = manager.create(params)
        nt.assert_true(status[0] == 201)

        settings = manager.get_by_id('rtneuron')
        nt.assert_true(settings.id == 'rtneuron')
        nt.assert_true(settings.command_line == 'rtneuron-app.py')
        nt.assert_true(settings.environment_variables ==
                       'EQ_WINDOW_IATTR_HINT_HEIGHT=512,EQ_WINDOW_IATTR_HINT_WIDTH=512')
        nt.assert_true(settings.process_rest_parameters_format ==
                       '--rest {$rest_hostname}:${rest_port}')
        nt.assert_true(settings.scheduler_rest_parameters_format ==
                       '--rest $SLURMD_NODENAME:${rest_port}')

    def test_format_rest_parameters(self):
        log.debug(1, 'test_format_rest_parameters')
        manager = RenderingResourceSettingsManager()
        # test 1
        value = manager.format_rest_parameters(
            '--rest ${rest_hostname}:${rest_port}',
            'localhost', 3000, 'schema')
        nt.assert_true(value == '--rest localhost:3000')

        # test 2
        value = manager.format_rest_parameters(
            '--rest ${rest_hostname}:${rest_port} --rest-schema ${rest_schema}',
            'localhost', 3000, 'schema')
        nt.assert_true(value == '--rest localhost:3000 --rest-schema schema')

        # test 3
        value = manager.format_rest_parameters(
            '--rest ${rest_hostname}:${rest_port} --rest-schema ${rest_schema}',
            'localhost', 3000, 'schema')
        nt.assert_true(value == '--rest localhost:3000 --rest-schema schema')

        # test 4
        value = manager.format_rest_parameters(
            '--rest ${rest_hostname}:${rest_port} --rest-schema ${rest_schema}',
            'localhost', '3000', 'schema')
        nt.assert_true(value == '--rest localhost:3000 --rest-schema schema')

        # test 5
        value = manager.format_rest_parameters(
            '--rest $SLURMD_NODENAME:${rest_port}',
            'localhost', 3000, 'schema')
        nt.assert_true(value == '--rest $SLURMD_NODENAME:3000')

        # test 6
        value = manager.format_rest_parameters(
            '--rest ${rest_hostname}:${rest_port}:${rest_schema}',
            'localhost', 3000, 'schema')
        nt.assert_true(value == '--rest localhost:3000:schema')