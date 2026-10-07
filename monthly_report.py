import os
import requests
import boto3

from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

# ============================================================
# ZOHO CONFIGURATION
# ============================================================

ZOHO_ACCOUNTS_URL = "https://accounts.zoho.in"
ZOHO_API_URL = "https://www.zohoapis.in"

ZOHO_ORGANIZATION_ID = "60037332565"

# ============================================================
# AWS SES CONFIGURATION
# ============================================================

SES_FROM_EMAIL = "reports@frontlinesedutech.com"
SES_FROM_NAME = "Expense Report"


# ============================================================
# GET CURRENT MONTH DATE RANGE
# ============================================================

def get_current_month_date_range():
    today = date.today()

    start_date = date(
        today.year,
        today.month,
        1
    )

    end_date = today

    return (
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        today.year,
        today.month
    )


# ============================================================
# FORMAT DATE FOR DISPLAY
#
# INTERNAL/API FORMAT:
#     YYYY-MM-DD
#
# EMAIL DISPLAY FORMAT:
#     DD/MM/YYYY
# ============================================================

def format_display_date(date_string):
    try:

        parsed_date = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        )

        return parsed_date.strftime(
            "%d/%m/%Y"
        )

    except Exception:

        return date_string


# ============================================================
# GET ZOHO ACCESS TOKEN
# ============================================================

def get_zoho_access_token():
    client_id = os.getenv(
        "ZOHO_CLIENT_ID"
    )

    client_secret = os.getenv(
        "ZOHO_CLIENT_SECRET"
    )

    refresh_token = os.getenv(
        "ZOHO_REFRESH_TOKEN"
    )

    if (
            not client_id
            or not client_secret
            or not refresh_token
    ):
        raise Exception(
            "Missing Zoho OAuth environment variables. "
            "Please check your .env file."
        )

    params = {

        "refresh_token":
            refresh_token,

        "client_id":
            client_id,

        "client_secret":
            client_secret,

        "grant_type":
            "refresh_token"
    }

    try:

        response = requests.post(

            ZOHO_ACCOUNTS_URL +
            "/oauth/v2/token",

            params=params,

            timeout=60
        )

    except requests.exceptions.RequestException as error:

        raise Exception(
            "Network error while connecting to "
            "Zoho authentication API: "
            + str(error)
        )

    print(
        "Zoho token response code:",
        response.status_code
    )

    if response.status_code != 200:
        raise Exception(
            "Zoho authentication failed:\n"
            + response.text
        )

    try:

        data = response.json()

    except ValueError:

        raise Exception(
            "Zoho authentication API returned "
            "invalid JSON:\n"
            + response.text
        )

    if not data.get(
            "access_token"
    ):
        raise Exception(
            "Zoho access token was not returned:\n"
            + str(data)
        )

    print(
        "Zoho access token generated successfully."
    )

    return data["access_token"]


# ============================================================
# GET EXPENSES FOR CURRENT MONTH
# ============================================================

