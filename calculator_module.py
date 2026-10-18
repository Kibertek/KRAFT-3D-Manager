import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QMessageBox,
    QFrame,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "kraft3d.db"
PRODUCTS_DIR = BASE_DIR / "products"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def parse_number(text):
    text = str(text).strip().replace(" ", "").replace(",", ".")
    if not text:
        return 0.0

    try:
        return max(0.0, float(text))
    except ValueError:
        return 0.0


def money(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def number(value, decimals=2):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def safe_folder_name(value):
    invalid = '<>:"/\\|?*'
    value = "".join("_" if char in invalid else char for char in value)
    return value.strip(" .") or "product"


class NumberInput(QLineEdit):
    """Числовое поле с поддержкой десятичной запятой."""

    def __init__(self, value="0", decimals=3, parent=None):
        super().__init__(parent)

        validator = QDoubleValidator(0.0, 100000000.0, decimals, self)
        validator.setLocale(QLocale(QLocale.Language.Russian))
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.setValidator(validator)
        self.setMinimumHeight(30)
        self.setText(str(value).replace(".", ","))

    def value(self):
        return parse_number(self.text())


class AddProductDialog(QDialog):
    """Форма добавления товара из калькулятора."""

    def __init__(self, parent=None, article="K3D-001"):
        super().__init__(parent)

        self.setWindowTitle("Добавить изделие в каталог")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.article_input = QLineEdit(article)
        self.article_input.setPlaceholderText("Например, K3D-001")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название изделия")

        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems([
            "Брелоки и сувениры",
            "Предметы для дома",
            "Органайзеры",
            "Подарки",
            "Детали и комплектующие",
            "Прочее",
        ])

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Описание изделия и примечания"
        )
        self.description_input.setMaximumHeight(110)

        form.addRow("Артикул *", self.article_input)
        form.addRow("Название *", self.name_input)
        form.addRow("Категория", self.category_input)
        form.addRow("Описание", self.description_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_form)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.category_input.setCurrentText("Брелоки и сувениры")

    def validate_form(self):
        if not self.article_input.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажи артикул изделия.")
            self.article_input.setFocus()
            return

        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажи название изделия.")
            self.name_input.setFocus()
            return

        self.accept()

    def get_data(self):
        return {
            "article": self.article_input.text().strip(),
            "name": self.name_input.text().strip(),
            "category": (
                self.category_input.currentText().strip()
                or "Без категории"
            ),
            "description": self.description_input.toPlainText().strip(),
        }


class MaterialCostRow(QWidget):
    """Одна строка материала и расхода."""

    def __init__(self, materials, changed_callback, remove_callback):
        super().__init__()

        self.materials = materials
        self.changed_callback = changed_callback
        self.remove_callback = remove_callback

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 3, 0, 3)
        row_layout.setSpacing(8)

        self.material_combo = QComboBox()
        self.material_combo.setMinimumWidth(220)
        self.material_combo.setMinimumHeight(34)
        self.material_combo.setSizePolicy(
            self.material_combo.sizePolicy().Policy.Expanding,
            self.material_combo.sizePolicy().Policy.Fixed,
        )

        self.grams_input = NumberInput("30", decimals=3)
        self.grams_input.setMaximumWidth(110)
        self.grams_input.setToolTip(
            "Расход выбранного материала на одно изделие, в граммах"
        )

        self.cost_label = QLabel("0,00 ₽")
        self.cost_label.setMinimumWidth(105)
        self.cost_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.remove_button = QPushButton("Удалить")
        self.remove_button.setMaximumWidth(90)

        row_layout.addWidget(self.material_combo, 1)
        row_layout.addWidget(QLabel("Расход, г:"))
        row_layout.addWidget(self.grams_input)
        row_layout.addWidget(self.cost_label)
        row_layout.addWidget(self.remove_button)

        self.material_combo.currentIndexChanged.connect(
            self.changed_callback
        )
        self.grams_input.textChanged.connect(self.changed_callback)
        self.remove_button.clicked.connect(self.remove_self)

        self.refresh_materials()

    def refresh_materials(self):
        """Обновляет список материалов, сохраняя текущий выбор."""

        current_data = self.material_combo.currentData()
        current_id = current_data.get("id") if current_data else None

        self.material_combo.blockSignals(True)
        self.material_combo.clear()
        self.material_combo.addItem("Выберите материал", None)

        for material in self.materials:
            self.material_combo.addItem(
                f"{material['name']} "
                f"({money(material['price_per_gram'])}/г)",
                material,
            )

        if current_id is not None:
            for index in range(self.material_combo.count()):
                data = self.material_combo.itemData(index)

                if data and data["id"] == current_id:
                    self.material_combo.setCurrentIndex(index)
                    break

        self.material_combo.blockSignals(False)

    def remove_self(self):
        self.remove_callback(self)

    def selected_material(self):
        return self.material_combo.currentData()

    def cost(self):
        material = self.selected_material()

        if not material:
            return 0.0

        return material["price_per_gram"] * self.grams_input.value()

    def update_cost(self):
        self.cost_label.setText(money(self.cost()))


