# Dynamics NAV — Migration Documentation

> **Generated:** 2026-06-11 12:31:07  
> **NAV Version:** 2013  
> **Source files:** sample_objects.txt  
> **Total objects:** 6

---

## Table of Contents

1. [Summary Statistics](#summary-statistics)
2. [Migration Overview](#migration-overview)
3. [Effort & Risk Matrix](#effort--risk-matrix)
4. [Codeunits (1)](#codeunits)
5. [Forms (1)](#forms)
6. [Pages (1)](#pages)
7. [Reports (1)](#reports)
8. [Tables (2)](#tables)

---

## Summary Statistics

| Object Type | Count | Migration Complexity | Est. Total Hours |
|---|---|---|---|
| Codeunit | 1 | 🟡 Medium | ~6h |
| Form | 1 | 🔴 High | ~8h |
| Page | 1 | 🟢 Low | ~3h |
| Report | 1 | 🟡 Medium | ~6h |
| Table | 2 | 🟡 Medium | ~6h |
| **Total** | **6** | | **~29h** |

- **Tables:** 2 tables, 25 total fields
- **Codeunits:** 3 procedures across 1 codeunits
- ⚠️ **Deprecated patterns found:** 2 occurrences across all objects

---

## Migration Overview

### 🔴 High Priority
_No direct BC equivalent — must be fully redesigned._

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

## Effort & Risk Matrix

| Object | Type | Risk | Est. Hours | Deprecated Hits | Key Dependencies |
|---|---|---|---|---|---|
| Customer Card | Form | 🔴 High | ~8h | 0 | — |
| Sales-Post | Codeunit | 🟡 Medium | ~6h | 1 | Table:IF SalesLine; Table:TempSalesLine |
| Customer List | Report | 🟡 Medium | ~6h | 0 | Table:BEGIN
      CompanyInfo |
| Customer | Table | 🟡 Medium | ~4h | 1 | Table:IF Cust |
| Customer List | Page | 🟢 Low | ~3h | 0 | — |
| Item | Table | 🟢 Low | ~2h | 0 | Table:IF Item |

---

## Tables

> ℹ️ **BC Migration:** Tables migrate to AL. Check BLOB→Media, OemCode→Code, and obsolete field types.

### Table 18: Customer
_Modified: `01/15/14`_  _Risk: 🟡 Medium_  _Est. effort: ~4h_

#### 📋 Algorithm Summary

Table **Customer** stores data with 14 fields. Primary key fields include: `No.`, `Name`, `Search Name`, `Name 2`, `Address`. Contains 1 FlowField(s) that aggregate data from related tables. Business logic is enforced through triggers: `OnInsert`, `OnModify`, `OnDelete`. 

> ⚠️ Contains deprecated calls: `ERROR()` — **requires refactoring before migration**.

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

Review field structure for BLOB fields (must be converted to Media/MediaSet in BC).  1 FlowFields — verify CalcFormula compatibility with AL. 

</details>

<details>
<summary>💻 Developer</summary>

- `ERROR()`: Replace with Error() in AL

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🟡 Medium  
**Estimated effort:** ~4h  
**Blockers:** 1 deprecated pattern(s) must be resolved by developer before UAT.  

</details>

#### Properties

| Property | Value |
|---|---|
| DataCaptionFields | `No.,Name` |
| LookupPageID | `Page22` |
| DrillDownPageID | `Page22` |

#### ⚠️ Deprecated Patterns

| Pattern | Migration Action |
|---|---|
| `ERROR()` | Replace with Error() in AL |

#### 🔗 Dependencies

| Type | Name | Operation |
|---|---|---|
| Table | `IF Cust` | FIND |

**Fields** (14 total):

| No | Name | Type | Legacy Type | Properties |
|---|---|---|---|---|
| 1 | `No.` | Code20 | — |  |
| 2 | `Name` | Text50 | — |  |
| 3 | `Search Name` | Code50 | — |  |
| 4 | `Name 2` | Text50 | — |  |
| 5 | `Address` | Text50 | — |  |
| 7 | `City` | Text30 | — |  |
| 8 | `Contact` | Text50 | — |  |
| 9 | `Phone No.` | Text30 | — |  |
| 21 | `Customer Posting Group` | Code10 | — | TableRelation="Customer Posting Group" |
| 22 | `Currency Code` | Code10 | — | TableRelation=Currency |
| 27 | `Payment Terms Code` | Code10 | — | TableRelation="Payment Terms" |
| 35 | `Balance (LCY)` | Decimal | — | CalcFormula=Sum("Detailed Cust. Ledg. Entry"."Amount (LCY)" WHERE (Customer No.=FIELD(No.))); FieldClass=FlowField |
| 103 | `Credit Limit (LCY)` | Decimal | — |  |
| 107 | `Blocked` | Option | — |  |

**Keys:**

| Enabled | Key Fields | SumIndexFields |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Search Name` | — |
|  | `Customer Posting Group` | — |

#### Global Variables

| Name | Type | Description |
|---|---|---|
| `Cust` | Record Customer | Record buffer for table "Customer" |

#### Procedures & Triggers (5 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnInsert` | trigger | — | — | 5 | ✅ |
| `OnModify` | trigger | — | — | 4 | ✅ |
| `OnDelete` | trigger | — | — | 4 | ✅ |
| `GetCustNo` | procedure | `CustName`:Text[50](in) | `Code[20]` | 10 | ✅ |
| `CheckBlockedCust` | procedure | `Cust`:Record Customer(in), `Transaction`:Boolean(in) | — | 7 | ⚠️ |

<details>
<summary>🔔 <code>OnInsert</code> — Procedure `OnInsert` — 5 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

<details>
<summary>🔔 <code>OnModify</code> — Procedure `OnModify` — 4 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnModify()
    BEGIN
      "Last Date Modified" := TODAY;
    END;
```

</details>

<details>
<summary>🔔 <code>OnDelete</code> — Procedure `OnDelete` — 4 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnDelete()
    BEGIN
      MoveEntries.MoveCustomerEntries(Rec);
    END;
```

</details>

<details>
<summary>⚙️ <code>GetCustNo</code> — Takes CustName as input. Returns `Code[20]`. This procedure reads from "IF Cust"</summary>

**Parameters:**

| Name | Type | Direction |
|---|---|---|
| `CustName` | Text[50] | in |

**Returns:** `Code[20]`

**Local Variables:**

| Name | Type | Description |
|---|---|---|
| `Cust` | Record Customer | Record buffer for table "Customer" |

**C/AL Source:**

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
<summary>⚙️ <code>CheckBlockedCust</code> — Takes Cust, Transaction as input. This procedure raises errors on validation fai</summary>

**Parameters:**

| Name | Type | Direction |
|---|---|---|
| `Cust` | Record Customer | in |
| `Transaction` | Boolean | in |

**⚠️ Deprecated Patterns in this block:**
- `ERROR()`: Replace with Error() in AL

**C/AL Source:**

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
_Modified: `01/15/14`_  _Risk: 🟢 Low_  _Est. effort: ~2h_

#### 📋 Algorithm Summary

Table **Item** stores data with 11 fields. Primary key fields include: `No.`, `Description`, `Search Description`, `Base Unit of Measure`, `Costing Method`. Business logic is enforced through triggers: `OnInsert`. 

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

Review field structure for BLOB fields (must be converted to Media/MediaSet in BC). 

</details>

<details>
<summary>💻 Developer</summary>

- No critical deprecated patterns detected. Standard AL rewrite applies.

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🟢 Low  
**Estimated effort:** ~2h  

</details>

#### Properties

| Property | Value |
|---|---|
| DataCaptionFields | `No.,Description` |
| LookupPageID | `Page31` |

#### 🔗 Dependencies

| Type | Name | Operation |
|---|---|---|
| Table | `IF Item` | FIND |

**Fields** (11 total):

| No | Name | Type | Legacy Type | Properties |
|---|---|---|---|---|
| 1 | `No.` | Code20 | — |  |
| 3 | `Description` | Text50 | — |  |
| 4 | `Search Description` | Code50 | — |  |
| 6 | `Base Unit of Measure` | Code10 | — | TableRelation="Unit of Measure" |
| 10 | `Costing Method` | Option | — |  |
| 12 | `Unit Price` | Decimal | — |  |
| 18 | `Item Disc. Group` | Code20 | — | TableRelation="Item Discount Group" |
| 19 | `Allow Invoice Disc.` | Boolean | — |  |
| 22 | `Inventory Posting Group` | Code10 | — | TableRelation="Inventory Posting Group" |
| 30 | `Reorder Point` | Decimal | — |  |
| 99000758 | `Option` |  | — |  |

**Keys:**

| Enabled | Key Fields | SumIndexFields |
|---|---|---|
|  | `No.` | Clustered=Yes |
|  | `Description` | — |
|  | `Search Description` | — |

#### Global Variables

| Name | Type | Description |
|---|---|---|
| `Item` | Record Item | Record buffer for table "Item" |

#### Procedures & Triggers (2 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnInsert` | trigger | — | — | 5 | ✅ |
| `FindItemByDesc` | procedure | `Desc`:Text[50](in), `ItemNo`:Code[20](in/out (VAR)) | `Boolean` | 11 | ✅ |

<details>
<summary>🔔 <code>OnInsert</code> — Procedure `OnInsert` — 5 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnInsert()
    BEGIN
      IF NoSeriesMgt.AreRelated("No. Series",xRec."No. Series") THEN
        "No. Series" := xRec."No. Series";
    END;
```

</details>

<details>
<summary>⚙️ <code>FindItemByDesc</code> — Takes Desc as input. Returns modified ItemNo by reference. Returns `Boolean`. Th</summary>

**Parameters:**

| Name | Type | Direction |
|---|---|---|
| `Desc` | Text[50] | in |
| `ItemNo` | Code[20] | in/out (VAR) |

**Returns:** `Boolean`

**Local Variables:**

| Name | Type | Description |
|---|---|---|
| `Item` | Record Item | Record buffer for table "Item" |

**C/AL Source:**

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

> ✅ **BC Migration:** Pages have a direct AL equivalent.

### Page 22: Customer List
_Modified: `01/15/14`_  _Risk: 🟢 Low_  _Est. effort: ~3h_

#### 📋 Algorithm Summary

Page **Customer List** is bound to table `Table18`. Page type: `List`. Contains 9 UI controls. 

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

Standard migration path. Verify AL event model covers all triggers used here. 

</details>

<details>
<summary>💻 Developer</summary>

- No critical deprecated patterns detected. Standard AL rewrite applies.

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🟢 Low  
**Estimated effort:** ~3h  

</details>

#### Properties

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer List` |
| SourceTable | `Table18` |
| PageType | `List` |

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

#### Procedures & Triggers (2 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnAfterGetRecord` | trigger | — | — | 4 | ✅ |
| `SetStyle` | procedure | — | `Text` | 6 | ✅ |

<details>
<summary>🔔 <code>OnAfterGetRecord</code> — Procedure `OnAfterGetRecord` — 4 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnAfterGetRecord()
    BEGIN
      StyleTxt := SetStyle;
    END;
```

</details>

<details>
<summary>⚙️ <code>SetStyle</code> — Procedure `SetStyle` — 6 lines of C/AL logic.</summary>

**Returns:** `Text`

**C/AL Source:**

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

> ℹ️ **BC Migration:** Codeunits migrate to AL with minimal structural changes. Review for deprecated function calls.

### Codeunit 80: Sales-Post
_Modified: `01/15/14`_  _Risk: 🟡 Medium_  _Est. effort: ~6h_

#### 📋 Algorithm Summary

Codeunit **Sales-Post** contains 4 procedures/triggers implementing business logic. Operates on tables: `IF SalesLine`, `TempSalesLine`. Appears to implement a **posting routine** — critical business process. 

> ⚠️ Contains deprecated calls: `ERROR()` — **requires refactoring before migration**.

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

Standard migration path. Verify AL event model covers all triggers used here. 

</details>

<details>
<summary>💻 Developer</summary>

- `ERROR()`: Replace with Error() in AL

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🟡 Medium  
**Estimated effort:** ~6h  
**Blockers:** 1 deprecated pattern(s) must be resolved by developer before UAT.  

</details>

#### ⚠️ Deprecated Patterns

| Pattern | Migration Action |
|---|---|
| `ERROR()` | Replace with Error() in AL |

#### 🔗 Dependencies

| Type | Name | Operation |
|---|---|---|
| Table | `IF SalesLine` | FIND |
| Table | `TempSalesLine` | INSERT |

#### Global Variables

| Name | Type | Description |
|---|---|---|
| `SalesHeader` | Record "Sales Header" | Record buffer for table "Sales Header" |
| `SalesLine` | Record "Sales Line" | Record buffer for table "Sales Line" |
| `Text001` | TextConst 'ENU=The document is not posted because the posting date is not within your allowed range of posting dates.' | String variable |
| `TempSalesLine` | Record "Sales Line" TEMPORARY | Record buffer for table "Sales Line" TEMPORARY" |

#### Procedures & Triggers (4 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnRun` | trigger | — | — | 6 | ✅ |
| `Code` | procedure | — | — | 12 | ✅ |
| `CheckPostingDate` | procedure | `SalesHeader`:Record "Sales Header"(in) | — | 5 | ⚠️ |
| `PostSalesLines` | procedure | `SalesHeader`:Record "Sales Header"(in/out (VAR)), `TempSalesLine`:Record "Sales Line"(in/out (VAR)) | — | 10 | ✅ |

<details>
<summary>🔔 <code>OnRun</code> — Procedure `OnRun` — 6 lines of C/AL logic.</summary>

**C/AL Source:**

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
<summary>⚙️ <code>Code</code> — Procedure `Code` — 12 lines of C/AL logic.</summary>

**Local Variables:**

| Name | Type | Description |
|---|---|---|
| `TempSalesLine` | Record "Sales Line" TEMPORARY | Record buffer for table "Sales Line" TEMPORARY" |

**C/AL Source:**

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
<summary>⚙️ <code>CheckPostingDate</code> — Takes SalesHeader as input. This procedure raises errors on validation failure.</summary>

**Parameters:**

| Name | Type | Direction |
|---|---|---|
| `SalesHeader` | Record "Sales Header" | in |

**⚠️ Deprecated Patterns in this block:**
- `ERROR()`: Replace with Error() in AL

**C/AL Source:**

```cal
LOCAL PROCEDURE CheckPostingDate(SalesHeader : Record "Sales Header")
    BEGIN
      IF NOT (SalesHeader."Posting Date" IN [WORKDATE-30..WORKDATE+30]) THEN
        ERROR(Text001);
    END;
```

</details>

<details>
<summary>⚙️ <code>PostSalesLines</code> — Returns modified SalesHeader, TempSalesLine by reference. This procedure reads f</summary>

**Parameters:**

| Name | Type | Direction |
|---|---|---|
| `SalesHeader` | Record "Sales Header" | in/out (VAR) |
| `TempSalesLine` | Record "Sales Line" | in/out (VAR) |

**C/AL Source:**

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

> ℹ️ **BC Migration:** Reports require layout conversion to RDLC or Word. Classic layouts (NAV 2009) must be fully rebuilt.

### Report 101: Customer List
_Modified: `01/15/14`_  _Risk: 🟡 Medium_  _Est. effort: ~6h_

#### 📋 Algorithm Summary

Report **Customer List** Preview mode: `PrintLayout`. 

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

Standard migration path. Verify AL event model covers all triggers used here. 

</details>

<details>
<summary>💻 Developer</summary>

- Classic report layout must be rebuilt as RDLC (.rdlc) or Word layout; dataset structure documented below.

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🟡 Medium  
**Estimated effort:** ~6h  

</details>

#### Properties

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer List` |

#### 🔗 Dependencies

| Type | Name | Operation |
|---|---|---|
| Table | `BEGIN
      CompanyInfo` | GET |

#### Procedures & Triggers (1 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnPreReport` | trigger | — | — | 4 | ✅ |

<details>
<summary>🔔 <code>OnPreReport</code> — This procedure reads from "BEGIN
      CompanyInfo".</summary>

**C/AL Source:**

```cal
OnPreReport()
    BEGIN
      CompanyInfo.GET;
    END;
```

</details>


---

## Forms

> ⚠️ **BC Migration:** Forms are **removed** in Business Central. Must be fully redesigned as Pages.

### Form 21: Customer Card
_Modified: `01/15/14`_  _Risk: 🔴 High_  _Est. effort: ~8h_

#### 📋 Algorithm Summary

Form **Customer Card** is bound to table `Table18`. Contains 7 UI controls. 

#### 🚦 Migration Notes by Role

<details>
<summary>🏗️ Architect</summary>

**No direct BC equivalent.** Must be redesigned from scratch. Plan discovery session with business to define new UX/workflow. 

</details>

<details>
<summary>💻 Developer</summary>

- No critical deprecated patterns detected. Standard AL rewrite applies.

</details>

<details>
<summary>📋 Project Manager</summary>

**Migration risk:** 🔴 High  
**Estimated effort:** ~8h  
**Action required:** Schedule redesign workshop with business stakeholders before sprint.  

</details>

#### Properties

| Property | Value |
|---|---|
| CaptionML | `ENU=Customer Card` |
| SourceTable | `Table18` |
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

#### Procedures & Triggers (2 total)

| Name | Kind | Params | Returns | LOC | Risk |
|---|---|---|---|---|---|
| `OnAfterGetRecord` | trigger | — | — | 4 | ✅ |
| `ActivateFields` | procedure | — | — | 3 | ✅ |

<details>
<summary>🔔 <code>OnAfterGetRecord</code> — Procedure `OnAfterGetRecord` — 4 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
OnAfterGetRecord()
    BEGIN
      ActivateFields;
    END;
```

</details>

<details>
<summary>⚙️ <code>ActivateFields</code> — Procedure `ActivateFields` — 3 lines of C/AL logic.</summary>

**C/AL Source:**

```cal
LOCAL PROCEDURE ActivateFields()
    BEGIN
      // Activate or deactivate fields based on customer type
    END;
```

</details>


---
