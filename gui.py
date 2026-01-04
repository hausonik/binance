import sys
import requests
import json
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QFileDialog, QMessageBox, QLineEdit, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from datetime import datetime

API_URL = "http://95.216.210.133:5000"

class BinanceDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binance GUI Bot")
        self.setGeometry(100, 100, 1200, 800)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Индикатор режима торговли
        self.mode_label = QLabel("Режим: Загрузка...")
        self.mode_label.setStyleSheet("font-weight: bold; padding: 5px;")
        self.layout.addWidget(self.mode_label)
        self.update_trading_mode()

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.init_signals_tab()
        self.init_recommendations_tab()
        self.init_trades_tab()

    def update_trading_mode(self):
        """Обновляет индикатор режима торговли."""
        try:
            res = requests.get(f"{API_URL}/trading_mode")
            data = res.json()
            mode = data.get("mode", "UNKNOWN")
            mode_names = {
                "CONFIRM_ALL": "🔒 Требуется подтверждение",
                "AUTO_GATED": "🟡 Авто (с проверкой риска)",
                "AUTO_ALL": "🟢 Полностью автоматический"
            }
            self.mode_label.setText(f"Режим торговли: {mode_names.get(mode, mode)}")
        except:
            self.mode_label.setText("Режим: Ошибка загрузки")

    # ---------------- Signals Tab ----------------
    def init_signals_tab(self):
        self.signals_tab = QWidget()
        self.tabs.addTab(self.signals_tab, "📡 Сигналы")

        layout = QVBoxLayout()
        self.signals_tab.setLayout(layout)

        self.signals_table = QTableWidget()
        layout.addWidget(self.signals_table)

        btn_refresh = QPushButton("🔄 Обновить сигналы")
        btn_refresh.clicked.connect(self.load_signals)
        layout.addWidget(btn_refresh)

        self.load_signals()

    def load_signals(self):
        try:
            res = requests.get(f"{API_URL}/scan_signals")
            data = res.json()
            signals = data.get("signals", [])
        except Exception as e:
            signals = []
            print("Ошибка загрузки сигналов:", e)

        self.signals_table.setRowCount(len(signals))
        self.signals_table.setColumnCount(2)
        self.signals_table.setHorizontalHeaderLabels(["Пара", "Тип"])

        for i, s in enumerate(signals):
            self.signals_table.setItem(i, 0, QTableWidgetItem(s.get("symbol", "")))
            self.signals_table.setItem(i, 1, QTableWidgetItem(s.get("type", "")))

    # ---------------- Recommendations Tab ----------------
    def init_recommendations_tab(self):
        self.reco_tab = QWidget()
        self.tabs.addTab(self.reco_tab, "💡 Предложения")

        layout = QVBoxLayout()
        self.reco_tab.setLayout(layout)

        self.reco_table = QTableWidget()
        layout.addWidget(self.reco_table)

        btn_refresh = QPushButton("🔄 Обновить предложения")
        btn_refresh.clicked.connect(self.load_recommendations)
        layout.addWidget(btn_refresh)

        self.open_trade_btn = QPushButton("🟢 Открыть выбранную сделку")
        self.open_trade_btn.clicked.connect(self.open_selected_trade)
        layout.addWidget(self.open_trade_btn)

        self.load_recommendations()

    def load_recommendations(self):
        try:
            res = requests.get(f"{API_URL}/recommend_all")
            recs = res.json().get("recommendations", [])
        except Exception as e:
            recs = []
            print("Ошибка загрузки предложений:", e)

        self.reco_table.setRowCount(len(recs))
        self.reco_table.setColumnCount(5)
        self.reco_table.setHorizontalHeaderLabels(["Пара", "Сумма", "TP%", "SL%", "Волат."])

        for i, r in enumerate(recs):
            self.reco_table.setItem(i, 0, QTableWidgetItem(r.get("symbol", "")))
            self.reco_table.setItem(i, 1, QTableWidgetItem(str(r.get("amount", ""))))
            self.reco_table.setItem(i, 2, QTableWidgetItem(str(r.get("take_profit_pct", ""))))
            self.reco_table.setItem(i, 3, QTableWidgetItem(str(r.get("stop_loss_pct", ""))))
            self.reco_table.setItem(i, 4, QTableWidgetItem(str(r.get("volatility_pct", ""))))

    def open_selected_trade(self):
        """Открываем выбранную рекомендацию через API"""
        row = self.reco_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите строку для открытия сделки")
            return

        symbol = self.reco_table.item(row, 0).text()
        amount = self.reco_table.item(row, 1).text()
        tp_pct = self.reco_table.item(row, 2).text()
        sl_pct = self.reco_table.item(row, 3).text()
        volatility = self.reco_table.item(row, 4).text()

        try:
            url = f"{API_URL}/open_trade?symbol={symbol}&amount={amount}&tp={tp_pct}&sl={sl_pct}&volatility={volatility}"
            res = requests.get(url)
            data = res.json()

            if data.get("message") == "BUY EXECUTED":
                QMessageBox.information(self, "Успех", f"Сделка {symbol} открыта")
                self.update_trade_table()
                self.load_recommendations()
                self.update_trading_mode()
            elif data.get("error") == "CONFIRM_REQUIRED":
                QMessageBox.warning(self, "Требуется подтверждение", 
                    "Режим торговли требует подтверждения всех сделок")
            else:
                QMessageBox.warning(self, "Ошибка", f"Ошибка открытия: {data.get('error','unknown')}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    # ---------------- Trades and PnL Tab ----------------
    def init_trades_tab(self):
        self.trades_tab = QWidget()
        self.tabs.addTab(self.trades_tab, "📊 Сделки и PnL")

        layout = QVBoxLayout()
        self.trades_tab.setLayout(layout)

        # График PnL
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        pnllayout = QHBoxLayout()

        self.period_selector = QComboBox()
        self.period_selector.addItems(["day", "week", "month", "year", "all"])
        self.period_selector.currentTextChanged.connect(self.update_pnl_chart)
        pnllayout.addWidget(QLabel("PnL за:"))
        pnllayout.addWidget(self.period_selector)

        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.clicked.connect(self.update_pnl_chart)
        pnllayout.addWidget(btn_refresh)

        btn_save = QPushButton("💾 Сохранить график")
        btn_save.clicked.connect(self.save_chart)
        pnllayout.addWidget(btn_save)

        layout.addLayout(pnllayout)

        # Таблица истории сделок
        self.trade_table = QTableWidget()
        self.trade_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.trade_table)

        # Кнопки управления позициями
        btn_layout = QHBoxLayout()
        
        btn_close = QPushButton("🔴 Закрыть позицию")
        btn_close.clicked.connect(self.close_selected_trade)
        btn_layout.addWidget(btn_close)

        btn_edit_tp_sl = QPushButton("✏️ Редактировать TP/SL")
        btn_edit_tp_sl.clicked.connect(self.edit_tp_sl)
        btn_layout.addWidget(btn_edit_tp_sl)

        btn_refresh_trades = QPushButton("🔄 Обновить таблицу")
        btn_refresh_trades.clicked.connect(self.update_trade_table)
        btn_layout.addWidget(btn_refresh_trades)

        layout.addLayout(btn_layout)

        self.update_pnl_chart()
        self.update_trade_table()

    def update_pnl_chart(self):
        """Обновляет график PnL из БД."""
        self.ax.clear()

        try:
            period = self.period_selector.currentText()
            res = requests.get(f"{API_URL}/pnl_history?period={period}")
            arr = res.json()
            
            if not arr:
                self.ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
                self.canvas.draw()
                return

            df = pd.DataFrame(arr)
            if "timestamp" in df.columns and "pnl" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")

                self.ax.plot(df["timestamp"], df["pnl"], marker="o", linewidth=2)
                self.ax.set_title(f"📈 PnL ({period})")
                self.ax.set_xlabel("Время")
                self.ax.set_ylabel("PnL (USDC)")
                self.ax.grid(True, alpha=0.3)
                plt.setp(self.ax.xaxis.get_majorticklabels(), rotation=45)
            else:
                self.ax.text(0.5, 0.5, "Неверный формат данных", ha="center", va="center")
        except Exception as e:
            self.ax.text(0.5, 0.5, f"Ошибка: {str(e)}", ha="center", va="center")

        self.canvas.draw()

    def update_trade_table(self):
        """Обновляет таблицу сделок из БД."""
        try:
            res = requests.get(f"{API_URL}/trades_export")
            trades = res.json()
        except Exception as e:
            trades = []
            print("Ошибка загрузки сделок:", e)

        self.trade_table.setRowCount(len(trades))
        self.trade_table.setColumnCount(8)
        self.trade_table.setHorizontalHeaderLabels(
            ["ID", "Пара", "Сторона", "Цена", "Кол-во", "TP%", "SL%", "Статус"]
        )

        for i, t in enumerate(reversed(trades)):
            self.trade_table.setItem(i, 0, QTableWidgetItem(str(t.get("id", ""))))
            self.trade_table.setItem(i, 1, QTableWidgetItem(t.get("symbol", "")))
            self.trade_table.setItem(i, 2, QTableWidgetItem(t.get("side", "")))
            self.trade_table.setItem(i, 3, QTableWidgetItem(str(t.get("price", ""))))
            self.trade_table.setItem(i, 4, QTableWidgetItem(str(t.get("quantity", ""))))
            self.trade_table.setItem(i, 5, QTableWidgetItem(str(t.get("take_profit_pct", ""))))
            self.trade_table.setItem(i, 6, QTableWidgetItem(str(t.get("stop_loss_pct", ""))))
            self.trade_table.setItem(i, 7, QTableWidgetItem(t.get("status", "")))

    def close_selected_trade(self):
        """Закрывает выбранную позицию."""
        row = self.trade_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите позицию для закрытия")
            return

        trade_id_item = self.trade_table.item(row, 0)
        if not trade_id_item:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить ID сделки")
            return

        trade_id = trade_id_item.text()
        status_item = self.trade_table.item(row, 7)
        status = status_item.text() if status_item else ""

        if status not in ["OPEN", "OPEN_SL_TP"]:
            QMessageBox.warning(self, "Ошибка", "Можно закрыть только открытые позиции")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Закрыть позицию #{trade_id}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                res = requests.post(f"{API_URL}/close_trade", json={"trade_id": int(trade_id)})
                data = res.json()
                if data.get("status") == "ok":
                    QMessageBox.information(self, "Успех", f"Позиция #{trade_id} закрыта")
                    self.update_trade_table()
                    self.update_pnl_chart()
                else:
                    QMessageBox.warning(self, "Ошибка", data.get("error", "Unknown error"))
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def edit_tp_sl(self):
        """Редактирует TP/SL для выбранной позиции."""
        row = self.trade_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите позицию")
            return

        trade_id_item = self.trade_table.item(row, 0)
        if not trade_id_item:
            return

        trade_id = trade_id_item.text()
        status_item = self.trade_table.item(row, 7)
        status = status_item.text() if status_item else ""

        if status not in ["OPEN", "OPEN_SL_TP"]:
            QMessageBox.warning(self, "Ошибка", "Можно редактировать только открытые позиции")
            return

        # Диалог редактирования
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать TP/SL")
        layout = QFormLayout(dialog)

        current_tp = self.trade_table.item(row, 5).text()
        current_sl = self.trade_table.item(row, 6).text()

        tp_edit = QLineEdit(current_tp)
        sl_edit = QLineEdit(current_sl)

        layout.addRow("Take Profit (%):", tp_edit)
        layout.addRow("Stop Loss (%):", sl_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_():
            try:
                new_tp = float(tp_edit.text())
                new_sl = float(sl_edit.text())

                res = requests.post(
                    f"{API_URL}/update_tp_sl",
                    json={"trade_id": int(trade_id), "tp_pct": new_tp, "sl_pct": new_sl}
                )
                data = res.json()
                if data.get("status") == "ok":
                    QMessageBox.information(self, "Успех", "TP/SL обновлены")
                    self.update_trade_table()
                else:
                    QMessageBox.warning(self, "Ошибка", data.get("error", "Unknown error"))
            except ValueError:
                QMessageBox.warning(self, "Ошибка", "Неверный формат чисел")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def save_chart(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Сохранить PNG", "", "PNG files (*.png)")
        if fname:
            self.figure.savefig(fname)

# ---------------- Run GUI ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BinanceDashboard()
    window.show()
    sys.exit(app.exec_())
