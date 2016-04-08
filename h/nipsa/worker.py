# -*- coding: utf-8 -*-
"""Worker functions for the NIPSA feature."""

from elasticsearch import helpers

from h.celery import celery
from h.celery import get_task_logger
from h.nipsa import search

log = get_task_logger(__name__)


def add_nipsa_action(index, annotation):
    """Return an Elasticsearch action for adding NIPSA to the annotation."""
    return {
        "_op_type": "update",
        "_index": index,
        "_type": "annotation",
        "_id": annotation["_id"],
        "doc": {"nipsa": True}
    }


def remove_nipsa_action(index, annotation):
    """Return an Elasticsearch action to remove NIPSA from the annotation."""
    source = annotation["_source"].copy()
    source.pop("nipsa", None)
    return {
        "_op_type": "index",
        "_index": index,
        "_type": "annotation",
        "_id": annotation["_id"],
        "_source": source,
    }


def bulk_update_annotations(client, query, action):
    """Update annotations for a user with the given NIPSA state."""
    annotations = helpers.scan(client=client.conn,
                               index=client.index,
                               query=query)
    actions = [action(client.index, a) for a in annotations]
    helpers.bulk(client=client.conn, actions=actions)


@celery.task
def add_nipsa(userid):
    log.info("setting nipsa flag for user annotations: %s", userid)
    bulk_update_annotations(celery.request.es,
                            search.not_nipsad_annotations(userid),
                            add_nipsa_action)


@celery.task
def remove_nipsa(userid):
    log.info("clearing nipsa flag for user annotations: %s", userid)
    bulk_update_annotations(celery.request.es,
                            search.nipsad_annotations(userid),
                            remove_nipsa_action)
