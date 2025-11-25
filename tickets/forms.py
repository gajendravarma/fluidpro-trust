from django import forms
from .models import Ticket

class TicketForm(forms.ModelForm):
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.gif,.zip,.rar'
        }),
        help_text='Optional: Upload a file (PDF, DOC, images, etc. Max 10MB)'
    )
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }
