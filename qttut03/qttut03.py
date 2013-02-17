import os
import logging

from functools import partial

from PySide.QtCore import QByteArray, QUrl, QCryptographicHash
from PySide.QtGui import QApplication
from PySide.QtWebKit import QWebView, QWebPage, QWebSettings
from PySide.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                              QNetworkReply, QSslCertificate)


def smart_str(src):
    try:
        return str(src)
    except ValueError:
        return unicode(src).encode('utf-8')


def make_abs_path(*args):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, *args)


def init_logger(filename='webkit.log'):
    logging.getLogger('').setLevel(logging.DEBUG)
    log_path = make_abs_path(filename)

    log_handler = logging.FileHandler(log_path)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter('%(message)s'))

    return log_handler


def receiver(parent_app, result):
    print 'Finished loading:', result['url']
    print 'Successful:', result['successful']
    if result['errors']:
        print 'Some error(s) occurred:', result['errors']

    html_path = make_abs_path('result.html')
    print 'HTML response saved to:', html_path
    with open(html_path, 'w') as html_file:
        html_file.write(smart_str(result['html']))

    parent_app.quit()


class NetworkManager(QNetworkAccessManager):

    def __init__(self, logger):
        QNetworkAccessManager.__init__(self)
        self.logger = logger
        self.errors = []

        # connect signals
        self.sslErrors.connect(self._ssl_errors)
        self.finished.connect(self._finished)

        # bind a custom virtual function to createRequest
        self.createRequest = self._create_request

    def log_reply(self, reply):
        """
        Print http request and response information to stdout.
        """
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        reason = reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
        redirect = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)

        self.logger.debug('URL: {0}'.format(smart_str(reply.url().toString())))
        self.logger.debug('STATUS CODE: {0} {1}'.format(status_code, reason))
        if redirect:
            redirect_url = smart_str(redirect.toString())
            self.logger.debug('REDIRECT TO: {0}'.format(redirect_url))

        if not reply.error() == QNetworkReply.NoError:
            msg = 'ERROR: {0} - {1}'.format(reply.error(), reply.errorString())
            self.logger.error(msg)

        # Request headers
        self.logger.debug("REQUEST HEADERS:")
        for hdr in reply.request().rawHeaderList():
            msg = '    {0}: {1}'.format(hdr, reply.request().rawHeader(hdr))
            self.logger.debug(msg)
        # Response headers
        self.logger.debug("RESPONSE HEADERS:")
        for hdr in reply.rawHeaderList():
            msg = '    {0}: {1}'.format(hdr, reply.rawHeader(hdr))
            self.logger.debug(msg)

        self.logger.debug("-" * 50)

    def log_post_data(self, data):
        try:
            raw_data = smart_str(data.peek(8192))
        except AttributeError:
            # data is None, nothing will be sent in this request
            pass
        else:
            self.logger.debug('POST DATA: {0}'.format(raw_data))

    def log_ssl(self, reply):
        """
        Print ssl related informations to stdout.
        """
        ssl_status = reply.sslConfiguration()
        ssl_protocol = str(ssl_status.protocol())

        certificate = ssl_status.peerCertificate()
        fingerprint = str(certificate.digest(QCryptographicHash.Sha1).toHex())

        subject = certificate.subjectInfo(QSslCertificate.Organization)
        issuer = certificate.issuerInfo(QSslCertificate.Organization)

        str_ssl_protocol = ssl_protocol[ssl_protocol.rfind('.') + 1:]
        self.logger.debug('SSL PROTOCOL: {0}'.format(str_ssl_protocol))
        self.logger.debug('PEER CERTIFICATE:')
        self.logger.debug('    SHA1 FINGERPRINT: {0}'.format(fingerprint))
        self.logger.debug('    SUBJECT: {0}'.format(subject))
        self.logger.debug('    ISSUER: {0}'.format(issuer))
        self.logger.debug('    PEM:')
        self.logger.debug('{0}'.format(certificate.publicKey().toPem()))
        self.logger.debug("-" * 50)

    def _ssl_errors(self, reply, errors):
        # currently we ignore all ssl related errors
        for error in errors:
            msg = 'IGNORED SSL ERROR: {0} - {1}'.format(error.error(),
                                                        error.errorString())
            self.logger.error(msg)

        reply.ignoreSslErrors()

    def _finished(self, reply):
        # Called when a request is finished, whether it was successful or not.
        self.log_reply(reply)
        self.log_ssl(reply)

        if not reply.error() == QNetworkReply.NoError:
            # an error occurred
            self.errors.append('{0}: {1}'.format(reply.error(),
                                                 reply.errorString()))

        # schedule the reply object for deletion
        reply.deleteLater()

    def _create_request(self, operation, request, data):
        self.log_post_data(data)
        reply = QNetworkAccessManager.createRequest(self,
                                                    operation,
                                                    request,
                                                    data)
        return reply


