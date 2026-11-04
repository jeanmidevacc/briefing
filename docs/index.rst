briefing
========

**briefing** turns analysis into one self-contained HTML file, built from a small
grammar of blocks — text, numbers, charts, tables and layout — that people and
coding agents both write. Reports work offline forever: no CDN, no server.

.. code-block:: bash

   pip install briefing

.. code-block:: python

   import briefing as bf

   bf.save(
       [
           bf.Text("# Weekly sales"),
           bf.Group(bf.BigNumber("Revenue", "$1.2M"), bf.BigNumber("Orders", 8_421), columns=2),
       ],
       "sales.html",
   )

.. toctree::
   :maxdepth: 2
   :caption: Guides

   quickstart
   guides/text
   guides/tables
   guides/charts
   guides/layout
   guides/banner
   guides/assets
   guides/theming
   guides/notebooks
   guides/export
   guides/lab
   recipes

.. toctree::
   :maxdepth: 2
   :caption: API reference

   api/blocks
   api/layout
   api/formatting
   api/output
   api/lab

.. toctree::
   :maxdepth: 1
   :caption: Project

   changelog
   GitHub <https://github.com/jeanmidevacc/briefing>
