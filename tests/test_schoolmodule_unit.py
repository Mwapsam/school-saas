"""
Unit tests for the SchoolModule model and module registry.

Tests the module registry, SchoolModule model validation, and permission enforcement.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.models import School, SchoolModule, User
from core.modules import MODULES, get_module_key, get_all_module_keys, is_module_required


@pytest.mark.unit
class TestModuleRegistry:
    """Test the module registry constant."""

    def test_modules_dict_structure(self):
        """Verify MODULES dict has expected structure."""
        assert isinstance(MODULES, dict)
        assert len(MODULES) > 0

        for key, config in MODULES.items():
            assert isinstance(key, str)
            assert isinstance(config, dict)
            assert "label" in config
            assert "description" in config
            assert isinstance(config["label"], str)
            assert isinstance(config["description"], str)

    def test_get_module_key_valid(self):
        """Test retrieval of valid module keys."""
        config = get_module_key("finance")
        assert config["label"] == "Finance"

    def test_get_module_key_invalid(self):
        """Test that invalid module keys raise KeyError."""
        with pytest.raises(KeyError):
            get_module_key("invalid_module")

    def test_get_all_module_keys(self):
        """Test retrieval of all valid module keys."""
        keys = get_all_module_keys()
        assert isinstance(keys, list)
        assert len(keys) == len(MODULES)
        assert "finance" in keys
        assert "hr" in keys

    def test_required_modules(self):
        """Test identification of required modules."""
        assert is_module_required("academics") is True
        assert is_module_required("finance") is False


@pytest.mark.unit
@pytest.mark.django_db
class TestSchoolModuleModel:
    """Test SchoolModule model creation and validation."""

    @pytest.fixture
    def school(self):
        """Create a test school."""
        return School.objects.create(
            name="Test School",
            code="TEST001",
        )

    def test_schoolmodule_creation(self, school):
        """Test creating a SchoolModule record."""
        module = SchoolModule.objects.create(
            school=school,
            module="finance",
            enabled=True,
        )
        assert module.school == school
        assert module.module == "finance"
        assert module.enabled is True

    def test_schoolmodule_unique_constraint(self, school):
        """Test that a school can't have duplicate module records."""
        SchoolModule.objects.create(school=school, module="finance", enabled=True)

        with pytest.raises(Exception):  # IntegrityError
            SchoolModule.objects.create(school=school, module="finance", enabled=False)

    def test_schoolmodule_invalid_module_key(self, school):
        """Test that invalid module keys are rejected by clean()."""
        module = SchoolModule(school=school, module="invalid_key")

        with pytest.raises(ValidationError):
            module.full_clean()

    def test_schoolmodule_configuration_jsonfield(self, school):
        """Test that configuration JSONField stores module-specific settings."""
        config_data = {
            "transport": {
                "fleet_management": True,
                "route_tracking": False,
            }
        }
        module = SchoolModule.objects.create(
            school=school,
            module="transport",
            configuration=config_data,
        )
        assert module.configuration == config_data

    def test_schoolmodule_string_representation(self, school):
        """Test __str__ method."""
        module = SchoolModule.objects.create(
            school=school,
            module="finance",
            enabled=True,
        )
        assert "Test School" in str(module)
        assert "finance" in str(module)
        assert "enabled" in str(module)

    def test_schoolmodule_cascade_delete(self, school):
        """Test that SchoolModule records are deleted when school is deleted."""
        SchoolModule.objects.create(school=school, module="finance", enabled=True)

        school_id = school.id
        school.delete()

        assert not SchoolModule.objects.filter(school_id=school_id).exists()