def get_expenses_for_current_month(
        access_token,
        start_date,
        end_date
):
    all_expenses = []

    page = 1
    per_page = 200

    headers = {

        "Authorization":
            "Zoho-oauthtoken " +
            access_token,

        "X-com-zoho-expense-organizationid":
            ZOHO_ORGANIZATION_ID
    }

    # ========================================================
    # FETCH EXPENSE LIST
    # ========================================================

    while True:

        print()
        print(
            "Fetching expense list..."
        )

        print(
            "Date range:",
            start_date,
            "to",
            end_date
        )

        print(
            "Page:",
            page
        )

        try:

            response = requests.get(

                ZOHO_API_URL +
                "/expense/v1/expenses",

                headers=headers,

                params={
                    "date_start": start_date,
                    "date_end": end_date,
                    "page": page,
                    "per_page": per_page
                },

                timeout=60
            )

        except requests.exceptions.RequestException as error:

            raise Exception(
                "Network error while fetching "
                "expenses from Zoho API: "
                + str(error)
            )

        print(
            "Expenses API response:",
            response.status_code
        )

        if response.status_code != 200:
            raise Exception(
                "Zoho Expenses API failed.\n"
                "HTTP Code: "
                + str(response.status_code)
                + "\n"
                + response.text
            )

        try:

            data = response.json()

        except ValueError:

            raise Exception(
                "Zoho Expenses API returned "
                "invalid JSON:\n"
                + response.text
            )

        if not isinstance(
                data,
                dict
        ):
            raise Exception(
                "Unexpected response format "
                "from Zoho Expenses API."
            )

        if data.get(
                "code"
        ) != 0:
            raise Exception(
                "Zoho Expenses API error:\n"
                + response.text
            )

        expenses = data.get(
            "expenses",
            []
        )

        if expenses is None:
            expenses = []

        if not isinstance(
                expenses,
                list
        ):
            raise Exception(
                "Unexpected 'expenses' format "
                "returned by Zoho Expenses API."
            )

        if expenses:
            all_expenses.extend(
                expenses
            )

        page_context = data.get(
            "page_context"
        )

        if (
                not page_context
                or page_context.get(
            "has_more_page"
        ) is not True
        ):
            break

        page += 1

    print()
    print(
        "Total expenses found:",
        len(all_expenses)
    )

    # ========================================================
    # ZERO RECORDS = VALID RESULT
    # ========================================================

    if len(all_expenses) == 0:
        return []

    # ========================================================
    # FETCH FULL DETAILS
    # ========================================================

    detailed_expenses = []

    print()
    print(
        "=" * 80
    )

    print(
        "FETCHING FULL EXPENSE DETAILS"
    )

    print(
        "=" * 80
    )

    for index, expense in enumerate(
            all_expenses,
            start=1
    ):

        expense_id = (
                expense.get("expense_id")
                or expense.get("id")
        )

        print(
            f"[{index}/{len(all_expenses)}] "
            f"Expense ID: {expense_id}"
        )

        if not expense_id:
            raise Exception(
                f"Expense record #{index} "
                "does not contain an expense ID."
            )

        try:

            detail_url = (
                    ZOHO_API_URL +
                    "/expense/v1/expenses/" +
                    str(expense_id)
            )

            detail_response = requests.get(

                detail_url,

                headers=headers,

                timeout=60
            )

        except requests.exceptions.RequestException as error:

            raise Exception(
                f"Network error while fetching "
                f"details for expense {expense_id}: "
                f"{error}"
            )

        if detail_response.status_code != 200:
            raise Exception(
                f"Zoho Expense detail API failed "
                f"for expense {expense_id}.\n"
                f"HTTP Code: "
                f"{detail_response.status_code}\n"
                f"{detail_response.text}"
            )

        try:

            detail_data = (
                detail_response.json()
            )

        except ValueError:

            raise Exception(
                f"Invalid JSON returned by Zoho "
                f"Expense detail API for "
                f"expense {expense_id}."
            )

        if not isinstance(
                detail_data,
                dict
        ):
            raise Exception(
                f"Unexpected response format for "
                f"expense {expense_id}."
            )

        if (
                "code" in detail_data
                and detail_data.get("code") != 0
        ):
            raise Exception(
                f"Zoho Expense detail API returned "
                f"an error for expense {expense_id}:\n"
                f"{detail_data}"
            )

        detail_expense = (
                detail_data.get("expense")
                or detail_data
        )

        if not isinstance(
                detail_expense,
                dict
        ):
            raise Exception(
                f"Unexpected expense detail structure "
                f"for expense {expense_id}."
            )

        # ----------------------------------------------------
        # IMPORTANT:
        # Preserve rcy_total from the ORIGINAL LIST API
        # ----------------------------------------------------

        original_rcy_total = (
            expense.get("rcy_total")
        )

        merged_expense = {

            **expense,

            **detail_expense,

            "_list_rcy_total":
                original_rcy_total
        }

        detailed_expenses.append(
            merged_expense
        )

    print(
        "=" * 80
    )

    print(
        "Expenses processed with details:",
        len(detailed_expenses)
    )

    print(
        "=" * 80
    )

    return detailed_expenses


# ============================================================
# PARSE AMOUNT
# ============================================================

def parse_amount(value):
    if value is None:
        return None

    try:

        cleaned = (
            str(value)
            .replace(",", "")
            .strip()
        )

        if cleaned == "":
            return None

        return Decimal(
            cleaned
        )

    except Exception:

        return None


