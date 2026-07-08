import frappe
from frappe import _
import json
import base64
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.bindings._rust import ObjectIdentifier
from zatca_erpgulf.zatca_erpgulf.create_invoice import (
    get_csr_data_multiple,
    get_csr_data,
    create_private_keys,
    encode_customoid,
)

@frappe.whitelist(allow_guest=False)
def create_csr(zatca_doc: dict | str, portal_type: str, company_abbr: str):
    """Custom override: treat Simulation same as Production for OID"""
    try:
        if isinstance(zatca_doc, str):
            zatca_doc = json.loads(zatca_doc)
        if (
            not isinstance(zatca_doc, dict)
            or "doctype" not in zatca_doc
            or "name" not in zatca_doc
        ):
            frappe.throw(_("Invalid 'zatca_doc' format. Must include 'doctype' and 'name'."))

        doc = frappe.get_doc(zatca_doc.get("doctype"), zatca_doc.get("name"))

        if doc.doctype == "ZATCA Multiple Setting":
            csr_values = get_csr_data_multiple(doc)
        elif doc.doctype == "Company":
            csr_values = get_csr_data(company_abbr)
        else:
            frappe.throw(_("Unsupported document type for CSR creation."))

        company_csr_data = csr_values

        csr_common_name = company_csr_data.get("csr.common.name")
        csr_serial_number = company_csr_data.get("csr.serial.number")
        csr_organization_identifier = company_csr_data.get("csr.organization.identifier")
        csr_organization_unit_name = company_csr_data.get("csr.organization.unit.name")
        csr_organization_name = company_csr_data.get("csr.organization.name")
        csr_country_name = company_csr_data.get("csr.country.name")
        csr_invoice_type = company_csr_data.get("csr.invoice.type")
        csr_location_address = company_csr_data.get("csr.location.address")
        csr_industry_business_category = company_csr_data.get("csr.industry.business.category")

        # --- Only change vs original: Simulation now uses production OID ---
        if portal_type == "Sandbox":
            customoid = encode_customoid("TESTZATCA-Code-Signing")
        else:
            # Simulation and Production both use ZATCA-Code-Signing
            customoid = encode_customoid("ZATCA-Code-Signing")

        if doc.doctype == "ZATCA Multiple Setting":
            private_key_pem = create_private_keys(doc, zatca_doc)
        elif doc.doctype == "Company":
            private_key_pem = create_private_keys(company_abbr, zatca_doc)
        else:
            frappe.throw(_("no private key."))

        private_key = serialization.load_pem_private_key(
            private_key_pem, password=None, backend=default_backend()
        )

        custom_oid_string = "1.3.6.1.4.1.311.20.2"
        oid = ObjectIdentifier(custom_oid_string)
        custom_extension = x509.extensions.UnrecognizedExtension(oid, customoid)

        dn = x509.Name([
            x509.NameAttribute(x509.NameOID.COUNTRY_NAME, csr_country_name),
            x509.NameAttribute(x509.NameOID.ORGANIZATIONAL_UNIT_NAME, csr_organization_unit_name),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, csr_organization_name),
            x509.NameAttribute(x509.NameOID.COMMON_NAME, csr_common_name),
        ])
        alt_name = x509.SubjectAlternativeName([
            x509.DirectoryName(x509.Name([
                x509.NameAttribute(x509.NameOID.SURNAME, csr_serial_number),
                x509.NameAttribute(x509.NameOID.USER_ID, csr_organization_identifier),
                x509.NameAttribute(x509.NameOID.TITLE, csr_invoice_type),
                x509.NameAttribute(ObjectIdentifier("2.5.4.26"), csr_location_address),
                x509.NameAttribute(x509.NameOID.BUSINESS_CATEGORY, csr_industry_business_category),
            ])),
        ])

        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(dn)
            .add_extension(custom_extension, critical=False)
            .add_extension(alt_name, critical=False)
            .sign(private_key, hashes.SHA256(), backend=default_backend())
        )
        mycsr = csr.public_bytes(serialization.Encoding.PEM)
        base64csr = base64.b64encode(mycsr)
        encoded_string = base64csr.decode("utf-8")

        if doc.doctype == "ZATCA Multiple Setting":
            multiple_setting_doc = frappe.get_doc("ZATCA Multiple Setting", doc.name)
            multiple_setting_doc.custom_csr_data = encoded_string.strip()
            multiple_setting_doc.save(ignore_permissions=True)
        elif doc.doctype == "Company":
            company_doc = frappe.get_doc("Company", {"abbr": company_abbr})
            company_doc.custom_csr_data = encoded_string.strip()
            company_doc.save(ignore_permissions=True)

        return encoded_string

    except (ValueError, KeyError, TypeError, frappe.ValidationError) as e:
        frappe.throw(_("error occurred while creating csr for company {company_abbr} " + str(e)))
        return None
