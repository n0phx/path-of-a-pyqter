import os
import logging

from functools import partial

from PySide.QtCore import (QByteArray, QIODevice, QBuffer, QFile,
                           QUrl, QCryptographicHash, QTimer)
from PySide.QtGui import QApplication
from PySide.QtWebKit import QWebView, QWebPage, QWebSettings
from PySide.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                              QNetworkReply, QSslCertificate, QSsl,
                              QSslConfiguration)


def smart_str(src):
    try:
        return str(src)
    except ValueError:
        return unicode(src).encode('utf-8')


def make_abs_path(*args):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, *args)


def get_log_handler(filename):
    log_path = make_abs_path(filename)
    log_handler = logging.FileHandler(log_path)
    log_handler.setFormatter(logging.Formatter('%(message)s'))
    return log_handler


def install_certificates():
    ssl_config = QSslConfiguration.defaultConfiguration()
    ssl_config.setProtocol(QSsl.SecureProtocols)

    certs = ssl_config.caCertificates()

    for cert_filename in os.listdir(make_abs_path('certs')):
        if os.path.splitext(cert_filename)[1] == '.pem':
            cert_filepath = make_abs_path('certs', cert_filename)
            cert_file = QFile(cert_filepath)
            cert_file.open(QIODevice.ReadOnly)
            cert = QSslCertificate(cert_file)
            certs.append(cert)

    ssl_config.setCaCertificates(certs)
    QSslConfiguration.setDefaultConfiguration(ssl_config)


class LogLevelFilter(logging.Filter):

    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


class ElementNotFound(Exception):
    pass


class SmartNetworkAccessManager(QNetworkAccessManager):

    def __init__(self, logger, max_request_retries):
        QNetworkAccessManager.__init__(self)

        self._http_methods = {
            QNetworkAccessManager.HeadOperation: lambda r, d: self.head(r),
            QNetworkAccessManager.GetOperation: lambda r, d: self.get(r),
            QNetworkAccessManager.PutOperation: lambda r, d: self.put(r, d),
            QNetworkAccessManager.PostOperation: lambda r, d: self.post(r, d),
            QNetworkAccessManager.DeleteOperation:
            lambda r, d: self.deleteResource(r)
        }

        self.logger = logger
        self._max_request_retries = max_request_retries

        self._requests = dict()
        self.errors = []

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
            self.logger.debug(msg)

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
            msg = 'SSL ERROR: {0} - {1}'.format(error.error(),
                                                error.errorString())
            self.logger.debug(msg)

    def _finished(self, reply):
        # Called when a request is finished, whether it was successful or not.
        self.logger.info('Request {0} finished.'.format(id(reply)))
        self.log_reply(reply)
        self.log_ssl(reply)

        request = self._requests[id(reply)]
        retry_count = request['retry_count']

        if (retry_count < self._max_request_retries and
            reply.error() in (QNetworkReply.TemporaryNetworkFailureError,
                              QNetworkReply.ContentReSendError)):
            # this request could be retried, it may succeed next time but
            # retry only if we didnt retry it already more than the allowed
            # number of times
            self.logger.info('Retrying request {0}'.format(id(reply)))
            outgoing_data = request['outgoing_data']
            http_method = self._http_methods[reply.operation()]
            new_reply = http_method(reply.request(), outgoing_data)
            # as a new reply object is created when we retry a failed one, we
            # must pass the old retry_count value to the new one
            self._requests[id(new_reply)]['retry_count'] = retry_count + 1

        elif reply.error() not in (QNetworkReply.NoError,):
            # request not successful and can't be retried
            self.errors.append('{0}: {1}'.format(reply.error(),
                                                 reply.errorString()))
        # as the request is finished, mark it as finished
        self._requests[id(reply)]['finished'] = True
        # schedule the reply object for deletion
        reply.deleteLater()

    def _reply_destroyed(self, reply_id):
        self.logger.info('Reply {0} destroyed.'.format(reply_id))
        self._requests.pop(reply_id, None)

    def _new_buffer(self, raw_data):
        buff = QBuffer()
        buff.setData(raw_data)
        buff.open(QIODevice.ReadOnly)
        return buff

    def _create_request(self, operation, request, data):
        self.log_post_data(data)
        # store the request object with the upload data
        try:
            raw_data = data.readAll()
        except AttributeError:
            original_data = backup_data = None
        else:
            original_data = self._new_buffer(raw_data)
            backup_data = self._new_buffer(raw_data)

        reply = QNetworkAccessManager.createRequest(self,
                                                    operation,
                                                    request,
                                                    original_data)
        self.logger.info('Request {0} started.'.format(id(reply)))

        if original_data is not None:
            original_data.setParent(reply)
            backup_data.setParent(reply)

        self._requests[id(reply)] = {'reply': reply,
                                     'outgoing_data': backup_data,
                                     'finished': False,
                                     'retry_count': 0}
        # in case the request object is destroyed, remove it from the dict
        # of request objects
        reply.destroyed.connect(partial(self._reply_destroyed, id(reply)))
        return reply

    def abort_requests(self):
        for request in self._requests.values():
            request['reply'].abort()

    @property
    def active_requests(self):
        return [id(req['reply']) for req in self._requests.values()
                if not req['finished']]


class CraftyWebPage(QWebPage):

    def __init__(self):
        QWebPage.__init__(self)

    def userAgentForUrl(self, url):
        return ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.19 (KHTML, '
                'like Gecko) Ubuntu/11.10 Chromium/18.0.1025.142 '
                'Chrome/18.0.1025.142 Safari/535.19')


