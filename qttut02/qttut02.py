from functools import partial

from PySide.QtCore import QByteArray, QUrl
from PySide.QtGui import QApplication
from PySide.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                              QNetworkReply)


def smart_str(src):
    try:
        return str(src)
    except ValueError:
        return unicode(src).encode('utf-8')


class NetManager(object):

    def __init__(self, callback):
        self._network_manager = QNetworkAccessManager()
        # connect signals
        self._network_manager.sslErrors.connect(self._ssl_errors)
        self._network_manager.finished.connect(self._finished)

        # bind a custom virtual function to createRequest
        self._network_manager.createRequest = self._create_request

        # a dict of available request methods
        self._request_methods = {
            'delete': lambda r, d: self._network_manager.deleteResource(r),
            'get': lambda r, d: self._network_manager.get(r),
            'head': lambda r, d: self._network_manager.head(r),
            'post': lambda r, d: self._network_manager.post(r, d),
            'put': lambda r, d: self._network_manager.put(r, d),
        }
        # store the callback function which will be called when a request is
        # finished
        self._result_callback = callback

    def _ssl_errors(self, reply, errors):
        # currently we ignore all ssl related errors
        reply.ignoreSslErrors()

    def _finished(self, reply):
        # Called when a request is finished, whether it was successful or not.
        # Obtain some basic information about the request

        reply_url = reply.url().toString()
        # Request headers
        request_headers = dict((str(hdr), str(reply.request().rawHeader(hdr)))
                               for hdr in reply.request().rawHeaderList())
        # Reply headers
        reply_headers = dict((str(hdr), str(reply.rawHeader(hdr)))
                             for hdr in reply.rawHeaderList())
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        reason = reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
        redirect = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        result = {'reply_url': smart_str(reply_url),
                  'status_code': status_code,
                  'reason': reason,
                  'redirect_to': smart_str(redirect.toString()),
                  'request_headers': request_headers,
                  'reply_headers': reply_headers}

        if reply.error() == QNetworkReply.NoError:
            # request was successful
            result['successful'] = True
            result['reply_data'] = reply.readAll()
        else:
            # request was not successful
            result['successful'] = False
            result['error'] = reply.error()
            result['error_msg'] = reply.errorString()

        # schedule the reply object for deletion
        reply.deleteLater()

        # calling the callback function which we passed upon instantiation to
        # report the results there
        self._result_callback(result)

    def _create_request(self, operation, request, data):
        try:
            raw_data = smart_str(data.peek(8192))
        except AttributeError:
            # data is None, nothing will be sent in this request
            pass
        else:
            parsed_data = '\n'.join(raw_data.split('&'))
            print parsed_data

        reply = QNetworkAccessManager.createRequest(self._network_manager,
                                                    operation,
                                                    request,
                                                    data)
        return reply

    def _prepare_request(self, url, headers):
        # create an empty request
        request = QNetworkRequest()
        # assign a url to it
        request.setUrl(QUrl(url))

        # add some custom headers to the request
        for (header_name, header_value) in headers.items():
            request.setRawHeader(header_name, QByteArray(header_value))

        return request

    def _urlencode_request_data(self, raw_data):
        # the data which we want to send to the server must be urlencoded
        request_data = QUrl()
        for (name, value) in raw_data.items():
            request_data.addQueryItem(name, unicode(value))

        return request_data.encodedQuery()

    def perform(self, method, url, headers, raw_data=None):
        # create the request object
        request = self._prepare_request(url, headers)
        # urlencode the request data
        request_data = self._urlencode_request_data(raw_data or dict())
        # locate the request function for the choosen request method
        request_func = self._request_methods[method.lower()]
        # initiate request
        request_func(request, request_data)


def receiver(parent_app, result):
    print 'Status Code: {0} {1} for {2}'.format(result['status_code'],
                                                result['reason'],
                                                result['reply_url'])
    if result['redirect_to']:
        print 'Redirection to:', result['redirect_to']

    print 'Request headers:'
    print result['request_headers']
    print 'Reply headers:'
    print result['reply_headers']
    if result['successful']:
        print 'Received {0} bytes.'.format(result['reply_data'].size())
    else:
        print 'Error:', result['error']
        print 'Error message:', result['error_msg']
    parent_app.quit()


if __name__ == '__main__':
    # QApplication's __init__ method accepts a list. In many places you will
    # see code snippets where sys.argv is passed to it(command line arguments),
    # but since we're not using them anyway, there's no need to pass them.
    app = QApplication([])

    # create our Browser instance
    net_manager = NetManager(partial(receiver, app))

    # start the loading of a url
    '''
    net_manager.perform("GET",
                        "http://www.python.org",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"})
    net_manager.perform("GET",
                        "http://invalidurlwillerror.org",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"})
    net_manager.perform("POST",
                        "http://www.python.org",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"},
                        {"field_name": "something"})
    net_manager.perform("POST",
                        "http://www.google.com",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"},
                        {"field_name": "something"})
    net_manager.perform("POST",
                        "https://secure.kaspersky.com/",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"},
                        {"field_name": "something"})
    '''
    net_manager.perform("POST",
                        "https://mail.google.com/mail",
                        {"Accept": "*/*",
                         "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                         "Accept-Encoding": "none"},
                        {"field_name": "something"})
    # start the famous event loop. At this point the code located after the
    # app.exec_() line will not be executed, until the event loop is closed.
    app.exec_()

    print 'Application closed.'
