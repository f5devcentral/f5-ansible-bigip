#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 F5 Networks Inc.
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = r'''
---
module: bigiq_utility_license_assignment
short_description: Manage utility license assignment on BIG-IPs from a BIG-IQ
description:
  - Manages the assignment of utility licenses on a BIG-IQ. Assignment means
    the license is assigned to a BIG-IP, or it needs to be assigned to a BIG-IP.
    Additionally, this module supports revoking the assignments from BIG-IP devices.
version_added: "1.0.0"
options:
  unit_of_measure:
    description:
      - Sets the rate at which this license usage is billed.
      - Depending on your license, you may have different units of measure
        available to you. If a particular unit is not available to you, the module
        notifies you at licensing time.
    type: str
    choices:
      - hourly
      - daily
      - monthly
      - yearly
    default: hourly
  key:
    description:
      - The registration key from which you want choose an offering.
    type: str
    required: True
  offering:
    description:
      - Name of the license offering to assign to the device.
    type: str
    required: True
  device:
    description:
      - When C(managed) is C(no), specifies the address, or hostname, where the BIG-IQ
        can reach the remote device to register.
      - When C(managed) is C(yes), specifies the managed device, or device UUID,
        you want to register.
      - If C(managed) is C(yes), it is very important you do not have more than
        one device with the same name. BIG-IQ internally recognizes devices by their ID,
        and therefore, this module cannot guarantee the correct device will be
        registered. The device returned is the device that is used.
    type: str
    required: True
  managed:
    description:
      - Whether the specified device is a managed or un-managed device.
      - When C(state) is C(present), this parameter is required.
    type: bool
  device_port:
    description:
      - Specifies the port of the remote device to connect to.
      - If this parameter is not specified, the default is C(443).
    type: int
    default: 443
  device_username:
    description:
      - The username used to connect to the remote device.
      - This username should be one that has sufficient privileges on the remote device
        to do licensing. Usually this is the C(Administrator) role.
      - When C(managed) is C(no), this parameter is required.
    type: str
  device_password:
    description:
      - The password of the C(device_username).
      - When C(managed) is C(no), this parameter is required.
    type: str
  state:
    description:
      - When C(present), ensures the device is assigned the specified license.
      - When C(absent), ensures the license is revokes from the remote device and freed
        on the BIG-IQ.
    type: str
    choices:
      - present
      - absent
    default: present
author:
  - Wojciech Wypior (@wojtek0806)
'''

EXAMPLES = r'''
- hosts: all
  collections:
    - f5networks.f5_bigip
  connection: httpapi

  vars:
    ansible_host: "lb.mydomain.com"
    ansible_user: "admin"
    ansible_httpapi_password: "secret"
    ansible_network_os: f5networks.f5_bigip.bigiq
    ansible_httpapi_use_ssl: yes

  tasks:
    - name: Register an unmanaged device
      bigiq_utility_license_assignment:
        key: XXXX-XXXX-XXXX-XXXX-XXXX
        offering: F5-BIG-MSP-AFM-10G-LIC
        device: 1.1.1.1
        managed: no
        device_username: admin
        device_password: secret
        state: present

    - name: Register a managed device, by name
      bigiq_utility_license_assignment:
        key: XXXX-XXXX-XXXX-XXXX-XXXX
        offering: F5-BIG-MSP-AFM-10G-LIC
        device: bigi1.foo.com
        managed: yes
        state: present

    - name: Register a managed device, by UUID
      bigiq_utility_license_assignment:
        key: XXXX-XXXX-XXXX-XXXX-XXXX
        offering: F5-BIG-MSP-AFM-10G-LIC
        device: 7141a063-7cf8-423f-9829-9d40599fa3e0
        managed: yes
        state: present
'''

RETURN = r'''
# only common fields returned
'''

import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

from ..module_utils.client import F5Client
from ..module_utils.common import (
    F5ModuleError, AnsibleF5Parameters
)
from ..module_utils.ipaddress import is_valid_ip


class Parameters(AnsibleF5Parameters):
    api_map = {
        'deviceReference': 'device_reference',
        'deviceAddress': 'device_address',
        'httpsPort': 'device_port',
        'unitOfMeasure': 'unit_of_measure'
    }

    api_attributes = [
        'deviceReference', 'deviceAddress', 'httpsPort', 'managed', 'unitOfMeasure'
    ]

    returnables = [
        'device_address', 'device_reference', 'device_username', 'device_password',
        'device_port', 'managed', 'unit_of_measure'
    ]

    updatables = [
        'device_reference', 'device_address', 'device_username', 'device_password',
        'device_port', 'managed', 'unit_of_measure'
    ]

    def to_return(self):
        result = {}
        try:
            for returnable in self.returnables:
                result[returnable] = getattr(self, returnable)
            result = self._filter_params(result)
        except Exception:
            raise
        return result


class ApiParameters(Parameters):
    pass


