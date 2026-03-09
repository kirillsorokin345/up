#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Менеджер заявок "Конди-Сервис" - система учета ремонта климатического оборудования
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime
import qrcode
import os
import time
from functools import wraps
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any


# =============================================================================
# КОНФИГУРАЦИЯ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

@dataclass
class AppConfig:
    """Конфигурация приложения"""
    DB_NAME: str = 'climate_repair.db'
    APP_TITLE: str = "❄️ Конди-Сервис | Учет ремонта"
    WINDOW_SIZE: str = "1000x600"
    FEEDBACK_URL: str = "https://docs.google.com/forms/d/e/1FAIpQLSdhZcExx6LSIXxk0ub55mSu-WIh23WYdGG9HY5EZhLDo7P8eA/viewform?usp=sf_link"
    COLOR_BG: str = "#f0f2f5"
    COLOR_PRIMARY: str = "#3498db"
    COLOR_SUCCESS: str = "#2ecc71"
    COLOR_WARNING: str = "#f39c12"
    COLOR_DANGER: str = "#e74c3c"
    COLOR_DARK: str = "#2c3e50"


class DatabaseManager:
    """Менеджер работы с базой данных"""

    def __init__(self, db_path: str = 'climate_repair.db'):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Создает подключение к БД с оптимальными настройками"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.row_factory = sqlite3.Row  # Возвращаем записи как словари
        return conn

    @staticmethod
    def retry_on_lock(max_attempts: int = 3):
        """Декоратор для повторных попыток при блокировке БД"""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except sqlite3.OperationalError as e:
                        if 'database is locked' in str(e) and attempt < max_attempts - 1:
                            time.sleep(0.5 * (attempt + 1))
                            continue
                        raise

            return wrapper

        return decorator


# =============================================================================
# КЛАССЫ ДЛЯ РАБОТЫ С ДАННЫМИ
# =============================================================================

class UserSession:
    """Класс для хранения данных текущей сессии пользователя"""

    def __init__(self):
        self.user_id: Optional[int] = None
        self.role_id: Optional[int] = None
        self.username: Optional[str] = None
        self.full_name: Optional[str] = None

    def is_authenticated(self) -> bool:
        return self.user_id is not None

    def clear(self):
        self.user_id = None
        self.role_id = None
        self.username = None
        self.full_name = None

    @property
    def role_name(self) -> str:
        roles = {1: "Оператор", 2: "Специалист", 3: "Заказчик", 4: "Менеджер"}
        return roles.get(self.role_id, "Неизвестно")


# =============================================================================
# БАЗОВЫЙ КЛАСС ДЛЯ ЭКРАНОВ
# =============================================================================

