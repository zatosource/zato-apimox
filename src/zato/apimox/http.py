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

# gevent
from gevent import pywsgi

# parse
from parse import compile as parse_compile

# Validate
from validate import is_integer, VdtTypeError

# Zato
from zato.apimox.common import BaseServer

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

# ################################################################################################################################

class MatchData(object):
    def __init__(self, match, name=None, status=None, content_type=None, response=None):
        self.match = match
        self.name = name
        self.status = status
        self.content_type = content_type
        self.response = response

# ################################################################################################################################

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

# ################################################################################################################################

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

# ################################################################################################################################

    def get_qs_from_environ(self):
        out = {}
        for key, value in parse_qs(self.wsgi_environ['QUERY_STRING']).items():
            out[key] = self.parse_qs_value(value[0])

        return out

# ################################################################################################################################

    def get_score(self):
        """ Assign 200 if a query string's element matched exactly what we've got in config,
        and 1 if the config allows for any value as long as keys are the same. It follows then
        that we allow for up to 200 query parameters on input which should be well enough.
        """
        any_value_add = 1
        value_add = 200

        score = 0

        # Go through the request's parameters and add score for each element matching the config
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

        # Now go through the config and substract score for each element in config which is not present in request
        for config_key in self.config.qs_values:
            config_value = self.config.qs_values.get(config_key, _EMPTY)

            if config_key not in self.wsgi_environ_qs:
                if config_value != _EMPTY:
                    score -= value_add
                else:
                    score -= any_value_add

        logger.info('Score {} for `{}` ({} {})'.format(
            score, self.config.name, self.wsgi_environ['PATH_INFO'], self.wsgi_environ_qs))

        return score

# ################################################################################################################################

class HTTPServer(BaseServer):

    SERVER_TYPE = 'http'

    def __init__(self, needs_tls=False, require_certs=False, log_type=None, config_dir=None):
        super(HTTPServer, self).__init__(log_type, config_dir)

        config = self.config.mocks_config.apimox

        if needs_tls:
            if require_certs:
                port = config.http_tls_client_certs_port
            else:
                port = config.http_tls_port
        else:
            port = config.http_plain_port

        self.port = port

        self._require_certs = require_certs
        self.needs_tls = needs_tls
        self.require_certs = ssl.CERT_REQUIRED if require_certs else ssl.CERT_OPTIONAL
        self.full_address = 'http{}://{}:{}'.format('s' if needs_tls else '', config.host, self.port)
        self.set_up()

# ################################################################################################################################

    def run(self):

        tls_args = {}

        if self.needs_tls:
            pem_dir = os.path.join(self.config.dir, '..', 'pem')
            tls_args.update({
                'keyfile': os.path.join(pem_dir, 'server.key.pem'),
                'certfile': os.path.join(pem_dir, 'server.cert.pem'),
                'ca_certs': os.path.join(pem_dir, 'ca.cert.pem'),
                'cert_reqs': self.require_certs,
                'server_side': True,
            })

        msg = '{}{} listening on {}'.format('TLS ' if self.needs_tls else '', self.__class__.__name__, self.full_address)
        if self.needs_tls:
            msg += ' (client certs: {})'.format('required' if self._require_certs else 'optional')

        logger.info(msg)

        server = pywsgi.WSGIServer((self.config.mocks_config.apimox.host, int(self.port)), self.on_request, **tls_args)
        server.serve_forever()

# ################################################################################################################################

    def log_req_resp(self, mock_name, status, response, resp_headers, environ):
        """ Log both request and response in an easy to read format.
        """
        req = [' Body=`{}`'.format(environ['wsgi.input'].read())]
        for key, value in sorted(environ.items()):
            if key[0] == key[0].upper():
                req.append('  {}=`{}`'.format(key, value))

        msg = '\n\n=====Request===== \n{}'.format('\n'.join(req))
        msg += '\n\n====Response==== \n Mock=`{}`\n Status=`{}`\n Headers=\n{}\n Body=`{}`\n'.format(
            mock_name, status, '\n'.join(' `{}`=`{}`'.format(key, value) for key, value in sorted(resp_headers)), response)

        msg += '\n'

        logger.info(msg)

