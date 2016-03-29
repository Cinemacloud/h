# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest
import mock
from mock import patch
from pyramid.testing import DummyRequest

from h import db
from h.api import storage
from h.api.models.annotation import Annotation
from h.api.models.document import Document, DocumentURI


def test_fetch_annotation_elastic(postgres_enabled, ElasticAnnotation):
    postgres_enabled.return_value = False
    ElasticAnnotation.fetch.return_value = mock.Mock()

    actual = storage.fetch_annotation(DummyRequest(), '123')

    ElasticAnnotation.fetch.assert_called_once_with('123')
    assert ElasticAnnotation.fetch.return_value == actual


def test_fetch_annotation_postgres(postgres_enabled):
    request = DummyRequest(db=db.Session)
    postgres_enabled.return_value = True

    annotation = Annotation(userid='luke')
    db.Session.add(annotation)
    db.Session.flush()

    actual = storage.fetch_annotation(request, annotation.id)
    assert annotation == actual


def test_expand_uri_postgres_no_document(postgres_enabled):
    request = DummyRequest(db=db.Session)
    postgres_enabled.return_value = True

    actual = storage.expand_uri(request, 'http://example.com/')
    assert actual == ['http://example.com/']


def test_expand_uri_elastic_no_document(postgres_enabled, document_model):
    postgres_enabled.return_value = False
    request = DummyRequest()
    document_model.get_by_uri.return_value = None
    assert storage.expand_uri(request, "http://example.com/") == [
            "http://example.com/"]


def test_expand_uri_postgres_document_doesnt_expand_canonical_uris(postgres_enabled):
    request = DummyRequest(db=db.Session)
    postgres_enabled.return_value = True

    document = Document(document_uris=[
        DocumentURI(uri='http://foo.com/', claimant='http://example.com'),
        DocumentURI(uri='http://bar.com/', claimant='http://example.com'),
        DocumentURI(uri='http://example.com/', type='rel-canonical', claimant='http://example.com'),
    ])
    db.Session.add(document)
    db.Session.flush()

    assert storage.expand_uri(request, "http://example.com/") == [
            "http://example.com/"]


def test_expand_uri_elastic_document_doesnt_expand_canonical_uris(postgres_enabled, document_model):
    postgres_enabled.return_value = False

    request = DummyRequest()
    document = document_model.get_by_uri.return_value
    type(document).document_uris = uris = mock.PropertyMock()
    uris.return_value = [
        mock.Mock(uri='http://foo.com/'),
        mock.Mock(uri='http://bar.com/'),
        mock.Mock(uri='http://example.com/', type='rel-canonical'),
    ]
    assert storage.expand_uri(request, "http://example.com/") == [
            "http://example.com/"]


def test_expand_uri_postgres_document_uris(postgres_enabled):
    request = DummyRequest(db=db.Session)
    postgres_enabled.return_value = True

    document = Document(document_uris=[
        DocumentURI(uri='http://foo.com/', claimant='http://bar.com'),
        DocumentURI(uri='http://bar.com/', claimant='http://bar.com'),
    ])
    db.Session.add(document)
    db.Session.flush()

    assert storage.expand_uri(request, 'http://foo.com/') == [
        'http://foo.com/',
        'http://bar.com/'
    ]


def test_expand_uri_elastic_document_uris(postgres_enabled, document_model):
    postgres_enabled.return_value = False
    request = DummyRequest()
    document = document_model.get_by_uri.return_value
    type(document).document_uris = uris = mock.PropertyMock()
    uris.return_value = [
        mock.Mock(uri="http://foo.com/"),
        mock.Mock(uri="http://bar.com/"),
    ]
    assert storage.expand_uri(request, "http://example.com/") == [
        "http://foo.com/",
        "http://bar.com/",
    ]


@pytest.mark.usefixtures('AnnotationBeforeSaveEvent',
                         'elastic',
                         'partial',
                         'transform')
class TestCreateAnnotation(object):

    """Tests for create_annotation() when postgres_write is off."""

    def test_it_inits_an_elastic_annotation_model(self, elastic):
        data = self.annotation_data()

        storage.create_annotation(self.mock_request(), data)

        elastic.Annotation.assert_called_once_with(data)

    def test_it_calls_partial(self, partial):
        request = self.mock_request()

        storage.create_annotation(request, self.annotation_data())

        partial.assert_called_once_with(storage.fetch_annotation, request)

    def test_it_calls_prepare(self, elastic, partial, transform):
        storage.create_annotation(self.mock_request(), self.annotation_data())

        transform.prepare.assert_called_once_with(
            elastic.Annotation.return_value, partial.return_value)

    def test_it_inits_AnnotationBeforeSaveEvent(self,
                                                AnnotationBeforeSaveEvent,
                                                elastic):
        request = self.mock_request()

        storage.create_annotation(request, self.annotation_data())

        AnnotationBeforeSaveEvent.assert_called_once_with(
            request, elastic.Annotation.return_value)

    def test_it_calls_notify(self, AnnotationBeforeSaveEvent):
        request = self.mock_request()

        storage.create_annotation(request, self.annotation_data())

        request.registry.notify.assert_called_once_with(
            AnnotationBeforeSaveEvent.return_value)

    def test_it_calls_annotation_save(self, elastic):
        storage.create_annotation(self.mock_request(), self.annotation_data())

        elastic.Annotation.return_value.save.assert_called_once_with()

    def test_it_returns_the_annotation(self, elastic):
        result = storage.create_annotation(self.mock_request(),
                                           self.annotation_data())

        assert result == elastic.Annotation.return_value

    def mock_request(self):
        request = DummyRequest(feature=mock.Mock(spec=lambda feature: False,
                               return_value=False))
        request.registry.notify = mock.Mock(spec=lambda event: None)
        return request

    def annotation_data(self):
        return {'foo': 'bar'}

    @pytest.fixture
    def AnnotationBeforeSaveEvent(self, request):
        patcher = patch('h.api.storage.AnnotationBeforeSaveEvent',
                        autospec=True)
        AnnotationBeforeSaveEvent = patcher.start()
        request.addfinalizer(patcher.stop)
        return AnnotationBeforeSaveEvent

    @pytest.fixture
    def elastic(self, request):
        patcher = patch('h.api.storage.elastic', autospec=True)
        elastic = patcher.start()
        request.addfinalizer(patcher.stop)
        return elastic

    @pytest.fixture
    def partial(self, request):
        patcher = patch('h.api.storage.partial', autospec=True)
        partial = patcher.start()
        request.addfinalizer(patcher.stop)
        return partial

    @pytest.fixture
    def transform(self, request):
        patcher = patch('h.api.storage.transform', autospec=True)
        transform = patcher.start()
        request.addfinalizer(patcher.stop)
        return transform


@pytest.fixture
def document_model(config, request):
    patcher = patch('h.api.models.elastic.Document', autospec=True)
    module = patcher.start()
    request.addfinalizer(patcher.stop)
    return module


@pytest.fixture
def postgres_enabled(request):
    patcher = patch('h.api.storage._postgres_enabled', autospec=True)
    func = patcher.start()
    request.addfinalizer(patcher.stop)
    return func


@pytest.fixture
def ElasticAnnotation(request):
    patcher = patch('h.api.storage.elastic.Annotation', autospec=True)
    cls = patcher.start()
    request.addfinalizer(patcher.stop)
    return cls
