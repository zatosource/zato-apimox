# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function

# stdlib
import os, ssl
from ast import literal_eval
from httplib import INTERNAL_SERVER_ERROR, OK, PRECONDITION_FAILED, responses
from logging import getLogger
from string import digits
from traceback import format_exc
from urlparse import parse_qs
from uuid import uuid4

# Bunch
from bunch import Bunch

# gevent
from gevent import pywsgi

# parse
from parse import compile as parse_compile

# Validate
from validate import is_integer, VdtTypeError

# Zato
from zato.mox.common import BaseServer, HOST

# ################################################################################################################################

logger = getLogger(__name__)

# ################################################################################################################################

_EMPTY = uuid4().int
_PRECONDITION_FAILED = '{} {}'.format(PRECONDITION_FAILED, responses[PRECONDITION_FAILED])

DEFAULT_CONTENT_TYPE = 'text/plain'

JSON_CHAR = '{"[' + digits
XML_CHAR = '<'
JSON_XML = JSON_CHAR + XML_CHAR

JSON_CONTENT_TYPE = 'application/json'
XML_CONTENT_TYPE = 'text/xml'

CONTENT_TYPE = {
    'json': JSON_CONTENT_TYPE,
    'xml': XML_CONTENT_TYPE,
    'txt': DEFAULT_CONTENT_TYPE,
    'csv': 'text/csv',
}

class RequestMatch(object):

    def __init__(self, config, wsgi_environ):
        self.config = config
        self.wsgi_environ = wsgi_environ
        self.wsgi_environ_qs = self.get_qs_from_environ()
        self.status = '{} {}'.format(config.status, responses[config.status])
        self.content_type = config.content_type
        self.response = config.response
        self.qs_score = self.get_score()

    def __cmp__(self, other):
        return self.qs_score > other.qs_score

    def parse_qs_value(self, value):

        try:
            value = is_integer(value)
        except VdtTypeError:
            # OK, not an integer
            pass

        # Could be a dict or another simple type then
        try:
            value = literal_eval(value)
        except Exception:
            pass

        # OK, let's just treat it as string
        return value

    def get_qs_from_environ(self):
        out = {}
        for key, value in parse_qs(self.wsgi_environ['QUERY_STRING']).items():
            out[key] = self.parse_qs_value(value[0])

        return out

    def get_score(self):
        """ Assign 200 if a query string's element matched exactly what we've got in config,
        and 1 if the config allows for any value as long as keys are the same. It follows then
        that we allow for up to 200 query parameters on input which should be well enough.
        """
        any_value_add = 1
        value_add = 200

        score = 0

        for wsgi_key, wsgi_value in self.wsgi_environ_qs.items():
            if wsgi_key in self.config.qs_values:

                config_value = self.config.qs_values.get(wsgi_key, _EMPTY)

                # Config requires an exact value
                if config_value and config_value != _EMPTY:
                    if config_value == wsgi_value:
                        score += value_add

                # Config requires any value
                else:
                    score += any_value_add

        logger.info('Score {} for `{}` ({} {})'.format(
            score, self.config.name, self.wsgi_environ['PATH_INFO'], self.wsgi_environ_qs))

        return score

# ################################################################################################################################

