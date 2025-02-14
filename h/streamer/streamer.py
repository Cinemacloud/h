# -*- coding: utf-8 -*-

import logging
import sys

import gevent

from h import db
from h import stats
from h.queue import resolve_topic
from h.streamer import nsq
from h.streamer import websocket

log = logging.getLogger(__name__)

# Queue of messages to process, from both client websockets and NSQ topics to
# which the streamer is subscribed.
#
# The maxsize ensures that memory used by this queue is bounded. Producers
# writing to the queue must consider their behaviour when the queue is full,
# using .put(...) with a timeout or .put_nowait(...) as appropriate.
WORK_QUEUE = gevent.queue.Queue(maxsize=4096)

# NSQ message topics that the streamer processes messages from
ANNOTATIONS_TOPIC = 'annotations'
USER_TOPIC = 'user'


class UnknownMessageType(Exception):
    """Raised if a message in the work queue if of an unknown type."""


def start(event):
    """
    Start some greenlets to process the incoming data from NSQ.

    This subscriber is called when the application is booted, and kicks off
    greenlets running `process_queue` for each NSQ topic we subscribe to. The
    function does not block.
    """
    settings = event.app.registry.settings
    greenlets = [
        # Start greenlets to process messages from NSQ
        gevent.spawn(nsq.process_nsq_topic,
                     settings,
                     ANNOTATIONS_TOPIC,
                     WORK_QUEUE),
        gevent.spawn(nsq.process_nsq_topic,
                     settings,
                     USER_TOPIC,
                     WORK_QUEUE),
        # A greenlet to periodically report to statsd
        gevent.spawn(report_stats, settings),
        # And one to process the queued work
        gevent.spawn(process_work_queue, settings, WORK_QUEUE)
    ]

    # Start a "greenlet of last resort" to monitor the worker greenlets and
    # bail if any unexpected errors occur.
    gevent.spawn(supervise, greenlets)


def process_work_queue(settings, queue, session_factory=db.Session):
    """
    Process each message from the queue in turn, handling exceptions.

    This is the core of the streamer: we pull messages off the work queue,
    dispatching them as appropriate. The handling of each message is wrapped in
    code that ensures the database session is appropriately committed and
    closed between messages.
    """
    session = session_factory()
    annotations_topic = resolve_topic(ANNOTATIONS_TOPIC, settings=settings)
    user_topic = resolve_topic(USER_TOPIC, settings=settings)
    topic_handlers = {
        annotations_topic: nsq.handle_annotation_event,
        user_topic: nsq.handle_user_event,
    }

    for msg in queue:
        try:
            # All access to the database in the streamer is currently
            # read-only, so enforce that:
            session.execute("SET TRANSACTION "
                            "ISOLATION LEVEL SERIALIZABLE "
                            "READ ONLY "
                            "DEFERRABLE")

            if isinstance(msg, nsq.Message):
                nsq.handle_message(msg, topic_handlers=topic_handlers)
            elif isinstance(msg, websocket.Message):
                websocket.handle_message(msg)
            else:
                raise UnknownMessageType(repr(msg))

        except (KeyboardInterrupt, SystemExit):
            session.rollback()
            raise
        except:
            log.exception('Caught exception handling streamer message:')
            session.rollback()
        else:
            session.commit()
        finally:
            session.close()


def report_stats(settings):
    client = stats.get_client(settings)
    while True:
        client.gauge('streamer.connected_clients',
                     len(websocket.WebSocket.instances))
        client.gauge('streamer.queue_length', WORK_QUEUE.qsize())
        gevent.sleep(10)


def supervise(greenlets):
    try:
        gevent.joinall(greenlets, raise_error=True)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        log.critical('Unexpected exception in streamer greenlet:',
                     exc_info=True)
    else:
        log.critical('Unexpected early exit of streamer greenlets. Aborting!')
    # If the worker greenlets exit early, our best option is to kill the worker
    # process and let the app server take care of restarting it.
    sys.exit(1)


def includeme(config):
    # Store a reference to the work queue on the registry for websocket clients
    config.registry['streamer.work_queue'] = WORK_QUEUE
