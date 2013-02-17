import unittest

from functools import partial

from PySide.QtGui import QApplication
from PySide.QtCore import QEventLoop

from httpserver import ServerProcess
from qttut07 import Browser


class MockedLogger(object):
    error = lambda x, y: None
    info = lambda x, y: None
    debug = lambda x, y: None


def init_test(func):
    def _init_test(self, *args, **kwargs):
        test_setup = func(self, *args, **kwargs)
        self.start_server(test_setup['server_context'])
        callback = partial(self.check_result, test_setup['expected'])
        options = test_setup['browser_options']
        self.browser = Browser(callback, self.logger, options)
        self.browser.make(test_setup['req_method'],
                          'http://{0}:{1}'.format(self.address, self.port),
                          test_setup['req_headers'],
                          test_setup['req_data'])
        self.event_loop = QEventLoop()
        self.event_loop.exec_()

    return _init_test


class BrowserTest(unittest.TestCase):

    def setUp(self):
        self.address = '127.0.0.1'
        self.port = 8088
        self.logger = MockedLogger()

    def start_server(self, server_context):
        self.server = ServerProcess(self.address, self.port, server_context)
        self.server.start()

    def check_result(self, expected, result):
        self.server.shutdown()
        self.server.join()
        try:
            self.assertEqual(result, expected)
        finally:
            self.event_loop.quit()

    @init_test
    def test_request_ok(self):
        html = u'<html><head></head><body>something</body></html>'
        server_context = {
            'delay': 0.0,
            'response': 200,
            'response_data': html,
            'headers': {'content-type': 'text/html;'}
        }
        expected = {
            'url': 'http://127.0.0.1:8088/',
            'successful': True,
            'html': html,
        }
        browser_options = {}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_request_retry_exceed_limit(self):
        server_context = {}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': [('PySide.QtNetwork.QNetworkReply.NetworkError'
                        '.ContentReSendError: Unknown error')]
        }
        browser_options = {'max_request_retries': 1}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_request_retry_fail(self):
        server_context = {}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': [('PySide.QtNetwork.QNetworkReply.NetworkError'
                        '.RemoteHostClosedError: Connection closed')]
        }
        browser_options = {}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_request_timeout(self):
        server_context = {'delay': 3}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': ['Request timed out.']
        }
        browser_options = {'timeout': 1}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}


if __name__ == '__main__':
    app = QApplication([])
    unittest.main()
    app.exec_()