# ============================================================
# GET REPORTING CURRENCY AMOUNT
#
# IMPORTANT:
# Use rcy_total only.
# Never use total/amount because those can be
# original foreign-currency values.
# ============================================================

def get_amount(expense):
    list_rcy_total = parse_amount(
        expense.get(
            "_list_rcy_total"
        )
    )

    if list_rcy_total is not None:
        return list_rcy_total

    rcy_total = parse_amount(
        expense.get(
            "rcy_total"
        )
    )

    if rcy_total is not None:
        return rcy_total

    return Decimal("0")


# ============================================================
# GET CUSTOM FIELD VALUE
# ============================================================

def get_custom_field_value(
        expense,
        possible_names
):
    custom_fields = expense.get(
        "custom_fields"
    )

    if not isinstance(
            custom_fields,
            list
    ):
        return None

    normalized_names = [

        str(name)
        .lower()
        .strip()

        for name in possible_names
    ]

    for field in custom_fields:

        if not isinstance(
                field,
                dict
        ):
            continue

        api_name = str(
            field.get(
                "api_name",
                ""
            )
        ).lower().strip()

        label = str(
            field.get(
                "label",
                ""
            )
        ).lower().strip()

        field_name = str(
            field.get(
                "field_name",
                ""
            )
        ).lower().strip()

        name = str(
            field.get(
                "name",
                ""
            )
        ).lower().strip()

        if (
                api_name in normalized_names
                or label in normalized_names
                or field_name in normalized_names
                or name in normalized_names
        ):

            value = field.get(
                "value"
            )

            if (
                    value is not None
                    and str(value).strip() != ""
            ):
                return value

            value_formatted = field.get(
                "value_formatted"
            )

            if (
                    value_formatted is not None
                    and str(
                value_formatted
            ).strip() != ""
            ):
                return value_formatted

            value_name = field.get(
                "value_name"
            )

            if (
                    value_name is not None
                    and str(
                value_name
            ).strip() != ""
            ):
                return value_name

    return None


# ============================================================
# GET GST
# ============================================================

def get_gst(expense):
    value = get_custom_field_value(

        expense,

        [
            "cf_gst",
            "gst",
            "GST"
        ]
    )

    amount = parse_amount(
        value
    )

    if amount is not None:
        return amount

    return Decimal("0")


# ============================================================
# GET TDS
# ============================================================

def get_tds(expense):
    value = get_custom_field_value(

        expense,

        [
            "cf_tds",
            "tds",
            "TDS"
        ]
    )

    amount = parse_amount(
        value
    )

    if amount is not None:
        return amount

    return Decimal("0")


# ============================================================
# CALCULATE TOTALS
# ============================================================

def calculate_totals(
        expenses
):
    total_amount = Decimal("0")
    total_gst = Decimal("0")
    total_tds = Decimal("0")

    print()
    print(
        "=" * 100
    )

    print(
        "EXPENSE-WISE GST / TDS"
    )

    print(
        "=" * 100
    )

    for expense in expenses:
        expense_id = (
                expense.get(
                    "expense_id"
                )
                or expense.get(
            "id"
        )
                or "UNKNOWN"
        )

        description = (
                expense.get(
                    "description"
                )
                or expense.get(
            "merchant_name"
        )
                or "Expense"
        )

        amount = get_amount(
            expense
        )

        gst = get_gst(
            expense
        )

        tds = get_tds(
            expense
        )

        print(
            f"ID: {expense_id} | "
            f"Expense: {description} | "
            f"rcy_total: {amount} | "
            f"GST: {gst} | "
            f"TDS: {tds}"
        )

        total_amount += amount
        total_gst += gst
        total_tds += tds

    print()
    print(
        "=" * 100
    )

    print(
        "TOTAL EXPENSE AMOUNT:",
        total_amount
    )

    print(
        "TOTAL GST:",
        total_gst
    )

    print(
        "TOTAL TDS:",
        total_tds
    )

    print(
        "=" * 100
    )

    return (
        total_amount,
        total_gst,
        total_tds
    )


# ============================================================
# FORMAT CURRENCY
# ============================================================

def format_currency(amount):
    amount = Decimal(
        str(
            amount or 0
        )
    )

    return (
            "₹" +
            f"{amount:,.2f}"
    )