class Browser(object):

    def __init__(self, callback, logger, options=None):
        self.logger = logger
        options = options or dict()

        self._request_ops = {'head': QNetworkAccessManager.HeadOperation,
                             'get': QNetworkAccessManager.GetOperation,
                             'put': QNetworkAccessManager.PutOperation,
                             'post': QNetworkAccessManager.PostOperation,
                             'delete': QNetworkAccessManager.DeleteOperation}

        self._timeout = int(options.pop('timeout', 30)) * 1000

        max_request_retries = options.pop('max_request_retries', 3)
        self._network_manager = SmartNetworkAccessManager(logger,
                                                          max_request_retries)
        self._web_page = CraftyWebPage()
        self._web_page.setNetworkAccessManager(self._network_manager)

        self._web_view = QWebView()
        self._web_view.setPage(self._web_page)

        # connect the loadFinished signal to a method defined by us.
        # loadFinished is the signal which is triggered when a page is loaded
        self._web_view.loadFinished.connect(self._load_finished)

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
        self._is_task_finished = False
        self._destroyed_status = dict()

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
        if self._is_task_finished:
            # in case loadFinished fires more than once and we already
            # reported back with a result, don't do that again
            self.logger.info('loadFinished emitted, but task was already '
                             'finished.')
            return

        pending_requests = self._network_manager.active_requests

        if ok == 'timed_out':
            self.logger.info('loadFinished emitted, request timed out.')
            self._network_manager.errors.append('Request timed out.')
            # to avoid treating the request by the driver as successful
            ok = False
        elif len(pending_requests) > 0:
            self.logger.info("loadFinished emitted, waiting for requests:"
                             " {0}".format(pending_requests))
            loaded = partial(lambda x: self._load_finished(x), ok)
            QTimer.singleShot(1000, loaded)
            return

        self.logger.info('loadFinshed emitted, returning result.')
        frame = self._web_view.page().mainFrame()
        url = smart_str(frame.url().toString())
        html = frame.toHtml()

        result = {'html': html,
                  'url': url,
                  'successful': ok}

        if self._network_manager.errors:
            result['errors'] = self._network_manager.errors

        self._finish_task(result)

    def _start_task(self):
        self._is_task_finished = False
        # abusing the ok param of loadFinished
        timed_out = lambda: self._load_finished('timed_out')
        self._timeout_timer = QTimer()
        self._timeout_timer.timeout.connect(timed_out)
        self._timeout_timer.start(self._timeout)

    def _finish_task(self, result):
        self._is_task_finished = True
        self._timeout_timer.stop()
        # calling the callback function which we passed upon instantiation to
        # report the results there
        self._result_callback(result)

    def make(self, method, url, headers, raw_data=None):
        request = self._prepare_request(url, headers)
        operation = self._request_ops[method.lower()]
        request_data = self._urlencode_request_data(raw_data or dict())
        self._start_task()
        self._web_view.load(request, operation, request_data)

    def _find_element(self, selector):
        main_frame = self._web_page.mainFrame()
        element = main_frame.findFirstElement(selector)

        if element.isNull():
            raise ElementNotFound(selector)

        return element

    def fill_input(self, selector, value):
        js_fill_input = """
            this.setAttribute("value", "{0}");
            this.value = "{0}";
        """.format(value)

        element = self._find_element(selector)
        element.evaluateJavaScript(js_fill_input)

    def click(self, selector):
        element = self._find_element(selector)
        offset = element.geometry()
        js_click = """
            function mouse_click(element) {{
                var event = document.createEvent('MouseEvents');
                var offsetX = {0} + 2;  //add 2 pixels otherwise it would
                var offsetY = {1} - 2;  //seem like we clicked on the margin
                event.initMouseEvent(
                    'click',                    //event type
                    true,                       //canBubble
                    true,                       //cancelable
                    document.defaultView,       //view
                    1,                          //detail
                    (window.screenX + offsetX), //screenX - The coords within
                    (window.screenY + offsetY), //screenY - the entire page
                    offsetX,                    //clientX - The coords within
                    offsetY,                    //clientY - the viewport
                    false,                      //ctrlKey
                    false,                      //altKey
                    false,                      //shiftKey
                    false,                      //metaKey
                    0,                          //0=left, 1=middle, 2=right
                    element                     //relatedTarget
                );
                element.dispatchEvent(event);   //Fire the event
            }}
            mouse_click(this);""".format(offset.left(), offset.top())

        self._start_task()
        element.evaluateJavaScript(js_click)

    def _destroyed(self, component):
        self._destroyed_status[component] = True
        if all(self._destroyed_status.values()):
            self._shutdown_callback()

    def shutdown(self, callback):
        self._shutdown_callback = callback
        self._web_view.stop()
        self._web_view.close()
        # will immediately stop any running javascript code
        self._web_view.settings().setAttribute(QWebSettings.JavascriptEnabled,
                                               False)
        # if any requests were started by javascript after loadFinished was
        # emitted, and before we stopped javascript execution, cancel them
        self._network_manager.abort_requests()

        self._destroyed_status['web_page'] = False
        self._web_page.destroyed.connect(lambda: self._destroyed('web_page'))
        self._web_page.deleteLater()

        self._destroyed_status['web_view'] = False
        self._web_view.destroyed.connect(lambda: self._destroyed('web_view'))
        self._web_view.deleteLater()

        self._destroyed_status['network_manager'] = False
        destroyer = lambda: self._destroyed('network_manager')
        self._network_manager.destroyed.connect(destroyer)
        self._network_manager.deleteLater()
