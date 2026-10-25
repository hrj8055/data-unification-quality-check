from unify.normalize import (name_similarity, normalize_city, normalize_email,
                             normalize_name, normalize_phone, phone_format)


def test_phone_formats_all_become_10_digits():
    for raw in ["9876543210", "+919876543210", "+91 98765 43210", "09876543210",
                "91-9876543210", "987-654-3210", "(987) 654 3210"]:
        assert normalize_phone(raw) == "9876543210", raw


def test_invalid_phones_rejected():
    for raw in ["98765", "", None, "1234567890", "abc", "nan"]:
        assert normalize_phone(raw) == ""


def test_email_lowercased_and_validated():
    assert normalize_email("  Priya.Sharma@Example.COM ") == "priya.sharma@example.com"
    assert normalize_email("not-an-email") == ""
    assert normalize_email(None) == ""


def test_name_and_city_standardised():
    assert normalize_name("  pRIYA   sharma ") == "Priya Sharma"
    assert normalize_city("BANGALORE") == "Bengaluru"


def test_phone_format_labels():
    assert phone_format("+91 98765 43210") == "+91 prefix"
    assert phone_format("09876543210") == "leading 0"
    assert phone_format("9876543210") == "10 digits"


def test_name_similarity():
    assert name_similarity("Priya Sharma", "priya  SHARMA") == 1.0
    assert name_similarity("Priya Sharma", "Rahul Verma") == 0.0
