# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# Originally part of Zato - open-source ESB, SOA, REST, APIs and cloud integrations in Python
# https://zato.io

from __future__ import absolute_import, division, print_function

# Zato
from zato.apimox.http import HTTPServer
from zato.apimox.zmq_ import ZMQServer

def handle(path, args=None):
    args = args or {}
    server_type = args.get('type') or 'http-plain'
    log_type = server_type.replace('-', '_').replace('http_', '').replace('zmq_', '')

    if server_type.startswith('http'):
        server = HTTPServer('tls' in server_type, 'client-certs' in server_type, log_type, path)

    elif server_type.startswith('zmq'):
        server = ZMQServer(log_type, path, server_type.replace('zmq-', ''))

    else:
        raise Exception('Unrecognized server type: `{}`'.format(server_type))

    # Good to go now
    server.run()