# ============================================================
# BUILD RESPONSIVE HTML EMAIL
#
# IMPORTANT DESIGN APPROACH:
#
# We use TWO completely separate layouts:
#
# 1. DESKTOP
#    Three cards in one row.
#
# 2. MOBILE
#    Three full-width cards stacked vertically.
#
# This avoids Gmail inheriting the desktop 33.33% width
# when rendering the mobile version.
# ============================================================

def build_html_email(
        year,
        month,
        start_date,
        end_date,
        total_amount,
        total_gst,
        total_tds
):
    month_name = datetime(
        year,
        month,
        1
    ).strftime(
        "%B %Y"
    )

    display_start_date = (
        format_display_date(
            start_date
        )
    )

    display_end_date = (
        format_display_date(
            end_date
        )
    )

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

<title>
Monthly Expense Report
</title>


<style>

/* ==========================================================
   RESET
   ========================================================== */

html,
body {{
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
}}

body {{
    background-color: #f2f4f7;
    font-family: Arial, Helvetica, sans-serif;
}}

table {{
    border-collapse: collapse;
    border-spacing: 0;
}}

img {{
    border: 0;
    outline: none;
    text-decoration: none;
}}


/* ==========================================================
   DESKTOP LAYOUT
   ========================================================== */

.mobile-layout {{
    display: none !important;
    max-height: 0;
    overflow: hidden;
    mso-hide: all;
}}

.desktop-layout {{
    display: table !important;
    width: 100% !important;
}}


/* ==========================================================
   MOBILE MEDIA QUERY
   ========================================================== */

@media only screen and (max-width: 600px) {{

    .desktop-layout {{
        display: none !important;
        max-height: 0 !important;
        overflow: hidden !important;
        mso-hide: all !important;
    }}

    .mobile-layout {{
        display: table !important;
        width: 100% !important;
        max-height: none !important;
        overflow: visible !important;
    }}

    .outer-wrapper {{
        padding: 8px !important;
    }}

    .main-container {{
        width: 100% !important;
        max-width: 100% !important;
    }}

    .mobile-padding {{
        padding-left: 16px !important;
        padding-right: 16px !important;
    }}

    .mobile-card {{
        width: 100% !important;
    }}

    .mobile-value {{
        font-size: 24px !important;
        line-height: 30px !important;
    }}

}}


/* ==========================================================
   SMALL PHONES
   ========================================================== */

@media only screen and (max-width: 380px) {{

    .outer-wrapper {{
        padding: 5px !important;
    }}

    .mobile-padding {{
        padding-left: 12px !important;
        padding-right: 12px !important;
    }}

    .mobile-value {{
        font-size: 22px !important;
        line-height: 28px !important;
    }}

}}

</style>

</head>


<body>


<!-- ========================================================
     OUTER BACKGROUND
     ======================================================== -->

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f2f4f7;
"
>

<tr>

<td
align="center"
class="outer-wrapper"
style="
padding:24px 12px;
"
>


<!-- ========================================================
     MAIN CONTAINER
     ======================================================== -->

<table
class="main-container"
width="720"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
max-width:720px;
background:#ffffff;
border-radius:12px;
"
>


<!-- ========================================================
     HEADER
     ======================================================== -->

<tr>

<td
align="center"
style="
padding:32px 20px 24px 20px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:28px;
line-height:36px;
font-weight:bold;
color:#172033;
text-align:center;
">

Monthly Expense Report

</div>


<div style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:17px;
line-height:24px;
color:#5f6b7a;
text-align:center;
">

{month_name}

</div>


<div style="
margin-top:5px;
font-family:Arial,Helvetica,sans-serif;
font-size:14px;
line-height:22px;
color:#7b8491;
text-align:center;
">

Period:
<strong>
{display_start_date}
</strong>

&nbsp;to&nbsp;

<strong>
{display_end_date}
</strong>

</div>

</td>

</tr>


<!-- ========================================================
     DESKTOP KPI LAYOUT
     ======================================================== -->

<tr>

<td
align="center"
style="
padding:0 18px 20px 18px;
"
>


<table
class="desktop-layout"
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
"
>

<tr>


<!-- ======================================================
     DESKTOP EXPENSE CARD
     ====================================================== -->

<td
width="33.33%"
align="center"
valign="top"
style="
width:33.33%;
padding:6px;
"
>

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 8px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:13px;
line-height:18px;
color:#6b7280;
text-align:center;
">

