import re
import requests

from dotenv import dotenv_values
from flask import Flask, request


config = dotenv_values(__name__ + "/../.env.local")
app = Flask(__name__)


@app.route("/", methods=['POST'])
def hook():
    headers = request.headers

    gitlab_validation_token = headers.get('X-Gitlab-Token')
    if not gitlab_validation_token or gitlab_validation_token != config['GITLAB_TOKEN']:
        return 'Invalid Gitlab token\n', 403

    event_type = headers.get('X-Gitlab-Event')
    if not event_type:
        return 'Must set X-Gitlab-Event\n', 422

    data = request.json
    if not data:
        return 'Must send JSON data\n', 422

    attrs = data.get('object_attributes')
    if not attrs:
        return 'Missing object_attributes\n', 422

    if event_type == 'Merge Request Hook':
        mr_title = attrs.get('title')
        if not mr_title:
            return 'Missing MR title\n', 422
        mr_url = attrs.get('url')
        if not mr_url:
            return 'Missing MR URL\n', 422

        fail = 0
        for ticket in parse_tickets(mr_title):
            try:
                update_ticket(ticket, mr_url)
            except Exception as e:
                fail = fail + 1

        if fail:
            return 'Failed to update %d tickets\n' % (fail,), 500

    return 'OK\n', 200


def parse_tickets(string):
    pattern = re.compile('#([0-9]+)')
    tickets = pattern.findall(string)

    return tickets


def update_ticket(ticket, mr_url):
    field_id = config['CODE_CHANGES_CUSTOM_FIELD_ID']
    data = {'issue': { 'custom_fields': [{'id': field_id, 'value': mr_url}]}}
    result = requests.put(
        '%s/issues/%s.json' % (config['REDMINE_URL'], ticket,),
        headers={'X-Redmine-API-Key': config['REDMINE_API_KEY']},
        json=data
    )
    if result.status_code != 204:
        raise Exception('Failed to update %s: %d %s' % (ticket, result.status_code, result.body))

