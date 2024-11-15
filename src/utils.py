import pandas as pd
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils.cell import get_column_letter
from openpyxl.styles import NamedStyle, Font, Alignment, Border, Side


def format_sheet(writer, name: str, df: pd.DataFrame, header, table):
    sheet: Worksheet = writer.sheets[name]
    for c_idx, row in enumerate(sheet.iter_rows()):
        for cell in row:
            cell.style = header if not c_idx else table
    for c_idx, col in enumerate(df.columns):
        column_width = max(8, df[col].astype(str).str.len().max(), df[col].name.__len__())
        sheet.column_dimensions[get_column_letter(c_idx + 1)].width = column_width


def generate_style():
    side = Side(border_style="thin", color="000000")
    font = "Sarasa Gothic TC"

    header = NamedStyle("标题样式")
    header.font = Font(name=font, bold=True, size=10)
    header.alignment = Alignment(horizontal="center", vertical="center")
    header.border = Border(left=side, right=side, top=side, bottom=side)
    table = NamedStyle("数据样式")
    table.font = Font(name=font, bold=False, size=10)
    table.alignment = Alignment(vertical="center")
    table.border = Border(left=side, right=side, top=side, bottom=side)

    return header, table


def save_temp_xlsx(data: dict[str, pd.DataFrame]):
    writer = pd.ExcelWriter("temp.xlsx", engine="openpyxl")

    header, table = generate_style()

    for name, df in data.items():
        df.to_excel(writer, sheet_name=name, index=False)
        format_sheet(writer, name, df, header, table)
    writer.close()
