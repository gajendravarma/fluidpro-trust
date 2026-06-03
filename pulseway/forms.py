from django import forms


class SiteForm(forms.Form):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    address = forms.CharField(max_length=500, widget=forms.TextInput(attrs={'class': 'form-control'}), required=False)
    parent_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select parent organization"
    )
    
    def __init__(self, *args, **kwargs):
        organizations = kwargs.pop('organizations', [])
        super().__init__(*args, **kwargs)
        self.fields['parent_id'].choices = [
            (org.get('Id'), f"{org.get('Id')} - {org.get('Name', 'Unknown')}")
            for org in organizations
        ]


class GroupForm(forms.Form):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    parent_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select parent site"
    )
    
    def __init__(self, *args, **kwargs):
        sites = kwargs.pop('sites', [])
        super().__init__(*args, **kwargs)
        self.fields['parent_id'].choices = [
            (site.get('Id'), f"{site.get('Id')} - {site.get('Name', 'Unknown')}")
            for site in sites
        ]


class ScriptForm(forms.Form):
    device_id = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    script_content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}))
    script_type = forms.ChoiceField(
        choices=[('powershell', 'PowerShell'), ('batch', 'Batch'), ('bash', 'Bash')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class PatchForm(forms.Form):
    device_id = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    patch_ids = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter patch IDs, one per line'}),
        help_text="Enter patch IDs, one per line"
    )
    reboot_required = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class DeviceEditForm(forms.Form):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        help_text="Device description / notes"
    )
    group_id = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group ID (optional)'}),
        required=False,
        help_text="Pulseway Group ID to assign this device to"
    )


class PolicyForm(forms.Form):
    SCOPE_CHOICES = [
        ('Organization', 'Organization'),
        ('Site', 'Site'),
        ('Group', 'Group'),
        ('Device', 'Device'),
    ]
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    scope = forms.ChoiceField(
        choices=SCOPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='Organization'
    )
    scope_id = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID of the target scope (optional)'}),
        required=False,
        help_text="Leave blank to apply at Organization level"
    )
    cpu_threshold = forms.IntegerField(
        min_value=0, max_value=100, initial=90,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="CPU usage alert threshold (%)"
    )
    memory_threshold = forms.IntegerField(
        min_value=0, max_value=100, initial=90,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Memory usage alert threshold (%)"
    )
    disk_threshold = forms.IntegerField(
        min_value=0, max_value=100, initial=90,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Disk usage alert threshold (%)"
    )


class AutomationTaskForm(forms.Form):
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    schedule = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0 2 * * * (daily at 2 AM)'}),
        help_text="Cron expression for scheduling"
    )
    script_content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 8}))
    target_devices = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'device1,device2,device3'}),
        help_text="Comma-separated device IDs"
    )
    enabled = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
