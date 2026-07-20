"""
Example: Filling a Medication Administration Consent Form
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdfiller import PDFFiller


def fill_medication_form():
    """
    Example of filling a medication consent form
    """

    # Input and output paths
    input_pdf = "MEDICATION_ADMINISTRATION_CONSENT_FORM.pdf"
    output_pdf = "MEDICATION_FORM_FILLED.pdf"

    # Create the filler
    with PDFFiller(input_pdf) as filler:
        # Option 1: Preserve existing student information
        filler.preserve_existing_fields(True)

        # Part I - Physician's Statement
        physician_fields = {
            "physician_medication": "Guanfacine 1mg",
            "physician_asthmatic": "No",
            "physician_dosage": "1 tablet",
            "physician_route": "Oral",
            "physician_frequency": "Once daily - afternoon",
            "physician_duration": "School year",
            "physician_diag_1": "ADHD - to improve focus and reduce impulsivity",
            "physician_other_med": "sertraline",
            "physician_other_req": "None",
            "physician_attend": "No",
            "physician_authorized": "Yes",
            "physician_unsupervised": "N/A",
            "physician_sign_address": "Dr. Matthew Graczyk, 1450 Techny Rd, Northbrook, IL 60062",
            "physician_sign_phone": "(847) 562-5612",
        }

        # Part II - Parent's Request/Approval
        parent_fields = {
            "parent_sign_phone": "773-828-9480",
            "parent_sign_date": "2/14/2026",
        }

        # Fill all fields
        filler.fill_fields(physician_fields)
        filler.fill_fields(parent_fields)

        # Check boxes for self-administration
        filler.check_box("parent_administer-2")  # Permit self-administration
        filler.check_box("parent_injector-2")  # Not asthma medication

        # Save with flattening
        output_path = filler.save(output_pdf, flatten=True)

        print("Done: Medication form filled successfully!")
        print(f"Saved to: {output_path}")


def fill_from_json():
    """
    Example of filling from a JSON configuration file
    """
    import json

    # Create a JSON config
    config = {
        "fields": {
            "physician_medication": "Guanfacine 1mg",
            "physician_asthmatic": "No",
            "physician_dosage": "1 tablet",
            "physician_route": "Oral",
            "physician_frequency": "Once daily - afternoon",
            "physician_duration": "School year",
            "physician_diag_1": "ADHD - to improve focus and reduce impulsivity",
            "physician_other_med": "sertraline",
            "physician_other_req": "None",
            "physician_attend": "No",
            "physician_authorized": "Yes",
            "physician_unsupervised": "N/A",
            "physician_sign_address": "Dr. Matthew Graczyk, 1450 Techny Rd, Northbrook, IL 60062",
            "physician_sign_phone": "(847) 562-5612",
            "parent_sign_phone": "773-828-9480",
            "parent_sign_date": "2/14/2026",
        },
        "checkboxes": ["parent_administer-2", "parent_injector-2"],
    }

    # Save config to JSON
    with open("medication_values.json", "w") as f:
        json.dump(config, f, indent=2)

    print("Done: Created medication_values.json")
    print("\nYou can now use it with:")
    print("  pdfiller fill -i form.pdf -j medication_values.json -o filled.pdf --preserve-existing")


if __name__ == "__main__":
    print("=" * 60)
    print("Medication Form Filling Example")
    print("=" * 60)
    print()

    # Example 1: Direct filling
    print("Example 1: Direct API usage")
    print("-" * 60)
    try:
        fill_medication_form()
    except Exception as e:
        print(f"Note: {e}")
        print("(Run this from a directory with the medication form PDF)")

    print()

    # Example 2: JSON config
    print("\nExample 2: JSON configuration")
    print("-" * 60)
    fill_from_json()
