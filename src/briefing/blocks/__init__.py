"""briefing.blocks — core block types re-exported from one place.

Custom-visualisation blocks (DataProfile, DataDive) live in ``briefing.lab``.
"""
from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block, BlockId, BlockOrPrimitive, ContainerBlock, wrap_block
from briefing.blocks.layout import Briefing, Group, Page, Select, SelectType, Toggle, VAlign
from briefing.blocks.text import HTML, Alert, AlertLevel, BigNumber, Code, Formula, Text

__all__: list[str] = [
    # base
    "Block",
    "BlockId",
    "BlockOrPrimitive",
    "ContainerBlock",
    "wrap_block",
    # text
    "Alert",
    "AlertLevel",
    "BigNumber",
    "Code",
    "Formula",
    "HTML",
    "Text",
    # layout
    "Briefing",
    "Group",
    "Page",
    "Select",
    "SelectType",
    "Toggle",
    "VAlign",
    # asset
    "Banner",
    "DataTable",
    "Plot",
    "Table",
]
