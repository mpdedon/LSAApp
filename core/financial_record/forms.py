from django import forms
from ..models import FinancialRecord

class FinancialRecordForm(forms.ModelForm):
    class Meta:
        model = FinancialRecord
        fields = '__all__'
