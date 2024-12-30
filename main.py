from textual import on, work
from textual.app import App
from textual.screen import Screen
from textual.containers import Container, Center, Horizontal, Vertical
from textual.widgets import Label, DataTable, Input, Button
from textual.coordinate import Coordinate
from sqlite3 import connect, Connection
from typing import Optional

COLUMNS = ("id", "name", "author", "publish", "isbn", "status", "location")

class BookTable(DataTable):
    db: Connection

    operation_map = {
        "已借出": "归还",
        "在库": "借出",
    }

    @staticmethod
    def mapper(x):
        x = list(x)
        if x[5] in BookTable.operation_map:
            x.append(BookTable.operation_map[x[5]])
        else:
            x.append(None)
        x.append("X")
        return x

        
    def __init__(self, db, *, show_header = True, show_row_labels = True, fixed_rows = 0, fixed_columns = 0, zebra_stripes = False, header_height = 1, show_cursor = True, cursor_foreground_priority = "css", cursor_background_priority = "renderable", cursor_type = "cell", cell_padding = 1, name = None, id = None, classes = None, disabled = False):
        self.db = db
        super().__init__(show_header=show_header, show_row_labels=show_row_labels, fixed_rows=fixed_rows, fixed_columns=fixed_columns, zebra_stripes=zebra_stripes, header_height=header_height, show_cursor=show_cursor, cursor_foreground_priority=cursor_foreground_priority, cursor_background_priority=cursor_background_priority, cursor_type=cursor_type, cell_padding=cell_padding, name=name, id=id, classes=classes, disabled=disabled)

    def on_mount(self):
        super().on_mount()
        self.add_columns(*("ID", "书名", "作者", "出版年份", "ISBN", "状态", "所在位置", "操作", "删除"))
        self.display()
    
    def display(self, query = None):
        if query is None or query == "":
            result = map(BookTable.mapper, self.db.execute("SELECT * FROM books"))
        else:
            result = map(BookTable.mapper, self.db.execute(f'SELECT * FROM books WHERE id=? OR name LIKE ? OR author LIKE ? OR location LIKE ? OR isbn LIKE ?;', [query] + [f"%{query}%"] * 4))
        self.clear()
        self.add_rows(result)
        self.add_row("+")

class ModifyScreen(Screen):
    CSS_PATH = "create.tcss"

    db: Connection
    cell_id: int
    column: str
    column_label: str
    value: str

    def __init__(self, db: Connection, id: int, column: str, label: str, value: str):
        self.db = db
        self.cell_id = id
        self.column = column
        self.column_label = label
        self.value = value
        super().__init__()

    def compose(self):
        with Container(id="container"):
            with Horizontal():
                yield Label(self.column_label, classes="input-labels")
                yield Input(self.value, id="input")
            with Horizontal():
                    yield Button("确定", id="button-confirm")
                    yield Button("取消", id="button-cancel", action="screen.dismiss")
    
    @on(Button.Pressed, "#button-confirm")
    @on(Input.Submitted, "#input")
    def confirm(self):
        value: Optional[str] = self.query_one("#input").value
        self.db.execute(f"UPDATE books SET {self.column} = ? WHERE id = ?;", (value, self.cell_id))
        self.db.commit()
        
        self.dismiss(value)

class CreateScreen(Screen):
    CSS_PATH = "create.tcss"

    db: Connection

    def __init__(self, db: Connection):
        self.db = db
        super().__init__()

    def compose(self):
        with Container(id="container"):
            with Horizontal():
                yield Label("书名", classes="input-labels")
                yield Input(id="name")
            with Horizontal():
                yield Label("作者", classes="input-labels")
                yield Input(id="author")
            with Horizontal():
                yield Label("出版年份", classes="input-labels")
                yield Input(id="publish")
            with Horizontal():
                yield Label("ISBN", classes="input-labels")
                yield Input(id="isbn")
            with Horizontal():
                yield Label("状态", classes="input-labels")
                yield Input(id="status")
            with Horizontal():
                yield Label("所在位置", classes="input-labels")
                yield Input(id="location")
            with Horizontal():
                yield Button("确定", id="button-confirm")
                yield Button("取消", id="button-cancel", action="screen.dismiss")


    @on(Button.Pressed, "#button-confirm")
    def confirm(self):
        name: Optional[str] = self.query_one("#name").value
        author: Optional[str] = self.query_one("#author").value
        publish: Optional[str] = self.query_one("#publish").value
        isbn: Optional[str] = self.query_one("#isbn").value
        status: Optional[str] = self.query_one("#status").value
        location: Optional[str] = self.query_one("#location").value

        cur = self.db.execute(f"""
INSERT INTO books (name, author, publish, isbn, status, location) VALUES
(?,?,?,?,?,?) RETURNING *;""", (name, author, publish, isbn, status, location))
        row = cur.fetchone()
        self.db.commit()
        
        self.dismiss(row)

