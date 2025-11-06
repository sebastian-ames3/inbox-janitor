"""
Unit tests for usage tracking functionality.

Tests:
- UserSettings usage tracking properties
- Monthly limit checking
- Usage percentage calculation
- Plan tier limits
- Usage reset logic

Run tests:
    pytest tests/unit/test_usage_tracking.py -v
"""

import pytest
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.models.user_settings import UserSettings


# Test fixtures

@pytest.fixture
def starter_settings():
    """Create UserSettings for starter tier."""
    settings = UserSettings()
    settings.plan_tier = "starter"
    settings.monthly_email_limit = 10000
    settings.emails_processed_this_month = 0
    settings.ai_cost_this_month = 0.0
    settings.current_billing_period_start = date.today()
    return settings


@pytest.fixture
def pro_settings():
    """Create UserSettings for pro tier."""
    settings = UserSettings()
    settings.plan_tier = "pro"
    settings.monthly_email_limit = 25000
    settings.emails_processed_this_month = 0
    settings.ai_cost_this_month = 0.0
    settings.current_billing_period_start = date.today()
    return settings


# Test usage tracking properties

class TestUsageProperties:
    """Test usage tracking properties and calculations."""

    def test_has_not_reached_limit(self, starter_settings):
        """Test that user has not reached limit."""
        starter_settings.emails_processed_this_month = 5000
        assert starter_settings.has_reached_monthly_limit is False

    def test_has_reached_limit_exactly(self, starter_settings):
        """Test that user has exactly reached limit."""
        starter_settings.emails_processed_this_month = 10000
        assert starter_settings.has_reached_monthly_limit is True

    def test_has_exceeded_limit(self, starter_settings):
        """Test that user has exceeded limit."""
        starter_settings.emails_processed_this_month = 12000
        assert starter_settings.has_reached_monthly_limit is True

    def test_emails_remaining_with_usage(self, starter_settings):
        """Test emails remaining calculation."""
        starter_settings.emails_processed_this_month = 3000
        assert starter_settings.emails_remaining_this_month == 7000

    def test_emails_remaining_at_limit(self, starter_settings):
        """Test emails remaining when at limit."""
        starter_settings.emails_processed_this_month = 10000
        assert starter_settings.emails_remaining_this_month == 0

    def test_emails_remaining_over_limit(self, starter_settings):
        """Test emails remaining when over limit (should be 0)."""
        starter_settings.emails_processed_this_month = 12000
        assert starter_settings.emails_remaining_this_month == 0

    def test_usage_percentage_zero(self, starter_settings):
        """Test usage percentage with zero usage."""
        starter_settings.emails_processed_this_month = 0
        assert starter_settings.usage_percentage == 0.0

    def test_usage_percentage_half(self, starter_settings):
        """Test usage percentage at 50%."""
        starter_settings.emails_processed_this_month = 5000
        assert starter_settings.usage_percentage == 50.0

    def test_usage_percentage_full(self, starter_settings):
        """Test usage percentage at 100%."""
        starter_settings.emails_processed_this_month = 10000
        assert starter_settings.usage_percentage == 100.0

    def test_usage_percentage_over_100(self, starter_settings):
        """Test usage percentage capped at 100%."""
        starter_settings.emails_processed_this_month = 15000
        assert starter_settings.usage_percentage == 100.0

    def test_is_not_approaching_limit(self, starter_settings):
        """Test that user is not approaching limit (<80%)."""
        starter_settings.emails_processed_this_month = 5000  # 50%
        assert starter_settings.is_approaching_limit is False

    def test_is_approaching_limit_at_80(self, starter_settings):
        """Test that user is approaching limit at exactly 80%."""
        starter_settings.emails_processed_this_month = 8000  # 80%
        assert starter_settings.is_approaching_limit is True

    def test_is_approaching_limit_above_80(self, starter_settings):
        """Test that user is approaching limit above 80%."""
        starter_settings.emails_processed_this_month = 9500  # 95%
        assert starter_settings.is_approaching_limit is True


# Test plan tier limits

