Saving and exporting
====================

.. currentmodule:: briefing

HTML
----

.. autofunction:: save
.. autofunction:: stringify
.. autofunction:: preview
.. autoclass:: Preview

Images and PDF
--------------

Both need ``pip install "briefing[image]"`` and, once, ``playwright install chromium``.
The same exports run from the command line as ``python -m briefing image`` and
``python -m briefing pdf`` (``python -m briefing --help`` lists the options).

.. autofunction:: save_image
.. autofunction:: save_pdf

Errors
------

.. autoexception:: BriefingError
