# Dynamics NAV Object Documentation

> **Generated:** 2026-06-11 08:18:01  
> **NAV Version:** 2013–2015  
> **Source files:** sample_objects.txt  
> **Total objects:** 6

---

## Table of Contents

1. [Summary Statistics](#summary-statistics)
2. [Migration Overview](#migration-overview)
3. [Codeunits (1)](#codeunits)
4. [Forms (1)](#forms)
5. [Pages (1)](#pages)
6. [Reports (1)](#reports)
7. [Tables (2)](#tables)

---

## Summary Statistics

| Object Type | Count | Migration Complexity |
|---|---|---|
| Codeunit | 1 | 🟡 Medium |
| Form | 1 | 🔴 High |
| Page | 1 | 🟢 Low |
| Report | 1 | 🟡 Medium |
| Table | 2 | 🟡 Medium |
| **Total** | **6** | |

- **Tables:** 2 tables with **25 total fields**
- **Codeunits:** 3 procedures, 1 triggers

---

## Migration Overview

Summary of key migration actions required when moving to Business Central (AL):

### 🔴 High Priority
_Must be fully redesigned. No direct equivalent in BC._

- **Forms (1):** `Customer Card`

### 🟡 Medium Priority
_Require code review and partial refactoring._

- **Tables (2):** `Customer`, `Item`
- **Codeunits (1):** `Sales-Post`
- **Reports (1):** `Customer List`

### 🟢 Low Priority
_Direct AL equivalents exist with minimal changes._

- **Pages (1):** `Customer List`

---

## Tables

> ℹ️ **Migration:** Tables migrate to AL. Check for BLOB fields and obsolete field types.

### Table 18: Customer

**Properties:**

| Property | Value |
|---|---|
| DataCaptionFields | `No.,Name` |
| LookupPageID | `Page22` |
| DrillDownPageID | `Page22` |

**Fields** (14 total):

| No | Name | Type | Properties |
|---|---|---|---|
| 1 | `No.` | Code20 |  |
| 2 | `Name` | Text50 |  |
| 3 | `Search Name` | Code50 |  |
| 4 | `Name 2` | Text50 |  |
| 5 | `Address` | Text50 |  |
| 7 | `City` | Text30 |  |
| 8 | `Contact` | Text50 |  |
| 9 | `Phone No.` | Text30 |  |
| 21 | `Customer Posting Group` | Code10 | TableRelation="Customer Posting Group" |
| 22 | `Currency Code` | Code10 | TableRelation=Currency |
| 27 | `Payment Terms Code` | Code10 | TableRelation="Payment Terms" |
| 35 | `Balance (LCY)` | Decimal | CalcFormula=Sum("Detailed Cust. Ledg. Entry"."Amount (LCY)" WHERE (Customer No.=FIELD(No.))); FieldClass=FlowField |
| 103 | `Credit Limit (LCY)` | Decimal |  |
| 107 | `Blocked` | Option |  |

**Keys:**

| Enabled | Key Fields | SumIndexFields |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Search Name` | - |
|  | `Customer Posting Group` | - |

**Triggers** (3):

<details>
<summary><code>OnInsert</code></summary>

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

<details>
<summary><code>OnModify</code></summary>

```cal
OnModify()
    BEGIN
      "Last Date Modified" := TODAY;
    END;
```

</details>

<details>
<summary><code>OnDelete</code></summary>

```cal
OnDelete()
    BEGIN
      MoveEntries.MoveCustomerEntries(Rec);
    END;
```

</details>

**Procedures** (2):

`GetCustNo`, `CheckBlockedCust`

<details>
<summary><code>GetCustNo</code></summary>

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
<summary><code>CheckBlockedCust</code></summary>

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

**Properties:**

| Property | Value |
|---|---|
| DataCaptionFields | `No.,Description` |
| LookupPageID | `Page31` |

**Fields** (11 total):

| No | Name | Type | Properties |
|---|---|---|---|
| 1 | `No.` | Code20 |  |
| 3 | `Description` | Text50 |  |
| 4 | `Search Description` | Code50 |  |
| 6 | `Base Unit of Measure` | Code10 | TableRelation="Unit of Measure" |
| 10 | `Costing Method` | Option |  |
| 12 | `Unit Price` | Decimal |  |
| 18 | `Item Disc. Group` | Code20 | TableRelation="Item Discount Group" |
| 19 | `Allow Invoice Disc.` | Boolean |  |
| 22 | `Inventory Posting Group` | Code10 | TableRelation="Inventory Posting Group" |
| 30 | `Reorder Point` | Decimal |  |
| 99000758 | `Option` |  |  |

**Keys:**

| Enabled | Key Fields | SumIndexFields |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Description` | - |
|  | `Search Description` | - |

**Triggers** (1):

<details>
<summary><code>OnInsert</code></summary>

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

**Procedures** (1):

`FindItemByDesc`

<details>
<summary><code>FindItemByDesc</code></summary>

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

> ✅ **Migration:** Pages have a direct AL equivalent. Review for obsolete properties.

### Page 22: Customer List

**Properties:**

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer List` |

**Controls** (9 total):

| ID | Parent | Type |
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

**Triggers** (1):

<details>
<summary><code>OnAfterGetRecord</code></summary>

```cal
OnAfterGetRecord()
    BEGIN
      StyleTxt := SetStyle;
    END;
```

</details>

**Procedures** (1):

`SetStyle`

<details>
<summary><code>SetStyle</code></summary>

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

> ℹ️ **Migration:** Codeunits migrate to AL with minimal changes. Review for deprecated functions.

### Codeunit 80: Sales-Post

**Triggers** (1):

<details>
<summary><code>OnRun</code></summary>

```cal
OnRun()
    BEGIN
      SalesHeader := Rec;
      Code;
      Rec := SalesHeader;
    END;
```

</details>

**Procedures** (3):

`Code`, `CheckPostingDate`, `PostSalesLines`

<details>
<summary><code>Code</code></summary>

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
<summary><code>CheckPostingDate</code></summary>

```cal
LOCAL PROCEDURE CheckPostingDate(SalesHeader : Record "Sales Header")
    BEGIN
      IF NOT (SalesHeader."Posting Date" IN [WORKDATE-30..WORKDATE+30]) THEN
        ERROR(Text001);
    END;
```

</details>

<details>
<summary><code>PostSalesLines</code></summary>

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

> ℹ️ **Migration:** Reports can be migrated but layouts must be converted to **RDLC or Word** layouts.

### Report 101: Customer List

**Properties:**

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer List` |

**Triggers** (1):

<details>
<summary><code>OnPreReport</code></summary>

```cal
OnPreReport()
    BEGIN
      CompanyInfo.GET;
    END;
```

</details>


---

## Forms

> ⚠️ **Migration:** Forms are deprecated. Must be redesigned as **Pages** in Business Central.

### Form 21: Customer Card

**Properties:**

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer Card` |
| DataCaptionFields | `No.,Name` |

**Controls** (7 total):

| ID | Parent | Type |
|---|---|---|
| 1 | 0 | Frame |
| 2 | 1 | TabControl |
| 3 | 2 | Tab |
| 4 | 3 | TextBox |
| 5 | 3 | TextBox |
| 6 | 3 | TextBox |
| 7 | 3 | TextBox |

**Triggers** (1):

<details>
<summary><code>OnAfterGetRecord</code></summary>

```cal
OnAfterGetRecord()
    BEGIN
      ActivateFields;
    END;
```

</details>

**Procedures** (1):

`ActivateFields`

<details>
<summary><code>ActivateFields</code></summary>

```cal
LOCAL PROCEDURE ActivateFields()
    BEGIN
      // Activate or deactivate fields based on customer type
    END;
```

</details>


---
