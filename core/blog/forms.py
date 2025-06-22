# blog/forms.py
from django import forms
from core.models import Post, Category, Tag
from django_ckeditor_5.widgets import CKEditor5Widget

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

class PostForm(forms.ModelForm):

    #content = forms.CharField(widget=CKEditor5Widget())

    class Meta:
        model = Post
        fields = [
            'title', 'content', 'featured_image', 'status',
            'published_date', 'categories', 'tags',
            'meta_description', 'meta_keywords'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'featured_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'published_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'categories': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'meta_keywords': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # You can customize field attributes further here if needed
        self.fields['published_date'].input_formats = ['%Y-%m-%dT%H:%M'] # Match datetime-local format