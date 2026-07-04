__version__ = "0.0.1"
__version__ = "0.0.1"

def apply_zatca_patch():
	try:
		import zatca_erpgulf.zatca_erpgulf.sign_invoice_first as sif
		import zatca_erpgulf.zatca_erpgulf.sign_invoice as si
		from zatca_fix.zatca_patches import patched_compliance_api_call

		sif.compliance_api_call = patched_compliance_api_call
		si.compliance_api_call = patched_compliance_api_call
	except ImportError:
		# zatca_erpgulf not installed on this site, skip
		pass

apply_zatca_patch()