class BookApp(App):
    CSS_PATH = "table.tcss"

    db: Connection
    query: Optional[str]

    def __init__(self, db: Connection):
        super().__init__()
        self.db = db
        self.query = None
        db.execute("""
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    author TEXT,
    publish DATE,
    isbn TEXT,
    status TEXT,
    location TEXT
);
""")

    def compose(self):
        with Container(id="container"):
            with Center():
                yield Label("图书管理", id="title")
            yield Label("使用说明：点击+号创建新书数据，点击X删除数据，点击单元格修改数据，在下面的输入框输入SQL语句查询数据。按Ctrl+Q退出程序。", id="manual")
            yield Input("", placeholder="搜索", id="query")

            with Vertical(id="table-scroller"):
                yield BookTable(self.db, id="table")

    @work
    @on(DataTable.CellSelected)
    async def cell_selected(self, event: DataTable.CellSelected):
        if event.coordinate.column == 0 and event.coordinate.row == event.data_table.row_count - 1:
            row = await self.push_screen_wait(CreateScreen(self.db))
            if row is not None:
                table = event.data_table
                table.remove_row(table.coordinate_to_cell_key(Coordinate(event.data_table.row_count - 1, 0)).row_key)
                table.add_row(*BookTable.mapper(row))
                table.add_row("+")

        if event.coordinate.column == 7 and event.coordinate.row < event.data_table.row_count - 1:
            table = event.data_table
            id = table.get_cell_at(Coordinate(event.coordinate.row, 0))
            status = table.get_cell_at(Coordinate(event.coordinate.row, 5))
            if status == "已借出":
                status = "在库"
                operation = "借出"
            elif status == "在库":
                status = "已借出"
                operation = "归还"
            else:
                status = None

            if status is not None:
                self.db.execute(f"UPDATE books SET status = ? WHERE id = ?;", (status, id))
                self.db.commit()
                table.update_cell_at(Coordinate(event.coordinate.row, 5), status)
                table.update_cell_at(event.coordinate, operation)

        if event.coordinate.column == 8 and event.coordinate.row < event.data_table.row_count - 1:
            table = event.data_table
            id = table.get_cell_at(Coordinate(event.coordinate.row, 0))
            self.db.execute("DELETE FROM books WHERE id = ?;", (id,))
            self.db.commit()
            table.remove_row(table.coordinate_to_cell_key(event.coordinate).row_key)
                
        if 0 < event.coordinate.column < 7 and event.coordinate.row < event.data_table.row_count - 1:
            table = event.data_table
            value = await self.push_screen_wait(ModifyScreen(
                self.db,
                table.get_cell_at(Coordinate(event.coordinate.row, 0)),
                COLUMNS[event.coordinate.column],
                table.columns[table.coordinate_to_cell_key(event.coordinate).column_key].label,
                table.get_cell_at(event.coordinate),
            ))
            if value is not None:
                table.update_cell_at(event.coordinate, value)
                if event.coordinate.column == 5:
                    if value in BookTable.operation_map:
                        table.update_cell_at(Coordinate(event.coordinate.row, 7), BookTable.operation_map[value])
                    else:
                        table.update_cell_at(Coordinate(event.coordinate.row, 7), None)
    
    @on(Input.Submitted, "#query")
    def query(self, event: Input.Submitted):
        self.query = event.value
        table: BookTable = self.query_one("#table")
        table.display(event.value)

if __name__ == "__main__":
    app = BookApp(connect("books.db"))
    app.run()