class BaseScreen(ttk.Frame):
    """Базовый класс для всех экранов приложения"""

    def __init__(self, parent, controller, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.controller = controller
        self.db = DatabaseManager()
        self.session = controller.session
        self._setup_style()

    def _setup_style(self):
        """Настройка стилей для экрана"""
        style = ttk.Style()
        style.configure("Screen.TFrame", background=AppConfig.COLOR_BG)
        self.configure(style="Screen.TFrame")

    def on_show(self):
        """Вызывается при показе экрана"""
        pass

    def on_hide(self):
        """Вызывается при скрытии экрана"""
        pass


# =============================================================================
# ЭКРАН АВТОРИЗАЦИИ
# =============================================================================

class LoginScreen(BaseScreen):
    """Экран входа в систему"""

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Центральный контейнер
        self.center_frame = ttk.Frame(self)
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")

        # Заголовок
        title_label = tk.Label(
            self.center_frame,
            text="❄️ Конди-Сервис",
            font=("Segoe UI", 28, "bold"),
            fg=AppConfig.COLOR_PRIMARY,
            bg=AppConfig.COLOR_BG
        )
        title_label.pack(pady=(0, 20))

        subtitle_label = tk.Label(
            self.center_frame,
            text="Система учета заявок на ремонт",
            font=("Segoe UI", 12),
            fg=AppConfig.COLOR_DARK,
            bg=AppConfig.COLOR_BG
        )
        subtitle_label.pack(pady=(0, 30))

        # Карточка входа
        login_card = ttk.Frame(self.center_frame, relief="solid", borderwidth=1)
        login_card.pack(padx=20, pady=10, fill="both")

        # Поля ввода
        ttk.Label(login_card, text="Логин:", font=("Segoe UI", 10)).pack(pady=(20, 5))
        self.login_entry = ttk.Entry(login_card, font=("Segoe UI", 11), width=25)
        self.login_entry.pack(padx=30, pady=(0, 10))
        self.login_entry.bind("<Return>", lambda e: self.password_entry.focus())

        ttk.Label(login_card, text="Пароль:", font=("Segoe UI", 10)).pack(pady=(5, 5))
        self.password_entry = ttk.Entry(login_card, show="●", font=("Segoe UI", 11), width=25)
        self.password_entry.pack(padx=30, pady=(0, 20))
        self.password_entry.bind("<Return>", lambda e: self._login())

        # Кнопка входа
        login_btn = tk.Button(
            login_card,
            text="🔑 ВОЙТИ",
            font=("Segoe UI", 11, "bold"),
            bg=AppConfig.COLOR_PRIMARY,
            fg="white",
            cursor="hand2",
            relief="flat",
            padx=30,
            pady=8,
            command=self._login
        )
        login_btn.pack(pady=(0, 30))
        login_btn.bind("<Enter>", lambda e: login_btn.config(bg="#2980b9"))
        login_btn.bind("<Leave>", lambda e: login_btn.config(bg=AppConfig.COLOR_PRIMARY))

    def on_show(self):
        self.login_entry.focus()

    def _login(self):
        """Обработка попытки входа"""
        username = self.login_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning("Внимание", "Пожалуйста, заполните все поля!")
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, role_id, fio FROM users WHERE login=? AND password=?",
                    (username, password)
                )
                user = cursor.fetchone()

            if user:
                self.session.user_id = user['id']
                self.session.role_id = user['role_id']
                self.session.full_name = user['fio']
                self.session.username = username

                self.login_entry.delete(0, tk.END)
                self.password_entry.delete(0, tk.END)

                self.controller.show_screen("main")
                messagebox.showinfo(
                    "Добро пожаловать",
                    f"Здравствуйте, {user['fio']}!\nВаша роль: {self.session.role_name}"
                )
            else:
                messagebox.showerror("Ошибка", "Неверный логин или пароль!")
                self.password_entry.delete(0, tk.END)

        except sqlite3.Error as e:
            messagebox.showerror("Ошибка базы данных", str(e))


# =============================================================================
# ГЛАВНЫЙ ЭКРАН
# =============================================================================

