import json
import frappe
from frappe import _
from zatca_erpgulf.zatca_erpgulf.sign_invoice_first import (
    get_api_url,
    xml_base64_decode,
)


def patched_compliance_api_call(
    uuid1, encoded_hash, signed_xmlfile_name, company_abbr, source_doc
):
    """Patched: fixes unconditional throw + inverted status check in original."""
    import requests

    try:
        company_name = frappe.db.get_value("Company", {"abbr": company_abbr}, "name")
        if not company_name:
            frappe.throw(_(f"Company with abbreviation {company_abbr} not found."))
        company_doc = frappe.get_doc("Company", company_name)
        payload = json.dumps(
            {
                "invoiceHash": encoded_hash,
                "uuid": uuid1,
                "invoice": xml_base64_decode(signed_xmlfile_name),
            }
        )
        if (
            hasattr(source_doc, "custom_zatca_pos_name")
            and source_doc.custom_zatca_pos_name
        ):
            zatca_settings = frappe.get_doc(
                "ZATCA Multiple Setting", source_doc.custom_zatca_pos_name
            )
            if zatca_settings.custom__use_company_certificate__keys != 1:
                csid = zatca_settings.custom_basic_auth_from_csid
            else:
                linked_doc = frappe.get_doc(
                    "Company", zatca_settings.custom_linked_doctype
                )
                csid = linked_doc.custom_basic_auth_from_csid
        else:
            csid = company_doc.custom_basic_auth_from_csid

        if not csid:
            frappe.throw(
                _(f"CSID for company {company_abbr} not found or not found in multiple setting page")
            )

        headers = {
            "accept": "application/json",
            "Accept-Language": "en",
            "Accept-Version": "V2",
            "Authorization": "Basic " + csid,
            "Content-Type": "application/json",
        }

        response = requests.request(
            "POST",
            url=get_api_url(company_abbr, base_url="compliance/invoices"),
            headers=headers,
            data=payload,
            timeout=300,
        )

        if response.status_code not in (200, 202):
            frappe.throw(_(f"Error in compliance: {response.text}"))

        return response.text

    except requests.exceptions.RequestException as e:
        frappe.msgprint(_(f"Request exception occurred: {str(e)}"))
        return "error in compliance", "NOT ACCEPTED"
    except (ValueError, KeyError, TypeError, frappe.ValidationError) as e:
        frappe.throw(_(f"ERROR in clearance invoice, ZATCA validation: {str(e)}"))
        return None


def apply_patch():
    """Patch both module references since sign_invoice.py imported
    compliance_api_call directly into its own namespace."""
    import zatca_erpgulf.zatca_erpgulf.sign_invoice_first as sif
    import zatca_erpgulf.zatca_erpgulf.sign_invoice as si

    sif.compliance_api_call = patched_compliance_api_call
    si.compliance_api_call = patched_compliance_api_call