class ModuleParameters(Parameters):
    @property
    def device_password(self):
        if self._values['device_password'] is None:
            return None
        return self._values['device_password']

    @property
    def device_username(self):
        if self._values['device_username'] is None:
            return None
        return self._values['device_username']

    @property
    def device_address(self):
        if self.device_is_address:
            return self._values['device']

    @property
    def device_port(self):
        if self._values['device_port'] is None:
            return None
        return int(self._values['device_port'])

    @property
    def device_is_address(self):
        if is_valid_ip(self.device):
            return True
        return False

    @property
    def device_is_id(self):
        pattern = r'[A-Za-z0-9]{8}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{12}'
        if re.match(pattern, self.device):
            return True
        return False

    @property
    def device_is_name(self):
        if not self.device_is_address and not self.device_is_id:
            return True
        return False

    @property
    def device_reference(self):
        if not self.managed:
            return None
        if self.device_is_address:
            # This range lookup is how you do lookups for single IP addresses. Weird.
            filter = "address+eq+'{0}...{0}'".format(self.device)
        elif self.device_is_name:
            filter = "hostname+eq+'{0}'".format(self.device)
        elif self.device_is_id:
            filter = "uuid+eq+'{0}'".format(self.device)
        else:
            raise F5ModuleError(
                "Unknown device format '{0}'".format(self.device)
            )

        uri = "/mgmt/shared/resolver/device-groups/cm-bigip-allBigIpDevices/devices/?$filter={0}&$top=1".format(filter)
        response = self.client.get(uri)

        if response['code'] not in [200, 201, 202]:
            raise F5ModuleError(response['contents'])

        if response['code'] == 200 and response['contents']['totalItems'] == 0:
            raise F5ModuleError(
                "No device with the specified address was found."
            )

        id = response['contents']['items'][0]['uuid']
        result = dict(
            link='https://localhost/mgmt/shared/resolver/device-groups/cm-bigip-allBigIpDevices/devices/{0}'.format(id)
        )
        return result

    @property
    def offering_id(self):
        filter = "(name+eq+'{0}')".format(self.offering)
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings?$filter={1}&$top=1".format(
            self.key, filter
        )
        response = self.client.get(uri)

        if response['code'] not in [200, 201, 202]:
            raise F5ModuleError(response['contents'])

        if response['code'] == 200 and response['contents']['totalItems'] == 0:
            raise F5ModuleError(
                "No offering with the specified name was found."
            )

        result = response['contents']['items'][0]['id']
        return result

    @property
    def member_id(self):
        if self.device_is_address:
            # This range lookup is how you do lookups for single IP addresses. Weird.
            filter = "deviceAddress+eq+'{0}...{0}'".format(self.device)
        elif self.device_is_name:
            filter = "deviceName+eq+'{0}'".format(self.device)
        elif self.device_is_id:
            filter = "deviceMachineId+eq+'{0}'".format(self.device)
        else:
            raise F5ModuleError(
                "Unknown device format '{0}'".format(self.device)
            )
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings/{1}/members/?$filter={2}".format(
            self.key, self.offering_id, filter
        )
        response = self.client.get(uri)

        if response['code'] not in [200, 201, 202]:
            raise F5ModuleError(response['contents'])

        if response['code'] == 200 and response['contents']['totalItems'] == 0:
            return None

        result = response['contents']['items'][0]['id']
        return result


class Changes(Parameters):
    pass


class UsableChanges(Changes):
    @property
    def device_port(self):
        if self._values['managed']:
            return None
        return self._values['device_port']

    @property
    def device_username(self):
        if self._values['managed']:
            return None
        return self._values['device_username']

    @property
    def device_password(self):
        if self._values['managed']:
            return None
        return self._values['device_password']

    @property
    def device_reference(self):
        if not self._values['managed']:
            return None
        return self._values['device_reference']

    @property
    def device_address(self):
        if self._values['managed']:
            return None
        return self._values['device_address']

    @property
    def managed(self):
        return None


class ReportableChanges(Changes):
    pass


class Difference(object):
    def __init__(self, want, have=None):
        self.want = want
        self.have = have

    def compare(self, param):
        try:
            result = getattr(self, param)
            return result
        except AttributeError:
            return self.__default(param)

    def __default(self, param):
        attr1 = getattr(self.want, param)
        try:
            attr2 = getattr(self.have, param)
            if attr1 != attr2:
                return attr1
        except AttributeError:
            return attr1


