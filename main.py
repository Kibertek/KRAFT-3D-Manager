import sys
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


# ============================================================
# ПУТИ ПРОГРАММЫ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
PRODUCTS_DIR = BASE_DIR / "products"
REPORTS_DIR = BASE_DIR / "reports"
BACKUPS_DIR = BASE_DIR / "backups"

DATABASE_FILE = DATA_DIR / "kraft3d.db"


# ============================================================
# СОЗДАНИЕ ПАПОК
# ============================================================

def create_directories():
    """Создаёт необходимые папки программы."""

    DATA_DIR.mkdir(exist_ok=True)
    PRODUCTS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    BACKUPS_DIR.mkdir(exist_ok=True)


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def initialize_database():
    """Создаёт локальную SQLite-базу и основные таблицы."""

    connection = sqlite3.connect(DATABASE_FILE)
    cursor = connection.cursor()

    # Настройки программы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT
        )
    """)

    # Каталог изделий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'Активно',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Материалы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            material_type TEXT,
            color TEXT,
            brand TEXT,
            spool_weight REAL DEFAULT 1000,
            spool_price REAL DEFAULT 0,
            price_per_gram REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Комплектующие
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            unit TEXT DEFAULT 'шт.',
            price REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Принтеры
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS printers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            power REAL DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            resource_hours REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# СТРАНИЦЫ
# ============================================================

class HomePage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("KRAFT 3D Manager")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Управление производством, себестоимостью и продажами"
        )
        subtitle.setObjectName("subtitle")

        welcome = QLabel(
            "Добро пожаловать!\n\n"
            "Здесь будет собрана вся информация по вашему 3D-производству."
        )
        welcome.setObjectName("welcomeText")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(welcome)
        layout.addStretch()


class ProductsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Изделия")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Здесь будет каталог изделий KRAFT 3D.\n\n"
            "Карточки товаров, фотографии, модели, G-code,\n"
            "описание, артикулы и расчёт себестоимости."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class MaterialsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Материалы")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Пластик, катушки, цвета, бренды и стоимость грамма."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class ComponentsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Комплектующие")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Фурнитура, крепёж, упаковка, магниты,\n"
            "кольца, цепочки и другие комплектующие."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class PrintersPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Принтеры")
        title.setObjectName("pageTitle")

        text = QLabel(
            "3D-принтеры, мощность, стоимость,\n"
            "ресурс и стоимость часа работы."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class CalculatorPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Калькулятор")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Здесь появится полноценный расчёт себестоимости изделия."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class ReportsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Отчёты")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Экспорт данных в Excel и формирование отчётов."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


class SettingsPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Настройки")
        title.setObjectName("pageTitle")

        text = QLabel(
            "Настройки программы, папок, расчётов и резервного копирования."
        )

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(text)
        layout.addStretch()


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("KRAFT 3D Manager")
        self.setMinimumSize(1100, 700)

        self.create_interface()

    # --------------------------------------------------------
    # ИНТЕРФЕЙС
    # --------------------------------------------------------

    def create_interface(self):

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------------------------------------------
        # БОКОВОЕ МЕНЮ
        # ----------------------------------------------------

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(6)

        # Логотип
        logo = QLabel("KRAFT 3D")
        logo.setObjectName("logo")

        logo_subtitle = QLabel("MANAGER")
        logo_subtitle.setObjectName("logoSubtitle")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(logo_subtitle)
        sidebar_layout.addSpacing(25)

        # ----------------------------------------------------
        # СТРАНИЦЫ
        # ----------------------------------------------------

        self.pages = QStackedWidget()

        self.home_page = HomePage()
        self.products_page = ProductsPage()
        self.materials_page = MaterialsPage()
        self.components_page = ComponentsPage()
        self.printers_page = PrintersPage()
        self.calculator_page = CalculatorPage()
        self.reports_page = ReportsPage()
        self.settings_page = SettingsPage()

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.products_page)
        self.pages.addWidget(self.materials_page)
        self.pages.addWidget(self.components_page)
        self.pages.addWidget(self.printers_page)
        self.pages.addWidget(self.calculator_page)
        self.pages.addWidget(self.reports_page)
        self.pages.addWidget(self.settings_page)

        # ----------------------------------------------------
        # КНОПКИ МЕНЮ
        # ----------------------------------------------------

        menu_buttons = [
            ("Главная", 0),
            ("Изделия", 1),
            ("Материалы", 2),
            ("Комплектующие", 3),
            ("Принтеры", 4),
            ("Калькулятор", 5),
            ("Отчёты", 6),
            ("Настройки", 7),
        ]

        for text, page_index in menu_buttons:

            button = QPushButton(text)
            button.setObjectName("menuButton")
            button.setCursor(Qt.PointingHandCursor)

            button.clicked.connect(
                lambda checked=False, index=page_index:
                self.change_page(index)
            )

            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        version = QLabel("KRAFT 3D Manager\nv0.1.0")
        version.setObjectName("version")

        sidebar_layout.addWidget(version)

        # ----------------------------------------------------
        # ДОБАВЛЯЕМ В ОСНОВНОЙ LAYOUT
        # ----------------------------------------------------

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.pages)

    # --------------------------------------------------------
    # ПЕРЕКЛЮЧЕНИЕ СТРАНИЦ
    # --------------------------------------------------------

    def change_page(self, index):

        self.pages.setCurrentIndex(index)


# ============================================================
# СТИЛИ
# ============================================================

STYLE = """

QMainWindow {
    background-color: #181818;
}

QWidget {
    color: #eeeeee;
    font-family: "Segoe UI";
    font-size: 14px;
}

#sidebar {
    background-color: #202020;
    border-right: 1px solid #303030;
}

#logo {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}

#logoSubtitle {
    color: #ff7a00;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
}

#menuButton {
    background-color: transparent;
    color: #bdbdbd;
    border: none;
    border-radius: 8px;
    padding: 12px 15px;
    text-align: left;
    font-size: 14px;
}

#menuButton:hover {
    background-color: #303030;
    color: #ffffff;
}

#menuButton:pressed {
    background-color: #ff7a00;
    color: #ffffff;
}

#pageTitle {
    color: #ffffff;
    font-size: 30px;
    font-weight: 700;
}

#subtitle {
    color: #ff7a00;
    font-size: 15px;
}

#welcomeText {
    color: #bdbdbd;
    font-size: 17px;
}

#version {
    color: #666666;
    font-size: 11px;
}

QLabel {
    color: #dddddd;
}

"""


# ============================================================
# ЗАПУСК
# ============================================================

def main():

    # Создаём структуру папок
    create_directories()

    # Создаём базу данных
    initialize_database()

    # Запускаем приложение
    app = QApplication(sys.argv)

    app.setApplicationName("KRAFT 3D Manager")
    app.setApplicationVersion("0.1.0")

    app.setFont(QFont("Segoe UI", 10))

    app.setStyleSheet(STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
