#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Encapsulate cinder-infinidat testing."""

import zaza.charm_lifecycle.utils as lifecycle_utils
import zaza.openstack.utilities.openstack as openstack
import zaza.openstack.utilities.generic as generic
from zaza.openstack.charm_tests.cinder_backend.tests import CinderBackendTest

from zaza.openstack.charm_tests.cinder.tests import CinderTests


import zaza.model as zaza_model

BACKEND_NAME='cinder-infinidat'

def configure_default_volume_type():

    session = openstack.get_overcloud_keystone_session()
    cinder = openstack.get_cinder_session_client(session, version=3)

    type_name = '__DEFAULT__'

    try:
        vol_type = cinder.volume_types.find(name=type_name)
        vol_type.set_keys(metadata={
          'volume_backend_name': BACKEND_NAME,
        })
    except cinder_exceptions.NotFound:
        raise

class CinderInfinidatBackendTest(CinderBackendTest):
    """Encapsulate Infinidat tests."""

    backend_name = BACKEND_NAME

    expected_config_content = {
        'cinder-infinidat': {
            'infinidat_storage_protocol': ['iscsi'],
            'volume_backend_name': [BACKEND_NAME],
            'volume_driver':
                ['cinder.volume.drivers.infinidat.InfiniboxVolumeDriver'],
        }}

    def test_create_volume(self):
        return super().test_create_volume()

class CinderInfinidatTest(CinderTests):
    """
    Re-use most relevant existing Cinder tests,
    skip tests that cover only Cinder itself
    """

    def test_901_pause_resume(self):
        return

    def test_900_restart_on_config_change(self):
        return