class ModuleManager(object):
    def __init__(self, *args, **kwargs):
        self.module = kwargs.get('module', None)
        self.connection = kwargs.get('connection', None)
        self.client = F5Client(module=self.module, client=self.connection)
        self.want = ModuleParameters(client=self.client, params=self.module.params)
        self.have = ApiParameters()
        self.changes = UsableChanges()

    def _set_changed_options(self):
        changed = {}
        for key in Parameters.returnables:
            if getattr(self.want, key) is not None:
                changed[key] = getattr(self.want, key)
        if changed:
            self.changes = Changes(params=changed)

    def _update_changed_options(self):
        diff = Difference(self.want, self.have)
        updatables = Parameters.updatables
        changed = dict()
        for k in updatables:
            change = diff.compare(k)
            if change is None:
                continue
            else:
                if isinstance(change, dict):
                    changed.update(change)
                else:
                    changed[k] = change
        if changed:
            self.changes = Changes(params=changed)
            return True
        return False

    def should_update(self):
        result = self._update_changed_options()
        if result:
            return True
        return False

    def exec_module(self):
        changed = False
        result = dict()
        state = self.want.state

        if state == "present":
            changed = self.present()
        elif state == "absent":
            changed = self.absent()

        reportable = ReportableChanges(params=self.changes.to_return())
        changes = reportable.to_return()
        result.update(**changes)
        result.update(dict(changed=changed))
        self._announce_deprecations(result)
        return result

    def _announce_deprecations(self, result):
        warnings = result.pop('__warnings', [])
        for warning in warnings:
            self.module.deprecate(
                msg=warning['msg'],
                version=warning['version']
            )

    def present(self):
        if self.exists():
            return False
        return self.create()

    def exists(self):
        if self.want.member_id is None:
            return False
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings/{1}/members/{2}".format(
            self.want.key, self.want.offering_id, self.want.member_id
        )
        response = self.client.get(uri)

        if response['code'] == 404:
            return False

        if response['code'] not in [200, 201, 202]:
            raise F5ModuleError(response['contents'])

        return True

    def remove(self):
        self._set_changed_options()
        if self.module.check_mode:
            return True
        self.remove_from_device()
        if self.exists():
            raise F5ModuleError("Failed to delete the resource.")
        return True

    def create(self):
        self._set_changed_options()
        if not self.want.managed:
            if self.want.device_username is None:
                raise F5ModuleError(
                    "You must specify a 'device_username' when working with unmanaged devices."
                )
            if self.want.device_password is None:
                raise F5ModuleError(
                    "You must specify a 'device_password' when working with unmanaged devices."
                )
        if self.module.check_mode:
            return True
        self.create_on_device()
        if not self.exists():
            raise F5ModuleError(
                "Failed to license the remote device."
            )
        self.wait_for_device_to_be_licensed()
        return True

    def create_on_device(self):
        params = self.changes.api_params()
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings/{1}/members/".format(
            self.want.key, self.want.offering_id
        )

        if not self.want.managed:
            params['username'] = self.want.device_username
            params['password'] = self.want.device_password

        response = self.client.post(uri, data=params)

        if response['code'] not in [200, 201, 202]:
            raise F5ModuleError(response['contents'])
        return True

    def wait_for_device_to_be_licensed(self):
        count = 0
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings/{1}/members/{2}".format(
            self.want.key, self.want.offering_id, self.want.member_id
        )
        while count < 3:
            response = self.client.get(uri)

            if response['code'] not in [200, 201, 202]:
                raise F5ModuleError(response['contents'])

            if response['contents']['status'] == 'LICENSED':
                count += 1
            else:
                count = 0

    def absent(self):
        if self.exists():
            return self.remove()
        return False

    def remove_from_device(self):
        uri = "/mgmt/cm/device/licensing/pool/utility/licenses/{0}/offerings/{1}/members/{2}".format(
            self.want.key, self.want.offering_id, self.want.member_id
        )
        params = {}
        if not self.want.managed:
            params.update(self.changes.api_params())
            params['id'] = self.want.member_id
            params['username'] = self.want.device_username
            params['password'] = self.want.device_password
        self.client.delete(uri, data=params)


class ArgumentSpec(object):
    def __init__(self):
        self.supports_check_mode = True
        argument_spec = dict(
            offering=dict(required=True),
            unit_of_measure=dict(
                default='hourly',
                choices=[
                    'hourly', 'daily', 'monthly', 'yearly'
                ]
            ),
            key=dict(required=True, no_log=True),
            device=dict(required=True),
            managed=dict(type='bool'),
            device_port=dict(type='int', default=443),
            device_username=dict(no_log=True),
            device_password=dict(no_log=True),
            state=dict(default='present', choices=['absent', 'present'])
        )
        self.argument_spec = {}
        self.argument_spec.update(argument_spec)
        self.required_if = [
            ['state', 'present', ['key', 'managed']],
            ['managed', False, ['device', 'device_username', 'device_password']],
            ['managed', True, ['device']]
        ]


def main():
    spec = ArgumentSpec()

    module = AnsibleModule(
        argument_spec=spec.argument_spec,
        supports_check_mode=spec.supports_check_mode,
        required_if=spec.required_if
    )

    try:
        mm = ModuleManager(module=module, connection=Connection(module._socket_path))
        results = mm.exec_module()
        module.exit_json(**results)
    except F5ModuleError as ex:
        module.fail_json(msg=str(ex))


if __name__ == '__main__':
    main()
