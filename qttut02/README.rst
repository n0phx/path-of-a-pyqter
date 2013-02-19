QRL (qt curl):
==============


Now as we want to use some more advanced features of *QT*, we will add some additional components to grant us greater control. As we saw in the previous example a ``QWebPage`` instance is added by default, even if we didn't create it explicitly. Also, all ``QWebPage`` instances have a ``QNetworkAccessManager`` instance attached to them. ``QNetworkAccessManager`` is invented to handle low-level networking, so it makes the actual requests, handles responses (called replies in *QT*), and it allows us to initiate requests manually, set the SSL settings, access cookies, etc.
So let's try out that powerful piece of equipment:

`qttut02.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut02/qttut02.py>`_.

Ok, so what we just created is most easily described as a dumbed-down *curl* written using *QT*. We can initiate http requests with it, send data and custom request headers to the targets. We passed a callback function to the ``NetManager``'s ``__init__`` method, which will be stored and called when ``QNetworkAccessManager``'s ``finished`` signal is emitted. So we initiate a request and once the reply has arrived, the ``finished`` signal is triggered. We connected the ``finished`` signal to our ``NetManager._finished`` method, where we extract some useful information from the reply, and pass that to the callback function, which will print the results. The callback itself is a newly constructed partial object, which we needed because the callback function needs access to the parent application in order to shut it down, but since the class which will invoke the callback function does not have access to the parent application, we freezed that parameter, and passed the freezed callable instead of the pure function.

The ``sslErrors`` signal which we connected to our ``NetManager._ssl_errors`` method is emitted in case we try to access a server running on https, and the SSL handshake fails for some reason. Well the most common reason is that the peer certificate validation fails, because there are no certificates installed at all, but expired or self-signed certificates will result with the same error. One solution for this is to ignore the error (like we did in this example), so it won't break the connection and will simply continue as if nothing happened. Of course that's not a good solution, it poses a security risk, because the SSL certificate validation was not completed, we kinda lose the point of using SSL at all. What we really need is a local store of certificates, and to do the validation properly, without ignoring SSL errors. That will be shown in the forthcoming examples.

Whenever you see in *QT*'s API documentation an attribute of a class for which the documentation states that it is a virtual function, you can simply bind a method(or even any callable? god bless *duck-typing*) to it. The only requirement is to accept the same number of input parameters, and return what the documentation states is expected of you. These virtual functions have a default implementation, but by binding your custom implementation, you can override the default one. We used the ``QNetworkAccessManager.createRequest`` virtual function, which is called every time a new request is created. Three parameters are passed to it, the request operation (method), the request object and the request data. It's task is to construct and return a ``QNetworkReply`` object from these parameters. This can be useful for a couple of reasons, first it's the only place where you can actually ``peek`` into the post data the network manager wants to send, and second, you can influence the request, like modifying it's SSL configuration, cookies, etc. By peeking I literally mean we have to use the ``peek`` method of the data object passed to the function, because it's a ``QIODevice`` instance. There are two types of ``QIODevices``, random access and sequential ``QIODevices``. Unfortunately this one's type is sequential, so it does not allow seeking, meaning if you would try to use ``data.readAll()``, you would get the data being posted, but *QT* won't be able to read it later, because the pointer has been moved, and we can not reset it. The only problem with the ``peek`` method is that it requires the number of bytes we want to read as input parameter. There is a conveniently looking function for obtaining the size of the ``QIODevice`` data, called ``bytesAvailable``, but unfortunately it was unreliable in my trials, as it always returned 0. I finally ended up hardcoding a value as size, like 8192 (8 kilobytes), which works, but we can not be sure that the size of the outgoing data won't get bigger than that, so use it only for debugging. Getting back to ``peek``, it reads the data, but does not move the pointer in the ``QIODevice``, so that's why we can use it, because it will leave the object in the same state as it was before peeking. Quantum mechanics made it's way into *QT* definitely.

As for the ``reply.deleteLater()`` call at the end of our ``NetManager.finished`` method, it was called because the *QT* documentation states that we are in charge of doing the cleanup of the reply objects. This means that we have to delete them explicitly, but not the way as we delete normal *Python* objects, as it would cause a segfault, because the method which emitted the ``finished`` signal will try to access the object after our method attached to the ``finished`` signal is executed. So instead we call the ``deleteLater`` method on it, which schedules the object for deletion, which will happen when control returns to the event loop.

While working with *QT*, the majority of segfaults are caused because of improper object deletions or losing references to objects in use. So when you instantiate a *QT* object in a method / function, but you don't store a reference to it somewhere, after it falls out of scope, *Python*'s garbage collector will mercilessly delete it, and that may cause a segfault. That's a pretty common pitfall. The main reason why that happens is that as we said earlier, *QT* is an *async* library, so let's say you instantiate an object in a method, you call a method on it, and of course it will immediately return, whereas you may have expected that the method will return only after it's executed, but it didn't happen that way, it's actually running in the background, and will emit a signal once it's finished. So you called that method, it returned immediately, *Python* reaches the end of the method where the object was instantiated, but the object's method is still running in the background, the object falls out of scope after *Python* leaves the method, and the garbage collector deletes it. When the background execution finishes, it emits the signal which will try to access the already deleted object, and that is a pure segfault scenario. Here's a pseudo-snippet of the situation::


    class SomeClass(object):
        ...
        def our_method(self):
            some_qt_object = QSomeObjectName()         # Instantiate a QT object in a method
            some_qt_object.call_a_method()             # Call one of the object's methods, which returns immediately after it was called,
                                                       # but is actually still running in the background
            return                                     # Python leaves our method, the object falls out of scope, and will be deleted

        # SEGFAULT!!


So to avoid these kind of problems, store a reference to the object as a class attribute, assuming of course that your class won't be deleted.::


    class SomeClass(object):
        ...
        def our_method(self):
            self.some_qt_object = QSomeObjectName()         # Instantiate a QT object in a method
            self.some_qt_object.call_a_method()             # Call one of the object's methods, which returns immediately after it was called,
                                                            # but is actually still running in the background
            return                                          # Python leaves our method, the object is stored as a class attribute, so it won't
                                                            # be deleted as long as the class won't be deleted


There are still some possible segfault scenarios, we'll cover some of them when we reach those code parts.