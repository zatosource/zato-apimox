# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function

# stdlib
import os

# Bunch
from bunch import Bunch, bunchify

# ConfigObj
from configobj import ConfigObj

HOST = '0.0.0.0'

class PORT:
    TLS_NO_CERTS = 63039
    TLS_CERTS = 49460
    ZMQ_PULL = 33669
    ZMQ_SUB = 59482

class BaseServer(object):

    SERVER_TYPE = None

    def __init__(self, cli_params):
        self.cli_params = cli_params

        self.config = Bunch()
        self.config.dir = None
        self.config.params = cli_params
        self.config.mocks = Bunch()
        self.config.mocks_config = self.get_mocks_config(self.cli_params.config_dir)

    def get_mocks_config(self, config_dir):
        self.config.dir = os.path.abspath(os.path.join(os.path.expanduser(config_dir), self.SERVER_TYPE))
        config_path = os.path.join(self.config.dir, 'config.ini')
        return bunchify(ConfigObj(open(config_path)))

    def set_up(self):
        raise NotImplementedError('Must be implemented in subclasses')