class ComponentCostRow(QWidget):
    """Одна строка комплектующего в калькуляторе."""

    def __init__(self, components, changed_callback, remove_callback):
        super().__init__()

        self.changed_callback = changed_callback
        self.remove_callback = remove_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.component_combo = QComboBox()
        self.component_combo.setMinimumWidth(220)
        self.component_combo.setSizePolicy(
            self.component_combo.sizePolicy().Policy.Expanding,
            self.component_combo.sizePolicy().Policy.Fixed,
        )

        self.component_combo.addItem("Выберите комплектующее", None)

        for component in components:
            self.component_combo.addItem(
                f"{component['name']} "
                f"({money(component['price'])}/{component['unit']})",
                {
                    "id": component["id"],
                    "price": component["price"],
                    "unit": component["unit"],
                },
            )

        self.quantity_input = NumberInput("1", decimals=3)
        self.quantity_input.setMaximumWidth(100)
        self.quantity_input.setToolTip("Количество комплектующих")

        self.cost_label = QLabel("0,00 ₽")
        self.cost_label.setMinimumWidth(100)
        self.cost_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.remove_button = QPushButton("Удалить")
        self.remove_button.setMaximumWidth(90)

        layout.addWidget(self.component_combo, 1)
        layout.addWidget(QLabel("Кол-во:"))
        layout.addWidget(self.quantity_input)
        layout.addWidget(self.cost_label)
        layout.addWidget(self.remove_button)

        self.component_combo.currentIndexChanged.connect(
            self.changed_callback
        )
        self.quantity_input.textChanged.connect(self.changed_callback)
        self.remove_button.clicked.connect(self.remove_self)

        self.update_cost()

    def remove_self(self):
        self.remove_callback(self)

    def selected_component(self):
        return self.component_combo.currentData()

    def cost(self):
        component = self.selected_component()

        if not component:
            return 0.0

        return component["price"] * self.quantity_input.value()

    def update_cost(self):
        self.cost_label.setText(money(self.cost()))


