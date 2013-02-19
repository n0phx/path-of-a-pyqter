Simple Browser
==============


So let's create a basic headless-webbrowser, load a url into it, print the result when it's available, and terminate the program:

`qttut01.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut01/qttut01.py>`_.

Older versions of *PyQt* (prior to 4.5) had a much uglier style for connecting signals, read more about it `here <http://qt-project.org/wiki/Signals_and_Slots_in_PySide>`_. It's still supported, but is less readable, so it's not the preferred method unless your code must be backwards compatible with older *QT* versions. Here's how our ``loadFinished`` signal connection would look like with the old style signals::

    # We would have to import SIGNAL from QtCore
    from PySide.QtCore import QUrl, SIGNAL

    ...

    # and in our class, the self.loadFinished.connect would be replaced with
    self.connect(self, SIGNAL("loadFinished(bool)"), self._load_finished)

I'm quite misleading with talking about *PyQt* and using *PySide* in the actual code, but my rule of thumb is that the code is tolerable only if it works on both of them. Back to the topic, when the page loading is finished(meaning the page is rendered and all resources are downloaded completely), the ``loadFinished`` signal is emitted. *QT* then calls all the handler functions that were attached to that signal. It passes one boolean parameter to them, called "ok", which is ``True`` if the page was loaded successfully, and a helpful ``False`` if not.

After that we called ``self.page()``, which returned a reference to a ``QWebPage`` instance, which actually contains the webpage associated with this webview. ``QWebView`` is a widget, used to display what ``QWebPage`` contains (ironically we're not even using that feature now), while ``QWebPage`` is an object - the real deal, and I quote: "*holds a main frame responsible for web content, settings, the history of navigated links and actions*". So in most cases accessing a ``QWebPage``'s main frame (through the ``QWebPage.mainFrame()`` method) will give you access to all the elements on the page (except to elements inside other frames, if there are any, but we'll get back to that later). We went even further and we called the ``toHtml()`` method on the main frame, which returned us the whole html document as a string (actually a ``QString`` instance, but that's easily converted to a ``Python`` string).

The ``mainFrame``'s ``url()`` method is I guess self-explanatory. After we printed the results, we closed the webview and terminated the application. That was simple.