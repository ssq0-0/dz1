"""Банковские счета: базовый класс, наследники и очистка истории.

Домашнее задание по дисциплине «Язык Python для разработчиков».
История операций хранится структурированно, даты берутся из datetime.
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from statistics import median


class Account:
    """Базовый банковский счёт с историей операций.

    Номер счёта выдаётся автоматически в формате ACC-XXXX.
    Отсчёт номеров начинается с 1000 и общий для всех наследников.
    """

    _account_counter = 1000
    _name_word = re.compile(r"(?:[A-Z][a-z]+|[А-ЯЁ][а-яё]+)")

    def __init__(self, account_holder, balance=0):
        self.holder = self._validate_holder(account_holder)
        self._balance = self._validate_initial_balance(balance)
        self.account_number = f"ACC-{Account._account_counter:04d}"
        Account._account_counter += 1
        self.operations_history = []
        self._incoming = []
        self.rejected_records = []
        self._load_account_number = self.account_number

    @classmethod
    def reset_counter(cls, start=1000):
        """Сбрасывает нумерацию счетов. Удобно для повторного прогона."""
        cls._account_counter = start

    @staticmethod
    def _validate_initial_balance(balance):
        if isinstance(balance, bool) or not isinstance(balance, (int, float)):
            raise TypeError("Начальный баланс должен быть числом.")
        if balance < 0:
            raise ValueError("Начальный баланс не может быть отрицательным.")
        return round(float(balance), 2)

    @classmethod
    def _validate_holder(cls, account_holder):
        """Имя в формате «Имя Фамилия», кириллица или латиница."""
        if not isinstance(account_holder, str):
            raise TypeError("Имя владельца должно быть строкой.")
        cleaned = " ".join(account_holder.strip().split())
        parts = cleaned.split(" ")
        words_ok = all(cls._name_word.fullmatch(part) for part in parts)
        if len(parts) != 2 or not words_ok:
            raise ValueError(
                "Имя владельца должно быть в формате «Имя Фамилия» "
                "с заглавной буквы, кириллицей или латиницей."
            )
        first_script = "lat" if "A" <= parts[0][0] <= "Z" else "cyr"
        second_script = "lat" if "A" <= parts[1][0] <= "Z" else "cyr"
        if first_script != second_script:
            raise ValueError(
                "Имя и фамилия должны быть в одной письменности: "
                "либо кириллицей, либо латиницей."
            )
        return cleaned

    def _check_amount(self, amount):
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной.")
        return round(float(amount), 2)

    def _record(self, operation_type, amount, status, when=None):
        """Добавляет структурированную запись в историю операций."""
        self.operations_history.append(
            {
                "type": operation_type,
                "amount": round(float(amount), 2),
                "datetime": when or datetime.now(),
                "balance": round(self._balance, 2),
                "status": status,
            }
        )

    def deposit(self, amount, *, when=None):
        """Пополняет счёт. Отрицательная сумма вызывает исключение."""
        value = self._check_amount(amount)
        self._balance = round(self._balance + value, 2)
        self._record("deposit", value, "success", when)

    def withdraw(self, amount, *, when=None):
        """Снимает деньги. Нехватка средств фиксируется со статусом fail."""
        value = self._check_amount(amount)
        if value > self._balance:
            self._record("withdraw", value, "fail", when)
            return False
        self._balance = round(self._balance - value, 2)
        self._record("withdraw", value, "success", when)
        return True

    def get_balance(self):
        """Возвращает текущий баланс."""
        return self._balance

    def get_history(self):
        """Возвращает историю операций в читаемом виде."""
        lines = []
        for operation in self.operations_history:
            moment = operation["datetime"].strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                f"{moment} | {operation['type']} | "
                f"сумма: {operation['amount']:.2f} | "
                f"баланс: {operation['balance']:.2f} | "
                f"{operation['status']}"
            )
        return lines

    def get_large_operations(
        self, n, min_amount=None, date_from=None, date_to=None
    ):
        """Выводит последние n крупных успешных операций.

        Крупной считается операция не меньше порога min_amount.
        Если порог не задан, берётся медиана успешных сумм.
        Период можно ограничить аргументами date_from и date_to.
        """
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise ValueError("n должно быть целым положительным числом.")
        successful = [
            item
            for item in self.operations_history
            if item["status"] == "success"
        ]
        if date_from is not None:
            successful = [
                item for item in successful if item["datetime"] >= date_from
            ]
        if date_to is not None:
            successful = [
                item for item in successful if item["datetime"] <= date_to
            ]
        if not successful:
            print("Крупных операций нет.")
            return []
        if min_amount is None:
            min_amount = median(item["amount"] for item in successful)
        selected = [
            item for item in successful if item["amount"] >= min_amount
        ]
        selected.sort(
            key=lambda item: (item["datetime"], item["amount"]),
            reverse=True,
        )
        latest = selected[:n]
        if not latest:
            print("Крупных операций нет.")
            return []
        print(
            f"Последние {len(latest)} крупных операций "
            f"(порог {min_amount:.2f}):"
        )
        lines = []
        for operation in latest:
            moment = operation["datetime"].strftime("%Y-%m-%d %H:%M:%S")
            line = (
                f"{moment} | {operation['type']} | "
                f"сумма: {operation['amount']:.2f} | "
                f"баланс: {operation['balance']:.2f}"
            )
            print(line)
            lines.append(line)
        return lines

    def allowed_operation_types(self):
        """Типы операций, допустимые для этого счёта."""
        return {"deposit", "withdraw"}

    def load_history(self, filepath, account_number=None):
        """Загружает общий файл и оставляет строки одного счёта.

        account_number — номер из файла, например ACC-100001.
        Если его не передать, берётся номер самого объекта.
        Затем clean_history отбрасывает ошибки и обновляет баланс.
        """
        self._load_account_number = account_number or self.account_number
        records = self._read_transactions(filepath)
        self._incoming = self._filter_own_records(records)
        return self.clean_history()

    def clean_history(self):
        """Ищет ошибки во входящих данных и записывает валидные операции."""
        valid = []
        rejected = []
        seen = set()
        for record in self._incoming:
            reason = self._reject_reason(record)
            if reason:
                rejected.append({**record, "reason": reason})
                continue
            normalized = self._normalize_record(record)
            identity = (
                normalized["datetime"],
                normalized["type"],
                normalized["amount"],
            )
            if identity in seen:
                rejected.append({**record, "reason": "повтор операции"})
                continue
            seen.add(identity)
            valid.append(normalized)
        valid.sort(key=lambda item: item["datetime"])
        for record in valid:
            self._replay(record)
        self.rejected_records = rejected
        self._incoming = []
        return {"loaded": len(valid), "rejected": len(rejected)}

    def _filter_own_records(self, records):
        """Оставляет только строки выбранного счёта из общего файла."""
        target = self._load_account_number
        own = []
        for record in records:
            number = self._clean_text(record.get("account_number"))
            holder = self._clean_text(record.get("holder"))
            if number:
                if number != target:
                    continue
            elif holder != self.holder:
                continue
            own.append(record)
        return own

    def _reject_reason(self, record):
        file_type = self._clean_text(record.get("account_type")).lower()
        own_type = getattr(self, "account_type", "")
        if file_type and own_type and file_type != own_type:
            return "тип счёта не совпадает с классом"
        operation_type = self._normalize_type(record.get("type"))
        if operation_type not in self.allowed_operation_types():
            return "неверный или недопустимый тип операции"
        if self._parse_amount(record.get("amount")) is None:
            return "неверная или отрицательная сумма"
        if self._parse_datetime(record.get("datetime")) is None:
            return "неверная дата"
        status = self._clean_text(record.get("status")).lower()
        if status and status not in {"success", "fail"}:
            return "неверный статус операции"
        return None

    def _normalize_record(self, record):
        status = self._clean_text(record.get("status")).lower() or "success"
        return {
            "type": self._normalize_type(record.get("type")),
            "amount": self._parse_amount(record.get("amount")),
            "datetime": self._parse_datetime(record.get("datetime")),
            "status": status,
        }

    def _replay(self, record):
        operation_type = record["type"]
        amount = record["amount"]
        moment = record["datetime"]
        if record["status"] == "fail":
            self._record(operation_type, amount, "fail", moment)
            return
        if operation_type == "deposit":
            self.deposit(amount, when=moment)
        elif operation_type == "withdraw":
            self.withdraw(amount, when=moment)
        elif operation_type == "interest":
            self._apply_interest_amount(amount, when=moment)

    def _apply_interest_amount(self, amount, when=None):
        value = self._check_amount(amount)
        self._balance = round(self._balance + value, 2)
        self._record("interest", value, "success", when)

    @staticmethod
    def _clean_text(value):
        if value is None:
            return ""
        return " ".join(str(value).strip().split())

    @staticmethod
    def _normalize_type(value):
        return Account._clean_text(value).lower()

    @staticmethod
    def _parse_amount(value):
        """Возвращает положительную сумму или None, если значение ошибочно."""
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            amount = float(value)
        else:
            text = Account._clean_text(value).lower()
            text = text.replace("руб.", "").replace("руб", "").replace("₽", "")
            text = text.replace(" ", "")
            if not text:
                return None
            if "," in text and "." not in text:
                text = text.replace(",", ".")
            text = text.replace(",", "")
            try:
                amount = float(text)
            except ValueError:
                return None
        if amount <= 0:
            return None
        return round(amount, 2)

    @staticmethod
    def _parse_datetime(value):
        if isinstance(value, datetime):
            return value
        text = Account._clean_text(value)
        if not text:
            return None
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y/%m/%d",
        )
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _read_transactions(self, filepath):
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {path}")
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._read_json(path)
        if suffix == ".csv":
            return self._read_csv(path)
        raise ValueError("Поддерживаются только файлы CSV и JSON.")

    def _read_json(self, path):
        with path.open(encoding="utf-8-sig") as source:
            payload = json.load(source)
        if isinstance(payload, dict):
            for key in ("transactions", "data", "operations", "items"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ValueError("JSON должен содержать список транзакций.")
        return [
            self._map_record(item)
            for item in payload
            if isinstance(item, dict)
        ]

    def _read_csv(self, path):
        with path.open(encoding="utf-8-sig", newline="") as source:
            sample = source.read(4096)
            source.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(source, dialect=dialect)
            return [self._map_record(row) for row in reader]

    def _map_record(self, raw):
        """Приводит разные названия колонок к единому виду."""
        aliases = {
            "account_number": {
                "account_number",
                "account",
                "acc",
                "number",
                "счет",
                "счёт",
                "номер",
            },
            "holder": {
                "holder",
                "account_holder",
                "owner",
                "name",
                "владелец",
                "имя",
            },
            "account_type": {
                "account_type",
                "acc_type",
                "тип_счета",
                "тип_счёта",
            },
            "type": {
                "type",
                "operation",
                "operation_type",
                "op_type",
                "тип",
                "операция",
            },
            "amount": {"amount", "sum", "value", "сумма"},
            "datetime": {
                "datetime",
                "date",
                "timestamp",
                "time",
                "дата",
                "время",
            },
            "status": {"status", "статус"},
        }
        normalized = {}
        for key, value in raw.items():
            if key is None:
                continue
            label = str(key).strip().lower().replace(" ", "_")
            normalized[label] = value
        mapped = {}
        for target, names in aliases.items():
            for name in names:
                if name in normalized:
                    mapped[target] = normalized[name]
                    break
        return mapped

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"holder={self.holder!r}, "
            f"account_number={self.account_number!r}, "
            f"balance={self._balance:.2f})"
        )


class CheckingAccount(Account):
    """Расчётный счёт. Доступны только deposit и withdraw."""

    account_type = "checking"


class SavingsAccount(Account):
    """Сберегательный счёт: проценты и снятие не больше 50% баланса."""

    account_type = "savings"

    def allowed_operation_types(self):
        return {"deposit", "withdraw", "interest"}

    def apply_interest(self, rate, *, when=None):
        """Начисляет проценты на остаток. rate=0.07 означает 7%."""
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise TypeError("Ставка должна быть числом.")
        if rate < 0:
            raise ValueError("Ставка не может быть отрицательной.")
        amount = round(self._balance * float(rate), 2)
        if amount == 0:
            return 0.0
        self._apply_interest_amount(amount, when=when)
        return amount

    def withdraw(self, amount, *, when=None):
        """Нельзя снять больше 50% текущего баланса."""
        value = self._check_amount(amount)
        if value > self._balance or value > self._balance * 0.5 + 1e-9:
            self._record("withdraw", value, "fail", when)
            return False
        self._balance = round(self._balance - value, 2)
        self._record("withdraw", value, "success", when)
        return True
