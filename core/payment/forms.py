# core/payment/forms.py
from django import forms
from core.models import Payment, FinancialRecord, Term # Import Term

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['financial_record', 'amount_paid', 'payment_date']
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}), # Allow decimals
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'financial_record': "Select Student & Term Record", # Clearer label
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Customize the financial_record field ---
        # Get the currently active term (handle potential errors)
        active_term = Term.objects.filter(is_active=True).first()

        if active_term:
            # Filter Financial Records for the ACTIVE TERM ONLY
            queryset = FinancialRecord.objects.filter(
                term=active_term # Filter by the active term
            ).select_related(
                'student__user', 'term__session'
            ).order_by(
                'student__current_class__name', # Order by class name first
                'student__user__last_name',
                'student__user__first_name'
            )
        else:
            # If no active term, show no options (or all non-archived?)
            queryset = FinancialRecord.objects.none()
            # OR maybe show all non-archived if that's desired:
            # queryset = FinancialRecord.objects.filter(archived=False).select_related(...)

        self.fields['financial_record'].queryset = queryset

        # Customize dropdown text - make it robust
        self.fields['financial_record'].label_from_instance = lambda obj: f"{obj.student.user.get_full_name() if obj.student and obj.student.user else 'Unknown Student'} ({obj.term.name if obj.term else 'Unknown Term'}) - Bal: ₦{obj.outstanding_balance}"

        # Add Bootstrap classes
        for field_name, field in self.fields.items():
             if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                 css_class = 'form-select form-select-sm' if field_name == 'financial_record' else 'form-control form-control-sm'
                 field.widget.attrs.update({'class': css_class})