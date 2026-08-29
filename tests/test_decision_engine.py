import unittest
from step5_calculation import (
    calculate_verified_income,
    calculate_obligations,
    validate_statement_arithmetic,
    check_eligibility,
)
from step6_risk_anomaly import (
    detect_discrepancies,
    calculate_risk_and_routing,
    Discrepancy,
    classify_anomalies_with_llm,
    AnomalyAssessment,
)


class TestCalculationEngine(unittest.TestCase):
    def test_1_verified_income_calculation(self):
        payslips = [
            {"extracted": {"net_pay": 100000}},
            {"extracted": {"net_pay": 110000}},
        ]
        bank_txns = [
            {"amount": 105000, "category": "salary_credit"},
        ]
        metrics = calculate_verified_income(
            declared_income=105000,
            payslips=payslips,
            bank_transactions=bank_txns,
        )
        self.assertEqual(metrics.avg_payslip_income, 105000.0)
        self.assertEqual(metrics.avg_salary_credit, 105000.0)
        self.assertEqual(metrics.verified_monthly_income, 105000.0)
        self.assertEqual(metrics.income_variance, 0.0)
        self.assertEqual(metrics.income_variance_percent, 0.0)

    def test_2_obligations_and_foir(self):
        declared_liabilities = [{"emi_amount": 15000}]
        bank_txns = [{"amount": -15000, "category": "emi_debit"}]
        metrics = calculate_obligations(
            declared_liabilities=declared_liabilities,
            bank_transactions=bank_txns,
            verified_monthly_income=100000.0,
            proposed_emi=10000.0,
        )
        self.assertEqual(metrics.declared_total_emi, 15000.0)
        self.assertEqual(metrics.total_existing_emis, 15000.0)
        self.assertEqual(metrics.proposed_emi, 10000.0)
        self.assertEqual(metrics.total_monthly_obligations, 25000.0)
        self.assertEqual(metrics.foir_percentage, 25.0)
        self.assertEqual(metrics.disposable_income, 75000.0)
        self.assertFalse(metrics.has_undisclosed_liabilities)

    def test_3_undisclosed_liability_detection(self):
        declared_liabilities = [{"emi_amount": 10000}]
        bank_txns = [
            {"amount": -10000, "category": "emi_debit"},
            {"amount": -25000, "category": "emi_debit"},
        ]
        metrics = calculate_obligations(
            declared_liabilities=declared_liabilities,
            bank_transactions=bank_txns,
            verified_monthly_income=100000.0,
        )
        self.assertEqual(metrics.declared_total_emi, 10000.0)
        self.assertEqual(metrics.detected_bank_monthly_emi, 35000.0)
        self.assertEqual(metrics.undisclosed_liability_gap, 25000.0)
        self.assertTrue(metrics.has_undisclosed_liabilities)

    def test_4_statement_arithmetic_matching(self):
        res = validate_statement_arithmetic(
            opening_balance=10000,
            total_credits=50000,
            total_debits=20000,
            closing_balance=40000,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, "MATCH")
        self.assertEqual(res.difference_amount, 0.0)

    def test_5_statement_arithmetic_mismatch(self):
        res = validate_statement_arithmetic(
            opening_balance=10000,
            total_credits=50000,
            total_debits=20000,
            closing_balance=99999,
        )
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, "MISMATCH")
        self.assertEqual(res.difference_amount, 59999.0)

    def test_6_eligibility_check_pass_and_fail(self):
        pass_res = check_eligibility(
            verified_income=80000,
            foir_percentage=35.0,
            income_variance_percent=2.0,
            undisclosed_liability_gap=0.0,
        )
        self.assertTrue(pass_res.passed)

        fail_res = check_eligibility(
            verified_income=15000,
            foir_percentage=75.0,
            income_variance_percent=30.0,
            undisclosed_liability_gap=15000.0,
        )
        self.assertFalse(fail_res.passed)
        self.assertGreaterEqual(len(fail_res.reasons), 3)


class TestRiskAndAnomalyEngine(unittest.TestCase):
    def test_7_clean_applicant_routing_green(self):
        income = calculate_verified_income(100000, [{"extracted": {"net_pay": 100000}}], [{"amount": 100000, "category": "salary_credit"}])
        ob = calculate_obligations([{"emi_amount": 15000}], [{"amount": -15000, "category": "emi_debit"}], 100000.0, 10000.0)
        stmt = validate_statement_arithmetic(10000, 100000, 30000, 80000)
        elig = check_eligibility(100000.0, 25.0, 0.0, 0.0)

        risk = calculate_risk_and_routing(income, ob, stmt, elig, classified_anomalies=[])
        self.assertEqual(risk.routing_color, "green")
        self.assertEqual(risk.recommendation, "auto_approve")
        self.assertGreaterEqual(risk.score, 85.0)
        self.assertEqual(risk.grade, "Low")

    def test_8_major_anomaly_routing_red(self):
        income = calculate_verified_income(150000, [{"extracted": {"net_pay": 80000}}], [{"amount": 80000, "category": "salary_credit"}])
        ob = calculate_obligations([], [{"amount": -40000, "category": "emi_debit"}], 80000.0, 20000.0)
        stmt = validate_statement_arithmetic(10000, 80000, 30000, 99999)
        elig = check_eligibility(80000.0, 75.0, 87.5, 40000.0)

        anomalies = [
            {"discrepancy_type": "INCOME_MISMATCH", "severity": "Major", "reasoning": "Grossly overstated income"},
            {"discrepancy_type": "UNDISCLOSED_LIABILITY", "severity": "Major", "reasoning": "Hidden Rs. 40k EMI"},
        ]
        risk = calculate_risk_and_routing(income, ob, stmt, elig, classified_anomalies=anomalies)
        self.assertEqual(risk.routing_color, "red")
        self.assertEqual(risk.recommendation, "reject")
        self.assertLess(risk.score, 50.0)
        self.assertEqual(risk.grade, "High")

    def test_9_llm_fallback_resilience(self):
        income = calculate_verified_income(100000, [], [])
        ob = calculate_obligations([], [], 100000.0)
        stmt = validate_statement_arithmetic(10000, 10000, 5000, 15000)
        elig = check_eligibility(100000.0, 10.0, 0.0, 0.0)
        discrepancies = [
            Discrepancy(
                discrepancy_type="INCOME_MISMATCH",
                difference_amount=20000.0,
                difference_percent=20.0,
                evidence_summary="Income variance detected",
            )
        ]
        assessment, is_fallback = classify_anomalies_with_llm({}, income, ob, stmt, elig, discrepancies)
        self.assertIsInstance(assessment, AnomalyAssessment)
        self.assertEqual(len(assessment.anomalies), 1)
        self.assertEqual(assessment.anomalies[0].discrepancy_type, "INCOME_MISMATCH")


if __name__ == "__main__":
    unittest.main()
