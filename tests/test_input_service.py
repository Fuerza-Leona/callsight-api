import pytest
from datetime import datetime
from fastapi import HTTPException
from app.services.input_service import parse_inputs


@pytest.mark.parametrize(
    "date_string, participants, expected_date, expected_participants",
    [
        (
            "2023-10-01 15:30",
            "00000000-0000-0000-0000-000000000001,00000000-0000-0000-0000-000000000002",
            datetime(2023, 10, 1, 15, 30),
            [
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ],
        ),
        ("", "", datetime.now(), []),
        ("2023-10-01 15:30", "", datetime(2023, 10, 1, 15, 30), []),
        ("2023-10-01 15:30", "   ", datetime(2023, 10, 1, 15, 30), []),
    ],
)
def test_parse_inputs_valid(
    date_string, participants, expected_date, expected_participants
):
    parsed_date, parsed_participants = parse_inputs(date_string, participants)

    # Allow a small margin for datetime.now() default
    if date_string == "":
        assert abs((parsed_date - expected_date).total_seconds()) < 1
    else:
        assert parsed_date == expected_date

    assert parsed_participants == expected_participants


def test_parse_inputs_invalid_date():
    date_string = "invalid-date"
    participants = "00000000-0000-0000-0000-000000000001"

    with pytest.raises(HTTPException) as exc_info:
        parse_inputs(date_string, participants)

    assert exc_info.value.detail == "Invalid date format. Expected YYYY-MM-DD HH:MM"
