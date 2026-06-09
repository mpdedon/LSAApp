# core/payment/forms.py
from django import forms
from core.models import Class, Guardian, Payment, FinancialRecord, Term # Import Term

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['financial_record', 'amount_paid', 'payment_date', 'batch_reference']
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}), # Allow decimals
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'batch_reference': forms.TextInput(attrs={'placeholder': 'Optional receipt or batch reference'}),
        }
        labels = {
            'financial_record': "Select Student & Term Record", # Clearer label
            'batch_reference': 'Receipt / batch reference',
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

        # If the form is bound and the POST includes a financial_record value that
        # would otherwise be excluded by the active-term filter, include it so
        # ModelChoiceField validation doesn't reject a legitimate submitted id.
        bound_value = None
        # `data` can be passed either positionally or via kwargs depending on Django internals
        data = kwargs.get('data') if 'data' in kwargs else (args[0] if args else None)
        if data and hasattr(data, 'get'):
            bound_value = data.get('financial_record')
        elif isinstance(data, dict):
            bound_value = data.get('financial_record')

        if bound_value:
            try:
                # Accept integer-like strings too
                fr_pk = int(bound_value)
                extra_qs = FinancialRecord.objects.filter(pk=fr_pk)
                queryset = (queryset | extra_qs).distinct()
            except Exception:
                # Ignore parse errors and leave queryset as-is
                pass

        self.fields['financial_record'].queryset = queryset

        # Customize dropdown text - make it robust
        self.fields['financial_record'].label_from_instance = lambda obj: f"{obj.student.user.get_full_name() if obj.student and obj.student.user else 'Unknown Student'} ({obj.term.name if obj.term else 'Unknown Term'}) - Bal: ₦{obj.outstanding_balance}"

        # Add Bootstrap classes
        for field_name, field in self.fields.items():
             if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                 css_class = 'form-select form-select-sm' if field_name == 'financial_record' else 'form-control form-control-sm'
                 field.widget.attrs.update({'class': css_class})


class BulkPaymentForm(forms.Form):
    scope = forms.ChoiceField(
        choices=[('guardian', 'Guardian grouped payment'), ('class', 'Class bulk payment')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    guardian = forms.ModelChoiceField(
        queryset=Guardian.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    class_instance = forms.ModelChoiceField(
        queryset=Class.objects.order_by('name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Class',
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.select_related('session').order_by('-start_date'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    allocation_mode = forms.ChoiceField(
        choices=[('auto', 'Automatic split'), ('manual', 'Manual split')],
        initial='auto',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Automatic uses outstanding balances. Manual lets you edit the split before saving.',
    )
    total_amount = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        label='Total payment amount',
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    batch_reference = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional receipt or batch reference'}),
        help_text='Saved on every split payment entry created from this bulk action.',
        label='Receipt / batch reference',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['guardian'].queryset = Guardian.objects.filter(status='active').select_related('user').order_by('user__last_name', 'user__first_name')
        active_term = Term.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term

    def clean(self):
        cleaned_data = super().clean()
        scope = cleaned_data.get('scope')
        guardian = cleaned_data.get('guardian')
        class_instance = cleaned_data.get('class_instance')

        if scope == 'guardian' and not guardian:
            self.add_error('guardian', 'Select a guardian for grouped payment allocation.')
        if scope == 'class' and not class_instance:
            self.add_error('class_instance', 'Select a class for bulk payment allocation.')

        return cleaned_data