from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Company

class RegistrationForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=True,
        empty_label="Select Company"
    )
    mobile_number = forms.CharField(max_length=15, required=True)
    location = forms.CharField(max_length=100, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
    
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
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.company = self.cleaned_data['company']
            profile.mobile_number = self.cleaned_data.get('mobile_number', '')
            profile.location = self.cleaned_data.get('location', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
        return user