class MainScreen(BaseScreen):
    """Главный экран со списком заявок"""

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Верхняя панель
        self._create_top_panel()

        # Панель инструментов
        self._create_toolbar()

        # Таблица заявок
        self._create_requests_table()

        # Нижняя панель
        self._create_bottom_panel()

    def _create_top_panel(self):
        """Создание верхней панели с заголовком"""
        header_frame = tk.Frame(self, bg=AppConfig.COLOR_PRIMARY, height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        # Логотип и название
        title_label = tk.Label(
            header_frame,
            text="📋 УПРАВЛЕНИЕ ЗАЯВКАМИ",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg=AppConfig.COLOR_PRIMARY
        )
        title_label.pack(side="left", padx=20, pady=15)

        # Информация о пользователе
        user_frame = tk.Frame(header_frame, bg=AppConfig.COLOR_PRIMARY)
        user_frame.pack(side="right", padx=20)

        user_label = tk.Label(
            user_frame,
            text="👤 Пользователь",
            font=("Segoe UI", 10),
            fg="white",
            bg=AppConfig.COLOR_PRIMARY
        )
        user_label.pack(side="left", padx=5)

        role_label = tk.Label(
            user_frame,
            text="Роль:",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=AppConfig.COLOR_PRIMARY
        )
        role_label.pack(side="left", padx=5)

    def _create_toolbar(self):
        """Создание панели инструментов"""
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=10)

        # Поиск
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side="left")

        ttk.Label(search_frame, text="🔍 Поиск по №:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=10,
            font=("Segoe UI", 10)
        )
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<Return>", lambda e: self._search_request())

        self.search_btn = ttk.Button(
            search_frame,
            text="Найти",
            command=self._search_request,
            style="Accent.TButton"
        )
        self.search_btn.pack(side="left", padx=2)

        self.reset_btn = ttk.Button(
            search_frame,
            text="Сброс",
            command=self._refresh_data
        )
        self.reset_btn.pack(side="left", padx=2)

        # Кнопки действий справа
        action_frame = ttk.Frame(toolbar)
        action_frame.pack(side="right")

        self.stats_btn = ttk.Button(
            action_frame,
            text="📊 Статистика",
            command=lambda: self.controller.show_screen("stats")
        )
        self.stats_btn.pack(side="left", padx=2)

        self.qr_btn = ttk.Button(
            action_frame,
            text="📱 QR-отзыв",
            command=self._generate_qr
        )
        self.qr_btn.pack(side="left", padx=2)

        self.logout_btn = ttk.Button(
            action_frame,
            text="🚪 Выход",
            command=self._logout
        )
        self.logout_btn.pack(side="left", padx=2)

    def _create_requests_table(self):
        """Создание таблицы заявок"""
        # Контейнер для таблицы с прокруткой
        table_container = ttk.Frame(self)
        table_container.pack(expand=True, fill="both", padx=10, pady=(0, 10))

        # Создаем Treeview с прокруткой
        columns = ("id", "date", "type", "model", "client", "status")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=15,
            selectmode="browse"
        )

        # Настройка колонок
        column_configs = [
            ("id", "№", 60, "center"),
            ("date", "Дата", 90, "center"),
            ("type", "Тип оборудования", 150, "w"),
            ("model", "Модель", 150, "w"),
            ("client", "Заказчик", 180, "w"),
            ("status", "Статус", 150, "center")
        ]

        for col, heading, width, anchor in column_configs:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)

        # Добавляем скроллбары
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Размещение
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.pack(side="bottom", fill="x", padx=10)

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Привязка двойного клика
        self.tree.bind("<Double-1>", lambda e: self._show_details())

    def _create_bottom_panel(self):
        """Создание нижней панели с кнопками действий"""
        bottom_panel = ttk.Frame(self)
        bottom_panel.pack(fill="x", padx=10, pady=(0, 10))

        # Кнопки действий над заявкой
        self.edit_btn = ttk.Button(
            bottom_panel,
            text="✏️ Изменить статус",
            command=self._edit_status,
            style="Accent.TButton"
        )
        self.edit_btn.pack(side="left", padx=2)

        self.help_btn = ttk.Button(
            bottom_panel,
            text="🆘 Запросить помощь",
            command=self._request_help
        )
        self.help_btn.pack(side="left", padx=2)

        self.details_btn = ttk.Button(
            bottom_panel,
            text="📄 Детали заявки",
            command=self._show_details
        )
        self.details_btn.pack(side="left", padx=2)

    def on_show(self):
        """Обновление данных при показе экрана"""
        self._refresh_data()
        self._update_button_states()

    @DatabaseManager.retry_on_lock()
    def _refresh_data(self, search_id: Optional[str] = None):
        """Обновление данных в таблице"""
        # Очистка таблицы
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if search_id:
                    cursor.execute("""
                                   SELECT r.id,
                                          r.start_date,
                                          r.equipment_type,
                                          r.device_model,
                                          u.fio as client_name,
                                          r.status
                                   FROM requests r
                                            LEFT JOIN users u ON r.client_id = u.id
                                   WHERE r.id = ?
                                   """, (search_id,))
                else:
                    cursor.execute("""
                                   SELECT r.id,
                                          r.start_date,
                                          r.equipment_type,
                                          r.device_model,
                                          u.fio as client_name,
                                          r.status
                                   FROM requests r
                                            LEFT JOIN users u ON r.client_id = u.id
                                   ORDER BY r.id DESC
                                   """)

                for row in cursor.fetchall():
                    # Определяем цвет для статуса
                    tags = ()
                    if row['status'] in ['Завершена', 'Готова к выдаче']:
                        tags = ('completed',)
                    elif row['status'] == 'Ожидание комплектующих':
                        tags = ('waiting',)

                    self.tree.insert("", tk.END, values=tuple(row), tags=tags)

            # Настройка цветов для строк
            self.tree.tag_configure('completed', background='#d4edda')
            self.tree.tag_configure('waiting', background='#fff3cd')

        except sqlite3.Error as e:
            messagebox.showwarning("Ошибка", f"Не удалось загрузить данные: {e}")

    def _search_request(self):
        """Поиск заявки по номеру"""
        search_text = self.search_var.get().strip()
        if search_text.isdigit():
            self._refresh_data(search_text)
        elif search_text:
            messagebox.showwarning("Внимание", "Введите числовой номер заявки")

    def _edit_status(self):
        """Редактирование статуса заявки"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите заявку из списка")
            return

        request_id = self.tree.item(selected[0])['values'][0]

        # Создаем диалог выбора статуса
        status_dialog = tk.Toplevel(self)
        status_dialog.title("Изменение статуса")
        status_dialog.geometry("300x200")
        status_dialog.transient(self)
        status_dialog.grab_set()

        ttk.Label(
            status_dialog,
            text=f"Заявка №{request_id}",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=10)

        ttk.Label(status_dialog, text="Выберите новый статус:").pack(pady=5)

        status_var = tk.StringVar()
        status_combo = ttk.Combobox(
            status_dialog,
            textvariable=status_var,
            values=[
                "В процессе ремонта",
                "Ожидание комплектующих",
                "Готова к выдаче",
                "Завершена"
            ],
            state="readonly",
            width=25
        )
        status_combo.pack(pady=5)
        status_combo.current(0)

        def save_status():
            new_status = status_var.get()
            if not new_status:
                return

            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()

                    if new_status.lower() in ['завершена', 'готова к выдаче']:
                        today = datetime.now().strftime("%Y-%m-%d")
                        cursor.execute(
                            "UPDATE requests SET status=?, completion_date=? WHERE id=?",
                            (new_status, today, request_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE requests SET status=? WHERE id=?",
                            (new_status, request_id)
                        )

                    conn.commit()

                status_dialog.destroy()
                self._refresh_data()
                messagebox.showinfo("Успех", "Статус успешно обновлен!")

            except sqlite3.Error as e:
                messagebox.showerror("Ошибка", str(e))

        btn_frame = ttk.Frame(status_dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Сохранить", command=save_status).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=status_dialog.destroy).pack(side="left", padx=5)

    def _request_help(self):
        """Запрос помощи у менеджера"""
        if self.session.role_id != 2:
            messagebox.showwarning("Доступ запрещен", "Только специалисты могут запрашивать помощь!")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите заявку из списка")
            return

        request_id = self.tree.item(selected[0])['values'][0]

        # Диалог ввода комментария
        comment = simpledialog.askstring(
            "Запрос помощи",
            "Опишите проблему:",
            parent=self
        )

        if comment:
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()

                    # Добавляем комментарий
                    cursor.execute("""
                                   INSERT INTO comments (message, master_id, request_id, comment_date)
                                   VALUES (?, ?, ?, ?)
                                   """, (
                                       f"🆘 ЗАПРОС ПОМОЩИ: {comment}",
                                       self.session.user_id,
                                       request_id,
                                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                   ))

                    # Помечаем заявку
                    cursor.execute("UPDATE requests SET needs_help=1 WHERE id=?", (request_id,))

                    conn.commit()

                messagebox.showinfo("Успех", "Запрос на помощь отправлен менеджеру!")

            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _show_details(self):
        """Показ деталей заявки"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Информация", "Выберите заявку из списка")
            return

        request_id = self.tree.item(selected[0])['values'][0]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Получаем данные заявки
                cursor.execute("""
                               SELECT r.*,
                                      client.fio   as client_fio,
                                      client.phone as client_phone,
                                      master.fio   as master_fio
                               FROM requests r
                                        LEFT JOIN users client ON r.client_id = client.id
                                        LEFT JOIN users master ON r.master_id = master.id
                               WHERE r.id = ?
                               """, (request_id,))

                request = cursor.fetchone()

                # Получаем комментарии
                cursor.execute("""
                               SELECT c.*, u.fio
                               FROM comments c
                                        LEFT JOIN users u ON c.master_id = u.id
                               WHERE c.request_id = ?
                               ORDER BY c.comment_date
                               """, (request_id,))

                comments = cursor.fetchall()

            if request:
                self._show_details_window(request, comments)

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _show_details_window(self, request: sqlite3.Row, comments: List[sqlite3.Row]):
        """Отображение окна с деталями"""
        details_window = tk.Toplevel(self)
        details_window.title(f"Детали заявки №{request['id']}")
        details_window.geometry("600x550")
        details_window.transient(self)

        # Основной фрейм с прокруткой
        main_frame = ttk.Frame(details_window)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Заголовок
        header_label = tk.Label(
            scrollable_frame,
            text=f"📋 ЗАЯВКА №{request['id']}",
            font=("Segoe UI", 16, "bold"),
            fg=AppConfig.COLOR_PRIMARY
        )
        header_label.pack(pady=(0, 15))

        # Информация о заявке
        info_frame = ttk.LabelFrame(scrollable_frame, text="Информация о заявке", padding=10)
        info_frame.pack(fill="x", pady=5)

        info_items = [
            ("📅 Дата создания:", request['start_date']),
            ("🔧 Тип оборудования:", request['equipment_type']),
            ("📱 Модель:", request['device_model']),
            ("📝 Описание проблемы:", request['problem_description']),
            ("📊 Статус:", request['status']),
            ("✅ Дата завершения:", request['completion_date'] or "Не завершена"),
            ("🔩 Запчасти:", request['parts_used'] or "Не указаны"),
        ]

        for label, value in info_items:
            item_frame = ttk.Frame(info_frame)
            item_frame.pack(fill="x", pady=2)
            ttk.Label(item_frame, text=label, font=("Segoe UI", 9, "bold"), width=15).pack(side="left")
            ttk.Label(item_frame, text=value, font=("Segoe UI", 9)).pack(side="left", padx=5)

        # Информация о клиенте и мастере
        people_frame = ttk.LabelFrame(scrollable_frame, text="Участники", padding=10)
        people_frame.pack(fill="x", pady=10)

        people_items = [
            ("👤 Клиент:", request['client_fio'] or "Не указан"),
            ("📞 Телефон:", request['client_phone'] or "Не указан"),
            ("👨‍🔧 Мастер:", request['master_fio'] or "Не назначен"),
        ]

        for label, value in people_items:
            item_frame = ttk.Frame(people_frame)
            item_frame.pack(fill="x", pady=2)
            ttk.Label(item_frame, text=label, font=("Segoe UI", 9, "bold"), width=10).pack(side="left")
            ttk.Label(item_frame, text=value, font=("Segoe UI", 9)).pack(side="left", padx=5)

        # Комментарии
        comments_frame = ttk.LabelFrame(scrollable_frame, text="Комментарии", padding=10)
        comments_frame.pack(fill="x", pady=5)

        if comments:
            for comment in comments:
                comment_text = comment['message']
                comment_date = comment['comment_date']
                author = comment['fio'] or "Неизвестно"

                comment_box = tk.Frame(
                    comments_frame,
                    bg="#f8f9fa",
                    relief="solid",
                    borderwidth=1
                )
                comment_box.pack(fill="x", pady=3)

                tk.Label(
                    comment_box,
                    text=f"{author} • {comment_date}",
                    font=("Segoe UI", 8, "bold"),
                    bg="#f8f9fa",
                    anchor="w"
                ).pack(fill="x", padx=5, pady=2)

                tk.Label(
                    comment_box,
                    text=comment_text,
                    font=("Segoe UI", 9),
                    bg="#f8f9fa",
                    wraplength=500,
                    justify="left"
                ).pack(fill="x", padx=5, pady=2)
        else:
            ttk.Label(comments_frame, text="Нет комментариев").pack()

        # Кнопка закрытия
        ttk.Button(
            scrollable_frame,
            text="Закрыть",
            command=details_window.destroy
        ).pack(pady=10)

        # Упаковка canvas и scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _generate_qr(self):
        """Генерация QR-кода для отзыва"""
        try:
            img = qrcode.make(AppConfig.FEEDBACK_URL)
            img.save("feedback_qr.png")
            os.startfile("feedback_qr.png")
            messagebox.showinfo("Успех", "QR-код создан и открыт!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать QR-код: {e}")

    def _logout(self):
        """Выход из системы"""
        if messagebox.askyesno("Подтверждение", "Вы действительно хотите выйти?"):
            self.session.clear()
            self.controller.show_screen("login")

    def _update_button_states(self):
        """Обновление состояния кнопок в зависимости от роли"""
        if self.session.role_id == 2:  # Специалист
            self.help_btn.state(['!disabled'])
        else:
            self.help_btn.state(['disabled'])


