# -*- coding: utf-8 -*-

import mock
from pyramid import testing
import pytest

from h.api.events import AnnotationEvent

from h import subscribers


class FakeMailer(object):
    def __init__(self):
        self.calls = []

    def __call__(self, recipients, subject, body, html):
        self.calls.append((recipients, subject, body, html))


def fake_generate(data=None):
    def generate(*args):
        if data:
            for item in data:
                yield item
    return generate


class TestSendReplyNotifications(object):
    def test_calls_generate_with_request_annotation_and_action(self):
        send = FakeMailer()
        generate = mock.Mock(spec_set=[], return_value=[])
        event = AnnotationEvent(mock.sentinel.request,
                                mock.sentinel.annotation,
                                mock.sentinel.action)

        subscribers.send_reply_notifications(event,
                                             generate=generate,
                                             send=send)

        generate.assert_called_once_with(mock.sentinel.request,
                                         mock.sentinel.annotation,
                                         mock.sentinel.action)

    def test_sends_mail_generated_by_generate(self):
        send = FakeMailer()
        generate = fake_generate([
            ('Your email', 'Text body', 'HTML body', ['foo@example.com']),
            ('Safari', 'Giraffes', '<p>Elephants!</p>', ['bar@example.com']),
        ])
        event = AnnotationEvent(None, None, None)

        subscribers.send_reply_notifications(event,
                                             generate=generate,
                                             send=send)

        assert send.calls == [
            (['foo@example.com'], 'Your email', 'Text body', 'HTML body'),
            (['bar@example.com'], 'Safari', 'Giraffes', '<p>Elephants!</p>'),
        ]

    def test_catches_exceptions_and_reports_to_sentry(self):
        send = FakeMailer()
        generate = mock.Mock(spec_set=[], side_effect=RuntimeError('asplode!'))
        request = testing.DummyRequest(sentry=mock.Mock(), debug=False)
        event = AnnotationEvent(request, None, None)

        subscribers.send_reply_notifications(event,
                                             generate=generate,
                                             send=send)

        event.request.sentry.captureException.assert_called_once_with()

    def test_reraises_exceptions_in_debug_mode(self):
        send = FakeMailer()
        generate = mock.Mock(spec_set=[], side_effect=RuntimeError('asplode!'))
        request = testing.DummyRequest(sentry=mock.Mock(), debug=True)
        event = AnnotationEvent(request, None, None)

        with pytest.raises(RuntimeError):
            subscribers.send_reply_notifications(event,
                                                 generate=generate,
                                                 send=send)
