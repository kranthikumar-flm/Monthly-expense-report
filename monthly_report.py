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

    # --------------------------------------------------------
    # Get today's date from the computer.
    #
    # Example:
    #
    # If the script runs on 2026-10-06:
    #
    # start_date = 2026-10-01
    # end_date   = 2026-10-06
    #
    # If it runs on 2026-11-10:
    #
    # start_date = 2026-11-01
    # end_date   = 2026-11-10
    # --------------------------------------------------------

    today = date.today()


    # --------------------------------------------------------
    # First day of current month
    # --------------------------------------------------------

    start_date = date(
        today.year,
        today.month,
        1
    )


    # --------------------------------------------------------
    # End date = today
    # --------------------------------------------------------

    end_date = today


    return (
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        today.year,
        today.month
    )


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


    response = requests.post(

        ZOHO_ACCOUNTS_URL +
        "/oauth/v2/token",

        params=params,

        timeout=60
    )


    print(
        "Zoho token response code:",
        response.status_code
    )


    if response.status_code != 200:

        raise Exception(
            "Zoho authentication failed:\n" +
            response.text
        )


    data = response.json()


    if not data.get(
        "access_token"
    ):

        raise Exception(
            "Zoho access token was not returned:\n" +
            str(data)
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
    # GET EXPENSE LIST
    # ========================================================

    while True:

        url = (
            ZOHO_API_URL +
            "/expense/v1/expenses" +
            "?date_start=" +
            start_date +
            "&date_end=" +
            end_date +
            "&page=" +
            str(page) +
            "&per_page=" +
            str(per_page)
        )


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


        response = requests.get(

            url,

            headers=headers,

            timeout=60
        )


        print(
            "Expenses API response:",
            response.status_code
        )


        if response.status_code != 200:

            raise Exception(
                "Zoho Expenses API failed.\n"
                "HTTP Code: " +
                str(response.status_code) +
                "\n" +
                response.text
            )


        data = response.json()


        if data.get("code") != 0:

            raise Exception(
                "Zoho Expenses API error:\n" +
                response.text
            )


        expenses = data.get(
            "expenses",
            []
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
    # FETCH FULL DETAILS FOR EVERY EXPENSE
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


        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Preserve rcy_total from original list response.
        #
        # This is the value we want to use for the report.
        # ----------------------------------------------------

        original_rcy_total = expense.get(
            "rcy_total"
        )


        print(
            "Original list rcy_total:",
            original_rcy_total
        )


        # ----------------------------------------------------
        # If ID is missing, keep original record.
        # ----------------------------------------------------

        if not expense_id:

            print(
                "Expense ID not found. "
                "Using list response."
            )


            detailed_expenses.append(
                expense
            )


            continue


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


            if detail_response.status_code != 200:

                print(
                    "Could not fetch full details "
                    f"for expense {expense_id}. "
                    f"HTTP {detail_response.status_code}"
                )


                detailed_expenses.append(
                    expense
                )


                continue


            detail_data = (
                detail_response.json()
            )


            if detail_data.get("code") != 0:

                print(
                    "Expense detail API returned "
                    f"an error for {expense_id}"
                )


                detailed_expenses.append(
                    expense
                )


                continue


            # ------------------------------------------------
            # Get detail expense object.
            # ------------------------------------------------

            detail_expense = (
                detail_data.get("expense")
                or detail_data
            )


            detail_rcy_total = (
                detail_expense.get(
                    "rcy_total"
                )
            )


            print(
                "Detail rcy_total:",
                detail_rcy_total
            )


            # ------------------------------------------------
            # Merge list + detail data.
            #
            # Preserve original rcy_total separately.
            # ------------------------------------------------

            merged_expense = {

                **expense,

                **detail_expense,

                "_list_rcy_total":
                    original_rcy_total
            }


            detailed_expenses.append(
                merged_expense
            )


        except Exception as error:

            print(
                f"Error fetching expense details "
                f"for {expense_id}: {error}"
            )


            detailed_expenses.append(
                expense
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
# GET EXPENSE AMOUNT
#
# PRIMARY FIELD:
#     rcy_total
#
# DO NOT USE:
#     total
#     amount
#
# rcy_total is the reporting-currency amount.
# ============================================================

def get_amount(expense):

    # --------------------------------------------------------
    # FIRST PRIORITY:
    #
    # rcy_total from ORIGINAL list response.
    # --------------------------------------------------------

    list_rcy_total = parse_amount(
        expense.get(
            "_list_rcy_total"
        )
    )


    if list_rcy_total is not None:

        return list_rcy_total


    # --------------------------------------------------------
    # SECOND PRIORITY:
    #
    # rcy_total from merged/detail response.
    # --------------------------------------------------------

    rcy_total = parse_amount(
        expense.get(
            "rcy_total"
        )
    )


    if rcy_total is not None:

        return rcy_total


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT use:
    #     total
    #     amount
    #
    # as fallback.
    # --------------------------------------------------------

    return Decimal("0")


# ============================================================
# GET GST
# ============================================================

def get_gst(expense):

    custom_fields = expense.get(
        "custom_fields"
    )


    if (
        custom_fields
        and isinstance(
            custom_fields,
            list
        )
    ):

        for field in custom_fields:

            if (
                field.get("api_name")
                == "cf_gst"
            ):

                value = field.get(
                    "value"
                )


                try:

                    return Decimal(
                        str(
                            value or 0
                        )
                    )


                except Exception:

                    return Decimal("0")


    return Decimal("0")


# ============================================================
# GET TDS
# ============================================================

def get_tds(expense):

    custom_fields = expense.get(
        "custom_fields"
    )


    if (
        custom_fields
        and isinstance(
            custom_fields,
            list
        )
    ):

        for field in custom_fields:

            if (
                field.get("api_name")
                == "cf_tds"
            ):

                value = field.get(
                    "value"
                )


                try:

                    return Decimal(
                        str(
                            value or 0
                        )
                    )


                except Exception:

                    return Decimal("0")


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
        "EXPENSE-WISE GST / TDS / RCY TOTAL"
    )


    print(
        "=" * 100
    )


    for expense in expenses:

        expense_id = (
            expense.get("expense_id")
            or expense.get("id")
            or "UNKNOWN"
        )


        description = (
            expense.get("description")
            or expense.get("merchant_name")
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
        "TOTAL EXPENSE AMOUNT (rcy_total):",
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

def format_currency(
    amount
):

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
# BUILD HTML EMAIL
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


    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

</head>

<body style="
font-family:Arial,sans-serif;
background:#f5f6f8;
margin:0;
padding:30px;
">

<div style="
max-width:900px;
margin:auto;
background:white;
padding:30px;
">

<h2 style="
margin-top:0;
color:#222;
">

Monthly Expense Report - {month_name}

</h2>


<div style="
font-size:13px;
color:#777;
margin-bottom:20px;
">

Period: {start_date} to {end_date}

</div>


<table
width="100%"
cellspacing="15"
cellpadding="0"
>

<tr>


<td style="
background:#f1f3f5;
padding:25px;
text-align:center;
">

<div style="
font-size:14px;
color:#666;
">

Total Expense Amount

</div>


<div style="
font-size:28px;
font-weight:bold;
margin-top:8px;
">

{format_currency(total_amount)}

</div>

</td>


<td style="
background:#f1f3f5;
padding:25px;
text-align:center;
">

<div style="
font-size:14px;
color:#666;
">

Total GST

</div>


<div style="
font-size:28px;
font-weight:bold;
margin-top:8px;
">

{format_currency(total_gst)}

</div>

</td>


<td style="
background:#f1f3f5;
padding:25px;
text-align:center;
">

<div style="
font-size:14px;
color:#666;
">

Total TDS

</div>


<div style="
font-size:28px;
font-weight:bold;
margin-top:8px;
">

{format_currency(total_tds)}

</div>

</td>


</tr>

</table>


<div style="
margin-top:25px;
font-size:12px;
color:#777;
">

This is an automatically generated monthly expense report.

</div>


</div>

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


    body = ""


    body += (
        "Monthly Expense Report - "
        + month_name
        + "\n\n"
    )


    body += (
        "Report Period: "
        + start_date
        + " to "
        + end_date
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
    # GET CURRENT MONTH DATE RANGE
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
        "REPORT MONTH:",
        month_name
    )


    print(
        "REPORT PERIOD:",
        start_date,
        "to",
        end_date
    )


    print()


    # --------------------------------------------------------
    # GET ZOHO ACCESS TOKEN
    # --------------------------------------------------------

    access_token = (
        get_zoho_access_token()
    )


    # --------------------------------------------------------
    # GET CURRENT MONTH EXPENSES
    # --------------------------------------------------------

    expenses = (
        get_expenses_for_current_month(
            access_token,
            start_date,
            end_date
        )
    )


    # --------------------------------------------------------
    # CALCULATE TOTALS
    # --------------------------------------------------------

    (
        total_amount,
        total_gst,
        total_tds
    ) = calculate_totals(
        expenses
    )


    # --------------------------------------------------------
    # BUILD EMAIL
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # EMAIL SUBJECT
    # --------------------------------------------------------

    subject = (
        "Monthly Expense Report - "
        + month_name
    )


    # --------------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------------

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
        start_date,
        "to",
        end_date
    )


    print(
        "Total Expense Amount (rcy_total):",
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


        raise