class TestPlanTierLimits:
    """Test plan tier limit configuration."""

    def test_get_limit_for_starter(self, starter_settings):
        """Test getting limit for starter tier."""
        assert starter_settings.get_limit_for_tier("starter") == 10000

    def test_get_limit_for_pro(self, starter_settings):
        """Test getting limit for pro tier."""
        assert starter_settings.get_limit_for_tier("pro") == 25000

    def test_get_limit_for_business(self, starter_settings):
        """Test getting limit for business tier."""
        assert starter_settings.get_limit_for_tier("business") == 100000

    def test_get_limit_for_unknown_tier(self, starter_settings):
        """Test getting limit for unknown tier (defaults to starter)."""
        assert starter_settings.get_limit_for_tier("unknown") == 10000


# Test different plan tiers

class TestPlanTiers:
    """Test usage tracking across different plan tiers."""

    def test_starter_tier_limit(self, starter_settings):
        """Test starter tier has correct limit."""
        assert starter_settings.monthly_email_limit == 10000

    def test_pro_tier_limit(self, pro_settings):
        """Test pro tier has correct limit."""
        assert pro_settings.monthly_email_limit == 25000

    def test_pro_tier_higher_capacity(self, pro_settings):
        """Test pro tier allows more emails before limit."""
        pro_settings.emails_processed_this_month = 15000
        assert pro_settings.has_reached_monthly_limit is False
        assert pro_settings.usage_percentage == 60.0


# Test AI cost tracking

class TestAICostTracking:
    """Test AI cost tracking functionality."""

    def test_initial_ai_cost_zero(self, starter_settings):
        """Test AI cost starts at zero."""
        assert starter_settings.ai_cost_this_month == 0.0

    def test_track_ai_cost(self, starter_settings):
        """Test tracking AI costs."""
        starter_settings.ai_cost_this_month += 0.003
        starter_settings.ai_cost_this_month += 0.003
        starter_settings.ai_cost_this_month += 0.003

        assert starter_settings.ai_cost_this_month == pytest.approx(0.009, abs=0.0001)

    def test_track_ai_cost_over_month(self, starter_settings):
        """Test tracking AI costs over month (1000 classifications)."""
        # Simulate 1000 AI classifications at $0.003 each
        for _ in range(1000):
            starter_settings.ai_cost_this_month += 0.003

        assert starter_settings.ai_cost_this_month == pytest.approx(3.0, abs=0.01)


# Test billing period

class TestBillingPeriod:
    """Test billing period tracking."""

    def test_billing_period_current(self, starter_settings):
        """Test billing period set to today."""
        assert starter_settings.current_billing_period_start == date.today()

    def test_billing_period_one_month_old(self, starter_settings):
        """Test billing period from one month ago."""
        one_month_ago = date.today() - relativedelta(months=1)
        starter_settings.current_billing_period_start = one_month_ago

        # Calculate if billing period has ended
        billing_period_end = starter_settings.current_billing_period_start + relativedelta(months=1)
        assert date.today() >= billing_period_end


# Test edge cases

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_limit_never_approaching(self):
        """Test that zero limit doesn't break percentage calculation."""
        settings = UserSettings()
        settings.monthly_email_limit = 0
        settings.emails_processed_this_month = 0

        assert settings.usage_percentage == 0.0
        assert settings.has_reached_monthly_limit is False

    def test_negative_emails_processed(self):
        """Test handling of negative emails (should not happen, but defensive)."""
        settings = UserSettings()
        settings.monthly_email_limit = 10000
        settings.emails_processed_this_month = -100  # Shouldn't happen

        # emails_remaining should handle this gracefully
        assert settings.emails_remaining_this_month > 0

    def test_very_high_usage(self):
        """Test handling of very high usage (10x limit)."""
        settings = UserSettings()
        settings.monthly_email_limit = 10000
        settings.emails_processed_this_month = 100000  # 10x limit

        assert settings.has_reached_monthly_limit is True
        assert settings.emails_remaining_this_month == 0
        assert settings.usage_percentage == 100.0  # Capped at 100%


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
