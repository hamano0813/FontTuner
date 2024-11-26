import re
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, NamedStyle, Side
from openpyxl.worksheet.worksheet import Worksheet

from constants import FONT_WEIGHT, FONT_WIDTH


def format_sheet(writer: pd.ExcelWriter, name: str, header: NamedStyle, table: NamedStyle):
    """Format the sheet with the given name."""
    sheet: Worksheet = writer.sheets[name]
    for c_idx, row in enumerate(sheet.iter_rows()):
        for cell in row:
            cell.style = header if not c_idx else table


def init_style() -> tuple[NamedStyle, NamedStyle]:
    """Initialize the styles for the Excel file."""
    side = Side(border_style="thin", color="000000")
    font = "Sarasa Gothic TC"

    header = NamedStyle("标题样式")
    header.font = Font(name=font, bold=True, size=9)
    header.alignment = Alignment(horizontal="center", vertical="center")
    header.border = Border(left=side, right=side, top=side, bottom=side)
    table = NamedStyle("数据样式")
    table.font = Font(name=font, bold=False, size=9)
    table.alignment = Alignment(vertical="center")
    table.border = Border(left=side, right=side, top=side, bottom=side)

    return header, table


def write_excel(metadata_df: pd.DataFrame):
    """Write the metadata to an Excel file."""
    illegal_characters_re = re.compile(r'[\x00-\x1F]')
    def clean_illegal_characters(value):
        if isinstance(value, str):  # 仅对字符串进行清理
            return illegal_characters_re.sub("", value)
        return value
    metadata_df = metadata_df.map(clean_illegal_characters)   

    writer = pd.ExcelWriter("metadata.xlsx", engine="openpyxl")
    header, table = init_style()


    metadata_df.to_excel(writer, sheet_name="metadata", index=False)

    weight_df = pd.DataFrame(FONT_WEIGHT.values(), index=FONT_WEIGHT.keys(), columns=["English", "Chinese"])
    width_df = pd.DataFrame(FONT_WIDTH.values(), index=FONT_WIDTH.keys(), columns=["English", "Chinese"])
    weight_df.to_excel(writer, sheet_name="weight", index=True)
    width_df.to_excel(writer, sheet_name="width", index=True)

    format_sheet(writer, "metadata", header, table)
    format_sheet(writer, "weight", header, table)
    format_sheet(writer, "width", header, table)
    writer.close()


def read_excel(path: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="metadata", engine="openpyxl", dtype=str, na_values="", keep_default_na=False)
