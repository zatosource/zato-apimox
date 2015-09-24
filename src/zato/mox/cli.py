# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# Originally part of Zato - open-source ESB, SOA, REST, APIs and cloud integrations in Python
# https://zato.io

from __future__ import absolute_import, division, print_function

# stdlib
import logging

# Bunch
from bunch import bunchify

# Click
import click

# Zato
from zato.mox.common import PORT
from zato.mox.tls import TLSServer
from zato.mox.zmq_ import ZMQServer

# ################################################################################################################################

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ################################################################################################################################

@click.group()
@click.option('--config-dir', default='~/.config/zato/apimox/default')
def main(**kwargs):
    pass

# ################################################################################################################################

@click.command()
@click.pass_context
def tls_no_certs(ctx):
    s = TLSServer(PORT.TLS_NO_CERTS, False, bunchify(ctx.parent.params))
    s.run()

@click.command()
@click.pass_context
def tls_certs(ctx):
    s = TLSServer(PORT.TLS_CERTS, True, bunchify(ctx.parent.params))
    s.run()

# ################################################################################################################################

@click.command()
@click.pass_context
def zmq_pull(ctx):
    s = ZMQServer(PORT.ZMQ_PULL, 'PULL', bunchify(ctx.parent.params))
    s.run()

@click.command()
@click.pass_context
def zmq_sub(ctx):
    s = ZMQServer(PORT.ZMQ_SUB, 'SUB', bunchify(ctx.parent.params))
    s.run()

# ################################################################################################################################

main.add_command(tls_no_certs)
main.add_command(tls_certs)
main.add_command(zmq_pull)
main.add_command(zmq_sub)

if __name__ == '__main__':
    main()
