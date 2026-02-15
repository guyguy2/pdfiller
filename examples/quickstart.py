"""
Quick Start Examples for PDFiller
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdfiller import PDFFiller


def example_1_basic():
    """Example 1: Basic form filling"""
    print("\n" + "="*60)
    print("Example 1: Basic Form Filling")
    print("="*60)

    with PDFFiller("sample_form.pdf") as filler:
        # Fill some fields
        filler.fill_field("name", "John Doe")
        filler.fill_field("email", "john@example.com")
        filler.fill_field("phone", "555-0123")

        # Check a checkbox
        filler.check_box("agree_to_terms")

        # Save
        filler.save("filled_form.pdf")

    print("Done: Basic form filled!")


def example_2_method_chaining():
    """Example 2: Method chaining for concise code"""
    print("\n" + "="*60)
    print("Example 2: Method Chaining")
    print("="*60)

    with PDFFiller("sample_form.pdf") as filler:
        filler.fill_field("first_name", "Jane") \
              .fill_field("last_name", "Smith") \
              .fill_field("age", "30") \
              .check_box("newsletter") \
              .save("chained_form.pdf")

    print("Done: Form filled with method chaining!")


def example_3_bulk_filling():
    """Example 3: Fill multiple fields at once"""
    print("\n" + "="*60)
    print("Example 3: Bulk Field Filling")
    print("="*60)

    # Prepare data
    user_data = {
        "name": "Alice Johnson",
        "address": "123 Main Street",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "phone": "555-0199"
    }

    with PDFFiller("sample_form.pdf") as filler:
        # Fill all fields at once
        filler.fill_fields(user_data)

        # Add checkboxes
        filler.check_box("consent")
        filler.check_box("privacy_agreement")

        # Save
        filler.save("bulk_filled.pdf")

    print("Done: Bulk filling complete!")


def example_4_discover_fields():
    """Example 4: Discover what fields are in a PDF"""
    print("\n" + "="*60)
    print("Example 4: Field Discovery")
    print("="*60)

    with PDFFiller("sample_form.pdf") as filler:
        fields = filler.list_fields()

        print(f"\nFound {len(fields)} fields:\n")
        for field in fields:
            print(f"  -{field['name']}")
            print(f"    Type: {field['type']}")
            if field['value']:
                print(f"    Current value: {field['value']}")
            print()


def example_5_preserve_existing():
    """Example 5: Preserve existing values"""
    print("\n" + "="*60)
    print("Example 5: Preserve Existing Values")
    print("="*60)

    with PDFFiller("partially_filled_form.pdf") as filler:
        # Only fill empty fields
        filler.preserve_existing_fields(True)

        # These will only fill if the fields are empty
        filler.fill_fields({
            "name": "Bob Smith",
            "email": "bob@example.com",
            "city": "Chicago"
        })

        filler.save("preserved_form.pdf")

    print("Done: Form filled, existing values preserved!")


def example_6_field_validation():
    """Example 6: Validate field names"""
    print("\n" + "="*60)
    print("Example 6: Field Validation")
    print("="*60)

    with PDFFiller("sample_form.pdf") as filler:
        # Check if fields exist
        fields_to_check = ["name", "email", "nonexistent_field"]
        results = filler.validate_fields(fields_to_check)

        print("\nValidation results:")
        for field_name, exists in results.items():
            status = "Exists" if exists else "Not found"
            print(f"  {field_name}: {status}")


# Run examples
if __name__ == "__main__":
    print("\n" + "="*60)
    print("PDFiller Quick Start Examples")
    print("="*60)

    print("\nNote: These examples assume you have a 'sample_form.pdf'")
    print("Replace with your actual PDF file path.")

    # Uncomment the examples you want to try:
    # example_1_basic()
    # example_2_method_chaining()
    # example_3_bulk_filling()
    # example_4_discover_fields()
    # example_5_preserve_existing()
    # example_6_field_validation()

    print("\nUncomment the examples in the script to try them!")