class CalculatorPage(QWidget):
    MAX_MATERIALS = 4

    def __init__(self, parent=None):
        super().__init__(parent)

        self.materials = []
        self.components = []
        self.packaging_kits = []
        self.material_rows = []
        self.component_rows = []

        self.setup_ui()
        self.load_reference_data()
        self.recalculate()

    def setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(12)

        title = QLabel("Калькулятор себестоимости")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        outer_layout.addWidget(title)

        description = QLabel(
            "Расчёт затрат на печать, комплектующие и продажу изделия."
        )
        description.setStyleSheet("color: #aaaaaa;")
        outer_layout.addWidget(description)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 8, 2)
        layout.setSpacing(14)

        self.setStyleSheet("""
            QWidget {
                color: #F2F2F2;
            }

            QGroupBox {
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #606060;
                border-radius: 7px;
                margin-top: 12px;
                padding: 12px;
            }

            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                background-color: #252525;
            }

            QLabel {
                color: #F2F2F2;
                background-color: transparent;
            }

            QLineEdit, QComboBox, QTextEdit {
                background-color: #353535;
                color: #FFFFFF;
                border: 1px solid #707070;
                border-radius: 5px;
                padding: 6px;
                min-height: 20px;
                selection-background-color: #E88732;
                selection-color: #FFFFFF;
            }

            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #E88732;
            }

            QComboBox QAbstractItemView {
                background-color: #353535;
                color: #FFFFFF;
                selection-background-color: #E88732;
                selection-color: #FFFFFF;
            }

            QPushButton {
                background-color: #414141;
                color: #FFFFFF;
                border: 1px solid #606060;
                border-radius: 5px;
                padding: 7px 10px;
            }

            QPushButton:hover {
                background-color: #E88732;
                color: #FFFFFF;
            }

            QPushButton#accentButton {
                background-color: #ff7a00;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }

            QPushButton#accentButton:hover {
                background-color: #e86f00;
            }

            
            QScrollArea {
                background-color: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }

        """)

        # 1. Материалы
        material_group = QGroupBox("1. Материалы")
        material_layout = QVBoxLayout(material_group)
        material_layout.setSpacing(6)

        material_description = QLabel(
            "Добавьте до 4 материалов. Для каждого укажите расход в граммах."
        )
        material_description.setWordWrap(True)
        material_description.setStyleSheet("color: #bbbbbb;")
        material_layout.addWidget(material_description)

        self.material_rows_layout = QVBoxLayout()
        self.material_rows_layout.setSpacing(4)
        material_layout.addLayout(self.material_rows_layout)

        self.add_material_button = QPushButton("+ Добавить материал")
        self.add_material_button.clicked.connect(self.add_material_row)
        material_layout.addWidget(
            self.add_material_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.material_cost_label = QLabel("Итого по материалам: 0,00 ₽")
        self.material_cost_label.setStyleSheet(
            "font-weight: bold; color: #ff9d3d;"
        )
        material_layout.addWidget(self.material_cost_label)

        layout.addWidget(material_group)

        # 2. Комплектующие
        component_group = QGroupBox("2. Комплектующие и упаковка")
        component_layout = QVBoxLayout(component_group)

        self.component_rows_layout = QVBoxLayout()
        self.component_rows_layout.setSpacing(5)
        component_layout.addLayout(self.component_rows_layout)

        add_component_button = QPushButton("+ Добавить комплектующее")
        add_component_button.clicked.connect(self.add_component_row)
        component_layout.addWidget(
            add_component_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        packaging_layout = QHBoxLayout()
        self.packaging_kit_combo = QComboBox()
        self.packaging_kit_combo.addItem("Без набора упаковки", None)
        self.packaging_kit_combo.setMinimumWidth(250)
        self.packaging_kit_quantity = NumberInput("1", decimals=3)
        self.packaging_kit_quantity.setMaximumWidth(100)
        self.packaging_kit_quantity.setToolTip("Количество наборов упаковки на одно изделие")
        self.packaging_kit_cost_label = QLabel("0,00 ₽")
        packaging_layout.addWidget(QLabel("Набор упаковки:"))
        packaging_layout.addWidget(self.packaging_kit_combo, 1)
        packaging_layout.addWidget(QLabel("Кол-во:"))
        packaging_layout.addWidget(self.packaging_kit_quantity)
        packaging_layout.addWidget(self.packaging_kit_cost_label)
        component_layout.addLayout(packaging_layout)
        self.packaging_kit_combo.currentIndexChanged.connect(self.recalculate)
        self.packaging_kit_quantity.textChanged.connect(self.recalculate)

        self.components_cost_label = QLabel(
            "Итого по комплектующим и упаковке: 0,00 ₽"
        )
        self.components_cost_label.setStyleSheet(
            "font-weight: bold; color: #ff9d3d;"
        )
        component_layout.addWidget(self.components_cost_label)

        layout.addWidget(component_group)

        # 3. Производственные затраты
        production_group = QGroupBox("3. Производственные затраты")
        production_form = QFormLayout(production_group)

        self.print_hours = NumberInput("2", decimals=2)
        self.print_hours.setToolTip("Время печати в часах, например 1,5")

        self.printer_watts = NumberInput("150", decimals=2)
        self.electricity_tariff = NumberInput("7", decimals=4)
        self.depreciation_per_hour = NumberInput("10", decimals=2)
        self.labor_cost = NumberInput("0", decimals=2)
        self.other_costs = NumberInput("0", decimals=2)

        production_form.addRow("Время печати (ч):", self.print_hours)
        production_form.addRow("Мощность принтера (Вт):", self.printer_watts)
        production_form.addRow(
            "Тариф электричества (₽/кВт·ч):",
            self.electricity_tariff,
        )
        production_form.addRow(
            "Износ принтера (₽/ч):",
            self.depreciation_per_hour,
        )
        production_form.addRow(
            "Работа и постобработка (₽):",
            self.labor_cost,
        )
        production_form.addRow(
            "Прочие расходы на изделие (₽):",
            self.other_costs,
        )

        self.electricity_cost_label = QLabel("0,00 ₽")
        self.depreciation_cost_label = QLabel("0,00 ₽")

        production_form.addRow("Электричество:", self.electricity_cost_label)
        production_form.addRow("Амортизация:", self.depreciation_cost_label)

        layout.addWidget(production_group)

        # 4. Продажа и расходы маркетплейса
        sales_group = QGroupBox("4. Продажа и расходы маркетплейса")
        sales_form = QFormLayout(sales_group)

        self.sale_price = NumberInput("265", decimals=2)
        self.tax_percent = NumberInput("4", decimals=2)
        self.commission_percent = NumberInput("23", decimals=2)
        self.fbs_percent = NumberInput("0", decimals=2)

        self.fbs_percent.setToolTip(
            "Все дополнительные расходы в процентах от цены продажи. "
            "Учитывайте здесь расходы, которые ещё не внесены отдельно."
        )

        sales_form.addRow("Цена продажи (₽):", self.sale_price)
        sales_form.addRow("Налог (%):", self.tax_percent)
        sales_form.addRow("Комиссия площадки (%):", self.commission_percent)
        sales_form.addRow("FBS и продвижение (%):", self.fbs_percent)

        layout.addWidget(sales_group)

        # 5. Результат расчёта
        results_group = QGroupBox("5. Результат расчёта")
        results_layout = QGridLayout(results_group)

        self.material_total_result = QLabel("0,00 ₽")
        self.components_total_result = QLabel("0,00 ₽")
        self.production_total_result = QLabel("0,00 ₽")
        self.marketplace_total_result = QLabel("0,00 ₽")
        self.total_cost_result = QLabel("0,00 ₽")
        self.profit_result = QLabel("0,00 ₽")
        self.margin_result = QLabel("0,00 %")
        self.markup_result = QLabel("0,00 %")

        result_rows = [
            ("Материалы:", self.material_total_result),
            ("Комплектующие:", self.components_total_result),
            ("Производственные расходы:", self.production_total_result),
            ("Налог и маркетплейс:", self.marketplace_total_result),
            ("Полная себестоимость:", self.total_cost_result),
            ("Прибыль с одного изделия:", self.profit_result),
            ("Рентабельность от цены продажи:", self.margin_result),
            ("Наценка на прямые затраты:", self.markup_result),
        ]

        for row_index, (caption, value_label) in enumerate(result_rows):
            results_layout.addWidget(QLabel(caption), row_index, 0)
            results_layout.addWidget(value_label, row_index, 1)

        self.total_cost_result.setStyleSheet(
            "font-size: 15px; font-weight: bold;"
        )
        self.profit_result.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #ff9d3d;"
        )

        layout.addWidget(results_group)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Кнопки действий
        buttons_layout = QHBoxLayout()

        recalculate_button = QPushButton("Пересчитать")
        recalculate_button.clicked.connect(self.recalculate)
        buttons_layout.addWidget(recalculate_button)

        add_product_button = QPushButton("Добавить в список товаров")
        add_product_button.setObjectName("accentButton")
        add_product_button.clicked.connect(self.add_product_to_catalog)
        buttons_layout.addWidget(add_product_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll, 1)

        # Подключаем пересчёт после создания всех полей.
        inputs = [
            self.print_hours,
            self.printer_watts,
            self.electricity_tariff,
            self.depreciation_per_hour,
            self.labor_cost,
            self.other_costs,
            self.sale_price,
            self.tax_percent,
            self.commission_percent,
            self.fbs_percent,
        ]

        for field in inputs:
            field.textChanged.connect(self.recalculate)

        self.add_material_row()

    def load_reference_data(self):
        self.materials = []
        self.components = []

        try:
            with get_connection() as connection:
                material_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(materials)"
                    ).fetchall()
                }

                component_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(components)"
                    ).fetchall()
                }

                if not material_columns or not component_columns:
                    QMessageBox.warning(
                        self,
                        "Справочники не найдены",
                        "Не найдены таблицы материалов или комплектующих. "
                        "Сначала откройте соответствующие разделы программы.",
                    )
                    return

                required_material_columns = {
                    "id", "name", "spool_weight", "spool_price"
                }

                if not required_material_columns.issubset(material_columns):
                    QMessageBox.warning(
                        self,
                        "Структура материалов",
                        "В таблице материалов отсутствуют необходимые поля.",
                    )
                    return

                material_rows = connection.execute("""
                    SELECT id, name, spool_weight, spool_price
                    FROM materials
                    ORDER BY name COLLATE NOCASE
                """).fetchall()

                required_component_columns = {
                    "id", "name", "price", "unit"
                }

                if not required_component_columns.issubset(component_columns):
                    QMessageBox.warning(
                        self,
                        "Структура комплектующих",
                        "В таблице комплектующих отсутствуют необходимые поля.",
                    )
                    return

                component_rows = connection.execute("""
                    SELECT id, name, price, unit
                    FROM components
                    ORDER BY name COLLATE NOCASE
                """).fetchall()

                kit_rows = []
                table_names = {
                    row["name"] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if {"packaging_kits", "packaging_kit_items", "packaging_labels"}.issubset(table_names):
                    kit_rows = connection.execute("""
                        SELECT k.id, k.name,
                               COALESCE(SUM(
                                   CASE WHEN i.item_type = 'component' THEN COALESCE(c.price, 0)
                                        WHEN i.item_type = 'label' THEN COALESCE(l.price, 0)
                                        ELSE 0 END * i.quantity
                               ), 0) AS total
                        FROM packaging_kits k
                        LEFT JOIN packaging_kit_items i ON i.kit_id = k.id
                        LEFT JOIN components c ON i.item_type = 'component' AND i.item_id = c.id
                        LEFT JOIN packaging_labels l ON i.item_type = 'label' AND i.item_id = l.id
                        GROUP BY k.id, k.name
                        ORDER BY k.name COLLATE NOCASE
                    """).fetchall()

            for material in material_rows:
                weight = float(material["spool_weight"] or 0)
                spool_price = float(material["spool_price"] or 0)

                price_per_gram = (
                    spool_price / weight if weight > 0 else 0
                )

                self.materials.append({
                    "id": material["id"],
                    "name": material["name"],
                    "price_per_gram": price_per_gram,
                })

            self.components = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": float(row["price"] or 0),
                    "unit": row["unit"] or "шт.",
                }
                for row in component_rows
            ]
            self.packaging_kits = [
                {"id": row["id"], "name": row["name"], "price": float(row["total"] or 0)}
                for row in kit_rows
            ]
            selected_kit_id = self.packaging_kit_combo.currentData()
            self.packaging_kit_combo.blockSignals(True)
            self.packaging_kit_combo.clear()
            self.packaging_kit_combo.addItem("Без набора упаковки", None)
            for kit in self.packaging_kits:
                self.packaging_kit_combo.addItem(
                    f"{kit['name']} ({money(kit['price'])})", kit["id"]
                )
            if selected_kit_id is not None:
                index = self.packaging_kit_combo.findData(selected_kit_id)
                if index >= 0:
                    self.packaging_kit_combo.setCurrentIndex(index)
            self.packaging_kit_combo.blockSignals(False)

            for row in self.material_rows:
                row.materials = self.materials
                row.refresh_materials()

            if not self.materials:
                QMessageBox.information(
                    self,
                    "Нет материалов",
                    "Добавьте материалы в разделе «Материалы», "
                    "чтобы рассчитывать стоимость пластика.",
                )

            self.update_material_buttons()

        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Ошибка базы данных",
                f"Не удалось загрузить справочники:\n{error}",
            )

    def add_material_row(self):
        if len(self.material_rows) >= self.MAX_MATERIALS:
            return

        row = MaterialCostRow(
            self.materials,
            self.recalculate,
            self.remove_material_row,
        )

        self.material_rows.append(row)
        self.material_rows_layout.addWidget(row)

        self.update_material_buttons()
        self.recalculate()

    def remove_material_row(self, row):
        if len(self.material_rows) <= 1:
            return

        if row in self.material_rows:
            self.material_rows.remove(row)
            self.material_rows_layout.removeWidget(row)
            row.deleteLater()

            self.update_material_buttons()
            self.recalculate()

    def update_material_buttons(self):
        count = len(self.material_rows)

        self.add_material_button.setEnabled(
            count < self.MAX_MATERIALS
        )

        for row in self.material_rows:
            row.remove_button.setEnabled(count > 1)

        if count >= self.MAX_MATERIALS:
            self.add_material_button.setText("Добавлено 4 материала")
        else:
            self.add_material_button.setText("+ Добавить материал")

    def add_component_row(self):
        if not self.components:
            QMessageBox.information(
                self,
                "Нет комплектующих",
                "Сначала добавьте комплектующие в разделе «Комплектующие».",
            )
            return

        row = ComponentCostRow(
            self.components,
            self.recalculate,
            self.remove_component_row,
        )

        self.component_rows.append(row)
        self.component_rows_layout.addWidget(row)
        self.recalculate()

    def remove_component_row(self, row):
        if row in self.component_rows:
            self.component_rows.remove(row)
            self.component_rows_layout.removeWidget(row)
            row.deleteLater()
            self.recalculate()

    def recalculate(self, *_):
        # Общая стоимость всех выбранных материалов.
        material_cost = 0.0

        for row in self.material_rows:
            row.update_cost()
            material_cost += row.cost()

        # Общая стоимость комплектующих и выбранного набора упаковки.
        components_cost = 0.0

        for row in self.component_rows:
            row.update_cost()
            components_cost += row.cost()

        selected_kit_id = self.packaging_kit_combo.currentData()
        selected_kit = next(
            (kit for kit in self.packaging_kits if kit["id"] == selected_kit_id),
            None,
        )
        packaging_cost = (
            selected_kit["price"] * self.packaging_kit_quantity.value()
            if selected_kit else 0.0
        )
        components_cost += packaging_cost
        self.packaging_kit_cost_label.setText(money(packaging_cost))

        # Производственные затраты.
        hours = self.print_hours.value()
        watts = self.printer_watts.value()
        tariff = self.electricity_tariff.value()
        depreciation_rate = self.depreciation_per_hour.value()
        labor = self.labor_cost.value()
        other = self.other_costs.value()

        electricity_cost = watts * hours / 1000 * tariff
        depreciation_cost = hours * depreciation_rate

        production_cost = (
            electricity_cost
            + depreciation_cost
            + labor
            + other
        )

        # Расходы на продажу.
        sale_price = self.sale_price.value()
        tax_percent = self.tax_percent.value()
        commission_percent = self.commission_percent.value()
        fbs_percent = self.fbs_percent.value()

        marketplace_cost = sale_price * (
            tax_percent + commission_percent + fbs_percent
        ) / 100

        # Полная себестоимость и прибыль.
        direct_cost = (
            material_cost
            + components_cost
            + production_cost
        )

        total_cost = direct_cost + marketplace_cost
        profit = sale_price - total_cost

        margin = (
            profit / sale_price * 100
            if sale_price > 0 else 0
        )

        markup = (
            profit / direct_cost * 100
            if direct_cost > 0 else 0
        )

        # Промежуточные суммы.
        self.material_cost_label.setText(
            f"Итого по материалам: {money(material_cost)}"
        )
        self.components_cost_label.setText(
            f"Итого по комплектующим: {money(components_cost)}"
        )
        self.electricity_cost_label.setText(money(electricity_cost))
        self.depreciation_cost_label.setText(money(depreciation_cost))

        # Итоговые показатели.
        self.material_total_result.setText(money(material_cost))
        self.components_total_result.setText(money(components_cost))
        self.production_total_result.setText(money(production_cost))
        self.marketplace_total_result.setText(money(marketplace_cost))
        self.total_cost_result.setText(money(total_cost))
        self.profit_result.setText(money(profit))
        self.margin_result.setText(f"{number(margin)} %")
        self.markup_result.setText(f"{number(markup)} %")

        # Статус расчёта.
        if sale_price <= 0:
            message = "Укажите цену продажи больше нуля."
            color = "#ffcc66"
        elif profit < 0:
            message = (
                "Убыток: расходы превышают цену продажи. "
                "Увеличьте цену или уменьшите затраты."
            )
            color = "#ff7777"
        elif profit == 0:
            message = "Продажа без прибыли: вы покрываете только расходы."
            color = "#ffcc66"
        else:
            message = "Изделие приносит прибыль при указанных параметрах."
            color = "#8bd49c"

        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"font-weight: bold; color: {color}; padding: 5px;"
        )

    def suggest_article(self):
        """Находит следующий свободный артикул K3D-XXX."""

        try:
            with get_connection() as connection:
                rows = connection.execute(
                    "SELECT article FROM products"
                ).fetchall()

            used_articles = {
                row["article"].strip().upper()
                for row in rows
                if row["article"]
            }

            number_value = 1

            while True:
                article = f"K3D-{number_value:03d}"

                if article.upper() not in used_articles:
                    return article

                number_value += 1

        except sqlite3.Error:
            return "K3D-001"

    def create_product_folder(self, product_id, article):
        """Создаёт папку изделия и стандартные подкаталоги."""

        PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

        folder_name = safe_folder_name(article)
        folder = PRODUCTS_DIR / folder_name

        if folder.exists():
            folder = PRODUCTS_DIR / f"{folder_name}_{product_id}"

        folder.mkdir(parents=True, exist_ok=True)

        for name in (
            "photos",
            "source",
            "slicer",
            "gcode",
            "documents",
            "other",
        ):
            (folder / name).mkdir(exist_ok=True)

        relative_path = folder.relative_to(BASE_DIR).as_posix()

        with get_connection() as connection:
            connection.execute(
                "UPDATE products SET folder_path = ? WHERE id = ?",
                (relative_path, product_id),
            )

    def add_product_to_catalog(self):
        """Добавляет изделие в существующий каталог товаров."""

        dialog = AddProductDialog(
            self,
            article=self.suggest_article(),
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        product_id = None

        try:
            with get_connection() as connection:
                cursor = connection.execute("""
                    INSERT INTO products (
                        article,
                        name,
                        description,
                        category,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    data["article"],
                    data["name"],
                    data["description"],
                    data["category"],
                    "Активно",
                ))

                product_id = cursor.lastrowid

            self.create_product_folder(
                product_id,
                data["article"],
            )

            QMessageBox.information(
                self,
                "Товар добавлен",
                f"Изделие «{data['name']}» добавлено в каталог.\n\n"
                f"Артикул: {data['article']}\n"
                f"Цена продажи: {money(self.sale_price.value())}\n"
                f"Себестоимость: {self.total_cost_result.text()}\n"
                f"Прибыль: {self.profit_result.text()}\n\n"
                "Финансовые показатели показаны для справки. "
                "Они пока не сохраняются в отдельных полях товара.",
            )

        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Артикул уже существует",
                "Такой артикул уже есть в каталоге. "
                "Укажи другой артикул.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка добавления",
                f"Не удалось добавить изделие:\n{error}",
            )