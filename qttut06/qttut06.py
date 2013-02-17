import os
import logging

from PySide.QtCore import (QByteArray, QUrl, QCryptographicHash, QFile,
                           QIODevice)
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


def init_logger(filename='webkit.log'):
    logging.getLogger('').setLevel(logging.DEBUG)
    log_path = make_abs_path(filename)

    log_handler = logging.FileHandler(log_path)
    log_handler.setLevel(logging.DEBUG)
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


class ElementNotFound(Exception):
    pass


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
            msg = 'SSL ERROR: {0} - {1}'.format(error.error(),
                                                error.errorString())
            self.logger.error(msg)

        #reply.ignoreSslErrors()

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

        self._request_ops = {'head': QNetworkAccessManager.HeadOperation,
                             'get': QNetworkAccessManager.GetOperation,
                             'put': QNetworkAccessManager.PutOperation,
                             'post': QNetworkAccessManager.PostOperation,
                             'delete': QNetworkAccessManager.DeleteOperation}

        self._network_manager = NetworkManager(logger)

        self._web_page = CraftyWebPage()
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
        element.evaluateJavaScript(js_click)


class BaseWebDriver(object):

    def __init__(self, parent_app, browser_cls, options):
        self.parent_app = parent_app
        # prepare a logger
        log_handler = init_logger()
        self.logger = logging.getLogger('webkit_logger')
        self.logger.addHandler(log_handler)

        # create our Browser instance
        self.browser = browser_cls(self._finished, self.logger, options)

        step_names = sorted(step for step in dir(self.__class__)
                            if step.startswith('step_'))
        self._steps = (getattr(self, step) for step in step_names)

    def _finished(self, result):
        if result['successful']:
            self.run(result['html'])
        else:
            print 'An error occurred:', result['error']
            self.parent_app.quit()

    def run(self, html=None):
        try:
            next_step = self._steps.next()
        except StopIteration:
            print 'All finished.'
            self.parent_app.quit()
            return

        try:
            next_step(html)
        except Exception as exc:
            print 'Fatal error:', exc.__class__.__name__, exc
            self.parent_app.quit()


class YahooDriver(BaseWebDriver):

    def __init__(self, *args, **kwargs):
        options = {'images': True, 'javascript': True}
        super(YahooDriver, self).__init__(browser_cls=Browser,
                                          options=options,
                                          *args,
                                          **kwargs)

    def step_1(self, html=None):
        print 'Loading'
        headers = {"Accept": "*/*",
                   "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
                   "Accept-Encoding": "none"}
        self.browser.make(method='get',
                          url='https://login.yahoo.com',
                          headers=headers)


if __name__ == '__main__':
    install_certificates()
    # QApplication's __init__ method accepts a list. In many places you will
    # see code snippets where sys.argv is passed to it(command line arguments),
    # but since we're not using them anyway, there's no need to pass them.
    app = QApplication([])
    driver = YahooDriver(app)
    driver.run()
    # start the famous event loop. At this point the code located after the
    # app.exec_() line will not be executed, until the event loop is closed.
    app.exec_()

    print 'Application closed.'