Total Expense Amount

</div>

<div style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:22px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
">

{format_currency(total_amount)}

</div>

</td>

</tr>

</table>

</td>


<!-- ======================================================
     DESKTOP GST CARD
     ====================================================== -->

<td
width="33.33%"
align="center"
valign="top"
style="
width:33.33%;
padding:6px;
"
>

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 8px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:13px;
line-height:18px;
color:#6b7280;
text-align:center;
">

Total GST

</div>

<div style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:22px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
">

{format_currency(total_gst)}

</div>

</td>

</tr>

</table>

</td>


<!-- ======================================================
     DESKTOP TDS CARD
     ====================================================== -->

<td
width="33.33%"
align="center"
valign="top"
style="
width:33.33%;
padding:6px;
"
>

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 8px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:13px;
line-height:18px;
color:#6b7280;
text-align:center;
">

Total TDS

</div>

<div style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:22px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
">

{format_currency(total_tds)}

</div>

</td>

</tr>

</table>

</td>


</tr>

</table>


<!-- ========================================================
     MOBILE KPI LAYOUT

     IMPORTANT:
     Each card is independently 100% width.
     There is NO 33.33% desktop column involved here.
     ======================================================== -->

<table
class="mobile-layout"
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
display:none;
width:100%;
"
>

<!-- MOBILE EXPENSE -->

<tr>

<td
align="center"
class="mobile-padding"
style="
padding:6px 20px;
"
>

<table
class="mobile-card"
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 10px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:14px;
line-height:20px;
color:#6b7280;
text-align:center;
">

Total Expense Amount

</div>

<div
class="mobile-value"
style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:24px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
"
>

{format_currency(total_amount)}

</div>

</td>

</tr>

</table>

</td>

</tr>


<!-- MOBILE GST -->

<tr>

<td
align="center"
class="mobile-padding"
style="
padding:6px 20px;
"
>

<table
class="mobile-card"
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 10px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:14px;
line-height:20px;
color:#6b7280;
text-align:center;
">

Total GST

</div>

<div
class="mobile-value"
style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:24px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
"
>

{format_currency(total_gst)}

</div>

</td>

</tr>

</table>

</td>

</tr>


<!-- MOBILE TDS -->

<tr>

<td
align="center"
class="mobile-padding"
style="
padding:6px 20px 10px 20px;
"
>

<table
class="mobile-card"
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
background:#f5f6f8;
border-radius:12px;
"
>

<tr>

<td
align="center"
style="
padding:22px 10px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:14px;
line-height:20px;
color:#6b7280;
text-align:center;
">

Total TDS

</div>

<div
class="mobile-value"
style="
margin-top:8px;
font-family:Arial,Helvetica,sans-serif;
font-size:24px;
line-height:30px;
font-weight:bold;
color:#111827;
text-align:center;
white-space:nowrap;
"
>

{format_currency(total_tds)}

</div>

</td>

</tr>

</table>

</td>

</tr>

</table>


</td>

</tr>


<!-- ========================================================
     FOOTER
     ======================================================== -->

<tr>

<td
align="center"
style="
padding:8px 24px 28px 24px;
"
>

<div style="
font-family:Arial,Helvetica,sans-serif;
font-size:12px;
line-height:19px;
color:#8a919c;
text-align:center;
">

This is an automatically generated monthly expense report.

</div>

</td>

</tr>


</table>


</td>

</tr>

</table>


</body>

