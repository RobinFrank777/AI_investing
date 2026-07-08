import validate_config as config_validator


def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def run_failure_case(case_name, changes, expected_error_fragment):
    print_section(f"Running failure case: {case_name}")

    original_values = {}

    for name, bad_value in changes.items():
        original_values[name] = getattr(config_validator, name)
        setattr(config_validator, name, bad_value)

    try:
        errors = config_validator.validate_config()

        print("Temporary config changes:")
        for name, bad_value in changes.items():
            print(f"- {name}: {bad_value}")

        print("\nValidation errors detected:")
        for error in errors:
            print(f"- {error}")

        if not errors:
            raise AssertionError(
                f"{case_name} failed: validate_config() did not detect any error"
            )

        if not any(expected_error_fragment in error for error in errors):
            raise AssertionError(
                f"{case_name} failed: expected error containing "
                f"'{expected_error_fragment}' was not found"
            )

        print(f"\nCASE PASSED: {case_name}")

    finally:
        for name, original_value in original_values.items():
            setattr(config_validator, name, original_value)


def run_config_validation_failure_demo():
    print_section("AI INVESTING CONFIG VALIDATION FAILURE DEMO")
    print("This demo intentionally injects invalid config values.")
    print("It does not modify config.py on disk.")
    print("Each case should produce validation errors.")

    failure_cases = [
        {
            "case_name": "negative account value",
            "changes": {
                "ACCOUNT_VALUE": -100000,
            },
            "expected_error_fragment": "ACCOUNT_VALUE must be greater than 0",
        },
        {
            "case_name": "total exposure above 100 percent",
            "changes": {
                "MAX_TOTAL_EXPOSURE": 1.50,
            },
            "expected_error_fragment": "MAX_TOTAL_EXPOSURE must be between 0 and 1",
        },
        {
            "case_name": "cash reserve plus exposure above 100 percent",
            "changes": {
                "MAX_TOTAL_EXPOSURE": 0.90,
                "CASH_RESERVE_RATIO": 0.30,
            },
            "expected_error_fragment": (
                "MAX_TOTAL_EXPOSURE + CASH_RESERVE_RATIO must not exceed 1"
            ),
        },
        {
            "case_name": "zero max order count",
            "changes": {
                "MAX_ORDER_COUNT": 0,
            },
            "expected_error_fragment": "MAX_ORDER_COUNT must be greater than 0",
        },
        {
            "case_name": "missing BUY action",
            "changes": {
                "ALLOWED_ACTIONS": ["SELL"],
            },
            "expected_error_fragment": "ALLOWED_ACTIONS must include BUY",
        },
        {
            "case_name": "project version missing v prefix",
            "changes": {
                "PROJECT_VERSION": "2.12.0",
            },
            "expected_error_fragment": "PROJECT_VERSION should start with v",
        },
    ]

    for failure_case in failure_cases:
        run_failure_case(
            case_name=failure_case["case_name"],
            changes=failure_case["changes"],
            expected_error_fragment=failure_case["expected_error_fragment"],
        )

    print_section("CONFIG VALIDATION FAILURE DEMO PASSED")
    print("All intentional invalid config cases were detected.")


if __name__ == "__main__":
    run_config_validation_failure_demo()