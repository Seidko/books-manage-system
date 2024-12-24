from textual import on, work
from textual.app import App
from textual.screen import Screen
from textual.containers import Container, Center, Horizontal
from textual.widgets import Label, DataTable, Input, Button
from textual.coordinate import Coordinate
from sqlite3 import connect, Connection, OperationalError
from typing import Optional

COLUMNS = ("id", "name", "author", "publish", "isbn", "status", "location")

class BookTable(DataTable):
    db: Connection
    def __init__(self, db, *, show_header = True, show_row_labels = True, fixed_rows = 0, fixed_columns = 0, zebra_stripes = False, header_height = 1, show_cursor = True, cursor_foreground_priority = "css", cursor_background_priority = "renderable", cursor_type = "cell", cell_padding = 1, name = None, id = None, classes = None, disabled = False):
        self.db = db
        super().__init__(show_header=show_header, show_row_labels=show_row_labels, fixed_rows=fixed_rows, fixed_columns=fixed_columns, zebra_stripes=zebra_stripes, header_height=header_height, show_cursor=show_cursor, cursor_foreground_priority=cursor_foreground_priority, cursor_background_priority=cursor_background_priority, cursor_type=cursor_type, cell_padding=cell_padding, name=name, id=id, classes=classes, disabled=disabled)

    def on_mount(self):
        super().on_mount()
        self.add_columns(*("ID", "书名", "作者", "出版年份", "ISBN", "状态", "所在位置", "删除"))
        self.display()
    
    def display(self, query = None):
        if query is None or query == "":
            query = "true"
        result = map(lambda x: list(x) + ["X"], self.db.execute(f"SELECT * FROM books WHERE {query};"))
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
                yield Label(self.column_label, classes="item-labels")
                yield Input(self.value, id="item")
            with Horizontal():
                    yield Button("确定", id="button-confirm")
                    yield Button("取消", id="button-cancel", action="screen.dismiss")
    
    @on(Button.Pressed, "#button-confirm")
    def confirm(self):
        value: Optional[str] = self.query_one("#item").value
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
                yield Label("书名", classes="item-labels")
                yield Input(id="name")
            with Horizontal():
                yield Label("作者", classes="item-labels")
                yield Input(id="author")
            with Horizontal():
                yield Label("出版年份", classes="item-labels")
                yield Input(id="publish")
            with Horizontal():
                yield Label("ISBN", classes="item-labels")
                yield Input(id="isbn")
            with Horizontal():
                yield Label("状态", classes="item-labels")
                yield Input(id="status")
            with Horizontal():
                yield Label("所在位置", classes="item-labels")
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

        self.db.execute(f"""
INSERT INTO books (name, author, publish, isbn, status, location) VALUES
(?,?,?,?,?,?);""", (name, author, publish, isbn, status, location))
        self.db.commit()
        
        self.dismiss()

class BookApp(App):
    CSS_PATH = "table.tcss"
    BINDINGS = [("c", "push_screen('create')", "Create Screen")]

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
            yield Label("使用说明：点击+号创建新书数据，点击X删除数据，点击单元格修改数据，在下面的输入框输入SQL语句查询数据。", id="manual")
            yield Input("", placeholder="输入SQL查询语句：（WHERE 后面的部分）", id="query")

            error = Label("查询语法错误！", id="error")
            error.visible = False
            yield error

            with Center():
                yield BookTable(self.db, id="table")

    def on_mount(self):
        self.install_screen(CreateScreen(self.db), name="create")

    @work
    @on(DataTable.CellSelected)
    async def cell_selected(self, event: DataTable.CellSelected):
        if event.coordinate.column == 0 and event.coordinate.row == event.data_table.row_count - 1:
            await self.push_screen_wait("create")
            table: BookTable = self.query_one("#table")
            table.display(self.query)
        if event.coordinate.column == 7 and event.coordinate.row < event.data_table.row_count - 1:
            table: BookTable = self.query_one("#table")
            id = table.get_cell_at(Coordinate(event.coordinate.row, 0))
            self.db.execute("DELETE FROM books WHERE id = ?;", (id,))
            self.db.commit()
            table.remove_row(table.coordinate_to_cell_key(event.coordinate).row_key)
        if 0 < event.coordinate.column < 7 and event.coordinate.row < event.data_table.row_count - 1:
            table: BookTable = self.query_one("#table")
            value = await self.push_screen_wait(ModifyScreen(
                self.db,
                table.get_cell_at(Coordinate(event.coordinate.row, 0)),
                COLUMNS[event.coordinate.column],
                table.columns[table.coordinate_to_cell_key(event.coordinate).column_key].label,
                table.get_cell_at(event.coordinate),
            ))
            if value is not None:
                table.update_cell_at(event.coordinate, value)
    
    @on(Input.Submitted, "#query")
    def query(self, event: Input.Submitted):
        self.query = event.value
        table: BookTable = self.query_one("#table")
        error_label: Label = self.query_one("#error")
        try:
            table.display(event.value)
        except OperationalError:
            error_label.visible = True
        else:
            error_label.visible = False



if __name__ == "__main__":
    app = BookApp(connect("books.db"))
    app.run()