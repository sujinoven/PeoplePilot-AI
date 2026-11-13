"""Offline unit tests for the 7 HR tools.

Expected values come from the PROITBRIDGE Employee Handbook (v6.0), NOT from the
tool code, so a test fails when the code drifts from the handbook.

Tests marked xfail(strict=True) document a known gap between the code and the
handbook. They are written for the CORRECT behaviour. When you fix the gap the
test starts passing, strict mode turns that into a failure, and you delete the
xfail marker. That is the signal that the fix landed.
"""

import json

import pytest

from src.tools import (
    HR_TOOLS,
    calculate_earned_leave_accrual,
    calculate_probation_end,
    calculate_remote_work_allowance,
    calculate_travel_daily_allowance,
    check_payroll_deadline,
    validate_leave_request,
    validate_reimbursement_claim,
)


def leave(leave_type, days, probation=False, advance=30):
    return validate_leave_request.invoke(
        {
            "leave_type": leave_type,
            "days": days,
            "is_on_probation": probation,
            "advance_days": advance,
        }
    )


def claim(days_since_return=5, amount=1000.0, travel_request=True, docs=True):
    return validate_reimbursement_claim.invoke(
        {
            "days_since_return": days_since_return,
            "amount": amount,
            "has_approved_travel_request": travel_request,
            "has_required_documents": docs,
        }
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_seven_tools_with_unique_names_and_descriptions():
    names = [t.name for t in HR_TOOLS]
    assert len(names) == 7
    assert len(set(names)) == 7
    assert all(t.description.strip() for t in HR_TOOLS)


def test_tool_results_are_json_serialisable():
    """ToolNode stores results as JSON strings and edges.py json.loads() them."""
    samples = [
        leave("EL", 2),
        calculate_earned_leave_accrual.invoke({"completed_months": 6}),
        calculate_probation_end.invoke({"joining_date": "2026-01-01"}),
        check_payroll_deadline.invoke({"date": "2026-11-10"}),
        claim(),
        calculate_remote_work_allowance.invoke({"work_model": "hybrid"}),
        calculate_travel_daily_allowance.invoke({"location_type": "metro", "grade": 3}),
    ]
    for result in samples:
        assert isinstance(json.loads(json.dumps(result)), dict)


# ---------------------------------------------------------------------------
# 1. validate_leave_request  (Handbook 4.5, 7.2, 7.3, 7.4)
# ---------------------------------------------------------------------------
class TestValidateLeaveRequest:
    def test_el_blocked_during_probation(self):
        r = leave("EL", 2, probation=True)
        assert r["valid"] is False
        assert "probation" in r["reason"].lower()

    def test_cl_and_sl_allowed_during_probation(self):
        assert leave("CL", 1, probation=True)["valid"] is True
        assert leave("SL", 1, probation=True)["valid"] is True

    @pytest.mark.parametrize(
        "days, advance, expected",
        [
            (1, 6, False),   # 1-3 days needs 7 working days
            (1, 7, True),
            (3, 6, False),
            (3, 7, True),
            (4, 20, False),  # 4+ days needs 21 days
            (4, 21, True),
            (10, 21, True),
        ],
    )
    def test_el_advance_notice_boundaries(self, days, advance, expected):
        assert leave("EL", days, advance=advance)["valid"] is expected

    @pytest.mark.parametrize("days, expected", [(1, True), (3, True), (4, False), (8, False)])
    def test_cl_max_three_consecutive_days(self, days, expected):
        assert leave("CL", days)["valid"] is expected

    def test_leave_type_is_case_and_space_insensitive(self):
        assert leave(" el ", 1, advance=7)["valid"] is True

    @pytest.mark.parametrize("days", [0, -1])
    def test_non_positive_days_rejected(self, days):
        assert leave("CL", days)["valid"] is False

    def test_unsupported_leave_type_rejected(self):
        r = leave("XX", 1)
        assert r["valid"] is False
        assert "unsupported" in r["reason"].lower()

    
    def test_sl_three_days_mentions_medical_certificate(self):
        assert "certificate" in json.dumps(leave("SL", 3)).lower()

    
    def test_half_day_el_supported(self):
        assert leave("EL", 0.5, advance=7)["valid"] is True

    def test_sl_under_three_days_has_no_certificate_note(self):
        assert "certificate" not in json.dumps(leave("SL", 2)).lower()

    def test_non_half_day_increment_rejected(self):
        assert leave("CL", 1.3)["valid"] is False


# ---------------------------------------------------------------------------
# 2. calculate_earned_leave_accrual  (Handbook 7.2: 1.5 days / completed month)
# ---------------------------------------------------------------------------
class TestEarnedLeaveAccrual:
    @pytest.mark.parametrize("months, expected", [(0, 0.0), (1, 1.5), (6, 9.0), (12, 18.0)])
    def test_accrual_matches_handbook(self, months, expected):
        r = calculate_earned_leave_accrual.invoke({"completed_months": months})
        assert r["valid"] is True
        assert r["earned_leave_days"] == expected

    def test_twelve_months_equals_annual_entitlement(self):
        """Handbook 7.1 lists EL as 18 days per year."""
        r = calculate_earned_leave_accrual.invoke({"completed_months": 12})
        assert r["earned_leave_days"] == 18

    def test_negative_months_rejected(self):
        r = calculate_earned_leave_accrual.invoke({"completed_months": -1})
        assert r["valid"] is False


# ---------------------------------------------------------------------------
# 3. calculate_probation_end  (Handbook 4.5: 90 calendar days; 180 for Manager+)
# ---------------------------------------------------------------------------
class TestProbationEnd:
    def test_standard_probation_is_90_days(self):
        r = calculate_probation_end.invoke({"joining_date": "2026-01-01"})
        assert r["valid"] is True
        assert r["probation_days"] == 90
        assert r["probation_end_date"] == "2026-04-01"

    def test_leap_year_is_counted_in_calendar_days(self):
        r = calculate_probation_end.invoke({"joining_date": "2028-01-01"})
        assert r["probation_end_date"] == "2028-03-31"

    def test_surrounding_whitespace_is_stripped(self):
        r = calculate_probation_end.invoke({"joining_date": "  2026-01-01 "})
        assert r["valid"] is True

    @pytest.mark.parametrize("bad", ["01-01-2026", "2026/01/01", "tomorrow", "2026-13-01", ""])
    def test_bad_date_format_rejected(self, bad):
        assert calculate_probation_end.invoke({"joining_date": bad})["valid"] is False

    
    def test_tool_accepts_a_role_or_grade_input(self):
        assert {"role", "grade", "is_manager"} & set(calculate_probation_end.args)

    def test_manager_probation_is_180_days(self):
        r = calculate_probation_end.invoke({"joining_date": "2026-01-01", "is_manager": True})
        assert r["probation_days"] == 180
        assert r["probation_end_date"] == "2026-06-30"


# ---------------------------------------------------------------------------
# 4. check_payroll_deadline  (Handbook 8.1)
# ---------------------------------------------------------------------------
class TestPayrollDeadline:
    def test_before_cutoff_inputs_open(self):
        r = check_payroll_deadline.invoke({"date": "2026-11-10"})
        assert r["valid"] is True
        assert r["payroll_cutoff"] == "2026-11-20"
        assert r["payroll_inputs_status"].startswith("Open")
        assert r["payslip_by"] == "2026-12-01"

    def test_cutoff_day_itself_is_still_open(self):
        r = check_payroll_deadline.invoke({"date": "2026-11-20"})
        assert r["payroll_inputs_status"].startswith("Open")

    def test_day_after_cutoff_is_closed(self):
        r = check_payroll_deadline.invoke({"date": "2026-11-21"})
        assert r["payroll_inputs_status"].startswith("Closed")

    def test_december_payslip_rolls_into_next_year(self):
        r = check_payroll_deadline.invoke({"date": "2026-12-15"})
        assert r["payslip_by"] == "2027-01-01"

    def test_invalid_date_rejected(self):
        assert check_payroll_deadline.invoke({"date": "20/11/2026"})["valid"] is False

    
    def test_salary_credit_skips_weekends(self):
        r = check_payroll_deadline.invoke({"date": "2026-10-10"})
        assert r["salary_credit_date"].startswith("2026-10-30")


# ---------------------------------------------------------------------------
# 5. validate_reimbursement_claim  (Handbook 17.4)
# ---------------------------------------------------------------------------
class TestReimbursementClaim:
    def test_clean_claim_within_15_days_is_valid(self):
        r = claim(days_since_return=5, amount=1000)
        assert r["valid"] is True

    def test_amount_must_be_positive(self):
        assert claim(amount=0)["valid"] is False

    def test_approved_travel_request_is_mandatory(self):
        r = claim(travel_request=False)
        assert r["valid"] is False
        assert "travel request" in r["reason"].lower()

    def test_bills_above_500_need_scans(self):
        assert claim(amount=501, docs=False)["valid"] is False

    def test_amount_of_exactly_500_does_not_need_scans(self):
        assert claim(amount=500, docs=False)["valid"] is True

    @pytest.mark.parametrize(
        "days, expected",
        [
            (0, True),
            (15, True),    # "within 15 days"
            (16, None),    # handbook silent for 16-45
            (45, None),
            (46, False),   # older than 45 needs Finance Head approval
            (90, False),
        ],
    )
    def test_submission_window_boundaries(self, days, expected):
        assert claim(days_since_return=days)["valid"] is expected

    def test_undefined_window_defers_to_hr_instead_of_guessing(self):
        r = claim(days_since_return=20)
        assert r["valid"] is None
        assert "hr" in r["next_step"].lower()

    def test_settlement_time_threshold_is_strictly_above_50000(self):
        assert "payroll cycle" in claim(amount=50000)["next_step"]
        assert "10 working days" in claim(amount=50001)["next_step"]

    def test_missing_travel_request_checked_before_age(self):
        r = claim(days_since_return=90, travel_request=False)
        assert "travel request" in r["reason"].lower()


# ---------------------------------------------------------------------------
# 6. calculate_remote_work_allowance  (Handbook 18.3)
# ---------------------------------------------------------------------------
class TestRemoteWorkAllowance:
    @pytest.mark.parametrize(
        "model, expected",
        [
            ("hybrid", 1500),
            ("remote-first", 2500),
            ("Remote First", 2500),
            ("remote_first", 2500),
            ("  HYBRID ", 1500),
        ],
    )
    def test_allowance_by_work_model(self, model, expected):
        r = calculate_remote_work_allowance.invoke({"work_model": model})
        assert r["valid"] is True
        assert r["internet_allowance_per_month"] == expected
        assert r["currency"] == "INR"

    @pytest.mark.parametrize("model", ["onsite", "office", ""])
    def test_unknown_work_model_rejected(self, model):
        assert calculate_remote_work_allowance.invoke({"work_model": model})["valid"] is False


# ---------------------------------------------------------------------------
# 7. calculate_travel_daily_allowance  (Handbook 17.3, full table)
# ---------------------------------------------------------------------------
HANDBOOK_DA = {
    # location: {grade band: (amount, currency)}
    "metro": {(1, 2): (1200, "INR"), (3,): (1600, "INR"), (4, 5): (2200, "INR")},
    "other_india": {(1, 2): (900, "INR"), (3,): (1200, "INR"), (4, 5): (1600, "INR")},
    "asia_middle_east": {(1, 2): (45, "USD"), (3,): (60, "USD"), (4, 5): (80, "USD")},
    "europe_americas": {(1, 2): (65, "USD"), (3,): (85, "USD"), (4, 5): (110, "USD")},
}
HANDBOOK_DA_CASES = [
    (location, grade, amount, currency)
    for location, bands in HANDBOOK_DA.items()
    for grades, (amount, currency) in bands.items()
    for grade in grades
]


class TestTravelDailyAllowance:
    @pytest.mark.parametrize("location, grade, amount, currency", HANDBOOK_DA_CASES)
    def test_every_cell_of_the_handbook_table(self, location, grade, amount, currency):
        r = calculate_travel_daily_allowance.invoke({"location_type": location, "grade": grade})
        assert r["valid"] is True
        assert r["daily_allowance"] == amount
        assert r["currency"] == currency

    def test_location_is_case_and_space_insensitive(self):
        r = calculate_travel_daily_allowance.invoke({"location_type": " Metro ", "grade": 3})
        assert r["daily_allowance"] == 1600

    @pytest.mark.parametrize("grade", [0, 6, -1])
    def test_grade_out_of_range_rejected(self, grade):
        r = calculate_travel_daily_allowance.invoke({"location_type": "metro", "grade": grade})
        assert r["valid"] is False

    def test_unknown_location_rejected(self):
        r = calculate_travel_daily_allowance.invoke({"location_type": "mars", "grade": 3})
        assert r["valid"] is False


    def test_supports_half_day_or_meals_provided(self):
        assert {"half_day", "meals_provided"} & set(calculate_travel_daily_allowance.args)

    def test_one_meal_provided_cuts_one_third(self):
        r = calculate_travel_daily_allowance.invoke(
            {"location_type": "metro", "grade": 3, "meals_provided": 1}
        )
        assert r["daily_allowance"] == 1066.67   # 1600 * 2/3

    def test_meals_provided_out_of_range_rejected(self):
        r = calculate_travel_daily_allowance.invoke(
            {"location_type": "metro", "grade": 3, "meals_provided": 4}
        )
        assert r["valid"] is False

    def test_half_day_is_flagged_as_assumption(self):
        r = calculate_travel_daily_allowance.invoke(
            {"location_type": "metro", "grade": 3, "is_half_day": True}
        )
        assert r["daily_allowance"] == 800.0
        assert "assumption" in r