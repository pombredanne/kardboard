import urlparse
import logging
import datetime

from kardboard.models import Kard
from kardboard import cache
from kardboard.util import ImproperlyConfigured, log_exception


class TicketHelper(object):
    def __init__(self, config, kard):
        self.app_config = config
        self.card = kard

    def get_title(self, key=None):
        raise NotImplemented

    def get_ticket_url(self, key=None):
        raise NotImplemented

    def update(self, sync=False):
        now = datetime.datetime.now()
        self.card._ticket_system_updated_at = now


class TestTicketHelper(TicketHelper):
    def get_title(self, key=None):
        title = self.card.ticket_system_data.get('summary', '')
        return title

    def get_ticket_url(self):
        return u"""http://example.com/ticket/%s""" % self.card.key

    def update(self, sync=False):
        super(TestTicketHelper, self).update()
        test_data = {
            'summary': u"""Dummy Title from Dummy Ticket System""",
        }
        self.card._ticket_system_data = test_data


class JIRAConnection(object):
    __shared_state = {}

    def __init__(self, client):
        self.__dict__ = self.__shared_state
        self.client = client

    def connect(self, username, password):
        self.auth = self.client.service.login(username, password)
        return self.auth


class JIRAHelper(TicketHelper):
    def __init__(self, config, kard):
        super(JIRAHelper, self).__init__(config, kard)
        self.logger = logging.getLogger('kardboard.tickethelpers.JIRAHelper')
        self.issues = {}

        try:
            self.wsdl_url = self.app_config['JIRA_WSDL']
        except KeyError:
            raise ImproperlyConfigured("You must provide a JIRA_WSDL setting")

        try:
            self.username, self.password = self.app_config['JIRA_CREDENTIALS']
        except KeyError:
            raise ImproperlyConfigured(
                "You must provide a JIRA_CREDENTIALS setting")
        except ValueError:
            raise ImproperlyConfigured(
                "JIRA_CREDENTIALS should be a two-item tuple (user, pass)")

        from suds.client import Client
        self.Client = Client

    @property
    def cache_prefix(self):
        return "jira_%s" % self.wsdl_url

    def connect(self):
        client = self.Client(self.wsdl_url)
        jc = JIRAConnection(client)  # Avoid double-login
        if hasattr(jc, 'auth'):
            auth = jc.auth
        else:
            auth = jc.connect(self.username, self.password)

        self.auth = auth
        self.service = client.service

    def get_issue(self, key=None):
        if not hasattr(self, 'service'):
            self.connect()

        key = key or self.card.key
        if self.issues.get(key, None):
            return self.issues.get(key)

        issue = self.service.getIssue(self.auth, key)
        self.issues[key] = issue
        return issue

    def get_title(self, key=None):
        title = self.card.ticket_system_data.get('summary', '')
        return title

    def issue_to_dictionary(self, obj):
        idic = {}
        keys = ['summary', 'key', 'reporter', 'assignee', 'description',
            'status', 'type']
        for key in keys:
            idic[key] = getattr(obj, key)
        idic['status'] = self.resolve_status(idic['status'])
        idic['type'] = self.resolve_type(idic['type'])
        return idic

    def object_to_dict(self, obj):
        keys = [k for k in dir(obj) if not k.startswith("_")]
        dic = dict([(key, getattr(obj, key)) for key in keys])
        return dic

    def resolve_status(self, status_id):
        key = "%s_statuses" % self.cache_prefix
        statuses = cache.get(key)
        if not statuses:
            self.logger.info("Cache miss for %s" % key)
            statuses = self.service.getStatuses()
            statuses = [self.object_to_dict(s) for s in statuses]
            cache.set(key, statuses)
        status = [s for s in statuses if s['id'] == status_id]
        try:
            return status[0]
        except IndexError:
            return status_id

    def resolve_type(self, type_id):
        key = "%s_issue_types" % self.cache_prefix
        the_types = cache.get(key)
        if not the_types:
            self.logger.info("Cache miss for %s" % key)
            the_types = self.service.getIssueTypes()
            the_types = [self.object_to_dict(t) for t in the_types]
            cache.set(key, the_types)
        the_type = [t for t in the_types if t['id'] == type_id]
        try:
            return the_type[0]
        except IndexError:
            return type_id

    def update(self, sync=True):
        if self.card._ticket_system_data:
            # We have some data, lets see if it's old
            threshold = 60 * 60  #1 hour
            now = datetime.datetime.now()
            diff = now - self.card._ticket_system_updated_at
            if diff.seconds >= threshold:
                self.logger.info("Card %s info is out of date" % self.card.key)
                if sync:
                    self.actually_update()
                else:
                    # schedule an actual update here
                    pass
            else:
                self.logger.info(
                    "Card %s info is less than an hour old" % self.card.key)
        else:
            # first fetch
            self.actually_update()

    def actually_update(self):
        super(JIRAHelper, self).update()
        self.logger.info("Fetching JIRA data for %s" % self.card.key)
        try:
            issue = self.get_issue(self.card.key)
        except Exception:
            issue = None
            log_exception("Couldn't fetch JIRA issue %s" % self.card.key)
        if issue:
            issue_dict = self.issue_to_dictionary(issue)
        else:
            issue_dict = {}

        self.card._ticket_system_data = issue_dict
        if self.card.id:
            Kard.objects(id=self.card.id).update_one(
                set___ticket_system_data=issue_dict)

    def get_ticket_url(self, key=None):
        key = key or self.card.key
        parsed_url = urlparse.urlparse(self.wsdl_url)
        browse_url_parts = [
            parsed_url.scheme,
            '://',
            parsed_url.netloc,
            '/browse/',
            key,
        ]
        return ''.join(browse_url_parts)