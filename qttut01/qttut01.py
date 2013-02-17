from PySide.QtCore import QUrl
#from PySide.QtCore import QUrl, SIGNAL
from PySide.QtGui import QApplication
from PySide.QtWebKit import QWebView


class Browser(QWebView):

    def __init__(self, app):
        QWebView.__init__(self)

        # By storing a reference to the application which started this
        # instance, we will be able to close the application once we get what
        # we want
        self.parent_app = app

        # connect the loadFinished signal to a method defined by us.
        # loadFinished is the signal which is triggered when a page is loaded
        self.loadFinished.connect(self._load_finished)
        # self.connect(self, SIGNAL("loadFinished(bool)"), self._load_finished)

    def _load_finished(self, ok):
        frame = self.page().mainFrame()
        url = frame.url().toString()
        html = frame.toHtml()

        # printing the html code which is loaded
        print unicode(html).encode('utf-8')
        print unicode(url).encode('utf-8')

        # closing the webview
        self.close()
        # terminating the application (this will break the event loop)
        self.parent_app.quit()

    def open(self, url):
        self.load(QUrl(url))


if __name__ == '__main__':
    # QApplication's __init__ method accepts a list. In many places you will
    # see code snippets where sys.argv is passed to it(command line arguments),
    # but since we're not using them anyway, there's no need to pass them.
    app = QApplication([])

    # create our Browser instance
    browser = Browser(app)

    # start the loading of a url
    browser.open("http://www.python.org")

    # start the famous event loop. At this point the code located after the
    # app.exec_() line will not be executed, until the event loop is closed.
    app.exec_()

    print 'Application closed.'