# =============================================================================
# ЭКРАН СТАТИСТИКИ
# =============================================================================

class StatisticsScreen(BaseScreen):
    """Экран статистики"""

    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Заголовок
        header_frame = tk.Frame(self, bg=AppConfig.COLOR_PRIMARY, height=50)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="📊 СТАТИСТИКА РАБОТЫ",
            font=("Segoe UI", 14, "bold"),
            fg="white",
            bg=AppConfig.COLOR_PRIMARY
        ).pack(side="left", padx=20, pady=12)

        # Основной контент
        content_frame = ttk.Frame(self)
        content_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Карточки со статистикой
        self.stats_frame = ttk.Frame(content_frame)
        self.stats_frame.pack(fill="x", pady=(0, 20))

        # Текстовое поле с прокруткой для детальной статистики
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(expand=True, fill="both")

        self.stats_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#f8f9fa",
            relief="solid",
            borderwidth=1
        )

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=scrollbar.set)

        self.stats_text.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")

        # Кнопки
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)

        ttk.Button(
            btn_frame,
            text="🔄 Обновить",
            command=self._calculate_stats,
            style="Accent.TButton"
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame,
            text="◀ Назад",
            command=lambda: self.controller.show_screen("main")
        ).pack(side="left", padx=5)

    def on_show(self):
        """Обновление статистики при показе экрана"""
        self._calculate_stats()

    @DatabaseManager.retry_on_lock()
    def _calculate_stats(self):
        """Расчет и отображение статистики"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                               SELECT equipment_type, status, start_date, completion_date
                               FROM requests
                               """)
                records = cursor.fetchall()

            # Статистические данные
            completed_count = 0
            total_days = 0
            fault_stats: Dict[str, int] = {}
            status_stats: Dict[str, int] = {}
            total_requests = len(records)

            for rec in records:
                eq_type = rec['equipment_type']
                status = rec['status']
                start = rec['start_date']
                end = rec['completion_date']

                # Статистика по типам
                fault_stats[eq_type] = fault_stats.get(eq_type, 0) + 1

                # Статистика по статусам
                status_stats[status] = status_stats.get(status, 0) + 1

                # Время выполнения
                if status.lower() in ['завершена', 'готова к выдаче'] and end:
                    completed_count += 1
                    try:
                        date_format = "%Y-%m-%d"
                        d1 = datetime.strptime(start, date_format)
                        d2 = datetime.strptime(end, date_format)
                        total_days += (d2 - d1).days
                    except (ValueError, TypeError):
                        pass

            avg_time = total_days / completed_count if completed_count > 0 else 0

            # Формирование отчета
            self.stats_text.config(state="normal")
            self.stats_text.delete(1.0, tk.END)

            report = []
            report.append("=" * 60)
            report.append("            СТАТИСТИЧЕСКИЙ ОТЧЕТ")
            report.append("=" * 60)
            report.append("")
            report.append(f"📊 Всего заявок: {total_requests}")
            report.append(f"✅ Выполнено заявок: {completed_count}")
            report.append(f"⏱️ Среднее время выполнения: {avg_time:.1f} дней")
            report.append("")
            report.append("-" * 60)
            report.append("📈 СТАТИСТИКА ПО СТАТУСАМ:")

            for status, count in sorted(status_stats.items(), key=lambda x: x[1], reverse=True):
                percent = (count / total_requests * 100) if total_requests > 0 else 0
                bar = "█" * int(percent / 5)
                report.append(f"   {status:<20} {count:3} шт. ({percent:5.1f}%) {bar}")

            report.append("")
            report.append("-" * 60)
            report.append("🔧 СТАТИСТИКА ПО ТИПАМ ОБОРУДОВАНИЯ:")

            for eq_type, count in sorted(fault_stats.items(), key=lambda x: x[1], reverse=True):
                percent = (count / total_requests * 100) if total_requests > 0 else 0
                bar = "█" * int(percent / 5)
                report.append(f"   {eq_type:<25} {count:3} шт. ({percent:5.1f}%) {bar}")

            self.stats_text.insert(1.0, "\n".join(report))
            self.stats_text.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