class TLSServer(BaseServer):

    SERVER_TYPE = 'http'

    def __init__(self, port, require_certs=False, cli_params=None):
        super(TLSServer, self).__init__(cli_params)
        self.port = port
        self._require_certs = require_certs
        self.require_certs = ssl.CERT_REQUIRED if require_certs else ssl.CERT_OPTIONAL
        self.full_address = 'https://{}:{}'.format(HOST, self.port)
        self.set_up()

    def run(self):
        pem_dir = os.path.join(self.config.dir, '..', 'pem')

        tls_args = {
            'keyfile': os.path.join(pem_dir, 'server.key.pem'),
            'certfile': os.path.join(pem_dir, 'server.cert.pem'),
            'ca_certs': os.path.join(pem_dir, 'ca.cert.pem'),
            'cert_reqs': self.require_certs,
            'server_side': True,
        }

        logger.info('{} listening on {} (client certs: {})'.format(self.__class__.__name__,
            self.full_address, 'required' if self._require_certs else 'optional'))

        server = pywsgi.WSGIServer((HOST, self.port), self.on_request, **tls_args)
        server.serve_forever()

    def on_request(self, environ, start_response):
        mock_name, status, content_type, response = self.match(environ)

        # We've got everything we need, only logging left.

        req = [' Body=`{}`'.format(environ['wsgi.input'].read())]
        for key, value in sorted(environ.items()):
            if key[0] == key[0].upper():
                req.append('  {}=`{}`'.format(key, value))

        msg = '\n\n=====Request===== \n{}'.format('\n'.join(req))

        msg += '\n\n====Response==== \n Mock=`{}`\n Status=`{}`\n Content-type=`{}`\n Body=`{}`\n'.format(
            mock_name, status, content_type, response)

        msg += '\n'

        logger.info(msg)

        start_response(status, [(b'Content-Type', content_type)])
        return [response]

    def match(self, environ):
        matches = []

        for item in self.config.mocks_config.values():

            if not item.url_path_compiled.parse(environ['PATH_INFO']):
                continue

            method = item.get('method')
            if method and method != environ['REQUEST_METHOD']:
                continue

            matches.append(RequestMatch(item, environ))

        if not matches:
            return None, _PRECONDITION_FAILED, DEFAULT_CONTENT_TYPE, 'No matching mock found\n'

        # Find the max match match and then make sure it's only one of that score
        # If it isn't, it's a 409 Conflict because we don't know which response to serve.
        match = max(matches)
        found = 0
        conflicting = []
        for m in matches:
            if m.qs_score == match.qs_score:
                found += 1
                conflicting.append(m)

        if found > 1:
            return None, _PRECONDITION_FAILED, DEFAULT_CONTENT_TYPE, 'Multiple mocks matched request: {}\n'.format(
                [m.config.name for m in conflicting])

        return match.config.name, match.status, match.content_type, match.response

    def set_up(self):

        for name, config in sorted(self.config.mocks_config.items()):

            config.url_path_compiled = parse_compile(config.url_path)

            qs_values = {}
            for item, value in config.items():
                if item.startswith('qs_'):

                    if value:
                        try:
                            value = literal_eval(value.strip())
                        except ValueError:
                            pass # Ok, not an int/dict or another simple value
                    else:
                        value = ''

                    qs_values[item.split('qs_')[1]] = value
                    config.pop(item)

            config.qs_values = qs_values
            config.status = int(config.get('status', OK))
            config.method = config.get('method', 'GET')
            config.name = name

            response = config.get('response')

            if response:

                has_inline_resp = response[0] in JSON_XML

                if has_inline_resp:
                    _type = 'xml' if response[0] == XML_CHAR else 'json'
                else:
                    _type = response.split('.')[-1]
                    resp_dir = os.path.join(self.config.dir, 'response', _type)

                    try:
                        full_path = os.path.join(resp_dir, config.response)
                        response = open(full_path).read()
                    except IOError, e:
                        logger.warn('Could not open `{}`, e:`{}`'.format(full_path, format_exc(e)))
                        response = '(Response not found)\n'
                        config.status = INTERNAL_SERVER_ERROR

                if not config.get('content_type'):
                    config.content_type = CONTENT_TYPE.get(_type, DEFAULT_CONTENT_TYPE)

            else:
                if not config.get('content_type'):
                    config.content_type = DEFAULT_CONTENT_TYPE

            config.response = response or ''

            qs_info = '(qs: {})'.format(config.qs_values)
            logger.info('Mounting `{}` on {}{} {}'.format(name, self.full_address, config.url_path, qs_info))

# ################################################################################################################################
