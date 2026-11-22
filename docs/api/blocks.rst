Content blocks
==============

The blocks that hold content. Every block takes ``name=`` (a stable id) and
``label=`` (its title inside a :class:`~briefing.Select`) as its last arguments.

.. currentmodule:: briefing

Text and code
-------------

.. autoclass:: Text
.. autoclass:: HTML
.. autoclass:: Code
.. autoclass:: Formula

Highlights
----------

.. autoclass:: BigNumber
.. autoclass:: Alert
.. autoclass:: AlertLevel
   :members:
   :undoc-members:
.. autoclass:: Chips
.. autoclass:: Chip
.. autoclass:: Banner
.. autoclass:: Image
.. autoclass:: Attachment

Data and charts
---------------

.. autoclass:: Plot
.. autoclass:: DataTable
.. autoclass:: Table

Base class
----------

.. autoclass:: Block
.. autofunction:: wrap_block

Prose helpers
-------------

.. autofunction:: briefing.from_markdown

.. automodule:: briefing.fmt
   :members: date, span, percent, number

.. autofunction:: briefing.slug
