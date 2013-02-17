Driving our browser
===================


In order to actually use the features we implemented in the last segment, it's not enough to just make a request followed by the commands we want to run, because we're in "*async* mode". So after a request is made, we need to wait for the signal that tells us the page is loaded to be able to run our next command, then wait again, then run a command, and so on. The process is naturally separated into steps, we do something in one step, after a response we run another step, etc. So we need to implement a chain of steps. Let's look at the code:

| 

`qttut05.py 
<https://github.com/integricho/path-of-a-pyqter/blob/master/qttut05/qttut05.py>`_.

| 

Feels hackish? Well it is. We haven't touched the ``Browser`` class, but implemented two new classes. We got a ``BaseWebDriver`` class which implements the basic mechanism to run all the steps we define, and when the process is finished or fails, report it to the user and exit the application. It's ``__init__`` method accepts the parent application as parameter (it's clear for what reasons), a browser class (not an instance) so one could easily mock it and write ``unittest``'s, and the options dictionary which will be passed to the browser class when we instantiate it.

| 

Magic happens after instantiating the browser, where we loop through all the attributes of the web driver class, and we're checking if an attribute name starts with the ``'step_'`` string. We do that because a subclass of ``BaseWebDriver`` will need to define only these step methods in it's body. So we collect all these method names in a list, and sort them. This of course requires that the subclass is properly implemented, so the step method names are joined with a number indicating which step it is. After we have the list of method names, we create a generator expression, which will get the methods by their name (stored in the list), and yield them one by one.

| 

We passed the ``BaseWebDriver._finished`` method to the browser class as our callback function. This means when the ``loadFinished`` signal is emitted, no matter what will the result be, it will be passed to our callback function, which will check if the request was successful or not. In case it is not successful, it will print the error and quit the application. However if it was successful, we call the ``BaseWebDriver.run`` method, passing the html document to it as the only parameter, which we got as the result from the previous request. The ``BaseWebDriver.run`` method's ``html`` parameter is optional, because we use the very same ``run`` method to start the whole driving process, in which case on the first step we don't have an html result to pass to it yet. We could even avoid passing anything to the run method, and get the html document manually on each step by accessing our browser, but since the browser is already doing that for us (``loadFinished`` returns the html in the result), why would we ignore that convenient feature.

So the ``BaseWebDriver.run`` method tries to get the next step from our generator, and in case it raises the ``StopIteration`` exception, it means there are no more steps left to do, meaning the process is finished. If the generator returns a step method, we call it, and pass the previous step's html result to it. This can be useful if the next step needs to extract some information from the page in order to continue with the execution(dependencies are the first thing that came to my mind). In case the step method raises an exeption, the process will be aborted too.

| 

The ``HackerNewsDriver`` class which inherits our ``BaseWebDriver`` class, basically just defines the browser options it wishes to use in it's ``__init__`` method and calls the ``__init__`` method of it's *superclass* with that parameter and with the chosen browser class. The rest of it's body will contain the step methods, which basically just tells in which step where to click, and what input fields to fill with what values.
Surprisingly it actually works, and you may check out the log files what requests were made, what post data was sent, etc. You could even write the html data to a file at each step, to see what was actually loaded. Just make sure you replace the **username** / **password** values to make the login happen.