</html>
"""


# ============================================================
# BUILD PLAIN TEXT EMAIL
# ============================================================

def build_plain_text_email(
        year,
        month,
        start_date,
        end_date,
        total_amount,
        total_gst,
        total_tds
):
    month_name = datetime(
        year,
        month,
        1
    ).strftime(
        "%B %Y"
    )

    display_start_date = (
        format_display_date(
            start_date
        )
    )

    display_end_date = (
        format_display_date(
            end_date
        )
    )

    body = ""

    body += (
            "Monthly Expense Report - "
            + month_name
            + "\n\n"
    )

    body += (
            "Report Period: "
            + display_start_date
            + " to "
            + display_end_date
            + "\n\n"
    )

    body += (
            "Total Expense Amount: "
            + format_currency(
        total_amount
    )
            + "\n"
    )

    body += (
            "Total GST: "
            + format_currency(
        total_gst
    )
            + "\n"
    )

    body += (
            "Total TDS: "
            + format_currency(
        total_tds
    )
            + "\n"
    )

    return body


# ============================================================
# SEND EMAIL THROUGH AWS SES
# ============================================================

def send_email_via_ses(
        subject,
        text_body,
        html_body
):
    aws_access_key = os.getenv(
        "AWS_ACCESS_KEY_ID"
    )

    aws_secret_key = os.getenv(
        "AWS_SECRET_ACCESS_KEY"
    )

    aws_region = os.getenv(
        "AWS_REGION"
    )

    email_to = os.getenv(
        "EMAIL_TO"
    )

    if (
            not aws_access_key
            or not aws_secret_key
            or not aws_region
    ):
        raise Exception(
            "Missing AWS SES environment variables. "
            "Please check your .env file."
        )

    if not email_to:
        raise Exception(
            "EMAIL_TO is missing in the environment."
        )

    to_addresses = [

        address.strip()

        for address
        in email_to.split(",")

        if address.strip()
    ]

    if not to_addresses:
        raise Exception(
            "No valid recipient email addresses found."
        )

    try:

        ses_client = boto3.client(

            "ses",

            region_name=aws_region,

            aws_access_key_id=
            aws_access_key,

            aws_secret_access_key=
            aws_secret_key
        )

        response = ses_client.send_email(

            Source=(
                    SES_FROM_NAME +
                    " <" +
                    SES_FROM_EMAIL +
                    ">"
            ),

            Destination={

                "ToAddresses":
                    to_addresses

            },

            Message={

                "Subject": {

                    "Data":
                        subject,

                    "Charset":
                        "UTF-8"

                },

                "Body": {

                    "Text": {

                        "Data":
                            text_body,

                        "Charset":
                            "UTF-8"

                    },

                    "Html": {

                        "Data":
                            html_body,

                        "Charset":
                            "UTF-8"

                    }

                }

            }

        )

        print()
        print(
            "SES message sent."
        )

        print(
            "Message ID:",
            response.get(
                "MessageId"
            )
        )

        return response

    except Exception as error:

        print(
            "SES email sending failed:",
            error
        )

        raise


# ============================================================
# SEND FAILURE EMAIL
# ============================================================

def send_failure_email(
        error_message,
        start_date,
        end_date
):
    subject = (
        "FAILED - Monthly Expense Report"
    )

    failure_time = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    display_start_date = (
        format_display_date(
            start_date
        )
    )

    display_end_date = (
        format_display_date(
            end_date
        )
    )

    text_body = f"""
Monthly Expense Report Failed

Status: FAILED

Report Period:
{display_start_date} to {display_end_date}

Failure Time:
{failure_time}

Error:
{error_message}

