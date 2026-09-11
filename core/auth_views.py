from django.contrib.auth.views import LoginView

from .forms import StaffOnlyAuthenticationForm


class StaffOnlyLoginView(LoginView):
    """Dashboard login — rejects non-admin (teacher/parent) credentials.

    See core.forms.StaffOnlyAuthenticationForm for the actual gate.
    """
    form_class = StaffOnlyAuthenticationForm