# ################################################################################################################################

    def set_resp_headers(self, config, environ, content_type):
        """ Returns headers for the response. Note that Content-Type can be set either
        in one of headers or through the content_type explicitly and the latter takes precedence.
        """
        out = []
        has_content_type = False
        for key, value in config.resp_headers.items():
            if key.lower() == 'content-type':
                has_content_type = True
            out.append((key, value))

        if not has_content_type:
            out.append(('Content-Type', content_type))

        return out

# ################################################################################################################################

    def on_request(self, environ, start_response):

        data = self.match(environ)

        # We don't know if we match anything or perhaps more than one thing
        if data.match:
            name = data.match.config.name
            status = data.match.status
            content_type = data.match.content_type
            response = data.match.response
        else:
            name = data.name
            status = data.status
            content_type = data.content_type
            response = data.response

        # Set response headers, if any
        resp_headers = self.set_resp_headers(data.match.config, environ, content_type) if data.match else []

        # Now only logging is left
        self.log_req_resp(name, status, response, resp_headers, environ)

        start_response(status, resp_headers)
        return [response]

# ################################################################################################################################

    def match(self, environ):
        matches = []

        for name, item in self.config.mocks_config.items():

            # Ignore our own config
            if name == 'apimox':
                continue

            if not item.url_path_compiled.parse(environ['PATH_INFO']):
                continue

            method = item.get('method')
            if method and method != environ['REQUEST_METHOD']:
                continue

            matches.append(RequestMatch(item, environ))

        if not matches:
            return MatchData(None, None, _PRECONDITION_FAILED, DEFAULT_CONTENT_TYPE, 'No matching mock found\n')

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
            return MatchData(None, None, _PRECONDITION_FAILED, DEFAULT_CONTENT_TYPE, 'Multiple mocks matched request: {}\n'.format(
                sorted([m.config.name for m in conflicting])))

        return MatchData(match)

# ################################################################################################################################

    def get_file(self, config, name, default=''):

        ext = name.split('.')[-1]
        resp_dir = os.path.join(self.config.dir, 'response', ext)

        try:
            full_path = os.path.join(resp_dir, name)
            data = open(full_path).read()
        except IOError, e:
            logger.warn('Could not open `{}`, e:`{}`'.format(full_path, format_exc(e)))
            return False, ext, default
        else:
            return True, ext, data

# ################################################################################################################################

    def get_qs_values(self, config):
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

        return qs_values

    def get_response(self, config):
        response = config.get('response')

        if response:
            has_inline_resp = response[0] in JSON_XML

            if has_inline_resp:
                ext = 'xml' if response[0] == XML_CHAR else 'json'
            else:
                is_ok, ext, response = self.get_file(config, response, '(Response not found)\n')
                if not is_ok:
                    config.status = INTERNAL_SERVER_ERROR

            if not config.get('content_type'):
                config.content_type = CONTENT_TYPE.get(ext, DEFAULT_CONTENT_TYPE)

        else:
            if not config.get('content_type'):
                config.content_type = DEFAULT_CONTENT_TYPE

        return response or ''

    def get_resp_headers(self, config):
        resp_headers = {}

        file_text_headers = config.pop('resp_headers', None)
        if file_text_headers:
            is_ok, _, data = self.get_file(config, file_text_headers)
            if is_ok:
                for line in data.splitlines():
                    split_at = line.find('=')
                    key = line[0:split_at].strip()
                    value = line[split_at+1:].strip()
                    resp_headers[key] = value

        for orig_key, value in config.items():
            if orig_key.startswith('resp_header_'):

                key = orig_key.replace('resp_header_', '', 1)

                # Perhaps the value actually points to a file it can be found in
                if value.endswith('.txt'):
                    _, _, value = self.get_file(config, value, '(Configuration error)')

                resp_headers[key] = value

                # No namespace clutter
                config.pop(orig_key)

        return resp_headers

# ################################################################################################################################

    def set_up(self):

        for name, config in sorted(self.config.mocks_config.items()):

            # Ignore our own config
            if name == 'apimox':
                continue

            config.name = name
            config.url_path_compiled = parse_compile(config.url_path)
            config.status = int(config.get('status', OK))
            config.method = config.get('method', 'GET')
            config.qs_values = self.get_qs_values(config)
            config.response = self.get_response(config)
            config.resp_headers = self.get_resp_headers(config)

            qs_info = '(qs: {})'.format(config.qs_values)
            logger.info('Mounting `{}` on {}{} {}'.format(name, self.full_address, config.url_path, qs_info))

# ################################################################################################################################
