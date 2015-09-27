# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function

# stdlib
from logging import getLogger

# ZeroMQ
import zmq

# Zato
from zato.apimox.common import BaseServer

# ################################################################################################################################

logger = getLogger(__name__)

# ################################################################################################################################

class ZMQServer(BaseServer):

    SERVER_TYPE = 'zmq'

    def __init__(self, log_type, config_dir, socket_type):
        super(ZMQServer, self).__init__(log_type, config_dir)
        self.socket_type = socket_type

    def run(self):
        config = self.config.mocks_config.apimox

        address = 'tcp://{}:{}'.format(config.host, getattr(config, '{}_port'.format(self.socket_type)))
        context = zmq.Context()
        socket = context.socket(getattr(zmq, self.socket_type.upper()))

        if self.socket_type == 'sub':
            socket.setsockopt(zmq.SUBSCRIBE, config.sub_prefix)
            prefix_msg = '(prefix: {}) '.format(config.sub_prefix or None)
        else:
            prefix_msg = ''

        socket.bind(address)

        logger.info('ZMQ %s %slistening on %s', self.socket_type.upper(), prefix_msg, address)

        while True:
            msg = socket.recv()
            logger.info(msg)
