#! /usr/bin/env python3

# Copyright 2021 Canonical Ltd
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

from ops_openstack.plugins.classes import CinderStoragePluginCharm
from ops.main import main

from charmhelpers.core.host import (
    service_start,
    service_running,
    service_resume,
    install_ca_cert,
    lsb_release,
)

from charmhelpers.fetch import (
    apt_install,
    apt_update,
    add_source,
)

from ops.model import (
    ActiveStatus,
    BlockedStatus,
)

import logging


class CinderInfinidatCharm(CinderStoragePluginCharm):

    PACKAGES = ['python3-infinisdk', 'infinishell']

    MANDATORY_CONFIG = ['infinibox-ip', 'infinibox-login',
                        'infinibox-password', 'pool-name', 'protocol']

    REQUIRED_RELATIONS = ['storage-backend']

    RESTART_MAP = {'/etc/iscsi/iscsid.conf': ['iscsid']}

    PROTOCOL_VALID_VALUES = ['fc', 'iscsi']
    VOLUME_DRIVER = 'cinder.volume.drivers.infinidat.InfiniboxVolumeDriver'

    DISTRIB_CODENAME_PATTERN = '$codename'

    DEFAULT_REPO_BASEURL = \
        'https://repo.infinidat.com/packages/main-stable/apt/linux-ubuntu'

    # Overriden from the parent. May be set depending on the charm's properties
    stateless = True
    active_active = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register_status_check(self.check_mandatory_params)
        self.register_status_check(self.check_protocol_valid)
        self.register_status_check(self.check_iscsi_netspaces)

    def check_protocol_valid(self):
        if self.config.get('protocol').lower() not in \
                self.PROTOCOL_VALID_VALUES:
            return BlockedStatus(
                "valid values for 'protocol' are " +
                ','.join(self.PROTOCOL_VALID_VALUES)
            )
        return ActiveStatus()

    def check_iscsi_netspaces(self):
        if self.config.get('protocol').lower() == 'iscsi' \
                and not self.config.get('iscsi-netspaces'):

            return BlockedStatus("'iscsi-netspaces' must be set "
                                 "when using 'iscsi' protocol")
        return ActiveStatus()

    def _validate_config(self):
        for func in self.custom_status_checks:
            _result = func()

            if not isinstance(_result, ActiveStatus):
                self.unit.status = _result
                logging.error(_result.message)
                return False
        return True

    def check_mandatory_params(self):
        """
        Implements more detailed validation of the config params.
        Also prevents cinder config from updating if some of the crucial charm
        options are not specified. Add more checks that should prevent
        cinder.conf from updating.
        """

        missing = []
        for param in self.MANDATORY_CONFIG:
            if param not in self.config:
                missing.append(param)
        if missing:
            return BlockedStatus(
                'missing option(s): ' + ','.join(missing)
            )
        return ActiveStatus()

    def _install_ca_cert(self):
        config = dict(self.framework.model.config)
        install_ca_cert(config.get('infinibox-ssl-ca'))

    def _on_config(self, event):

        self._install_ca_cert()

        if not self._validate_config():
            return

        # This is called to trigger set_data()
        # for the cinder relation on a config change.
        self.on_config(event)
        try:
            self.install_pkgs()
        except Exception as e:
            self.unit.status = BlockedStatus(str(e))

        # See self._stored.is_started in OSBaseCharm
        # Without this line here the charm will be stuck in 'waiting' until
        # all the config parameters are provided correctly by the user
        # completely bypassing 'blocked' status, and we need 'blocked' status
        # because human intervention is needed.

        self._stored.is_started = True
        self.update_status()

    def on_storage_backend(self, event):
        # Prevent broken config from being propagated to Cinder
        if self._validate_config():
            super().on_storage_backend(event)
        else:
            event.defer()

    def install_pkgs(self):
        logging.info("Installing packages")

        # we implement $codename expansion here
        # see the default value for 'source' in config.yaml
        if self.model.config.get('install_sources'):
            distrib_codename = lsb_release()['DISTRIB_CODENAME'].lower()
            add_source(
                self.model.config['install_sources']
                    .format(distrib_codename=distrib_codename),
                self.model.config.get('install_keys'))
        apt_update(fatal=True)
        apt_install(self.PACKAGES, fatal=True)
        self.update_status()

    def on_install(self, event):
        self.install_pkgs()

        # start iscsid if it is not running
        # neded for cinder's boot-from-volume
        if not service_running('iscsid'):
            logging.info('Starting iscsid service')
            service_resume('iscsid')
            service_start('iscsid')

        self.update_status()

    def cinder_configuration(self, config):
        # Return the configuration to be set by the principal.
        backend_name = config.get('volume-backend-name',
                                  self.framework.model.app.name)
        # As per https://docs.openstack.org/cinder/latest/configuration/block-storage/drivers/infinidat-volume-driver.html # noqa: E501

        options = [
            ('volume_driver', self.VOLUME_DRIVER),
            ('use_multipath_for_image_xfer', config.get('use-multipath')),
            ('infinidat_storage_protocol', config.get('protocol')),
            ('volume_backend_name', backend_name),
            ('san_ip', config.get('infinibox-ip')),
            ('san_login', config.get('infinibox-login')),
            ('san_password', config.get('infinibox-password')),
            ('infinidat_iscsi_netspaces', config.get('iscsi-netspaces')),
        ]

        use_chap_auth = config.get('use-chap', False)
        options.extend([
            ('use_chap_auth', use_chap_auth),
        ])

        if use_chap_auth:
            options.extend([
                ('chap_username', config.get('chap-username')),
                ('chap_password', config.get('chap-password')),
            ])

        options.extend([
            ('infinidat_pool_name', config.get('pool-name')),
            ('infinidat_use_compression', config.get('use-compression')),
            ('san_thin_provision', config.get('thin-provision')),
            ('infinidat_use_ssl', config.get('infinibox-use-ssl')),
        ])

        return options


if __name__ == '__main__':
    main(CinderInfinidatCharm)
