# -*- coding: utf-8 -*-
#
# Copyright: (c) 2020, F5 Networks Inc.
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.f5networks.f5_bigip.plugins.modules.bigip_config import (
    Parameters, ModuleManager, ArgumentSpec
)
from ansible_collections.f5networks.f5_bigip.tests.compat import unittest
from ansible_collections.f5networks.f5_bigip.tests.compat.mock import Mock, patch
from ansible_collections.f5networks.f5_bigip.tests.modules.utils import set_module_args


fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')
fixture_data = {}


def load_fixture(name):
    path = os.path.join(fixture_path, name)

    if path in fixture_data:
        return fixture_data[path]

    with open(path) as f:
        data = f.read()

    try:
        data = json.loads(data)
    except Exception:
        pass

    fixture_data[path] = data
    return data


class TestParameters(unittest.TestCase):
    def test_module_parameters(self):
        args = dict(
            save='yes',
            reset='yes',
            merge_content='asdasd',
            verify='no',
        )
        p = Parameters(params=args)
        assert p.save == 'yes'
        assert p.reset == 'yes'
        assert p.merge_content == 'asdasd'


class TestManager(unittest.TestCase):

    def setUp(self):
        self.spec = ArgumentSpec()
        self.p1 = patch('ansible_collections.f5networks.f5_bigip.plugins.modules.bigip_config.send_teem')
        self.m1 = self.p1.start()
        self.m1.return_value = True

    def tearDown(self):
        self.p1.stop()

    def test_run_single_command(self, *args):
        set_module_args(dict(
            save='yes',
            reset='yes',
            merge_content='asdasd',
            verify='no'
        )
        )
        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode
        )
        mm = ModuleManager(module=module)

        # Override methods to force specific logic in the module to happen
        mm.exit_json = Mock(return_value=True)
        mm.reset_device = Mock(return_value='reset output')
        mm.upload_to_device = Mock(return_value=True)
        mm.move_on_device = Mock(return_value=True)
        mm.merge_on_device = Mock(return_value='merge output')
        mm.remove_temporary_file = Mock(return_value=True)
        mm.save_on_device = Mock(return_value='save output')

        results = mm.exec_module()

        assert results['changed'] is True
