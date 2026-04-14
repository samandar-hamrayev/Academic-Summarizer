from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Paper


class PaperUploadForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = ['title', 'author', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter paper title',
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Author(s) name(s)',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf',
                'id': 'pdf-file-input',
            }),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Only PDF files are allowed.')
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 50 MB.')
        return file


class PaperSearchForm(forms.Form):
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search papers by title or author...',
        }),
    )


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('username', 'password1', 'password2'):
            self.fields[field_name].widget.attrs['class'] = 'form-control'
