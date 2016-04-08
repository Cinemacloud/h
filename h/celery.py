# -*- coding: utf-8 -*-

"""
Celery worker bootstrap and configuration.

This module configures a Celery application for processing background jobs, and
integrates it with the Pyramid application by attaching a bootstrapped fake
"request" object to the application where it can be retrieved by tasks.
"""

from __future__ import absolute_import

import logging
import os

from celery import Celery
from celery import signals
from celery.utils.log import get_task_logger
from pyramid import paster
from pyramid.request import Request

__all__ = (
    'celery',
    'get_task_logger',
)

log = logging.getLogger(__name__)

celery = Celery('h')
celery.conf.update(
    # Default to using database number 10 so we don't conflict with the session
    # store.
    BROKER_URL=os.environ.get('BROKER_URL', 'redis://localhost:6379/10'),
    CELERY_ACCEPT_CONTENT=['json'],
    CELERY_DISABLE_RATE_LIMITS=True,
    CELERY_IGNORE_RESULT=True,
    CELERY_IMPORTS=('h.mailer', 'h.nipsa.worker'),
    CELERY_TASK_SERIALIZER='json',
)


@signals.worker_init.connect
def bootstrap_worker(sender, **kwargs):
    base_url = os.environ.get('APP_URL')
    config_uri = os.environ.get('CONFIG_URI', 'conf/app.ini')

    paster.setup_logging(config_uri)

    if base_url is None:
        base_url = 'http://localhost'
        log.warn('APP_URL not found in environment, using default: %s',
                 base_url)

    request = Request.blank('/', base_url=base_url)
    env = paster.bootstrap(config_uri, request=request)
    request.root = env['root']

    sender.app.request = request


def main():
    celery.start()
