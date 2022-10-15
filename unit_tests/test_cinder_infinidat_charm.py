# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from src.charm import CinderInfinidatCharm

from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness

from unittest import mock

from charmhelpers.core.host_factory.ubuntu import UBUNTU_RELEASES

SOURCE = "deb https://repo.infinidat.com/packages/main-stable/apt/linux-ubuntu focal main"  # noqa: E501
KEY = """\
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.11 (GNU/Linux)

mQENBFESDRIBCADMR7MQMbH4GdCQqfrOMt35MhBwwH4wv9kb1WRSTxa0CmuzYaBB
1nJ0nLaMAwHsEr9CytPWDpMngm/3nt+4F2hJcsOEkQkqeJ31gScJewM+AOUV3DEl
qOeXXYLcP+jUY6pPjlZpOw0p7moUQPXHn+7amVrk7cXGQ8O3B+5a5wjN86LT2hlX
DlBlV5bX/DYluiPUbvQLOknmwO53KpaeDeZc4a8iIOCYWu2ntuAMddBkTps0El5n
JJZMTf6os2ZzngWMZRMDiVJgqVRi2b+8SgFQlQy0cAmne/mpgPrRq0ZMX3DokGG5
hnIg1mF82laTxd+9qtiOxupzJqf8mncQHdaTABEBAAG0IWFwcF9yZXBvIChDb21t
ZW50KSA8bm9AZW1haWwuY29tPokBOAQTAQIAIgUCURINEgIbLwYLCQgHAwIGFQgC
CQoLBBYCAwECHgECF4AACgkQem2D/j05RYSrcggAsCc4KppV/SZX5XI/CWFXIAXw
+HaNsh2EwYKf9DhtoGbTOuwePvrPGcgFYM3Tu+m+rziPnnFl0bs0xwQyNEVQ9yDw
t465pSgmXwEHbBkoISV1e4WYtZAsnTNne9ieJ49Ob/WY4w3AkdPRK/41UP5Ct6lR
HHRXrSWJYHVq5Rh6BakRuMJyJLz/KvcJAaPkA4U6VrPD7PFtSecMTaONPjGCcomq
b7q84G5ZfeJWb742PWBTS8fJdC+Jd4y5fFdJS9fQwIo52Ff9In2QBpJt5Wdc02SI
fvQnuh37D2P8OcIfMxMfoFXpAMWjrMYc5veyQY1GXD/EOkfjjLne6qWPLfNojA==
=w5Os
-----END PGP PUBLIC KEY BLOCK-----
"""

PROTOCOL_INVALID_VALUE = 'not_fc_or_iscsi'


