from django import forms
from core.models import Payment, Student, Term

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['student', 'term', 'amount_paid', 'payment_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add queryset for the students and terms
        self.fields['student'].queryset = Student.objects.all()  # Adjust the queryset as necessary
        self.fields['term'].queryset = Term.objects.all()  # Adjust the queryset as necessary
        self.fields['amount_paid'].widget.attrs.update({'step': '1000'})
        self.fields['payment_date'].widget.attrs.update({'type': 'date'})

