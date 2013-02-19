Contents
========


- `Simple Browser <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut01>`_.
- `QRL <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut02>`_.
- `Joining forces of QRL and the Browser <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut03>`_.
- `Improving the Browser <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut04>`_.
- `Driving our browser <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut05>`_.
- `Solving SSL problems <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut06>`_.
- `Network errors, timeouts <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut07>`_.
- `Dynamic creation and deletion of browser instances <https://github.com/integricho/path-of-a-pyqter/tree/master/qttut08>`_.
- Accessing Frames
- Using Popups


Introduction
============


There's no doubt, *QT* is an incredibly awesome library. Unfortunately it's *Python* bindings, specifically it's ``QtWebKit`` and ``QtNetwork`` modules are not really well documented, I mean there are some tutorials scattered accross the web, the API documentation, and even some books covering parts of it, but in reality newcomers have a really hard time finding good resources for it. I found myself in the same situation, and had to learn it the hard way.

The API documentation is really good indeed, but it takes some time to figure out how things work, and in many cases you have to read *C++* answers on `stackoverflow <http://stackoverflow.com/>`_
, because no one asked such things for *Python*. Not to mention the times when you have to step through mailing lists, issue trackers, or the actual *C++* source code, when something just doesn't work the way you expected.

So while you're trying to figure out why the heck you got a segfault, why was or wasn't your signal emitted and similar questions, you'll learn a great deal. Some may think it's a waste of time, but I myself enjoyed every minute of doing that kind of research. The only thing I don't like about *QT* is it's unpythonic syntax, but that's again something we can live with...

My knowlegde is still limited and of course the need for quality articles on *QT*'s exotic modules won't be satisfied with this one, but I'll share what I learned. My observations and explanations may be wrong in some parts, so please report any issues you find, I intend to correct them. Let's start with some basics...


Laying the foundation
=====================


*QT* is an *asynschronous* library, roughly meaning most of it's methods will instantly return when they're invoked, without returning any result. But once the called method has some result, it will emit a signal. Our task is to connect handler functions to these signals and they will be called once the signal is emitted. All this is possible because of *QT*'s event loop, which basically along it's primary task to loop infinitely, emits and listens to signals.

*QT*'s ``QtWebKit`` module is extremely powerful, as it's one of the few libraries allowing us to create scrapers and webdrivers with *JavaScript* support. Of course there are numerous solutions already wrapping ``QtWebKit``, like *spynner*, *ghost.py*,... which are perfect to quickly scrape pages requiring *JavaScript*, but in some cases we still need to sit down and code our own tools.