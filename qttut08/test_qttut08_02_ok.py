import unittest

from functools import partial

from PySide.QtGui import QApplication
from PySide.QtCore import QEventLoop

from httpserver import ServerProcess
from qttut08_02_ok import Browser


class MockedLogger(object):
    error = lambda x, y: None
    info = lambda x, y: None
    debug = lambda x, y: None


def init_test(func):
    def _init_test(self, *args, **kwargs):
        test_setup = func(self, *args, **kwargs)
        self.start_server(test_setup['server_context'])
        callback = partial(self.completed_test, test_setup['expected'])
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

    def completed_test(self, expected, result):
        self.browser.shutdown(partial(self.check_result, expected, result))

    @init_test
    def test_simple_request(self):
        with open('html/simple_page.html', 'r') as html_file:
            html = html_file.read()

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
        browser_options = {'images': True,
                           'javascript': True}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_delayed_dom_change(self):
        with open('html/js_delayed_dom_change.html', 'r') as html_file:
            html = html_file.read()

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
        browser_options = {'images': True,
                           'javascript': True}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_delayed_redirect(self):
        with open('html/js_delayed_redirect.html', 'r') as html_file:
            html = html_file.read()

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
        browser_options = {'images': True,
                           'javascript': True}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_delayed_ajax(self):
        with open('html/js_delayed_ajax.html', 'r') as html_file:
            html = html_file.read()

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
        browser_options = {'images': True,
                           'javascript': True}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_slow_request_1(self):
        server_context = {'delay': 5}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': [
                'Request timed out.',
                ('PySide.QtNetwork.QNetworkReply.NetworkError.'
                 'OperationCanceledError: Operation canceled')
            ]
        }
        browser_options = {'timeout': 4}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_slow_request_2(self):
        server_context = {'delay': 5}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': [
                'Request timed out.',
                ('PySide.QtNetwork.QNetworkReply.NetworkError.'
                 'OperationCanceledError: Operation canceled')
            ]
        }
        browser_options = {'timeout': 4}
        return {'server_context': server_context,
                'expected': expected,
                'browser_options': browser_options,
                'req_method': 'post',
                'req_data': {'test': '1'},
                'req_headers': {}}

    @init_test
    def test_slow_request_3(self):
        server_context = {'delay': 15}
        expected = {
            'url': '',
            'successful': False,
            'html': u'<html><head></head><body></body></html>',
            'errors': [
                'Request timed out.',
                ('PySide.QtNetwork.QNetworkReply.NetworkError.'
                 'OperationCanceledError: Operation canceled')
            ]
        }
        browser_options = {'timeout': 14}
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
