# Dynamics NAV — Документация для миграции на 1С

> **Сформировано:** 2026-06-11 12:45:01  
> **Версия NAV:** 2013  
> **Целевая платформа:** 1С (редакция уточняется)  
> **Исходные файлы:** sample_objects.txt  
> **Всего объектов:** 6

> 📌 **Примечание:** Аналоги 1С указаны в общем виде, независимо от конкретной редакции (УП2, БП3, УТ11 и др.). При выборе редакции — уточнить маппинг под конкретную конфигурацию.

---

## Содержание

1. [Сводная статистика](#сводная-статистика)
2. [Обзор миграции](#обзор-миграции)
3. [Матрица рисков и трудозатрат](#матрица-рисков-и-трудозатрат)
4. [Справочник соответствий NAV → 1С](#справочник-соответствий-nav--1с)
5. [Codeunits (1)](#codeunits)
6. [Forms (1)](#forms)
7. [Pages (1)](#pages)
8. [Reports (1)](#reports)
9. [Tables (2)](#tables)

---

## Сводная статистика

| Тип объекта | Кол-во | Аналог в 1С | Сложность | Оценка (ч) |
|---|---|---|---|---|
| Codeunit | 1 | Общий модуль | 🟡 | ~7ч |
| Form | 1 | Форма (управляемая) | 🔴 | ~10ч |
| Page | 1 | Форма (управляемая) | 🟡 | ~4ч |
| Report | 1 | Отчёт (СКД или программный) | 🔴 | ~8ч |
| Table | 2 | Справочник / Регистр сведений / Документ | 🟡 | ~8ч |
| **Итого** | **6** | | | **~37ч** |

- **Таблицы:** 2 таблиц, 25 полей
- **Codeunit-ы:** 3 процедур в 1 объектах
- ⚠️ **Устаревших вызовов C/AL:** 2 — требуют замены при переносе

---

## Обзор миграции

### 🔴 Высокий приоритет
_Нет прямого аналога или требуется полный редизайн._

- **Form (1) → Форма (управляемая):** `Customer Card`
- **Report (1) → Отчёт (СКД или программный):** `Customer List`

### 🟡 Средний приоритет
_Есть аналоги в 1С, требуется анализ и адаптация._

- **Table (2) → Справочник / Регистр сведений / Документ:** `Customer`, `Item`
- **Codeunit (1) → Общий модуль:** `Sales-Post`
- **Page (1) → Форма (управляемая):** `Customer List`

---

## Матрица рисков и трудозатрат

| Объект | Тип | Аналог 1С | Риск | Часы | Устар. | Зависимости |
|---|---|---|---|---|---|---|
| Customer Card | Form | Форма (управляемая) | 🔴 Высокий | ~10ч | 0 | — |
| Customer List | Report | Отчёт (СКД или программный) | 🟡 Средний | ~8ч | 0 | Table:BEGIN
      CompanyInfo |
| Sales-Post | Codeunit | Общий модуль | 🟡 Средний | ~7ч | 1 | Table:IF SalesLine; Table:TempSalesLine |
| Customer | Table | Справочник / Регистр сведений / Документ | 🟡 Средний | ~5ч | 1 | Table:IF Cust |
| Customer List | Page | Форма (управляемая) | 🟡 Средний | ~4ч | 0 | — |
| Item | Table | Справочник / Регистр сведений / Документ | 🟢 Низкий | ~3ч | 0 | Table:IF Item |

---

## Справочник соответствий NAV → 1С

_Общий маппинг, не зависящий от конкретной редакции 1С. При выборе редакции уточнить под конкретную конфигурацию._

| Тип NAV | Аналог в 1С | Описание | Действие | Риск |
|---|---|---|---|---|
| Table | Справочник / Регистр сведений / Документ | В зависимости от назначения таблицы: справочные данные → Справочник, журнальные/ | Провести анализ назначения таблицы. Определить тип объекта 1С. Перенести поля вр | 🟡 |
| Form | Форма (управляемая) | NAV Form — классический интерфейс (аналог Windows Forms). В 1С — управляемые фор | Перепроектировать как управляемую форму 1С. Логику из Code-секции перенести в мо | 🔴 |
| Report | Отчёт (СКД или программный) | В 1С отчёты строятся на основе Системы Компоновки Данных (СКД) или программно че | Воссоздать структуру выборки данных в СКД. Макет оформления перенести в макет 1С | 🔴 |
| Dataport | Обработка загрузки/выгрузки данных | NAV Dataport — инструмент импорта/экспорта. В 1С аналог — внешняя обработка или  | Создать обработку 1С с форматом файла по спецификации Dataport. Рассмотреть испо | 🔴 |
| Codeunit | Общий модуль | Codeunit в NAV — библиотека процедур/функций без пользовательского интерфейса. П | Создать общий модуль 1С. Перенести логику процедур. Учесть различия: в 1С нет ст | 🟡 |
| XMLport | XDTO-пакет / Обработка XML | NAV XMLport — декларативный XML-обмен. В 1С: XDTO для структурированного XML или | Создать XDTO-пакет по XSD-схеме NAV XMLport или реализовать через встроенные сре | 🟡 |
| MenuSuite | Подсистема / Интерфейс | NAV MenuSuite определяет навигационное меню. В 1С навигация задаётся через Подси | Воссоздать структуру меню через подсистемы 1С. Настроить видимость объектов по р | 🟢 |
| Page | Форма (управляемая) | NAV Page — современный UI-объект (RoleTailored Client). В 1С — управляемая форма | Создать управляемую форму 1С. PageType=List → форма списка, PageType=Card → форм | 🟡 |
| Query | Запрос (объект конфигурации) / СКД | NAV Query — именованный запрос к нескольким таблицам. В 1С аналог — объект Запро | Реализовать как запрос 1С на языке запросов. Если используется в отчёте — включи | 🟢 |

### Соответствие типов данных полей

| Тип NAV | Тип 1С | Примечание |
|---|---|---|
| Code | Строка | Тип Строка с фиксированной длиной |
| OemCode | Строка | Тип Строка (был OemCode — устаревший тип NAV 2009) |
| Text | Строка | Тип Строка |
| OemText | Строка | Тип Строка (был OemText — устаревший тип NAV 2009) |
| Integer | Число | Целое число; в 1С — Число(10,0) |
| BigInteger | Число | Большое целое; в 1С — Число(15,0) |
| Decimal | Число | Число с десятичной частью; в 1С — Число(15,2) или по требованиям |
| Boolean | Булево | Тип Булево |
| Date | Дата | Тип Дата (без времени) |
| Time | Дата | Только время; в 1С хранить как Дата или Строка |
| DateTime | Дата и время | Тип Дата (с временем) |
| Option | Перечисление | В 1С — Перечисление или значение из списка значений |
| Blob | ХранилищеЗначения | Двоичные данные; в 1С — ХранилищеЗначения |
| GUID | УникальныйИдентификатор | Тип УникальныйИдентификатор |
| RecordID | Строка | Ссылка на запись; в 1С использовать ссылочный тип |
| DateFormula | Строка | Формула даты NAV; в 1С нет прямого аналога — хранить как строку |
| Duration | Число | Длительность в мс; в 1С — Число или разница дат |

---

## Tables

> **Аналог в 1С:** Справочник / Регистр сведений / Документ  
> В зависимости от назначения таблицы: справочные данные → Справочник, журнальные/операционные записи → Регистр сведений или Документ.

### Table 18: Customer
_Изменено: `01/15/14`_  _Риск: 🟡 Средний_  _Оценка: ~5ч_  _1С-аналог: **Справочник / Регистр сведений / Документ**_

#### 📋 Описание алгоритма

Таблица **Customer** содержит 14 полей. Ключевые поля: `No.`, `Name`, `Search Name`, `Name 2`, `Address`. Содержит 1 вычисляемых поля (FlowField) — агрегируют данные из связанных таблиц. Бизнес-логика реализована в триггерах: `OnInsert`, `OnModify`, `OnDelete`. 

> ⚠️ Содержит устаревшие вызовы: `ERROR()` — **требует переработки при миграции**.

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Справочник / Регистр сведений / Документ

В зависимости от назначения таблицы: справочные данные → Справочник, журнальные/операционные записи → Регистр сведений или Документ.

1 FlowField(ов) — реализовать через виртуальные реквизиты или запросы в 1С.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Провести анализ назначения таблицы. Определить тип объекта 1С. Перенести поля вручную с учётом типов данных 1С.

**Устаревшие вызовы (требуют замены):**
- `ERROR()` → В 1С: ВызватьИсключение или Сообщить()


</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🟡 Средний

**Оценка трудозатрат:** ~5ч

**Аналог в 1С:** Справочник / Регистр сведений / Документ

**Блокеры:** 1 устаревших вызовов — разработчик должен проработать до UAT.

</details>

#### Свойства

| Свойство | Значение |
|---|---|
| DataCaptionFields | `No.,Name` |
| LookupPageID | `Page22` |
| DrillDownPageID | `Page22` |

#### ⚠️ Устаревшие вызовы C/AL

| Паттерн | Действие при миграции на 1С |
|---|---|
| `ERROR()` | В 1С: ВызватьИсключение или Сообщить() |

#### 🔗 Зависимости

| Тип | Имя | Операция |
|---|---|---|
| Table | `IF Cust` | FIND |

**Поля** (14 всего):

| № | Имя поля | Тип NAV | Тип 1С | Устар. | Свойства |
|---|---|---|---|---|---|
| 1 | `No.` | Code20 | Строка | — | — |
| 2 | `Name` | Text50 | Строка | — | — |
| 3 | `Search Name` | Code50 | Строка | — | — |
| 4 | `Name 2` | Text50 | Строка | — | — |
| 5 | `Address` | Text50 | Строка | — | — |
| 7 | `City` | Text30 | Строка | — | — |
| 8 | `Contact` | Text50 | Строка | — | — |
| 9 | `Phone No.` | Text30 | Строка | — | — |
| 21 | `Customer Posting Group` | Code10 | Строка | — | TableRelation="Customer Posting Group" |
| 22 | `Currency Code` | Code10 | Строка | — | TableRelation=Currency |
| 27 | `Payment Terms Code` | Code10 | Строка | — | TableRelation="Payment Terms" |
| 35 | `Balance (LCY)` | Decimal | Число | — | CalcFormula=Sum("Detailed Cust. Ledg. Entry"."Amount (LCY)" WHERE (Customer No.=FIELD(No.))); FieldClass=FlowField |
| 103 | `Credit Limit (LCY)` | Decimal | Число | — | — |
| 107 | `Blocked` | Option | Перечисление | — | — |

**Ключи / Индексы:**

| Активен | Поля | SumIndex |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Search Name` | — |
|  | `Customer Posting Group` | — |

#### Глобальные переменные

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `Cust` | Record Customer | ? | Буфер записи таблицы «Customer» |

#### Процедуры и триггеры (5 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnInsert` | trigger | — | `—` | — | 5 | ✅ |
| `OnModify` | trigger | — | `—` | — | 4 | ✅ |
| `OnDelete` | trigger | — | `—` | — | 4 | ✅ |
| `GetCustNo` | procedure | `CustName`:Строка(Вх) | `Code[20]` | Строка | 10 | ✅ |
| `CheckBlockedCust` | procedure | `Cust`:?(Вх), `Transaction`:Булево(Вх) | `—` | — | 7 | ⚠️ |

<details>
<summary>🔔 <code>OnInsert</code> — Процедура «OnInsert» — 5 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

<details>
<summary>🔔 <code>OnModify</code> — Процедура «OnModify» — 4 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnModify()
    BEGIN
      "Last Date Modified" := TODAY;
    END;
```

</details>

<details>
<summary>🔔 <code>OnDelete</code> — Процедура «OnDelete» — 4 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnDelete()
    BEGIN
      MoveEntries.MoveCustomerEntries(Rec);
    END;
```

</details>

<details>
<summary>⚙️ <code>GetCustNo</code> — Принимает CustName. Возвращаемый тип: `Code[20]`. Процедура читает данные из таблиц.</summary>

**Параметры:**

| Имя | Тип NAV | Тип 1С | Направление |
|---|---|---|---|
| `CustName` | Text[50] | Строка | Вх |

**Возвращаемый тип NAV:** `Code[20]` → **1С:** Строка

**Локальные переменные:**

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `Cust` | Record Customer | ? | Буфер записи таблицы «Customer» |

**Код C/AL:**

```cal
PROCEDURE GetCustNo(CustName : Text[50]) : Code[20]
    VAR
      Cust : Record Customer;
    BEGIN
      Cust.SETRANGE(Name, CustName);
      IF Cust.FINDFIRST THEN
        EXIT(Cust."No.")
      ELSE
        EXIT('');
    END;
```

</details>

<details>
<summary>⚙️ <code>CheckBlockedCust</code> — Принимает Cust, Transaction. Процедура генерирует ошибку при нарушении условий.</summary>

**Параметры:**

| Имя | Тип NAV | Тип 1С | Направление |
|---|---|---|---|
| `Cust` | Record Customer | ? | Вх |
| `Transaction` | Boolean | Булево | Вх |

**⚠️ Устаревшие вызовы в этом блоке:**
- `ERROR()` → В 1С: ВызватьИсключение или Сообщить()

**Код C/AL:**

```cal
LOCAL PROCEDURE CheckBlockedCust(Cust : Record Customer;Transaction : Boolean)
    BEGIN
      IF Cust.Blocked = Cust.Blocked::All THEN
        ERROR(Text001, Cust."No.", Cust.Name);
      IF Transaction AND (Cust.Blocked = Cust.Blocked::Invoice) THEN
        ERROR(Text002, Cust."No.", Cust.Name);
    END;
```

</details>


### Table 27: Item
_Изменено: `01/15/14`_  _Риск: 🟢 Низкий_  _Оценка: ~3ч_  _1С-аналог: **Справочник / Регистр сведений / Документ**_

#### 📋 Описание алгоритма

Таблица **Item** содержит 11 полей. Ключевые поля: `No.`, `Description`, `Search Description`, `Base Unit of Measure`, `Costing Method`. Бизнес-логика реализована в триггерах: `OnInsert`. 

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Справочник / Регистр сведений / Документ

В зависимости от назначения таблицы: справочные данные → Справочник, журнальные/операционные записи → Регистр сведений или Документ.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Провести анализ назначения таблицы. Определить тип объекта 1С. Перенести поля вручную с учётом типов данных 1С.

**Поля без прямого аналога в 1С** (требуют ручного анализа): `Option`


</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🟢 Низкий

**Оценка трудозатрат:** ~3ч

**Аналог в 1С:** Справочник / Регистр сведений / Документ

</details>

#### Свойства

| Свойство | Значение |
|---|---|
| DataCaptionFields | `No.,Description` |
| LookupPageID | `Page31` |

#### 🔗 Зависимости

| Тип | Имя | Операция |
|---|---|---|
| Table | `IF Item` | FIND |

**Поля** (11 всего):

| № | Имя поля | Тип NAV | Тип 1С | Устар. | Свойства |
|---|---|---|---|---|---|
| 1 | `No.` | Code20 | Строка | — | — |
| 3 | `Description` | Text50 | Строка | — | — |
| 4 | `Search Description` | Code50 | Строка | — | — |
| 6 | `Base Unit of Measure` | Code10 | Строка | — | TableRelation="Unit of Measure" |
| 10 | `Costing Method` | Option | Перечисление | — | — |
| 12 | `Unit Price` | Decimal | Число | — | — |
| 18 | `Item Disc. Group` | Code20 | Строка | — | TableRelation="Item Discount Group" |
| 19 | `Allow Invoice Disc.` | Boolean | Булево | — | — |
| 22 | `Inventory Posting Group` | Code10 | Строка | — | TableRelation="Inventory Posting Group" |
| 30 | `Reorder Point` | Decimal | Число | — | — |
| 99000758 | `Option` |  | ? | — | — |

**Ключи / Индексы:**

| Активен | Поля | SumIndex |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Description` | — |
|  | `Search Description` | — |

#### Глобальные переменные

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `Item` | Record Item | ? | Буфер записи таблицы «Item» |

#### Процедуры и триггеры (2 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnInsert` | trigger | — | `—` | — | 5 | ✅ |
| `FindItemByDesc` | procedure | `Desc`:Строка(Вх), `ItemNo`:Строка(Вх/Вых (VAR)) | `Boolean` | Булево | 11 | ✅ |

<details>
<summary>🔔 <code>OnInsert</code> — Процедура «OnInsert» — 5 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

<details>
<summary>⚙️ <code>FindItemByDesc</code> — Принимает Desc. Возвращает по ссылке: ItemNo. Возвращаемый тип: `Boolean`. Процедура читае</summary>

**Параметры:**

| Имя | Тип NAV | Тип 1С | Направление |
|---|---|---|---|
| `Desc` | Text[50] | Строка | Вх |
| `ItemNo` | Code[20] | Строка | Вх/Вых (VAR) |

**Возвращаемый тип NAV:** `Boolean` → **1С:** Булево

**Локальные переменные:**

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `Item` | Record Item | ? | Буфер записи таблицы «Item» |

**Код C/AL:**

```cal
PROCEDURE FindItemByDesc(Desc : Text[50]; VAR ItemNo : Code[20]) : Boolean
    VAR
      Item : Record Item;
    BEGIN
      Item.SETRANGE(Description, Desc);
      IF Item.FINDFIRST THEN BEGIN
        ItemNo := Item."No.";
        EXIT(TRUE);
      END;
      EXIT(FALSE);
    END;
```

</details>


---

## Pages

> **Аналог в 1С:** Форма (управляемая)  
> NAV Page — современный UI-объект (RoleTailored Client). В 1С — управляемая форма, привязанная к объекту конфигурации.

### Page 22: Customer List
_Изменено: `01/15/14`_  _Риск: 🟡 Средний_  _Оценка: ~4ч_  _1С-аналог: **Форма (управляемая)**_

#### 📋 Описание алгоритма

Page **Customer List** привязан к таблице `Table18`. Тип: `List`. Содержит 9 элементов управления. 

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Форма (управляемая)

NAV Page — современный UI-объект (RoleTailored Client). В 1С — управляемая форма, привязанная к объекту конфигурации.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Создать управляемую форму 1С. PageType=List → форма списка, PageType=Card → форма элемента.


</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🟡 Средний

**Оценка трудозатрат:** ~4ч

**Аналог в 1С:** Форма (управляемая)

</details>

#### Свойства

| Свойство | Значение |
|---|---|
| CaptionML | `ENU=Customer List` |
| SourceTable | `Table18` |
| PageType | `List` |

**Элементы управления** (9 всего):

| ID | Родитель | Тип |
|---|---|---|
| 1 | 0 | Container |
| 2 | 1 | Group |
| 3 | 2 | Field |
| 4 | 2 | Field |
| 5 | 2 | Field |
| 6 | 2 | Field |
| 7 | 2 | Field |
| 8 | 2 | Field |
| 9 | 2 | Field |

#### Процедуры и триггеры (2 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnAfterGetRecord` | trigger | — | `—` | — | 4 | ✅ |
| `SetStyle` | procedure | — | `Text` | Строка | 6 | ✅ |

<details>
<summary>🔔 <code>OnAfterGetRecord</code> — Процедура «OnAfterGetRecord» — 4 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnAfterGetRecord()
    BEGIN
      StyleTxt := SetStyle;
    END;
```

</details>

<details>
<summary>⚙️ <code>SetStyle</code> — Процедура «SetStyle» — 6 строк C/AL логики.</summary>

**Возвращаемый тип NAV:** `Text` → **1С:** Строка

**Код C/AL:**

```cal
LOCAL PROCEDURE SetStyle() : Text
    BEGIN
      IF Blocked <> Blocked::" " THEN
        EXIT('Unfavorable');
      EXIT('');
    END;
```

</details>


---

## Codeunits

> **Аналог в 1С:** Общий модуль  
> Codeunit в NAV — библиотека процедур/функций без пользовательского интерфейса. Прямой аналог в 1С — Общий модуль.

### Codeunit 80: Sales-Post
_Изменено: `01/15/14`_  _Риск: 🟡 Средний_  _Оценка: ~7ч_  _1С-аналог: **Общий модуль**_

#### 📋 Описание алгоритма

Codeunit **Sales-Post** содержит 4 процедур/триггеров. Работает с таблицами: `TempSalesLine`, `IF SalesLine`. По характеру — **процедура проведения документа** (критический бизнес-процесс). 

> ⚠️ Содержит устаревшие вызовы: `ERROR()` — **требует переработки при миграции**.

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Общий модуль

Codeunit в NAV — библиотека процедур/функций без пользовательского интерфейса. Прямой аналог в 1С — Общий модуль.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Создать общий модуль 1С. Перенести логику процедур. Учесть различия: в 1С нет статических методов, есть Сеанс/Глобальный контекст.

**Устаревшие вызовы (требуют замены):**
- `ERROR()` → В 1С: ВызватьИсключение или Сообщить()


</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🟡 Средний

**Оценка трудозатрат:** ~7ч

**Аналог в 1С:** Общий модуль

**Блокеры:** 1 устаревших вызовов — разработчик должен проработать до UAT.

</details>

#### ⚠️ Устаревшие вызовы C/AL

| Паттерн | Действие при миграции на 1С |
|---|---|
| `ERROR()` | В 1С: ВызватьИсключение или Сообщить() |

#### 🔗 Зависимости

| Тип | Имя | Операция |
|---|---|---|
| Table | `IF SalesLine` | FIND |
| Table | `TempSalesLine` | INSERT |

#### Глобальные переменные

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `SalesHeader` | Record "Sales Header" | ? | Буфер записи таблицы «Sales Header» |
| `SalesLine` | Record "Sales Line" | ? | Буфер записи таблицы «Sales Line» |
| `Text001` | TextConst 'ENU=The document is not posted because the posting date is not within your allowed range of posting dates.' | Строка | Строковая переменная |
| `TempSalesLine` | Record "Sales Line" TEMPORARY | ? | Буфер записи таблицы «Sales Line" TEMPORARY» |

#### Процедуры и триггеры (4 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnRun` | trigger | — | `—` | — | 6 | ✅ |
| `Code` | procedure | — | `—` | — | 12 | ✅ |
| `CheckPostingDate` | procedure | `SalesHeader`:?(Вх) | `—` | — | 5 | ⚠️ |
| `PostSalesLines` | procedure | `SalesHeader`:?(Вх/Вых (VAR)), `TempSalesLine`:?(Вх/Вых (VAR)) | `—` | — | 10 | ✅ |

<details>
<summary>🔔 <code>OnRun</code> — Процедура «OnRun» — 6 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnRun()
    BEGIN
      SalesHeader := Rec;
      Code;
      Rec := SalesHeader;
    END;
```

</details>

<details>
<summary>⚙️ <code>Code</code> — Процедура «Code» — 12 строк C/AL логики.</summary>

**Локальные переменные:**

| Имя | Тип NAV | Тип 1С | Описание |
|---|---|---|---|
| `TempSalesLine` | Record "Sales Line" TEMPORARY | ? | Буфер записи таблицы «Sales Line" TEMPORARY» |

**Код C/AL:**

```cal
PROCEDURE Code()
    VAR
      TempSalesLine : Record "Sales Line" TEMPORARY;
    BEGIN
      WITH SalesHeader DO BEGIN
        TESTFIELD("Document Type");
        TESTFIELD("No.");
        TESTFIELD("Posting Date");
        CheckPostingDate(SalesHeader);
        PostSalesLines(SalesHeader, TempSalesLine);
      END;
    END;
```

</details>

<details>
<summary>⚙️ <code>CheckPostingDate</code> — Принимает SalesHeader. Процедура генерирует ошибку при нарушении условий.</summary>

**Параметры:**

| Имя | Тип NAV | Тип 1С | Направление |
|---|---|---|---|
| `SalesHeader` | Record "Sales Header" | ? | Вх |

**⚠️ Устаревшие вызовы в этом блоке:**
- `ERROR()` → В 1С: ВызватьИсключение или Сообщить()

**Код C/AL:**

```cal
LOCAL PROCEDURE CheckPostingDate(SalesHeader : Record "Sales Header")
    BEGIN
      IF NOT (SalesHeader."Posting Date" IN [WORKDATE-30..WORKDATE+30]) THEN
        ERROR(Text001);
    END;
```

</details>

<details>
<summary>⚙️ <code>PostSalesLines</code> — Возвращает по ссылке: SalesHeader, TempSalesLine. Процедура читает данные из таблиц; измен</summary>

**Параметры:**

| Имя | Тип NAV | Тип 1С | Направление |
|---|---|---|---|
| `SalesHeader` | Record "Sales Header" | ? | Вх/Вых (VAR) |
| `TempSalesLine` | Record "Sales Line" | ? | Вх/Вых (VAR) |

**Код C/AL:**

```cal
LOCAL PROCEDURE PostSalesLines(VAR SalesHeader : Record "Sales Header"; VAR TempSalesLine : Record "Sales Line")
    BEGIN
      SalesLine.SETRANGE("Document Type", SalesHeader."Document Type");
      SalesLine.SETRANGE("Document No.", SalesHeader."No.");
      IF SalesLine.FINDSET THEN
        REPEAT
          TempSalesLine := SalesLine;
          TempSalesLine.INSERT;
        UNTIL SalesLine.NEXT = 0;
    END;
```

</details>


---

## Reports

> **Аналог в 1С:** Отчёт (СКД или программный)  
> В 1С отчёты строятся на основе Системы Компоновки Данных (СКД) или программно через табличный документ.

### Report 101: Customer List
_Изменено: `01/15/14`_  _Риск: 🟡 Средний_  _Оценка: ~8ч_  _1С-аналог: **Отчёт (СКД или программный)**_

#### 📋 Описание алгоритма

Отчёт **Customer List** 

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Отчёт (СКД или программный)

В 1С отчёты строятся на основе Системы Компоновки Данных (СКД) или программно через табличный документ.

В 1С рекомендуется реализовать через СКД (Система компоновки данных). Структура DataItems → наборы данных СКД. Классический макет NAV 2009 → макет СКД или табличный документ.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Воссоздать структуру выборки данных в СКД. Макет оформления перенести в макет 1С (таблица/спредшит).

**Отчёт:** структура данных задокументирована ниже. Реализовать наборы данных в СКД, параметры → параметры СКД.

</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🟡 Средний

**Оценка трудозатрат:** ~8ч

**Аналог в 1С:** Отчёт (СКД или программный)

**⚠️ Требует встречи с бизнесом** для подтверждения функциональных требований перед началом разработки.

</details>

#### Свойства

| Свойство | Значение |
|---|---|
| CaptionML | `ENU=Customer List` |

#### 🔗 Зависимости

| Тип | Имя | Операция |
|---|---|---|
| Table | `BEGIN
      CompanyInfo` | GET |

#### Процедуры и триггеры (1 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnPreReport` | trigger | — | `—` | — | 4 | ✅ |

<details>
<summary>🔔 <code>OnPreReport</code> — Процедура читает данные из таблиц.</summary>

**Код C/AL:**

```cal
OnPreReport()
    BEGIN
      CompanyInfo.GET;
    END;
```

</details>


---

## Forms

> **Аналог в 1С:** Форма (управляемая)  
> NAV Form — классический интерфейс (аналог Windows Forms). В 1С — управляемые формы на основе объектов конфигурации.

### Form 21: Customer Card
_Изменено: `01/15/14`_  _Риск: 🔴 Высокий_  _Оценка: ~10ч_  _1С-аналог: **Форма (управляемая)**_

#### 📋 Описание алгоритма

Form **Customer Card** привязан к таблице `Table18`. Содержит 7 элементов управления. 

#### 🚦 Заметки по миграции на 1С

<details>
<summary>🏗️ Архитектор</summary>

**Аналог в 1С:** Форма (управляемая)

NAV Form — классический интерфейс (аналог Windows Forms). В 1С — управляемые формы на основе объектов конфигурации.

Требуется полный редизайн. Провести встречу с бизнесом для определения нового UX в 1С.

</details>

<details>
<summary>💻 Разработчик</summary>

**Действие:** Перепроектировать как управляемую форму 1С. Логику из Code-секции перенести в модуль формы.


</details>

<details>
<summary>📋 Проект-менеджер</summary>

**Риск миграции:** 🔴 Высокий

**Оценка трудозатрат:** ~10ч

**Аналог в 1С:** Форма (управляемая)

**⚠️ Требует встречи с бизнесом** для подтверждения функциональных требований перед началом разработки.

</details>

#### Свойства

| Свойство | Значение |
|---|---|
| CaptionML | `ENU=Customer Card` |
| SourceTable | `Table18` |
| DataCaptionFields | `No.,Name` |

**Элементы управления** (7 всего):

| ID | Родитель | Тип |
|---|---|---|
| 1 | 0 | Frame |
| 2 | 1 | TabControl |
| 3 | 2 | Tab |
| 4 | 3 | TextBox |
| 5 | 3 | TextBox |
| 6 | 3 | TextBox |
| 7 | 3 | TextBox |

#### Процедуры и триггеры (2 всего)

| Имя | Вид | Параметры | Возврат (NAV) | Возврат (1С) | LOC | ⚠️ |
|---|---|---|---|---|---|---|
| `OnAfterGetRecord` | trigger | — | `—` | — | 4 | ✅ |
| `ActivateFields` | procedure | — | `—` | — | 3 | ✅ |

<details>
<summary>🔔 <code>OnAfterGetRecord</code> — Процедура «OnAfterGetRecord» — 4 строк C/AL логики.</summary>

**Код C/AL:**

```cal
OnAfterGetRecord()
    BEGIN
      ActivateFields;
    END;
```

</details>

<details>
<summary>⚙️ <code>ActivateFields</code> — Процедура «ActivateFields» — 4 строк C/AL логики.</summary>

**Код C/AL:**

```cal
LOCAL PROCEDURE ActivateFields()
    BEGIN
      // Activate or deactivate fields based on customer type
    END;
```

</details>


---