Please check the Zoho Expense API,
authentication, or the monthly expense
report process.
"""

    html_body = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1.0"
>

</head>

<body style="
margin:0;
padding:15px;
background:#f2f4f7;
font-family:Arial,Helvetica,sans-serif;
">

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
>

<tr>

<td align="center">

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
max-width:700px;
background:#ffffff;
border-radius:10px;
"
>

<tr>

<td
style="
padding:28px;
"
>

<h2 style="
margin:0 0 20px 0;
color:#d32f2f;
text-align:center;
font-family:Arial,Helvetica,sans-serif;
">

Monthly Expense Report Failed

</h2>

<p>

<strong>Status:</strong>

<span style="
color:#d32f2f;
font-weight:bold;
">

FAILED

</span>

</p>

<p>

<strong>Report Period:</strong><br>

{display_start_date}
to
{display_end_date}

</p>

<p>

<strong>Failure Time:</strong><br>

{failure_time}

</p>

<p>

<strong>Error:</strong>

</p>

<div style="
background:#f5f5f5;
border-left:4px solid #d32f2f;
padding:15px;
font-family:monospace;
font-size:13px;
line-height:20px;
word-break:break-word;
">

{error_message}

</div>

<p style="
font-size:13px;
color:#666666;
line-height:20px;
">

Please check the Zoho Expense API,
authentication, or the monthly expense
report process.

</p>

</td>

</tr>

</table>

</td>

</tr>

</table>

</body>

</html>
"""

    try:

        send_email_via_ses(

            subject,

            text_body,

            html_body
        )

        print(
            "Failure notification email sent successfully."
        )

    except Exception as email_error:

        print(
            "CRITICAL: Could not send failure notification email."
        )

        print(
            "Failure email error:",
            email_error
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        "=" * 100
    )

    print(
        "MONTHLY EXPENSE REPORT"
    )

    print(
        "=" * 100
    )

    # --------------------------------------------------------
    # GET CURRENT MONTH
    # --------------------------------------------------------

    (
        start_date,
        end_date,
        year,
        month
    ) = get_current_month_date_range()

    month_name = datetime(
        year,
        month,
        1
    ).strftime(
        "%B %Y"
    )

    print()

    print(
        "CURRENT MONTH:",
        month_name
    )

    print(
        "REPORT PERIOD:",
        start_date,
        "to",
        end_date
    )

    print(
        "DISPLAY PERIOD:",
        format_display_date(start_date),
        "to",
        format_display_date(end_date)
    )

    print()

    # --------------------------------------------------------
    # STEP 1
    # --------------------------------------------------------

    print(
        "Step 1: Getting Zoho access token..."
    )

    access_token = (
        get_zoho_access_token()
    )

    # --------------------------------------------------------
    # STEP 2
    # --------------------------------------------------------

    print(
        "Step 2: Fetching current month expenses..."
    )

    expenses = (
        get_expenses_for_current_month(

            access_token,

            start_date,

            end_date
        )
    )

    # --------------------------------------------------------
    # ZERO RECORDS IS NOT AN ERROR
    # --------------------------------------------------------

    if len(expenses) == 0:
        print()
        print(
            "No expenses found for this period."
        )

        print(
            "This is a valid result."
        )

        print(
            "No failure email will be sent."
        )

        print(
            "No monthly report email will be sent."
        )

        return

    # --------------------------------------------------------
    # STEP 3
    # --------------------------------------------------------

    print(
        "Step 3: Calculating expense, GST and TDS totals..."
    )

    (
        total_amount,
        total_gst,
        total_tds
    ) = calculate_totals(
        expenses
    )

    # --------------------------------------------------------
    # STEP 4
    # --------------------------------------------------------

    print(
        "Step 4: Preparing monthly report email..."
    )

    html_body = (
        build_html_email(

            year,

            month,

            start_date,

            end_date,

            total_amount,

            total_gst,

            total_tds
        )
    )

    plain_text_body = (
        build_plain_text_email(

            year,

            month,

            start_date,

            end_date,

            total_amount,

            total_gst,

            total_tds
        )
    )

    subject = (
            "Monthly Expense Report - "
            + month_name
    )

    # --------------------------------------------------------
    # STEP 5
    # --------------------------------------------------------

    print(
        "Step 5: Sending monthly report..."
    )

    send_email_via_ses(

        subject,

        plain_text_body,

        html_body
    )

    # --------------------------------------------------------
    # FINAL OUTPUT
    # --------------------------------------------------------

    print()
    print(
        "=" * 100
    )

    print(
        "MONTHLY REPORT COMPLETED SUCCESSFULLY"
    )

    print(
        "=" * 100
    )

    print(
        "Month:",
        month_name
    )

    print(
        "Period:",
        format_display_date(start_date),
        "to",
        format_display_date(end_date)
    )

    print(
        "Total Expense Amount:",
        format_currency(
            total_amount
        )
    )

    print(
        "Total GST:",
        format_currency(
            total_gst
        )
    )

    print(
        "Total TDS:",
        format_currency(
            total_tds
        )
    )

    print(
        "=" * 100
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    start_date, end_date, _, _ = (
        get_current_month_date_range()
    )

    try:

        main()

    except Exception as error:

        print()
        print(
            "=" * 100
        )

        print(
            "MONTHLY REPORT FAILED"
        )

        print(
            "=" * 100
        )

        print(
            str(error)
        )

        print(
            "=" * 100
        )

        # ----------------------------------------------------
        # FAILURE EMAIL
        #
        # This executes only when an actual exception occurs.
        #
        # Zero records are handled above and never reach here.
        # ----------------------------------------------------

        send_failure_email(

            str(error),

            start_date,

            end_date
        )