class Browser(object):

    def __init__(self, callback, logger, options=None):
        self.logger = logger

        self._request_ops = {'head': QNetworkAccessManager.HeadOperation,
                             'get': QNetworkAccessManager.GetOperation,
                             'put': QNetworkAccessManager.PutOperation,
                             'post': QNetworkAccessManager.PostOperation,
                             'delete': QNetworkAccessManager.DeleteOperation}

        self._network_manager = NetworkManager(logger)

        self._web_page = QWebPage()
        self._web_page.setNetworkAccessManager(self._network_manager)

        self._web_view = QWebView()
        self._web_view.setPage(self._web_page)

        # connect the loadFinished signal to a method defined by us.
        # loadFinished is the signal which is triggered when a page is loaded
        self._web_view.loadFinished.connect(self._load_finished)

        options = options or dict()
        settings = self._web_view.settings()
        settings.setAttribute(QWebSettings.AutoLoadImages,
                              options.pop('images', False))
        settings.setAttribute(QWebSettings.JavascriptEnabled,
                              options.pop('javascript', False))
        settings.setAttribute(QWebSettings.JavascriptCanOpenWindows,
                              options.pop('popups', False))
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled,
                              options.pop('private_browsing', False))
        settings.setAttribute(QWebSettings.JavaEnabled, False)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.DnsPrefetchEnabled, True)

        # store the callback function which will be called when a request is
        # finished
        self._result_callback = callback

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

    def _load_finished(self, ok):
        """
        Called when the page is fully loaded. It will get the html file of
        the loaded page and call the callback function with that result.
        """
        frame = self._web_view.page().mainFrame()
        url = smart_str(frame.url().toString())
        html = frame.toHtml()

        result = {'html': html,
                  'url': url,
                  'successful': ok}

        if self._network_manager.errors:
            result['errors'] = self._network_manager.errors

        # calling the callback function which we passed upon instantiation to
        # report the results there
        self._result_callback(result)

    def make(self, method, url, headers, raw_data=None):
        request = self._prepare_request(url, headers)
        operation = self._request_ops[method.lower()]
        request_data = self._urlencode_request_data(raw_data or dict())
        self._web_view.load(request, operation, request_data)


if __name__ == '__main__':
    # QApplication's __init__ method accepts a list. In many places you will
    # see code snippets where sys.argv is passed to it(command line arguments),
    # but since we're not using them anyway, there's no need to pass them.
    app = QApplication([])
    # prepare a logger
    log_handler = init_logger()
    logger = logging.getLogger('webkit_logger')
    logger.addHandler(log_handler)

    # create our Browser instance
    browser = Browser(partial(receiver, app), logger, {'images': False})
    '''
    browser.make(method='get',
                 url='http://www.python.org',
                 headers={"Accept": "*/*",
                          "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                          "Accept-Encoding": "none"})
    browser.make(method='post',
                 url='http://www.facebook.com',
                 headers={"Accept": "*/*",
                          "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                          "Accept-Encoding": "none"},
                 raw_data={'username': 'wontwork',
                           'password': 'nosuchfield',
                           'whythen': 'justfortesting'})
    '''
    browser.make(method='post',
                 url='http://127.0.0.1:8088',
                 headers={"Accept": "*/*",
                          "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                          "Accept-Encoding": "none"},
                 raw_data={'username': 'wontwork',
                           'password': 'nosuchfield',
                           'whythen': 'justfortesting'})

    # start the famous event loop. At this point the code located after the
    # app.exec_() line will not be executed, until the event loop is closed.
    app.exec_()

    print 'Application closed.'