# =============================================================================
# ГЛАВНЫЙ КОНТРОЛЛЕР ПРИЛОЖЕНИЯ
# =============================================================================

class Application(tk.Tk):
    """Главный класс приложения"""

    def __init__(self):
        super().__init__()

        # Настройки окна
        self.title(AppConfig.APP_TITLE)
        self.geometry(AppConfig.WINDOW_SIZE)
        self.configure(bg=AppConfig.COLOR_BG)

        # Центрирование окна
        self.center_window()

        # Сессия пользователя
        self.session = UserSession()

        # Словарь экранов
        self.screens: Dict[str, BaseScreen] = {}

        # Создание экранов
        self._create_screens()

        # Показ экрана входа
        self.show_screen("login")

    def center_window(self):
        """Центрирование окна на экране"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _create_screens(self):
        """Создание всех экранов приложения"""
        screens_config = {
            "login": LoginScreen,
            "main": MainScreen,
            "stats": StatisticsScreen
        }

        for name, screen_class in screens_config.items():
            screen = screen_class(self, self)
            self.screens[name] = screen
            screen.grid(row=0, column=0, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def show_screen(self, screen_name: str):
        """Переключение между экранами"""
        if screen_name in self.screens:
            # Скрываем текущий экран
            for screen in self.screens.values():
                screen.grid_remove()

            # Показываем новый экран
            self.screens[screen_name].grid()
            self.screens[screen_name].on_show()
        else:
            raise ValueError(f"Экран '{screen_name}' не найден")


# =============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =============================================================================

if __name__ == "__main__":
    app = Application()
    app.mainloop()