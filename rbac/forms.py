from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Company
import re


class RegistrationForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    # Free-text field — accepts existing company name or new company name
    company = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'list': 'company-list'})
    )
    mobile_number = forms.CharField(max_length=15, required=True)
    location = forms.CharField(max_length=100, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def clean_company(self):
        name = self.cleaned_data['company'].strip()
        if not name:
            raise forms.ValidationError("Company name is required.")
        return name

    def _get_or_create_company(self, name):
        """Case-insensitive lookup; creates company if not found."""
        try:
            return Company.objects.get(name__iexact=name)
        except Company.DoesNotExist:
            # Auto-generate a unique code from the name
            base_code = re.sub(r'[^A-Za-z0-9]', '', name).upper()[:10] or 'COMPANY'
            code = base_code
            suffix = 1
            while Company.objects.filter(code=code).exists():
                code = f"{base_code}{suffix}"
                suffix += 1
            return Company.objects.create(name=name, code=code)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = True
        if commit:
            user.save()
            user.set_unusable_password()
            user.save()
            company = self._get_or_create_company(self.cleaned_data['company'])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.company = company
            profile.mobile_number = self.cleaned_data.get('mobile_number', '')
            profile.location = self.cleaned_data.get('location', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
        return user
