Improving the Browser
=====================


We barely touched the capabilities of the ``QtWebKit`` module, so it's time to utilize more features. We want the ability to click, to fill form fields, to specify user agent strings, to simulate *JavaScript* events... that's at least for the beginning. Lock'n'load...

`qttut04.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut04/qttut04.py>`_.

Cool, we added features to click on any element on a webpage, to fill input fields with some values, and we got a new class right? It's called ``CraftyWebPage``, which inherits ``QWebPage``. Basically the only method we override is ``QWebPage.userAgentForUrl``, which we use to return a realistic user-agent string, so those party-breaker websites won't be able ignore us, because it could happen.

The ``Browser._find_element`` method does exactly what it's name suggests. It accepts a css selector string, and will evaluate that on the main frame of the web page, returning the first matched element (it's a shame there's no *XPath* support). It will also raise an exception in case the passed selector does not find any element.

The ``Browser.fill_input`` method can be used to fill html input fields with some values. There is an obvious limitation with it, we can't use it for select elements, nor can we check / uncheck checkboxes or radio buttons. But let's ignore that for now. It calls our previously described ``Browser._find_element`` method to locate the target element, and then magic happens. All ``QWebElement`` instances have this incredibly awesome ``QWebElement.evaluateJavaScript`` method, which accepts a string argument. This string argument can be any ``JavaScript`` code we want to run. By accessing the "this" object in the *JavaScript* code we wish to evaluate, we gain access to the element upon which we called that method. So our code is very simple, we make sure our element has a "value" attribute (if not we create it), and we associate a value with it.

The ``Browser.click`` method works similarly as the ``Browser.fill_input`` method, except it simulates only a simple mouse click event over the element. But what is important, we can use it for multiple purposes, we may click on radio-buttons or checkboxes with it, in which case it's clear what would happen, and we can click on buttons or links with it. When we click on submit buttons or links, the page would automatically initiate a request (assuming the page works that way), so the same ``loadFinished`` signal will be triggered once again, when the loading of the new page is finished.

With all these features in place, we are able to command and conquer many websites. Of course some of them are heavily guarded against bots, where we have to utilize additional quirks and twists, but this is only a basic implementation. Now let's go for a ride...