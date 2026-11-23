Saving and exporting
====================

.. currentmodule:: briefing

HTML
----

.. autofunction:: save
.. autofunction:: run
.. autofunction:: stringify
.. autofunction:: embed_assets
.. autofunction:: preview
.. autoclass:: Preview

Images and PDF
--------------

Both need ``pip install "briefing[image]"`` and, once, ``playwright install chromium``.
The same exports run from the command line as ``python -m briefing image`` and
``python -m briefing pdf`` (``python -m briefing --help`` lists the options).

.. autofunction:: save_image
.. autofunction:: save_pdf

Email digests
-------------

.. automodule:: briefing.email
   :members: Digest, to_message, to_eml, to_html, to_text, Picture, from_report
   :no-index:

.. currentmodule:: briefing

Slide decks
-----------

.. automodule:: briefing.deck
   :members: Deck, Slide, to_html, save, save_pdf, save_image, from_spec, from_report
   :no-index:

.. currentmodule:: briefing

Comparing runs
--------------

.. autofunction:: diff

Errors
------

.. autoexception:: BriefingError
.. autoexception:: ExperimentalWarning
