# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# Originally part of Zato - open-source ESB, SOA, REST, APIs and cloud integrations in Python
# https://zato.io

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from setuptools import setup, find_packages

version = '1.1'

LONG_DESCRIPTION = ''

def parse_requirements(requirements):
    with open(requirements) as f:
        return [line.strip('\n') for line in f if line.strip('\n') and not line.startswith('#')]

setup(
      name = 'zato-apimox',
      version = version,

      scripts = ['src/zato/apimox/console/apimox'],

      author = 'Dariusz Suchojad',
      author_email = 'dsuch at zato.io',
      url = 'https://zato.io/docs',
      description = 'Zato API Mox - Human Friendly HTTP and ZeroMQ mocks',
      long_description = LONG_DESCRIPTION,
      platforms = ['OS Independent'],
      license = 'GNU Lesser General Public License v3 (LGPLv3)',

      package_dir = {'':b'src'},
      packages = find_packages(b'src'),

      namespace_packages = [b'zato'],
      install_requires = parse_requirements(
          os.path.join(os.path.dirname(os.path.realpath(__file__)), 'requirements.txt')),

      zip_safe = False,

      classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Other Audience',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Intended Audience :: Developers',
        'Topic :: Communications',
        'Topic :: Education :: Testing',
        'Topic :: Internet',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Networking',
        'Topic :: Utilities',
        ],
)
