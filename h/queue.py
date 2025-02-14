# -*- coding: utf-8 -*-
from pyramid.settings import aslist

import json
import gnsq


class NamespacedNsqd(object):
    def __init__(self, namespace, *args, **kwargs):
        self.client = gnsq.Nsqd(*args, **kwargs)
        self.namespace = namespace

    def publish(self, topic, data):
        topic = resolve_topic(topic, namespace=self.namespace)
        if not isinstance(data, str):
            data = json.dumps(data)
        return self.client.publish(topic, data)


def get_reader(settings, topic, channel, sentry_client=None):
    """
    Get a :py:class:`gnsq.Reader` instance configured to connect to the
    nsqd reader addresses specified in settings. The reader will read from
    the specified topic and channel.

    The caller is responsible for adding appropriate `on_message` hooks and
    starting the reader.
    """
    topic = resolve_topic(topic, settings=settings)
    addrs = aslist(settings.get('nsq.reader.addresses', 'localhost:4150'))
    reader = gnsq.Reader(topic, channel, nsqd_tcp_addresses=addrs)

    if sentry_client is not None:
        _attach_error_handlers(reader, sentry_client)

    return reader


def get_writer(settings):
    """
    Get a :py:class:`gnsq.Nsqd` instance configured to connect to the nsqd
    writer address configured in settings. The writer communicates over the
    nsq HTTP API and does not hold a connection open to the nsq instance.
    """
    ns = settings.get('nsq.namespace')
    addr = settings.get('nsq.writer.address', 'localhost:4151')
    hostname, port = addr.split(':', 1)
    nsqd = NamespacedNsqd(ns, hostname, http_port=port)
    return nsqd


def resolve_topic(topic, namespace=None, settings=None):
    """
    Return a resolved name for the requested topic.

    This uses the passed `namespace` to resolve the topic name, or,
    alternatively, a pyramid settings object.
    """
    if namespace is not None and settings is not None:
        raise ValueError('you must provide only one of namespace or settings')

    if settings is not None:
        ns = settings.get('nsq.namespace')
    else:
        ns = namespace

    if ns is not None:
        return '{0}-{1}'.format(ns, topic)

    return topic


def _attach_error_handlers(reader, client):
    """
    Attach error handlers to a queue reader that report to a Sentry client.

    :param reader: a reader instance
    :type reader: gnsq.Reader

    :param client: a Raven client instance
    :type client: raven.Client
    """
    def _capture_error(reader, error=None):
        exc_info = (type(error), error, None)
        extra = {'topic': reader.topic, 'channel': reader.channel}
        client.captureException(exc_info=exc_info, extra=extra)
    reader.on_error.connect(_capture_error, weak=False)

    def _capture_exception(reader, message=None, error=None):
        extra = {'topic': reader.topic, 'channel': reader.channel}
        if message is not None:
            extra['message'] = message.body
        client.captureException(exc_info=True, extra=extra)
    reader.on_exception.connect(_capture_exception, weak=False)

    def _capture_giving_up(reader, message=None):
        extra = {'topic': reader.topic, 'channel': reader.channel}
        if message is not None:
            extra['message'] = message.body
        client.captureMessage('Giving up on message', extra=extra)
    reader.on_giving_up.connect(_capture_giving_up, weak=False)


def _get_queue_reader(request, topic, channel):
    return get_reader(request.registry.settings,
                      topic,
                      channel,
                      sentry_client=request.sentry)


def includeme(config):
    config.add_request_method(_get_queue_reader, name='get_queue_reader')
    config.add_request_method(
        lambda req: get_writer(req.registry.settings),
        name='get_queue_writer'
    )
