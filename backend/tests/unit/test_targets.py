import pytest

from app.domain.targets import TargetError, bmr, compute_targets


def test_bmr_matches_hand_calculation():
    # 10*80 + 6.25*180 - 5*35 + 5 = 1755
    assert bmr("male", 35, 180, 80) == pytest.approx(1755)
    # 10*65 + 6.25*165 - 5*30 - 161 = 1370.25
    assert bmr("female", 30, 165, 65) == pytest.approx(1370.25)


def test_lose_weight_subtracts_daily_deficit():
    t = compute_targets(sex="male", age=35, height_cm=180, weight_kg=80, activity="moderate", goal="lose", kg_per_week=0.5)
    tdee = 1755 * 1.55
    assert t.kcal == round(tdee - 0.5 * 7700 / 7)
    assert not t.adjusted
    assert t.effective_kg_per_week == 0.5


def test_maintain_equals_tdee():
    t = compute_targets(sex="female", age=30, height_cm=165, weight_kg=65, activity="light", goal="maintain")
    assert t.kcal == round(1370.25 * 1.375)


def test_floor_applies_and_reports_effective_rate():
    t = compute_targets(sex="female", age=40, height_cm=155, weight_kg=55, activity="sedentary", goal="lose", kg_per_week=1.0)
    assert t.kcal == 1200
    assert t.adjusted
    assert 0 <= t.effective_kg_per_week < 1.0


def test_male_floor_is_1500():
    t = compute_targets(sex="male", age=60, height_cm=165, weight_kg=60, activity="sedentary", goal="lose", kg_per_week=1.0)
    assert t.kcal == 1500


def test_under_18_must_use_custom():
    with pytest.raises(TargetError):
        compute_targets(sex="male", age=12, height_cm=150, weight_kg=40, activity="light", goal="lose", kg_per_week=0.5)
    t = compute_targets(sex="male", age=12, height_cm=150, weight_kg=40, activity="light", goal="custom", custom_kcal=2000)
    assert t.kcal == 2000


@pytest.mark.parametrize("kg", [0.0, 0.05, 1.5, None])
def test_invalid_loss_rate_rejected(kg):
    with pytest.raises(TargetError):
        compute_targets(sex="male", age=35, height_cm=180, weight_kg=80, activity="moderate", goal="lose", kg_per_week=kg)


def test_heavy_member_has_non_negative_carbs_and_capped_protein():
    t = compute_targets(sex="male", age=45, height_cm=185, weight_kg=150, activity="sedentary", goal="lose", kg_per_week=1.0)
    assert t.carbs_g >= 0
    assert t.protein_g * 4 <= 0.35 * t.kcal + 4  # rounding allowance
    assert t.fat_g > 0


def test_custom_kcal_out_of_range_rejected():
    with pytest.raises(TargetError):
        compute_targets(sex="female", age=10, height_cm=140, weight_kg=35, activity="light", goal="custom", custom_kcal=300)


def test_notice_is_always_present():
    t = compute_targets(sex="male", age=35, height_cm=180, weight_kg=80, activity="moderate", goal="maintain")
    assert "not medical advice" in t.notice