class TestCinderInfinidatCharm(unittest.TestCase):

    def setUp(self):
        self.harness = Harness(CinderInfinidatCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.harness.set_leader(True)
        backend = self.harness.add_relation('storage-backend', 'cinder')
        self.harness.add_relation_unit(backend, 'cinder/0')

    def _get_partial_config_sample(self):
        """
        A config with all mandatory params set
        """
        return {
            'infinibox-ip': '123.123.123.123',
            'infinibox-login': 'login',
            'infinibox-password': 'password',
            'pool-name': 'test',
        }

    def _get_valid_config_sample(self):
        """
        A minimal config that would transition the charm to ActiveState
        """
        partial_config = self._get_partial_config_sample()
        partial_config.update({
            'protocol': 'iscsi',
            'iscsi-netspaces': 'A,B',
        })
        return partial_config

    def _get_source(self, codename, pocket, baseurl=None):
        if baseurl is None:
            baseurl = self.harness.charm.DEFAULT_REPO_BASEURL
        return ' '.join((
            'deb',
            baseurl,
            codename,
            pocket))

    def test_cinder_base(self):
        self.assertEqual(
            self.harness.framework.model.app.name,
            'cinder-infinidat')

        self.harness.update_config({})

        self.assertTrue(isinstance(
            self.harness.model.unit.status, BlockedStatus))

    @mock.patch('src.charm.CinderInfinidatCharm.install_pkgs')
    @mock.patch('src.charm.service_running')
    @mock.patch('src.charm.add_source')
    @mock.patch('src.charm.apt_update')
    @mock.patch('src.charm.apt_install')
    @mock.patch('ops_openstack.core.os_utils.ows_check_services_running')
    def test_protocol_config_validation(self, check, apt_install, apt_update,
                                        add_source, service_running,
                                        install_pkgs):
        install_pkgs.return_value = None
        service_running.return_value = True
        check.return_value = None, None

        add_source.return_value = None
        apt_install.return_value = None
        apt_update.return_value = None
        # Make sure we won't let incorrect value
        # for choice list on Cinder's side

        cfg = self._get_partial_config_sample()
        cfg.update({'protocol': PROTOCOL_INVALID_VALUE})

        self.harness.update_config(cfg)

        self.assertTrue(isinstance(
            self.harness.model.unit.status, BlockedStatus
        ))

        self.harness.update_config({'protocol': 'iscsi'})
        self.assertTrue(isinstance(
            self.harness.model.unit.status, BlockedStatus,
        ))

        self.harness.update_config({'iscsi-netspaces': 'A,B'})
        self.assertTrue(isinstance(
            self.harness.model.unit.status, ActiveStatus
        ))

        self.harness.update_config({'protocol': 'fc'}, unset='iscsi-netspaces')
        self.assertTrue(isinstance(
            self.harness.model.unit.status, ActiveStatus
        ))

    def test_cinder_conf_static_params(self):
        self.harness.update_config({})

        config = self.harness.framework.model.config

        self.assertIn(
            ('volume_driver', self.harness.charm.VOLUME_DRIVER),
            self.harness.charm.cinder_configuration(config)
        )

    def test_cinder_conf_backend_name_param(self):
        self.harness.update_config({})

        config = self.harness.framework.model.config
        self.assertIn(
            ('volume_backend_name', self.harness.model.app.name),
            self.harness.charm.cinder_configuration(config)
        )

        self.harness.update_config({'volume-backend-name': 'overridden'})
        self.assertIn(
            ('volume_backend_name', 'overridden'),
            self.harness.charm.cinder_configuration(config)
        )

    @mock.patch('src.charm.CinderInfinidatCharm.install_pkgs')
    @mock.patch('ops_openstack.core.os_utils.ows_check_services_running')
    def test_mandatory_config_params(self, check_services_running,
                                     install_pkgs):
        cfg = self._get_valid_config_sample()
        check_services_running.return_value = None, None
        install_pkgs.return_value = None

        self.harness.update_config(cfg)

        self.assertTrue(isinstance(
            self.harness.model.unit.status, ActiveStatus
        ))

        for p in self.harness.charm.MANDATORY_CONFIG:
            self.harness.update_config(unset=[p])
            # If the MANDATORY_CONFIG param has a default value,
            # it won't transition to the BlockedStatus because of
            # MANDATORY_CONFIG validation, so we unset it:
            if not self.harness.model.config.get(p):
                self.assertTrue(isinstance(
                    self.harness.model.unit.status, BlockedStatus
                ))

            self.harness.update_config(cfg)

            self.assertTrue(isinstance(
                self.harness.model.unit.status, ActiveStatus
            ))

    @mock.patch('src.charm.add_source')
    @mock.patch('src.charm.apt_update')
    @mock.patch('src.charm.apt_install')
    @mock.patch('src.charm.service_running')
    @mock.patch('src.charm.service_start')
    @mock.patch('src.charm.service_resume')
    @mock.patch('src.charm.lsb_release')
    def test_repo_management(self, lsb_release, svc_resume, svc_start,
                             svc_running, apt_install, apt_update, add_source):

        add_source.return_value = None
        apt_install.return_value = None
        apt_update.return_value = None
        svc_resume.return_value = None
        svc_start.return_value = None
        svc_running.return_value = None

        # we'll need the config the charm considers valid
        # in order to test repo management:
        cfg = self._get_valid_config_sample()

        dynamic_source = self._get_source('{distrib_codename}', 'main')

        # generate test data for both 'source' values that need substituion
        # and for the static ones

        test_data = []

        for release in UBUNTU_RELEASES:
            static_source = self._get_source(release, 'main')
            test_data.append(
                (dynamic_source, release,
                    self._get_source(release, 'main')),
            )
            test_data.append(
                (static_source, release, static_source),
            )

        for i in test_data:
            # distro codename the charm runs on
            lsb_release.return_value = {'DISTRIB_CODENAME': i[1]}

            # configure to use specific repo version
            cfg['install_sources'] = i[0]
            cfg['install_keys'] = KEY

            # on_config calls package installation
            self.harness.update_config(cfg)

            # make sure the repo management calls were correct
            add_source.assert_called_with(i[2], KEY)
            apt_install.assert_called_with(self.harness.charm.PACKAGES,
                                           fatal=True)

    def test_enable_ssl(self):
        pass
