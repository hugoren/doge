# coding: utf-8

from doge.common.doge import Request
from doge.common.exceptions import ClientError
from doge.rpc.context import new_endpoint


class Client(object):
    def __init__(self, context, service):
        self.service = service
        self.url = context.url
        self.context = context
        self.regisry = context.get_registry()
        self.endpoints = context.get_endpoints(self.regisry, service)
        self.ha = context.get_ha()
        self.lb = context.get_lb(self.endpoints.values())
        self.available = True
        self.closed = False

        self.watch()

    def call(self, method, *args):
        if self.available:
            r = Request(self.service, method, *args)
            res = self.ha.call(r, self.lb)
            if res.exception:
                raise res.exception
            return res.value
        raise ClientError("client not available")

    def watch(self):
        self.regisry.watch(self.service, self.notify)

    def notify(self, event):
        if event['action'] == 'delete':
            ep = self.endpoints[event['key']]
            self.lb.endpoints.remove(ep)
            del self.endpoints[event['key']]
        elif event['action'] == 'set':
            ep = new_endpoint(event['key'], event['value'])
            self.endpoints[event['key']] = ep
            self.lb.endpoints.append(ep)

    def destroy(self):
        if not self.closed:
            self.closed = True
            self.regisry.watch_thread.kill()
            for k, v in self.endpoints.iteritems():
                v.destroy()
            del self.context
            del self.regisry
            del self.ha
            del self.endpoints
            del self.lb
            self.closed = True
