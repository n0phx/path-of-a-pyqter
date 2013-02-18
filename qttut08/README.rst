Dynamic creation and deletion of browser instances
==================================================

I mentioned previously that somebody(read me) might get a crazy idea to create and delete instances of these ``Browser`` classes within one process at runtime. It would be totally natural to think about something like that, if I would want to use a pure *Python* library.

However, since *QT* is written in *C++*, the fact is that I can very easily set up a segfault scenario without too much hassle, and not even realize it until it happens of course. The sorry side of these segfaults is that we can not recover the process from it, there's no way to simply catch them and resume the process after it happened, no one guarantees that our memory is intact, it might be corrupted by the underlying *C++* library we're using. So we are either very brave and trust our code or just silly if we try something like that.

We can demonstrate a segfault scenario most easily by using only unittests, where each test creates a new instance of a browser, but this time, we explicitly write a shutdown method to delete the *QT* components. Deletion of these components is necessary if we plan to create a healthy and memory efficient application which runs for a long time, and dynamically spawns these browsers as it wishes. The reason we won't write a complex sample application is that the accent is on showing a proper way to deal with the problem of deletion, rather than to create something useless.

`qttut08_01_bad.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut08/qttut08_01_bad.py>`_.

`test_qttut08_01_bad.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut08/test_qttut08_01_bad.py>`_.

So by running ``test_qttut08_01_bad.py``, a series of tests will be ran, and will result in a juicy segmentation fault. What our browser's shutdown method did was that it called the ``deleteLater`` method on it's ``QWebView``, ``QWebPage`` and ``QNetworkAccessManager``. The logic is certainly right, the page was already loaded, we did wait for all requests to finish(the feature we recently implemented), after the browser returned the result it was supposed to do nothing, so calling ``deleteLater`` on it's components would signal *QT* that it's safe to delete those objects at *QT*'s convenience, which *QT* decently did, yet it caused a segmentation fault.

Ruddy mysterious, isn't it? Of course, it's because *QT* is still an *asynchronous* library, and even though ``loadFinished`` was emitted, *QT* was still working on something in the background. One could easily find out what was *QT* exactly doing, by installing the famous *gdb* and the *QT4* library debugging symbols. After those tools are in place::

    $ gdb --args python test_qttut08_01_bad.py
    GNU gdb (Ubuntu/Linaro 7.4-2012.04-0ubuntu2.1) 7.4-2012.04
    Copyright (C) 2012 Free Software Foundation, Inc.
    ...
    ...
    (gdb) run
    Starting program: ...
    ...
    ...
    Program received signal SIGSEGV, Segmentation fault.
    (gdb) bt

and ``bt`` will give a very nice traceback. This leads to a conclusion that we should force *QT* somehow to stop tinkering around everything, before we schedule those components for deletion. Spending several hours on the subject (probably way more actually), I found a couple of things that can cause these problems (and there may be still some I didn't encounter so far), but almost all of them relates to *JavaScript*.

- Delayed requests, initiated by *JavaScript* code after the page was loaded and ``loadFinished`` was fired, will cause *QT* to try to access the already deleted ``QNetworkAccessManager``, resulting in a segfault.
- The same way, if the *JavaScript* code tries to access the DOM after the page was loaded, it will try to do that through a ``QWebFrame`` on the already deleted ``QWebPage``, resulting in a segfault as well.

All this means that we shall somehow disable *JavaScript* before the deletion. We will write a series of unittests which will try to simulate these conditions, and then enhance the shutdown method to take all the safety precautions we can think of, before deleting the ``QT`` components.

`qttut08_02_ok.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut08/qttut08_02_ok.py>`_.

`test_qttut08_02_ok.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut08/test_qttut08_02_ok.py>`_.

If you run ``test_qttut08_02_ok.py``, the same tests will be executed, but all of them will pass without provoking a segmentation fault. That's a relief, and success didn't require major changes. Only the shutdown method works a bit differently...quite differently.

So if you compare the previous shutdown implementation with the current one, you'll notice that the first one basically just stopped the webview, and scheduled all *QT* components for deletion. It didn't wait until they were actually deleted, it just went further, the tests created a new instance of a browser, and disaster came when no reference was retained to any of those components, yet they were accessed by *QT* during the deletion.

This new shutdown implementation accepts a callback function, which will be invoked after the deletion was really completed, and the instance can be freely abandoned, meaning our tests had to be modified a bit to use a callback chain. The process is simple, after the browser loads it's target, it invokes the ``Browser._result_callback`` function and pass the result of the page loading to it. As we are in charge of specifying that callback function, it is now a newly constructed partial object from the ``BrowserTest.completed_test`` method. This method (when invoked) actually constructs another partial object from the ``BrowserTest.check_result`` method(which is the actual function in charge of making the assertion) and freezes the ``result`` and ``expected`` values into it. The ``Browser.shutdown`` method is invoked at that point, and the new partial object is passed as the callback parameter to it. As soon as the browser shuts itself down, it will invoke the callback, and the actual assertion will happen at that point along with the shutdown procedure of the test server. Ok, that sounds messy, here's a pseudo snippet again::

    completed_test_callback = partial(BrowserTest.completed_test, expected_value)
    browser = create_browser(callback=completed_test_callback)
    browser.completed_test_callback(result)
    check_result_callback = partial(BrowserTest.check_result, expected_value, result_value)
    browser.shutdown(callback=check_result_callback)
    check_result_callback does the assertion

All this was required because shutdown happens asynchronously now. We connected the destroyed signal of all deletable *QT* components to a partial object, which is constructed from the ``Browser._destroyed`` method and it freezed the name of the component. When deletion is scheduled, and a bit later it actually happens, the destroyed signal is emitted, which invokes the ``Browser._destroyed`` method and the name of the deleted component will be passed to it. This name was already stored in a dictionary, and a ``False`` flag indicated that the component was not yet deleted. Now this flag is switched to ``True``, and a check will be ran to see if all the flags are set to ``True``. That condition will be met when all the components are deleted, and at that point, the shutdown callback function will be invoked. That's the story.

However, before these components were scheduled for deletion, we took several safety precautions to keep surprises out of the process. First we set the ``JavaScriptEnabled`` flag to ``False``, which luckily has the side effect of immediately stopping the execution of *JavaScript* code, not just allowing it's execution at the first place. This is followed by a call to a newly defined ``SmartNetworkAccessManager.abort_requests`` method, which basically just iterates through all the requests present in the ``SmartNetworkAccessManager._requests`` dictionary, and calls the ``abort`` method on all of them.

These two instructions are very important, even their order of invocation, because even though we have a way to prevent the browser from returning a result before all pending requests are finished, there is a possibility that some pages will schedule additional requests through *JavaScript*. Now imagine a situation where we schedule the deletion of our ``SmartNetworkAccessManager``, and at the moment it's deleted, a delayed request is created by the ``JavaScript`` code. That is a highly segfaulty scenario. So this is the reason why we first stop the execution of any *JavaScript* code on the page, then abort all the requests that may have been already scheduled the same way as we described now, and the deletion is scheduled only after that.

Also, it's time to reveal that dirty little classified secret from the previous chapter, where I stated that we must keep the ``SmartNetworkAccessManager._requests`` dictionary clean from already deleted reply objects. The reason for that is simple, if we would try to abort a reply object which is deleted by *QT* earlier, we would get a segfault, because we kept a reference to an object which was already destroyed, yet we tried to call one of it's methods. This wraps up about the whole shutdown thing, and I think everything is explained now.